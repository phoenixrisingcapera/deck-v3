"""Publisher-side workflow handlers for Upload -> Smart Deck.

Owns: publishing final workflow phases like smart_deck_ready and export_ready,
and recording export artifacts.
Must not own: source extraction, preview rendering, or Smart Deck workspace
preparation.
Stage: final publication after source/generation stages complete.
Status: KEEP
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Deck,
    DeckSaveConfirmation,
    DesignVersion,
    SecurityAuditEvent,
    SmartDeckPreference,
    SmartDeckWorkspace,
    User,
    WorkflowJob,
)
from app.workers.dispatch.worker_runtime_service import _deck, _dependency_output, _job_payload, _mark_run_stage, _now, _processing_run
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state, transition_deck_state
from app.services.rendering.export_service import (
    FINAL_DECK_EXPORT_TYPE,
    PROVISIONAL_HTML_EXPORT_TYPE,
    create_export,
    reconcile_pending_export_handoffs,
)
from app.services.admin.security_audit import record_security_event
from app.services.deck_processing.workflow_jobs import (
    GENERATION_ROOT_JOB_TYPES,
    JOB_STATUS_COMPLETED,
    JOB_TYPE_DB_PUBLISHER,
    JOB_TYPE_SOURCE_EXTRACTION,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_SMART_DECK_CONTEXT,
    PREVIEW_PUBLISHER_SUPERSEDED_TERMINAL_REASON,
    PUBLISHER_DISPOSITION_SUPERSEDED_NOOP,
    PUBLISHABLE_WORKFLOW_PHASES,
    latest_generation_root_and_chain,
    list_workflow_jobs_for_deck,
    record_workflow_artifact,
    set_workflow_job_status,
    workflow_job_is_superseded_publisher_noop,
)


def _preview_publisher_input(job: WorkflowJob) -> dict:
    return job.input_json if isinstance(job.input_json, dict) else {}


class PreviewPublisherSuperseded(ValueError):
    """A stale publisher lost authority to a newer generation or publisher."""

    code = PREVIEW_PUBLISHER_SUPERSEDED_TERMINAL_REASON

    def __init__(self, message: str, *, authoritative_generation_job_id: str | None = None):
        super().__init__(message)
        self.authoritative_generation_job_id = authoritative_generation_job_id


def _select_published_instant_version(
    db: Session,
    *,
    deck: Deck,
    version: DesignVersion,
) -> None:
    """Atomically make the proof-complete Instant version authoritative."""
    slides = sorted(version.generated_slides, key=lambda item: (item.slide_number, item.id))
    if not slides:
        raise ValueError("Instant Deck publication requires persisted ordered slides.")

    workspace = (
        db.query(SmartDeckWorkspace)
        .filter(SmartDeckWorkspace.deck_id == deck.id)
        .with_for_update()
        .one_or_none()
    )
    preference = (
        db.query(SmartDeckPreference)
        .filter(SmartDeckPreference.deck_id == deck.id)
        .with_for_update()
        .one_or_none()
    )
    if workspace is None or preference is None:
        raise ValueError("Instant Deck publication requires persisted workspace selection state.")

    for prior_version in db.query(DesignVersion).filter(
        DesignVersion.deck_id == deck.id,
        DesignVersion.id != version.id,
        DesignVersion.is_active.is_(True),
    ).with_for_update().all():
        prior_version.is_active = False

    first_slide = slides[0]
    version.status = "applied"
    version.is_active = True
    version.applied_at = _now()
    deck.current_design_version_id = version.id
    workspace.status = "ready"
    workspace.active_design_version_id = version.id
    workspace.active_generated_slide_id = first_slide.id
    workspace.active_source_slide_id = first_slide.source_slide_id
    preference.active_design_version_id = version.id
    preference.active_generated_slide_id = first_slide.id
    preference.active_source_slide_id = first_slide.source_slide_id

    # Publication is the authoritative acceptance point for the upload-first
    # Instant Deck flow. Persist the immutable accepted-history snapshot in the
    # same transaction so the final export gate can prove exactly which
    # published version was accepted. This is idempotent on the version ID and
    # never manufactures acceptance for a provisional or failed candidate.
    from app.services.platform.shell.shell_service import record_accepted_deck_version

    accepted = record_accepted_deck_version(
        db,
        deck.id,
        source_surface="instant_deck",
        source_artifact_id=version.id,
        design_version_id=version.id,
        changed_slide_ids=[slide.source_slide_id for slide in slides if slide.source_slide_id],
        change_summary=version.summary or version.name or "Published Instant Deck",
        accepted_by_user_id=deck.user_id,
    )
    if accepted is None:
        raise ValueError("Instant Deck publication could not persist accepted deck-history lineage.")


def _validate_preview_publisher_authority(
    *,
    db: Session,
    job: WorkflowJob,
    jobs: list[WorkflowJob],
    generation_workflow_job_id: str,
    failed_transition: DeckSaveConfirmation | None,
) -> None:
    referenced_generation = next(
        (
            candidate
            for candidate in jobs
            if candidate.id == generation_workflow_job_id
            and candidate.job_type in GENERATION_ROOT_JOB_TYPES
        ),
        None,
    )
    if referenced_generation is None:
        raise PreviewPublisherSuperseded(
            "Preview publisher generation workflow is missing or not a generation root.",
        )
    from app.services.llm.full_html_generation_service import _newer_provider_authority_exists

    if _newer_provider_authority_exists(
        db,
        deck_id=job.deck_id,
        generation_job_id=generation_workflow_job_id,
    ):
        generation_root, _ = latest_generation_root_and_chain(
            jobs,
            generation_root_job_type=referenced_generation.job_type,
        )
        raise PreviewPublisherSuperseded(
            "Preview publisher has been superseded by a newer provider-backed generation workflow.",
            authoritative_generation_job_id=generation_root.id if generation_root is not None else None,
        )
    generation_root = referenced_generation
    generation_chain = []
    for candidate in jobs:
        input_payload = candidate.input_json if isinstance(candidate.input_json, dict) else {}
        output_payload = candidate.output_json if isinstance(candidate.output_json, dict) else {}
        input_root_id = input_payload.get("generationWorkflowJobId")
        output_root_id = output_payload.get("generationWorkflowJobId")
        if input_root_id and output_root_id and input_root_id != output_root_id:
            continue
        if candidate.id == generation_root.id or (input_root_id or output_root_id) == generation_root.id:
            generation_chain.append(candidate)
    if generation_root.status != JOB_STATUS_COMPLETED:
        raise ValueError("Preview publisher generation workflow is not completed.")

    matching_publishers = [
        candidate
        for candidate in generation_chain
        if candidate.job_type == JOB_TYPE_DB_PUBLISHER
        and str(_preview_publisher_input(candidate).get("publishTarget") or "") == "preview_ready"
        and not workflow_job_is_superseded_publisher_noop(candidate)
    ]
    if not matching_publishers or matching_publishers[0].id != job.id:
        raise PreviewPublisherSuperseded(
            "Preview publisher is stale or superseded by a parallel publisher.",
            authoritative_generation_job_id=generation_root.id,
        )

    if failed_transition is not None:
        metadata = failed_transition.metadata_json if isinstance(failed_transition.metadata_json, dict) else {}
        failed_generation_id = metadata.get("generationWorkflowJobId")
        if (
            metadata.get("targetState") != DeckState.FAILED.value
            or metadata.get("workflowJobId") != job.id
            or (failed_generation_id and failed_generation_id != generation_workflow_job_id)
        ):
            raise ValueError("Failed deck state does not belong to this preview publisher lineage.")


def _latest_failed_deck_transition(db: Session, deck_id: str) -> DeckSaveConfirmation | None:
    confirmations = (
        db.query(DeckSaveConfirmation)
        .filter(
            DeckSaveConfirmation.deck_id == deck_id,
            DeckSaveConfirmation.event_type == "deck_state_transition",
        )
        .order_by(DeckSaveConfirmation.created_at.desc())
        .all()
    )
    return next(
        (
            confirmation
            for confirmation in confirmations
            if isinstance(confirmation.metadata_json, dict)
            and confirmation.metadata_json.get("targetState") == DeckState.FAILED.value
        ),
        None,
    )


def _lock_and_validate_preview_publisher(
    db: Session,
    *,
    job: WorkflowJob,
    generation_workflow_job_id: str,
) -> Deck:
    deck = (
        db.query(Deck)
        .populate_existing()
        .filter(Deck.id == job.deck_id)
        .with_for_update()
        .one()
    )
    failed_transition = (
        _latest_failed_deck_transition(db, deck.id)
        if canonical_deck_state(deck.status) == DeckState.FAILED
        else None
    )
    if canonical_deck_state(deck.status) == DeckState.FAILED and failed_transition is None:
        raise ValueError("Failed deck state has no publisher recovery lineage.")
    _validate_preview_publisher_authority(
        db=db,
        job=job,
        jobs=list_workflow_jobs_for_deck(db, deck.id),
        generation_workflow_job_id=generation_workflow_job_id,
        failed_transition=failed_transition,
    )
    return deck


def _lock_and_validate_source_publisher(db: Session, *, job: WorkflowJob) -> Deck:
    deck = (
        db.query(Deck)
        .populate_existing()
        .filter(Deck.id == job.deck_id)
        .with_for_update()
        .one()
    )
    payload = _job_payload(job)
    source_checksum = str(payload.get("sourceChecksum") or "").strip()
    processing_run_id = str(payload.get("processingRunId") or "").strip()
    current_checksum = str(getattr(deck.file, "checksum_sha256", None) or "").strip()
    if (
        not source_checksum
        or source_checksum != current_checksum
        or not processing_run_id
        or processing_run_id != str(job.extraction_run_id or "")
    ):
        raise ValueError("Source publisher does not match the current source processing run.")

    file_metadata = (
        deck.file.metadata_json
        if getattr(deck, "file", None) is not None and isinstance(deck.file.metadata_json, dict)
        else {}
    )
    if file_metadata.get("preferredWorkspace") == "instant_deck":
        source_output = _dependency_output(db, job, JOB_TYPE_SOURCE_EXTRACTION)
        if (
            source_output.get("phase") != "source_ready"
            or int(source_output.get("slideCount") or 0) <= 0
        ):
            raise ValueError("Instant source publisher requires completed source extraction.")
        from app.services.deck_processing.source_page_readiness import require_extracted_page_records
        require_extracted_page_records(
            db, deck_id=deck.id, source_file_id=deck.file.id,
            extraction_run_id=processing_run_id,
            expected_page_count=int(source_output["slideCount"]),
        )
    else:
        source_output = _dependency_output(db, job, JOB_TYPE_SMART_DECK_CONTEXT)
        if (
            source_output.get("phase") != "source_ready"
            or not source_output.get("workspaceId")
            or not source_output.get("sourceRunId")
        ):
            raise ValueError("Source publisher requires validated Smart Deck context output.")

    if canonical_deck_state(deck.status) != DeckState.FAILED:
        return deck

    failed_transition = _latest_failed_deck_transition(db, deck.id)
    metadata = (
        failed_transition.metadata_json
        if failed_transition is not None and isinstance(failed_transition.metadata_json, dict)
        else {}
    )
    if (
        metadata.get("targetState") != DeckState.FAILED.value
        or metadata.get("workflowJobId") != job.id
    ):
        raise ValueError("Failed deck state does not belong to this source publisher lineage.")

    return deck


def handle_db_publisher(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    payload = _job_payload(job)
    target = str(payload.get("publishTarget") or "smart_deck_ready")
    generation_workflow_job_id = str(payload.get("generationWorkflowJobId") or "").strip()
    if target == "preview_ready":
        try:
            deck = _lock_and_validate_preview_publisher(
                db,
                job=job,
                generation_workflow_job_id=generation_workflow_job_id,
            )
        except PreviewPublisherSuperseded as exc:
            # A superseded publisher is terminal for dispatch purposes, but it
            # did not publish anything and must never retain publication state.
            superseded_output = {
                "phase": "upload_accepted",
                "publishTarget": "preview_ready",
                "publisherDisposition": PUBLISHER_DISPOSITION_SUPERSEDED_NOOP,
                "publicationSucceeded": False,
                "authoritative": False,
                "superseded": True,
                "supersededGenerationWorkflowJobId": generation_workflow_job_id or None,
                "authoritativeGenerationWorkflowJobId": exc.authoritative_generation_job_id,
            }
            set_workflow_job_status(
                db,
                job=job,
                status=JOB_STATUS_COMPLETED,
                worker_id=worker_id,
                message="Preview publisher completed without mutation because a newer workflow is authoritative.",
                terminal_reason=exc.code,
                output_payload=superseded_output,
            )
            # set_workflow_job_status normally merges outputs for progress
            # preservation. A no-op must replace any stale success output.
            job.output_json = superseded_output
            job.published_phase = None
            job.published_at = None
            instant_operation_id = str(payload.get("instantOperationId") or "").strip()
            if instant_operation_id:
                from app.services.llm.instant_html_operation_service import terminalize_operation_by_id

                terminalize_operation_by_id(db, instant_operation_id, reason="publication_superseded")
            db.commit()
            return
    elif target == "smart_deck_ready":
        deck = _lock_and_validate_source_publisher(db, job=job)
    else:
        deck = _deck(job, db)
    run = _processing_run(job, db)
    validated_recovery_lineage: dict[str, str] | None = None

    if target not in PUBLISHABLE_WORKFLOW_PHASES:
        raise ValueError(f"Unsupported db_publisher target: {target}")

    if target == "preview_ready":
        preview_output = _dependency_output(db, job, JOB_TYPE_PREVIEW_RENDER)
        design_version_id = str(preview_output.get("designVersionId") or "").strip()
        if not design_version_id or not generation_workflow_job_id:
            raise ValueError("Preview publication requires a validated design version.")
        if (
            preview_output.get("generationWorkflowJobId")
            and preview_output.get("generationWorkflowJobId") != generation_workflow_job_id
        ):
            raise ValueError("Preview publication dependencies do not match the generation workflow.")
        version = (
            db.query(DesignVersion)
            .filter(DesignVersion.deck_id == deck.id, DesignVersion.id == design_version_id)
            .one_or_none()
        )
        if version is None:
            raise ValueError("Preview publication cannot find the validated design version.")
        if version.generation_job_id != generation_workflow_job_id:
            raise ValueError("Preview publication design version does not match its generation workflow.")
        from app.services.llm.generation_service import generation_job_is_instant_deck, require_publishable_instant_design_version

        if generation_job_is_instant_deck(version.generation_job):
            require_publishable_instant_design_version(version)
        validated_recovery_lineage = {
            "generationWorkflowJobId": generation_workflow_job_id,
            "designVersionId": design_version_id,
        }
        if getattr(version, "render_mode", "scene_graph.v1") == "html_compiled.v1":
            from app.services.llm.instant_html_operation_service import mark_operation_published

            # Validate recovered provider/design/artifact lineage before any
            # publication state or deck transition is applied.
            mark_operation_published(db, design_version_id)
            _select_published_instant_version(db, deck=deck, version=version)

    if target == "smart_deck_ready":
        if canonical_deck_state(deck.status) == DeckState.FAILED:
            # Recovery is limited to the locked publisher whose failure
            # lineage and Smart Deck context dependency were validated above.
            transition_deck_state(
                db,
                deck,
                DeckState.PROCESSING,
                reason="workflow_db_publisher_source_recovery",
                summary="Validated source publication is recovering the deck.",
                source_surface="workflow_db_publisher",
                source_route=f"/decks/{deck.id}/workflow",
                metadata={
                    "workflowJobId": job.id,
                    "workerId": worker_id,
                    "publishTarget": target,
                },
            )
        transition_deck_state(
            db,
            deck,
            DeckState.READY,
            reason="workflow_db_publisher_smart_deck_ready",
            summary="Smart Deck source pipeline completed and was published by the workflow orchestrator.",
            source_surface="workflow_db_publisher",
            source_route=f"/decks/{deck.id}/workflow",
            metadata={"workflowJobId": job.id, "workerId": worker_id},
        )
        if run is not None:
            run.status = "completed"
            run.completed_at = run.completed_at or _now()
            _mark_run_stage(run, stage="smart_deck_context_ready", next_action="open_smart_deck", worker_id=worker_id)
        output_payload = {
            "phase": "smart_deck_ready",
            "deckState": DeckState.READY.value,
            "publishedAt": _now().isoformat(),
        }
    elif target == "preview_ready":
        if canonical_deck_state(deck.status) == DeckState.FAILED:
            # Recovery is intentionally limited to a preview publisher whose
            # dependency lineage and publishability were validated above.
            transition_deck_state(
                db,
                deck,
                DeckState.PROCESSING,
                reason="workflow_db_publisher_validated_preview_recovery",
                summary="Validated Smart Deck preview publication is recovering the deck.",
                source_surface="workflow_db_publisher",
                source_route=f"/decks/{deck.id}/workflow",
                metadata={
                    "workflowJobId": job.id,
                    "workerId": worker_id,
                    "publishTarget": target,
                    **(validated_recovery_lineage or {}),
                },
            )
        transition_deck_state(
            db,
            deck,
            DeckState.READY,
            reason="workflow_db_publisher_preview_ready",
            summary="Smart Deck preview was published by the workflow orchestrator.",
            source_surface="workflow_db_publisher",
            source_route=f"/decks/{deck.id}/workflow",
            metadata={"workflowJobId": job.id, "workerId": worker_id, "publishTarget": target},
        )
        output_payload = {
            "phase": "preview_ready",
            "publishTarget": "preview_ready",
            "deckState": DeckState.READY.value,
            "publishedAt": _now().isoformat(),
            **(validated_recovery_lineage or {}),
        }
    elif target == "applied":
        transition_deck_state(
            db,
            deck,
            DeckState.READY,
            reason="workflow_db_publisher_applied",
            summary="Applied design version was published by the workflow orchestrator.",
            source_surface="workflow_db_publisher",
            source_route=f"/decks/{deck.id}/workflow",
            metadata={"workflowJobId": job.id, "workerId": worker_id, "publishTarget": target},
        )
        output_payload = {
            "phase": "applied",
            "deckState": DeckState.READY.value,
            "publishedAt": _now().isoformat(),
        }
    elif target == "export_ready":
        transition_deck_state(
            db,
            deck,
            DeckState.READY,
            reason="workflow_db_publisher_export_ready",
            summary="Deck export was published by the workflow orchestrator.",
            source_surface="workflow_db_publisher",
            source_route=f"/decks/{deck.id}/workflow",
            metadata={"workflowJobId": job.id, "workerId": worker_id, "publishTarget": target},
        )
        output_payload = {
            "phase": "export_ready",
            "deckState": DeckState.READY.value,
            "publishedAt": _now().isoformat(),
        }
    else:
        deck.summary = "Workflow publisher completed."
        output_payload = {
            "phase": target,
            "deckState": deck.status,
            "publishedAt": _now().isoformat(),
        }

    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message=f"Publisher marked {target}.",
        output_payload=output_payload,
        published_phase=target,
    )
    if target == "smart_deck_ready":
        from app.services.deck_processing.workflow_orchestration import enqueue_upload_first_instant_html_baseline

        db.flush()
        brand_job = db.query(WorkflowJob).filter(
            WorkflowJob.deck_id == deck.id,
            WorkflowJob.extraction_run_id == job.extraction_run_id,
            WorkflowJob.job_type == "brand_extraction",
        ).one_or_none()
        if brand_job is not None and brand_job.status != JOB_STATUS_COMPLETED:
            job.output_json = {
                **(job.output_json if isinstance(job.output_json, dict) else {}),
                "instantDeckGenerationDeferredToBrandJobId": brand_job.id,
            }
        else:
            instant_generation = enqueue_upload_first_instant_html_baseline(
                db,
                deck,
                source_workflow_job=job,
            )
            if instant_generation is not None:
                job.output_json = {
                    **(job.output_json if isinstance(job.output_json, dict) else {}),
                    "instantDeckGenerationJobId": instant_generation["jobId"],
                }
    db.commit()


def handle_export(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    payload = _job_payload(job)
    export_type = str(payload.get("exportType") or "").strip()
    export_format = str(payload.get("format") or "").strip().lower()
    design_version_id = str(payload.get("designVersionId") or "").strip()
    if not export_type:
        raise ValueError("Workflow export job is missing exportType.")
    if export_format:
        if export_type not in {FINAL_DECK_EXPORT_TYPE, PROVISIONAL_HTML_EXPORT_TYPE} or export_format != "html" or not design_version_id:
            raise ValueError("Workflow export job has an invalid classified HTML contract.")
        export_payload = create_export(
            db,
            job.deck_id,
            export_type,
            export_format=export_format,
            design_version_id=design_version_id,
            idempotency_key=job.id,
            commit=False,
        )
    else:
        from app.services.deck_processing.workflow_orchestration import _require_complete_generation_coverage_for_export

        _require_complete_generation_coverage_for_export(db, job.deck_id)
        export_payload = create_export(db, job.deck_id, export_type, idempotency_key=job.id, commit=False)
    if export_payload is None:
        raise ValueError("Export could not be created.")
    export_id = str(export_payload.get("id") or "").strip()
    version_status = str(export_payload.get("versionStatus") or "")
    artifact_hash = str(export_payload.get("artifactHash") or "")
    classification = str(export_payload.get("classification") or ("provisional" if export_type == PROVISIONAL_HTML_EXPORT_TYPE else "final"))
    actor = db.query(User).filter(User.id == job.user_id).one_or_none() if job.user_id else None
    existing_audit = db.query(SecurityAuditEvent).filter(
        SecurityAuditEvent.action == "deck.export.snapshot_created",
        SecurityAuditEvent.resource_type == "deck_export",
        SecurityAuditEvent.resource_id == export_id,
    ).one_or_none()
    if existing_audit is None:
        record_security_event(
            db,
            action="deck.export.snapshot_created",
            result="success",
            actor=actor,
            resource_type="deck_export",
            resource_id=export_id,
            details={
                "deckId": job.deck_id,
                "designVersionId": design_version_id,
                "versionStatus": version_status,
                "format": export_format,
                "artifactHash": artifact_hash,
                "classification": classification,
                "exportType": export_type,
            },
        )
    storage_key = (
        export_payload.get("downloadUrl")
        or export_payload.get("download_url")
        or f"/api/products/deck-aistack-codes/decks/{job.deck_id}/exports/{export_id}/download"
    )
    record_workflow_artifact(
        db,
        job=job,
        artifact_type="deck_export",
        storage_key=storage_key,
        metadata={
            "exportId": export_id,
            "exportType": export_type,
            **({
                "designVersionId": design_version_id,
                "format": export_format,
                "versionStatus": version_status,
                "artifactHash": artifact_hash,
                "classification": classification,
            } if export_format else {}),
            "downloadUrl": export_payload.get("downloadUrl") or export_payload.get("download_url"),
        },
    )
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Export stage completed.",
        output_payload={
            "phase": "export_ready",
            "exportId": export_id,
            "exportType": export_type,
            **({"designVersionId": design_version_id, "format": export_format} if export_format else {}),
            "downloadUrl": export_payload.get("downloadUrl") or export_payload.get("download_url"),
        },
    )
    db.commit()
    reconcile_pending_export_handoffs(db, limit=10)
