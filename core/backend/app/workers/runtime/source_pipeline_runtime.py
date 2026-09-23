"""Source pipeline job handlers for Upload -> Smart Deck.

Owns: the source-side workflow stages after a job is claimed:
source_ingestion, source_extraction, miniatures, brand_extraction, and
smart_deck_context.
Must not own: generic worker claiming, workflow-state reads, or final ready
publication; db_publisher owns the final publish step.
Stage: source-side execution path before Smart Deck becomes openable.
Status: KEEP

File map for maintainers:
- `handle_source_ingestion` only confirms the uploaded file record exists.
- `handle_source_extraction` persists canonical DeckSlide/Block/Asset rows.
- `handle_miniatures` generates source slide previews/thumbnails.
- `handle_brand_extraction` owns the working brand-profile path; do not absorb
  it into agent code unless the brand DB contract is also migrated.
- `handle_smart_deck_context` compiles the source workspace baseline consumed by
  Smart Deck UI and downstream LLM generation.

Audit note: this file intentionally orchestrates deterministic source stages.
Market/competitor/team enrichment should attach typed artifacts to the Smart Deck
context instead of writing isolated JSON blobs or bypassing source facts.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DeckFile, WorkflowJob
from app.services.brand.company_profile import ensure_company_profile
from app.services.deck_processing.brand_extraction import run_brand_extraction_for_deck
from app.services.deck_processing.deterministic_extraction import (
    SourceFileLineageError,
    _require_active_workflow_fence,
    _require_active_workflow_job_lease,
    _exact_sha256,
    extract_source_deck,
    get_materialized_state,
)
from app.services.deck_processing.smart_deck_context import prepare_smart_deck_source_workspace
from app.workers.dispatch.worker_runtime_service import (
    _deck,
    _failure_status_for_job,
    _job_payload,
    _mark_run_stage,
    _mark_source_pipeline_failed,
    _now,
    _processing_run,
)
from app.services.deck_processing.source_preview_service import extract_source_previews
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_TYPE_BRAND_EXTRACTION,
    JOB_TYPE_MINIATURES,
    JOB_TYPE_SMART_DECK_CONTEXT,
    JOB_TYPE_SOURCE_EXTRACTION,
    set_workflow_job_status,
)


def handle_source_ingestion(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Mark an already-saved upload as ready for deterministic extraction."""
    deck = _deck(job, db)
    payload = _job_payload(job)
    output_payload = {
        "phase": "source_file_saved",
        "deckFileId": payload.get("deckFileId"),
        "sourceInputId": payload.get("sourceInputId"),
        "storagePath": payload.get("storagePath"),
        "ingestionMode": payload.get("ingestionMode"),
    }
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message=f"Source ingestion confirmed for deck {deck.id}.",
        output_payload=output_payload,
    )
    db.commit()


def handle_source_extraction(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Extract canonical slide/block/asset records from the uploaded source.

    Uses the science-backed deterministic extraction pipeline which:
    1. Extracts PDF structure (text, blocks, images)
    2. Persists slides, blocks, and assets to the database
    3. Creates structured deck JSON artifact
    4. Updates the materialized deck state
    5. Provides extraction report artifact
    """
    # Source extraction owns persisted source structure only. Smart Deck workspace
    # preparation is a separate smart_deck_context stage.
    invocation_attempt = int(job.attempt_count or 0)
    try:
        # Fence the claim before compatibility lookup can create/link a run.
        # populate_existing + FOR UPDATE prevents a stale in-memory worker from
        # using `_processing_run` to mutate the newer owner's job.
        job = _require_active_workflow_job_lease(
            db,
            deck_id=job.deck_id,
            workflow_job_id=job.id,
            worker_id=worker_id,
            attempt_count=invocation_attempt,
        )
    except Exception:
        db.rollback()
        raise
    compatibility_run_creation = not bool(job.extraction_run_id)
    run = _processing_run(job, db)
    if run is None:
        raise ValueError("Workflow source extraction job is missing its extraction run.")
    deck = _deck(job, db)
    created_storage_keys: list[str] = []
    try:
        if compatibility_run_creation:
            source_file = db.query(DeckFile).filter(
                DeckFile.id == run.source_file_id,
                DeckFile.deck_id == deck.id,
            ).one_or_none()
            source_checksum = _exact_sha256(source_file.checksum_sha256 if source_file is not None else None)
            if source_checksum is None:
                raise SourceFileLineageError(
                    "source_file_checksum_missing",
                    "The authoritative source checksum is missing; upload the source again before retrying.",
                )
            run.metadata_json = {**(run.metadata_json or {}), "sourceChecksum": source_checksum}
            db.flush()
            # Compatibility creation is a prerequisite identity record, not a
            # processing-state publication. Persist the immutable checksum and
            # job/run link together before execution so later failure fencing
            # can still identify the exact claimed invocation after rollback.
            db.commit()
            db.refresh(job)
            db.refresh(run)
        result = extract_source_deck(
            db,
            deck.id,
            extraction_run=run,
            workflow_job_id=job.id,
            worker_id=worker_id,
            attempt_count=invocation_attempt,
            created_storage_keys=created_storage_keys,
        )

        if not result.get("success"):
            raise ValueError(f"Extraction failed: {result.get('error', 'Unknown error')}")
        if int(result.get("slideCount") or 0) <= 0:
            raise ValueError("Deck extraction produced no slides.")

        # Sync the existing workflow extraction run with the new pipeline results
        refreshed_run = _processing_run(job, db)
        if refreshed_run is None:
            raise ValueError("Extraction run disappeared after source extraction.")

        # Update the run with counts from the new pipeline
        refreshed_run.slide_count = result.get("slideCount", 0)
        refreshed_run.block_count = result.get("blockCount", 0)
        refreshed_run.asset_count = result.get("assetCount", 0)
        refreshed_run.status = "completed"
        refreshed_run.completed_at = _now()

        _mark_run_stage(
            refreshed_run,
            stage="source_extraction_completed",
            next_action=(
                "wait_for_source_publication"
                if deck.file is not None and (deck.file.metadata_json or {}).get("preferredWorkspace") == "instant_deck"
                else "wait_for_miniatures"
            ),
            worker_id=worker_id,
            extra={
                "slideCount": refreshed_run.slide_count,
                "blockCount": refreshed_run.block_count,
                "assetCount": refreshed_run.asset_count,
                "sourceVersionId": result.get("sourceVersionId"),
            },
        )
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            message="Source extraction completed.",
            output_payload={
                "phase": "source_ready",
                "slideCount": refreshed_run.slide_count,
                "blockCount": refreshed_run.block_count,
                "assetCount": refreshed_run.asset_count,
                "processingMode": "deterministic_structured_extraction",
                "sourceVersionId": result.get("sourceVersionId"),
                "structuredJsonArtifactId": result.get("structuredJsonArtifactId"),
                "extractionReportArtifactId": result.get("extractionReportArtifactId"),
            },
        )
        db.commit()
        converted_metadata = result.get("convertedPdfMetadata")
        converted_keys = [str(key) for key in (result.get("convertedStorageKeys") or []) if key]
        if isinstance(converted_metadata, dict):
            try:
                source_file = db.query(DeckFile).filter(
                    DeckFile.id == run.source_file_id,
                    DeckFile.deck_id == deck.id,
                ).with_for_update().one()
                source_file.metadata_json = {
                    **(source_file.metadata_json or {}),
                    "convertedPdf": converted_metadata,
                }
                from app.services.llm.instant_html_operation_service import complete_artifact_cleanup_tasks
                complete_artifact_cleanup_tasks(db, converted_keys)
                db.commit()
            except Exception:
                # Core extraction/job publication is already durable. Keep the
                # cleanup rows pending so the reconciler removes an output whose
                # reuse metadata could not be published atomically.
                db.rollback()
    except Exception as exc:
        # Roll back the failed extraction transaction before writing retry state;
        # without this, PostgreSQL reports InFailedSqlTransaction and hides the
        # original root cause from the processing page.
        db.rollback()
        try:
            # Lock/CAS the canonical job lease before mutating shared failure
            # state. A resumed stale worker must not overwrite a newer attempt.
            _require_active_workflow_fence(
                db,
                deck_id=deck.id,
                extraction_run_id=run.id,
                workflow_job_id=job.id,
                worker_id=worker_id,
                attempt_count=invocation_attempt,
            )
        except SourceFileLineageError as fence_exc:
            if fence_exc.code == "source_extraction_lease_lost":
                db.rollback()
                raise exc
            raise
        from app.services.deck_processing.deterministic_extraction import (
            _complete_failed_artifact_cleanup,
            sanitize_source_extraction_error,
        )
        error_code, error_message = sanitize_source_extraction_error(exc)
        failure_status = _failure_status_for_job(job)
        failed_run = _processing_run(job, db)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.error_message = error_message
            failed_run.completed_at = _now()
            _mark_run_stage(
                failed_run,
                stage="failed",
                next_action="manual_review",
                worker_id=worker_id,
                extra={"failureCode": error_code},
            )
            if failure_status == JOB_STATUS_FAILED_FINAL:
                _mark_source_pipeline_failed(
                    db,
                    run=failed_run,
                    first_failed_job_type=JOB_TYPE_SOURCE_EXTRACTION,
                    worker_id=worker_id,
                    error_code=error_code,
                    error_message=error_message,
                )
        set_workflow_job_status(
            db,
            job=job,
            status=failure_status,
            worker_id=worker_id,
            message="Source extraction failed.",
            error_code=error_code,
            error_message=error_message,
            output_payload={"phase": "failed_final" if failure_status == JOB_STATUS_FAILED_FINAL else "failed_retryable"},
        )
        db.commit()
        _complete_failed_artifact_cleanup(db, created_storage_keys)
        raise


def handle_miniatures(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Generate slide preview assets used by the Smart Deck miniature rail."""
    deck = _deck(job, db)
    if deck.file is not None and (deck.file.metadata_json or {}).get("preferredWorkspace") == "instant_deck":
        # Historical jobs can still be claimed after rollout. They must neither
        # render source thumbnails nor mutate/fail the canonical extraction run.
        set_workflow_job_status(db, job=job, status=JOB_STATUS_COMPLETED, worker_id=worker_id,
            message="Optional Instant Deck source thumbnails are disabled.",
            output_payload={"optional": True, "skipped": True})
        db.commit()
        return
    run = _processing_run(job, db)
    if run is None:
        raise ValueError("Workflow miniatures job is missing its extraction run.")
    _mark_run_stage(run, stage="preview_generation_running", next_action="wait_for_preview_generation", worker_id=worker_id)
    db.commit()

    try:
        # Miniatures owns source preview generation directly. The compatibility
        # wrapper remains for older callers, but the source pipeline should not
        # route through an extra indirection layer.
        preview = extract_source_previews(db, job.deck_id)
        refreshed_run = _processing_run(job, db)
        if refreshed_run is not None:
            _mark_run_stage(
                refreshed_run,
                stage="preview_generation_completed",
                next_action="wait_for_smart_deck_context",
                worker_id=worker_id,
                extra={"previewCount": int(preview.get("previewCount") or preview.get("slideCount") or 0)},
            )
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            message="Miniatures completed.",
            output_payload={
                "phase": "source_ready",
                "slideCount": int(preview.get("slideCount") or 0),
                "previewCount": int(preview.get("previewCount") or preview.get("slideCount") or 0),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failure_status = _failure_status_for_job(job)
        failed_run = _processing_run(job, db)
        if failed_run is not None and failure_status == JOB_STATUS_FAILED_FINAL:
            _mark_source_pipeline_failed(
                db,
                run=failed_run,
                first_failed_job_type=JOB_TYPE_MINIATURES,
                worker_id=worker_id,
                error_code="thumbnail_generation_failed",
                error_message=str(exc),
            )
        set_workflow_job_status(
            db,
            job=job,
            status=failure_status,
            worker_id=worker_id,
            message="Miniatures generation failed.",
            error_code="thumbnail_generation_failed",
            error_message=str(exc),
            output_payload={"phase": "failed_final" if failure_status == JOB_STATUS_FAILED_FINAL else "failed_retryable"},
        )
        db.commit()
        raise


def handle_brand_extraction(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Build the DeckBrandProfile that constrains later visual generation."""
    deck = _deck(job, db)
    run = _processing_run(job, db)
    if run is not None:
        _mark_run_stage(run, stage="brand_extraction_running", next_action="wait_for_brand_extraction", worker_id=worker_id)
    db.commit()

    try:
        company_profile = ensure_company_profile(db, deck)
        profile = run_brand_extraction_for_deck(db, deck, company_profile=company_profile)
        if run is not None:
            _mark_run_stage(run, stage="brand_extraction_completed", next_action="brand_profile_ready", worker_id=worker_id)
        # Persist source and brand authority before external embedding I/O, but
        # keep the brand workflow job non-terminal so the publisher cannot race
        # generation ahead of the durable vector index.
        db.flush()
        db.commit()

        try:
            from app.services.llm.deck_chunking_service import (
                sync_deck_vector_chunks,
                sync_instant_deck_knowledge_chunks,
            )

            knowledge_index = sync_instant_deck_knowledge_chunks(db)
            deck_index = sync_deck_vector_chunks(
                db,
                deck.id,
                audience_label=deck.audience,
                release_core_transaction_before_provider=True,
            )
        except Exception as index_exc:
            # Canonical extraction remains usable when the provider is
            # temporarily unavailable. Record the truthful degraded state; the
            # generation worker will retry only missing chunks.
            # Provider/index writes can leave PostgreSQL's transaction in an
            # aborted state. The source and brand profile were committed above,
            # so clear that failed transaction before persisting the degraded
            # workflow result.
            db.rollback()
            knowledge_index = {"status": "degraded", "message": str(index_exc)}
            deck_index = {"status": "degraded", "message": str(index_exc)}

        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            message="Brand extraction completed.",
            output_payload={
                "phase": "source_ready",
                "brandProfileId": profile.id,
                "processingStatus": profile.processing_status,
                "palette": profile.palette_json or [],
                "logoUrl": profile.logo_url,
                "vectorIndex": {
                    "deckStatus": deck_index.get("status"),
                    "deckChunkCount": deck_index.get("chunkCount", 0),
                    "deckEmbeddedChunkCount": deck_index.get("embeddedChunkCount", 0),
                    "stableKnowledgeStatus": knowledge_index.get("status"),
                    "stableKnowledgeChunkCount": knowledge_index.get("chunkCount", 0),
                    "stableKnowledgeEmbeddedChunkCount": knowledge_index.get("embeddedChunkCount", 0),
                },
            },
        )
        publisher = db.query(WorkflowJob).filter(
            WorkflowJob.deck_id == deck.id,
            WorkflowJob.extraction_run_id == job.extraction_run_id,
            WorkflowJob.job_type == "db_publisher",
            WorkflowJob.status == JOB_STATUS_COMPLETED,
            WorkflowJob.published_phase == "smart_deck_ready",
        ).one_or_none()
        if publisher is not None:
            from app.services.deck_processing.workflow_orchestration import enqueue_upload_first_instant_html_baseline

            db.flush()
            instant_generation = enqueue_upload_first_instant_html_baseline(
                db,
                deck,
                source_workflow_job=publisher,
            )
            if instant_generation is not None:
                job.output_json = {
                    **(job.output_json if isinstance(job.output_json, dict) else {}),
                    "instantDeckGenerationJobId": instant_generation["jobId"],
                }
        db.commit()
    except Exception as exc:
        db.rollback()
        failure_status = _failure_status_for_job(job)
        if run is not None and failure_status == JOB_STATUS_FAILED_FINAL:
            _mark_source_pipeline_failed(
                db,
                run=run,
                first_failed_job_type=JOB_TYPE_BRAND_EXTRACTION,
                worker_id=worker_id,
                error_code="brand_extraction_failed",
                error_message=str(exc),
            )
        set_workflow_job_status(
            db,
            job=job,
            status=failure_status,
            worker_id=worker_id,
            message="Brand extraction failed.",
            error_code="brand_extraction_failed",
            error_message=str(exc),
            output_payload={"phase": "failed_final" if failure_status == JOB_STATUS_FAILED_FINAL else "failed_retryable"},
        )
        db.commit()
        raise


def handle_smart_deck_context(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Compile the source workspace baseline before any user-facing generation.

    This is the current merge point for extracted slides, semantic labels, and
    source_v1 artifacts. It should eventually become the canonical place that
    verifies SmartDeckContext readiness before LLM generation is allowed.
    """
    run = _processing_run(job, db)
    if run is not None:
        _mark_run_stage(run, stage="smart_deck_context_running", next_action="wait_for_smart_deck_context", worker_id=worker_id)
    db.commit()

    try:
        workspace = prepare_smart_deck_source_workspace(db, job.deck_id, commit=False)
        refreshed_run = _processing_run(job, db)
        if refreshed_run is not None:
            _mark_run_stage(
                refreshed_run,
                stage="smart_deck_context_completed",
                next_action="wait_for_publisher",
                worker_id=worker_id,
                extra={"workspaceId": workspace.get("workspaceId")},
            )
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            message="Smart Deck context completed.",
            output_payload={
                "phase": "source_ready",
                "sourceWorkspace": workspace,
                "sourceEnrichment": {
                    "source": workspace.get("enrichmentSource"),
                    "llmStatus": workspace.get("llmStatus"),
                    "provider": workspace.get("llmProvider"),
                    "model": workspace.get("llmModel"),
                },
                "workspaceId": workspace.get("workspaceId"),
                "sourceRunId": workspace.get("sourceRunId"),
                "slideCount": workspace.get("slideCount"),
                "artifactCount": workspace.get("artifactCount"),
                "enrichmentSource": workspace.get("enrichmentSource"),
                "llmStatus": workspace.get("llmStatus"),
                "llmProvider": workspace.get("llmProvider"),
                "llmModel": workspace.get("llmModel"),
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failure_status = _failure_status_for_job(job)
        failed_run = _processing_run(job, db)
        if failed_run is not None and failure_status == JOB_STATUS_FAILED_FINAL:
            _mark_source_pipeline_failed(
                db,
                run=failed_run,
                first_failed_job_type=JOB_TYPE_SMART_DECK_CONTEXT,
                worker_id=worker_id,
                error_code="smart_deck_context_failed",
                error_message=str(exc),
            )
        set_workflow_job_status(
            db,
            job=job,
            status=failure_status,
            worker_id=worker_id,
            message="Smart Deck context failed.",
            error_code="smart_deck_context_failed",
            error_message=str(exc),
            output_payload={"phase": "failed_final" if failure_status == JOB_STATUS_FAILED_FINAL else "failed_retryable"},
        )
        db.commit()
        raise
