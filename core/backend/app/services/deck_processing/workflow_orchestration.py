"""Workflow orchestration service.

Owns: source pipeline queuing, Smart Deck generation, apply-design-version,
export, compile-final-deck, and selected-slide generation orchestration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session
from app.core.config import settings
from app.services.llm.instant_deck_mvp_policy import MVP_UPLOAD_PROMPT, MVP_AUDIENCE

# Compatibility import for existing test instrumentation; upload-first publisher
# orchestration must not invoke this runtime-selected context builder.
from app.ai.instant_deck_knowledge_context import build_instant_deck_generation_context
from app.core.security import generate_id
from app.db.models import Deck, DeckExtractionRun, DeckFile, DeckSlide, DesignBatch, DesignVersion, GenerationJob, InstantDeckOperation, SmartDeckWorkspace, WorkflowJob
from app.schemas.due_diligence import DueDiligenceRunRequest
from app.schemas.deck_workflow import (
    WorkflowApplyRequest,
    WorkflowExportRequest,
    WorkflowFailedSlideRetryRequest,
    WorkflowGenerationRequest,
    WorkflowSelectedSlideGenerationRequest,
)
from app.schemas.shell import PrepareFullDeckRequest
from app.services.deck_processing.workflow_state_read_model import _coerce_mapping, _map_workflow_job_summary
from app.services.llm.selected_slide_generation_service import build_selected_slide_batches
from app.services.deck_processing.processing_queue import PROCESSING_RUN_TYPE
from app.services.llm.generation_service import (
    GenerationValidationError,
    SmartDeckProviderUnavailableError,
    generation_job_is_instant_deck,
    get_generation_provider_config,
    require_publishable_instant_design_version,
)
from app.services.rendering.export_service import PROVISIONAL_HTML_EXPORT_TYPE, resolve_html_export_design_version
from app.services.rendering.schema_validation import CompiledArtifactRegenerationRequired
from app.services.llm.instant_html_operation_service import (
    ActiveInstantOperationConflict,
    InstantOperationConflict,
    canonical_request_hash,
    resolve_operation,
    validate_durable_enqueue_feasibility,
    validate_output_feasibility,
)
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_BLOCKED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_TIMED_OUT,
    JOB_TYPE_APPLY_VERSION,
    JOB_TYPE_DB_PUBLISHER,
    JOB_TYPE_EXPORT,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_SELECTED_SLIDE_GENERATION,
    JOB_TYPE_SMART_DECK_CONTEXT,
    JOB_TYPE_SOURCE_INGESTION,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_SCHEMA_VALIDATION,
    JOB_TYPE_SOURCE_EXTRACTION,
    JOB_TYPE_COMPILE_FINAL_DECK,
    JOB_TYPE_DUE_DILIGENCE,
    JOB_TYPE_DECK_MAP_ANALYSIS,
    JOB_TYPE_MARKET_RESEARCH,
    SOURCE_PIPELINE_JOB_SEQUENCE,
    ensure_pipeline_jobs_for_run,
    ensure_workflow_dependency,
    ensure_workflow_job,
    get_workflow_job_by_idempotency_key,
    requeue_pipeline_jobs_for_run,
)

SOURCE_PIPELINE_MAX_ATTEMPTS = 3
DECK_INTELLIGENCE_ACTIVE_STATUSES = {JOB_STATUS_QUEUED, JOB_STATUS_RUNNING, JOB_STATUS_FAILED_RETRYABLE}
LEGACY_UPLOAD_FIRST_INSTANT_DECK_PROMPT = "Generate one complete grounded HTML deck from every selected source slide."
PREVIOUS_UPLOAD_FIRST_INSTANT_DECK_PROMPT = (
    "Redesign the complete source document into one investor-ready VC HTML deck using every selected source slide "
    "in canonical order. Strengthen the investment narrative and evidence hierarchy; rewrite copy concisely; and "
    "apply a premium, consistent visual system across the whole deck. Faithfully emphasize only risks or gaps already "
    "explicit in the source evidence. Stay source-grounded and do not invent claims, metrics, evidence, or facts."
)

GENERAL_UPLOAD_FIRST_INSTANT_DECK_PROMPT = (
    "Redesign the complete source document into one coherent HTML presentation using every selected source slide. "
    "Preserve the source's presentation intent, strengthen its visual narrative and evidence hierarchy, and rewrite copy concisely. "
    "Choose sections to serve the content, independently of source page count. Do not introduce unrelated subject matter. "
    "Stay source-grounded and do not invent claims, metrics, evidence, or facts."
)



UPLOAD_FIRST_INSTANT_DECK_PROMPT = MVP_UPLOAD_PROMPT


class WorkflowConflictError(ValueError):
    def __init__(self, *, code: str, message: str, recoverable: bool = True, next_action: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.next_action = next_action


def _generation_job_type_for_mode(generation_mode: str | None) -> str:
    return JOB_TYPE_INSTANT_DECK_GENERATION if generation_mode == "instant_deck" else JOB_TYPE_LLM_GENERATION


def queue_deck_intelligence_job(
    db: Session,
    deck_id: str,
    *,
    current_user_id: str,
    job_type: str,
) -> dict[str, Any]:
    """Queue one durable Deck Map or Market Research command.

    The body-less product commands have no caller-supplied idempotency key, so
    concurrent active commands are coalesced. A later explicit command receives
    a new identity after the previous job reaches a terminal state.
    """
    if job_type not in {JOB_TYPE_DECK_MAP_ANALYSIS, JOB_TYPE_MARKET_RESEARCH}:
        raise ValueError("Unsupported deck intelligence job type")
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")

    context_job = (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.job_type == JOB_TYPE_SMART_DECK_CONTEXT,
            WorkflowJob.status == JOB_STATUS_COMPLETED,
        )
        .order_by(WorkflowJob.completed_at.desc(), WorkflowJob.created_at.desc())
        .first()
    )
    if context_job is None:
        raise WorkflowConflictError(
            code="smart_deck_context_not_ready",
            message="Deck intelligence requires completed Smart Deck context.",
            recoverable=True,
            next_action="view_processing",
        )

    active_job = (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.job_type == job_type,
            WorkflowJob.status.in_(DECK_INTELLIGENCE_ACTIVE_STATUSES),
        )
        .order_by(WorkflowJob.created_at.desc())
        .first()
    )
    if active_job is None:
        command_id = generate_id("command")
        active_job = ensure_workflow_job(
            db,
            deck=deck,
            job_type=job_type,
            status=JOB_STATUS_QUEUED,
            idempotency_key=f"{job_type}:{command_id}",
            priority=55,
            max_attempts=3,
            input_payload={"requestedByUserId": current_user_id},
        )
        ensure_workflow_dependency(db, job=active_job, depends_on_job=context_job)
    db.commit()
    summary = _map_workflow_job_summary(active_job)
    return {
        "accepted": True,
        "jobId": active_job.id,
        "jobType": active_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{active_job.id}",
    }


def queue_due_diligence(
    db: Session,
    deck_id: str,
    *,
    current_user_id: str,
    payload: DueDiligenceRunRequest,
) -> dict[str, Any]:
    """Persist one idempotent Due Diligence command for worker execution."""
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")

    normalized_input = {
        "audience": payload.audience,
        "runMode": payload.runMode,
        "requestedByUserId": current_user_id,
    }
    idempotency_key = f"due-diligence:{current_user_id}:{payload.idempotencyKey}"
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=JOB_TYPE_DUE_DILIGENCE,
        idempotency_key=idempotency_key,
    )
    if existing is not None and _coerce_mapping(existing.input_json) != normalized_input:
        raise WorkflowConflictError(
            code="idempotency_key_conflict",
            message="The Due Diligence idempotency key was already used for a different command.",
            recoverable=True,
            next_action="retry_job",
        )

    job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_DUE_DILIGENCE,
        status=JOB_STATUS_QUEUED,
        idempotency_key=idempotency_key,
        priority=60,
        max_attempts=3,
        input_payload=normalized_input,
    )
    db.commit()
    summary = _map_workflow_job_summary(job)
    audience_query = payload.audience
    return {
        "accepted": True,
        "jobId": job.id,
        "jobType": job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{job.id}",
        "reportUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/due-diligence?audience={audience_query}",
    }


def _normalized_generation_payload(payload: WorkflowGenerationRequest) -> dict[str, Any]:
    return {
        "prompt": payload.prompt.strip(),
        "selectedSourceSlideIds": list(payload.selectedSourceSlideIds),
        "activeSourceSlideId": payload.activeSourceSlideId,
        "sourceVersionId": payload.sourceVersionId,
        "styleId": payload.styleId,
        "brandProductId": payload.brandProductId,
        "additionalContext": payload.additionalContext,
        "deckType": payload.deckType,
        "audience": payload.audience,
        "preferredModel": payload.preferredModel,
        "selectedElementId": payload.selectedElementId,
        "selectedSubject": payload.selectedSubject,
        "actionId": payload.actionId,
        "actionPrompt": payload.actionPrompt,
        "userPrompt": payload.userPrompt,
        "latestBatchId": payload.latestBatchId,
        "detectedSubjects": payload.detectedSubjects,
        "subjectConfidence": payload.subjectConfidence,
        "designContext": payload.designContext,
        "provenance": payload.provenance.model_dump() if payload.provenance is not None else None,
        "generationMode": payload.generationMode,
        "outputContract": payload.outputContract,
        "baseDesignVersionId": payload.baseDesignVersionId,
    }


def _normalized_apply_payload(payload: WorkflowApplyRequest) -> dict[str, Any]:
    return {"designVersionId": payload.designVersionId}


def _normalized_export_payload(payload: WorkflowExportRequest) -> dict[str, Any]:
    export_type = (payload.normalized_type or "").strip()
    if not export_type:
        raise ValueError("export type is required")
    if payload.format == "html":
        return {
            "designVersionId": payload.designVersionId,
            "exportType": export_type,
            "format": payload.format,
        }
    return {"exportType": export_type}


def export_fallback_idempotency_key(
    deck_id: str,
    *,
    export_type: str | None,
    export_format: str | None,
    design_version_id: str | None,
) -> str:
    return (
        f"{deck_id}:export:{export_type or 'unknown'}:"
        f"{export_format or 'legacy'}:{design_version_id or 'no-design-version'}"
    )


def _require_complete_generation_coverage_for_export(
    db: Session,
    deck_id: str,
    design_version_id: str | None = None,
) -> None:
    if design_version_id is None:
        deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
        workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).one_or_none()
        design_version_id = (deck.current_design_version_id if deck is not None else None) or (
            workspace.active_design_version_id if workspace is not None else None
        )
        if not design_version_id:
            return
    version = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == design_version_id)
        .one_or_none()
    )
    if version is None:
        raise WorkflowConflictError(
            code="active_design_version_invalid",
            message="Select a valid deck version before exporting.",
            recoverable=True,
            next_action="select_design_version",
        )
    if not version.generation_job_id:
        if version.generated_slides:
            raise WorkflowConflictError(
                code="generated_version_provenance_missing",
                message="Regenerate this deck version before exporting.",
                recoverable=True,
                next_action="regenerate_deck",
            )
        return
    generation_job = db.query(GenerationJob).filter(GenerationJob.id == version.generation_job_id).one_or_none()
    if generation_job is None:
        raise WorkflowConflictError(
            code="generated_version_provenance_missing",
            message="Regenerate this deck version before exporting.",
            recoverable=True,
            next_action="regenerate_deck",
        )
    if generation_job_is_instant_deck(generation_job):
        try:
            require_publishable_instant_design_version(version)
        except GenerationValidationError as exc:
            raise WorkflowConflictError(
                code="instant_deck_not_publishable",
                message="Regenerate this Instant Deck with complete LLM-grounded slides before exporting.",
                recoverable=True,
                next_action="regenerate_instant_deck",
            ) from exc
    result = generation_job.result_json if generation_job and isinstance(generation_job.result_json, dict) else None
    if result is None or "coverageComplete" not in result:
        return
    if result.get("coverageComplete") is not True:
        raise WorkflowConflictError(
            code="generation_coverage_incomplete",
            message="Retry failed generated slides before exporting this design version.",
            recoverable=True,
            next_action="retry_failed_slides",
        )


def _normalized_compile_final_payload(payload: PrepareFullDeckRequest, *, batch_id: str) -> dict[str, Any]:
    return {
        "batchId": batch_id,
        "title": payload.title.strip() if isinstance(payload.title, str) and payload.title.strip() else None,
        "latestSlideVersionId": payload.latestSlideVersionId,
    }


def _normalized_selected_slide_generation_payload(payload: WorkflowSelectedSlideGenerationRequest) -> dict[str, Any]:
    return {
        "prompt": payload.prompt.strip(),
        "selectedSourceSlideIds": list(payload.selectedSourceSlideIds),
        "partitionCount": int(payload.partitionCount),
        "batchSize": int(payload.batchSize),
        "preferredModel": payload.preferredModel,
    }


def _source_ingestion_job_for_checksum(db: Session, deck_id: str, source_checksum: str | None) -> WorkflowJob | None:
    if not source_checksum:
        return None
    return get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=JOB_TYPE_SOURCE_INGESTION,
        idempotency_key=f"{deck_id}:{source_checksum}:{JOB_TYPE_SOURCE_INGESTION}",
    )


def _source_checksum_from_run(run: DeckExtractionRun | None) -> str | None:
    if run is None or not isinstance(run.metadata_json, dict):
        return None
    raw = run.metadata_json.get("sourceChecksum")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _source_processing_run_metadata(
    *,
    deck: Deck,
    deck_file: DeckFile,
    source_checksum: str,
    requested_by_user_id: str | None,
    attempt_count: int = 0,
) -> dict[str, Any]:
    return {
        "requestedByUserId": requested_by_user_id,
        "sourceStoragePath": deck_file.storage_path,
        "sourceChecksum": source_checksum,
        "idempotencyKey": f"{deck.id}:{source_checksum}:{PROCESSING_RUN_TYPE}",
        "idempotencyScope": "deck_id_source_checksum_run_type",
        "stage": "source_saved",
        "stageLabel": "Source file saved",
        "nextAction": "wait_for_worker",
        "attemptCount": attempt_count,
        "maxAttempts": SOURCE_PIPELINE_MAX_ATTEMPTS,
        "heartbeatAt": datetime.utcnow().isoformat(),
    }


def _ensure_source_processing_run(
    db: Session,
    *,
    deck: Deck,
    deck_file: DeckFile,
    source_checksum: str,
    requested_by_user_id: str | None,
) -> DeckExtractionRun:
    ingestion_job = _source_ingestion_job_for_checksum(db, deck.id, source_checksum)
    if ingestion_job is not None and ingestion_job.extraction_run_id:
        workflow_run = (
            db.query(DeckExtractionRun)
            .filter(DeckExtractionRun.id == ingestion_job.extraction_run_id)
            .one_or_none()
        )
        if workflow_run is not None and _source_checksum_from_run(workflow_run) == source_checksum and workflow_run.source_file_id == deck_file.id:
            return workflow_run

    run_metadata = _source_processing_run_metadata(
        deck=deck,
        deck_file=deck_file,
        source_checksum=source_checksum,
        requested_by_user_id=requested_by_user_id,
    )
    run = DeckExtractionRun(
        id=generate_id("process"),
        deck_id=deck.id,
        source_file_id=deck_file.id,
        run_type=PROCESSING_RUN_TYPE,
        extractor_name="workflow_source_pipeline",
        extractor_version="v2",
        source_format=deck_file.file_extension,
        status="queued",
        metadata_json=run_metadata,
        current_stage="source_saved",
        current_stage_label="Source file saved",
        next_action="wait_for_worker",
        attempt_count=0,
        max_attempts=SOURCE_PIPELINE_MAX_ATTEMPTS,
        heartbeat_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()
    return run


def _requeue_source_processing_run(
    *,
    run: DeckExtractionRun,
    deck: Deck,
    deck_file: DeckFile,
    source_checksum: str,
    requested_by_user_id: str | None,
) -> None:
    previous_metadata = dict(run.metadata_json or {}) if isinstance(run.metadata_json, dict) else {}
    previous_attempt_count = int(previous_metadata.get("attemptCount") or 0)
    retry_reset_at = datetime.utcnow().isoformat()
    run.status = "queued"
    run.started_at = None
    run.completed_at = None
    run.error_message = None
    run.source_file_id = deck_file.id
    run.source_format = deck_file.file_extension
    run.extractor_name = "workflow_source_pipeline"
    run.extractor_version = "v2"
    run.metadata_json = {
        **_source_processing_run_metadata(
            deck=deck,
            deck_file=deck_file,
            source_checksum=source_checksum,
            requested_by_user_id=requested_by_user_id,
            attempt_count=0,
        ),
        "previousAttemptCount": previous_attempt_count,
        "retryResetAt": retry_reset_at,
        "previousStatus": previous_metadata.get("status") or run.status,
    }
    run.current_stage = "source_saved"
    run.current_stage_label = "Source file saved"
    run.next_action = "wait_for_worker"
    run.attempt_count = 0
    run.max_attempts = SOURCE_PIPELINE_MAX_ATTEMPTS
    run.locked_by = None
    run.locked_at = None
    run.heartbeat_at = datetime.utcnow()


def _sync_source_processing_run_from_jobs(
    *,
    run: DeckExtractionRun,
    deck: Deck,
    deck_file: DeckFile,
    source_checksum: str,
    requested_by_user_id: str | None,
    jobs: dict[str, WorkflowJob],
) -> WorkflowJob | None:
    previous_metadata = dict(run.metadata_json or {}) if isinstance(run.metadata_json, dict) else {}
    head_job = None
    for job_type in SOURCE_PIPELINE_JOB_SEQUENCE:
        candidate = jobs.get(job_type)
        if candidate is not None and candidate.status != JOB_STATUS_COMPLETED:
            head_job = candidate
            break
    if head_job is None:
        head_job = jobs.get(JOB_TYPE_DB_PUBLISHER) or jobs.get(JOB_TYPE_SOURCE_EXTRACTION) or jobs.get(JOB_TYPE_SOURCE_INGESTION)

    attempt_count = 0
    for candidate in jobs.values():
        attempt_count = max(attempt_count, int(candidate.attempt_count or 0))

    metadata = _source_processing_run_metadata(
        deck=deck,
        deck_file=deck_file,
        source_checksum=source_checksum,
        requested_by_user_id=requested_by_user_id,
        attempt_count=attempt_count,
    )
    for key in ("previousAttemptCount", "retryResetAt", "previousStatus"):
        if key in previous_metadata:
            metadata[key] = previous_metadata[key]
    if head_job is not None:
        metadata.update(
            {
                "workflowJobId": head_job.id,
                "workflowJobType": head_job.job_type,
                "workflowJobStatus": head_job.status,
            }
        )
    run.metadata_json = metadata
    run.current_stage = str(metadata.get("stage") or "source_saved")
    run.current_stage_label = str(metadata.get("stageLabel") or run.current_stage.replace("_", " ").title())
    run.next_action = str(metadata.get("nextAction") or "wait_for_worker")
    run.attempt_count = attempt_count
    run.max_attempts = SOURCE_PIPELINE_MAX_ATTEMPTS
    if head_job is not None:
        run.locked_by = head_job.locked_by
        run.locked_at = head_job.started_at
        run.heartbeat_at = head_job.heartbeat_at or datetime.utcnow()
    else:
        run.locked_by = None
        run.locked_at = None
        run.heartbeat_at = datetime.utcnow()

    has_running = any(candidate.status == JOB_STATUS_RUNNING for candidate in jobs.values())
    has_unfinished = any(candidate.status != JOB_STATUS_COMPLETED for candidate in jobs.values())
    if has_running:
        run.status = "processing"
        run.started_at = run.started_at or datetime.utcnow()
        run.completed_at = None
        run.error_message = None
    elif has_unfinished:
        run.status = "queued"
        run.completed_at = None
        run.error_message = None
    else:
        run.status = "completed"
        run.completed_at = run.completed_at or datetime.utcnow()
        run.error_message = None

    return head_job


def _ensure_generation_pipeline_jobs(
    db: Session,
    *,
    deck: Deck,
    generation_job: WorkflowJob,
    idempotency_key: str,
    current_user_id: str,
) -> tuple[WorkflowJob, WorkflowJob, WorkflowJob]:
    instant_operation_id = str((generation_job.input_json or {}).get("instantOperationId") or "").strip() or None
    schema_validation_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_SCHEMA_VALIDATION,
        status=JOB_STATUS_QUEUED,
        idempotency_key=f"{idempotency_key}:schema-validation",
        max_attempts=1,
        input_payload={
            "generationWorkflowJobId": generation_job.id,
            "requestedByUserId": current_user_id,
            **({"instantOperationId": instant_operation_id} if instant_operation_id else {}),
        },
    )
    preview_render_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_PREVIEW_RENDER,
        status=JOB_STATUS_QUEUED,
        idempotency_key=f"{idempotency_key}:preview-render",
        max_attempts=1,
        input_payload={
            "generationWorkflowJobId": generation_job.id,
            "schemaValidationWorkflowJobId": schema_validation_job.id,
            "requestedByUserId": current_user_id,
            **({"instantOperationId": instant_operation_id} if instant_operation_id else {}),
        },
    )
    publisher_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_DB_PUBLISHER,
        status=JOB_STATUS_QUEUED,
        idempotency_key=f"{idempotency_key}:publisher",
        max_attempts=1,
        input_payload={
            "publishTarget": "preview_ready",
            "generationWorkflowJobId": generation_job.id,
            "schemaValidationWorkflowJobId": schema_validation_job.id,
            "previewRenderWorkflowJobId": preview_render_job.id,
            "requestedByUserId": current_user_id,
            **({"instantOperationId": instant_operation_id} if instant_operation_id else {}),
        },
    )
    ensure_workflow_dependency(db, job=schema_validation_job, depends_on_job=generation_job)
    ensure_workflow_dependency(db, job=preview_render_job, depends_on_job=schema_validation_job)
    ensure_workflow_dependency(db, job=publisher_job, depends_on_job=preview_render_job)
    return schema_validation_job, preview_render_job, publisher_job


def queue_source_extraction(
    db: Session,
    deck_id: str,
    *,
    requested_by_user_id: str | None,
    requeue_failed: bool = True,
) -> dict[str, Any]:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")
    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck_id).one_or_none()
    if deck_file is None:
        raise ValueError("Deck source file not found")
    source_checksum = str(deck_file.checksum_sha256 or "").strip()
    if not source_checksum:
        raise ValueError("Deck source checksum is required for idempotent processing")

    run = _ensure_source_processing_run(
        db,
        deck=deck,
        deck_file=deck_file,
        source_checksum=source_checksum,
        requested_by_user_id=requested_by_user_id,
    )
    jobs = ensure_pipeline_jobs_for_run(
        db,
        deck=deck,
        run=run,
        source_checksum=source_checksum,
        max_attempts=SOURCE_PIPELINE_MAX_ATTEMPTS,
    )

    if requeue_failed and any(
        job.status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_BLOCKED, JOB_STATUS_TIMED_OUT}
        for job in jobs.values()
    ):
        _requeue_source_processing_run(
            run=run,
            deck=deck,
            deck_file=deck_file,
            source_checksum=source_checksum,
            requested_by_user_id=requested_by_user_id,
        )
        jobs = requeue_pipeline_jobs_for_run(
            db,
            deck=deck,
            run=run,
            source_checksum=source_checksum,
            max_attempts=SOURCE_PIPELINE_MAX_ATTEMPTS,
        )

    accepted_job = _sync_source_processing_run_from_jobs(
        run=run,
        deck=deck,
        deck_file=deck_file,
        source_checksum=source_checksum,
        requested_by_user_id=requested_by_user_id,
        jobs=jobs,
    )

    ingestion_job = jobs.get(JOB_TYPE_SOURCE_INGESTION)
    source_job = jobs.get(JOB_TYPE_SOURCE_EXTRACTION)
    active_source_pipeline = (
        (ingestion_job is not None and ingestion_job.status != JOB_STATUS_COMPLETED)
        or (source_job is not None and source_job.status != JOB_STATUS_COMPLETED)
    )

    if active_source_pipeline and deck.status != "processing":
        from app.services.deck_processing.state_machine import DeckState, transition_deck_state

        transition_deck_state(
            db,
            deck,
            DeckState.PROCESSING,
            actor_user_id=requested_by_user_id,
            reason="workflow_source_pipeline_queued",
            summary="Deck processing has been queued through workflow jobs.",
            source_surface="deck_workflow_service",
            source_route=f"/decks/{deck_id}/workflow",
            metadata={
                "processingRunId": run.id,
                "sourceChecksum": source_checksum,
                "workflowJobId": accepted_job.id if accepted_job is not None else None,
                "workflowJobType": accepted_job.job_type if accepted_job is not None else None,
            },
        )

    response_job = None
    for job_type in SOURCE_PIPELINE_JOB_SEQUENCE:
        candidate = jobs.get(job_type)
        if candidate is not None and candidate.status != JOB_STATUS_COMPLETED:
            response_job = candidate
            break
    if response_job is None:
        response_job = jobs.get(JOB_TYPE_DB_PUBLISHER) or jobs.get(JOB_TYPE_SOURCE_EXTRACTION)
    if response_job is None:
        raise ValueError("Workflow source extraction job was not created")
    summary = _map_workflow_job_summary(response_job)
    result = {
        "accepted": True,
        "jobId": response_job.id,
        "jobType": response_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{response_job.id}",
        "commitState": "committed",
    }
    # Nothing fallible follows this commit. Callers can treat a returned result
    # as durable and an exception as ambiguous, then inspect coordination state.
    db.commit()
    return result


def queue_smart_deck_generation(
    db: Session,
    deck_id: str,
    *,
    current_user_id: str,
    payload: WorkflowGenerationRequest,
    defer_instant_provider_release: bool = False,
    source_readiness_job: WorkflowJob | None = None,
) -> dict[str, Any]:
    from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
    from app.services.llm.generation_provenance_service import GenerationProvenanceError, validate_generation_provenance

    # Generation creation and preview publication serialize on the same deck
    # row, so a publisher cannot validate authority while a newer generation
    # lineage is being created in another transaction.
    deck = (
        db.query(Deck)
        .populate_existing()
        .filter(Deck.id == deck_id)
        .with_for_update()
        .one_or_none()
    )
    if deck is None:
        raise ValueError("Deck not found")
    normalized_input = _normalized_generation_payload(payload)
    generation_job_type = _generation_job_type_for_mode(payload.generationMode)
    worker_owned_instant_release = (
        defer_instant_provider_release
        and payload.generationMode == "instant_deck"
        and payload.outputContract == "full_html_deck.v1"
    )
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=generation_job_type,
        idempotency_key=payload.idempotencyKey,
    )
    if existing is not None:
        if existing.user_id != deck.user_id or existing.workspace_id != deck.workspace_id:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The upload-first idempotency key is bound to a different Instant Deck request.",
                recoverable=False,
            )
        existing_input = dict(_coerce_mapping(existing.input_json))
        existing_input.pop("instantOperationId", None)
        existing_input.pop("providerReleaseOwner", None)
        # This application-owned research release policy is attached after the
        # immutable user request is hashed. It must not make an exact replay
        # look like a different browser command.
        existing_input.pop("publicResearchPolicy", None)
        if existing_input != normalized_input:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The idempotency key is already bound to a different Smart Deck generation request.",
                recoverable=False,
            )
        html_operation = None
        if payload.outputContract == "full_html_deck.v1":
            html_operation = (
                db.query(InstantDeckOperation)
                .filter(
                    InstantDeckOperation.deck_id == deck_id,
                    InstantDeckOperation.user_id == current_user_id,
                    InstantDeckOperation.idempotency_key == payload.idempotencyKey,
                )
                .with_for_update()
                .one_or_none()
            )
            if html_operation is None or html_operation.request_hash != canonical_request_hash(normalized_input):
                raise WorkflowConflictError(
                    code="idempotency_key_conflict",
                    message="The persisted Instant Deck operation does not match this request.",
                    recoverable=False,
                )
            if html_operation.workflow_job_id not in {None, existing.id}:
                raise WorkflowConflictError(
                    code="idempotency_key_conflict",
                    message="The persisted Instant Deck operation is bound to another workflow job.",
                    recoverable=False,
                )
            if html_operation.workflow_job_id is None:
                html_operation.workflow_job_id = existing.id
                existing_input_with_operation = dict(existing.input_json or {})
                existing_input_with_operation["instantOperationId"] = html_operation.id
                existing.input_json = existing_input_with_operation
                db.commit()
        if existing.user_id is None:
            existing.user_id = current_user_id
        # Repair only an in-flight outbox. Terminal replays are observational
        # and must not recreate dependencies or requeue consumed work.
        operation_is_resumable = html_operation is None or html_operation.status in {
            "enqueue_pending",
            "charge_reconciling",
            "queued",
            "provider_running",
            "provider_reconciling",
            "provider_checkpoint_ready",
        }
        if (
            worker_owned_instant_release
            and html_operation is not None
            and existing.status in {JOB_STATUS_BLOCKED, JOB_STATUS_QUEUED, JOB_STATUS_RUNNING}
            and operation_is_resumable
        ):
            existing_input_with_operation = dict(existing.input_json or {})
            existing_input_with_operation["providerReleaseOwner"] = "instant_worker"
            existing.input_json = existing_input_with_operation
            if existing.status == JOB_STATUS_BLOCKED and html_operation.charge_status == "pending":
                existing.status = JOB_STATUS_QUEUED
        if existing.status in {JOB_STATUS_BLOCKED, JOB_STATUS_QUEUED, JOB_STATUS_RUNNING} and operation_is_resumable:
            _ensure_generation_pipeline_jobs(
                db,
                deck=deck,
                generation_job=existing,
                idempotency_key=payload.idempotencyKey,
                current_user_id=current_user_id,
            )
            db.commit()
        summary = _map_workflow_job_summary(existing)
        return {
            "accepted": True,
            "jobId": existing.id,
            "jobType": existing.job_type,
            "status": summary["status"],
            "phase": summary["phase"],
            "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
            "jobUrl": f"/api/workflow-jobs/{existing.id}",
            "instantOperationId": html_operation.id if html_operation is not None else None,
            "instantOperationStatus": html_operation.status if html_operation is not None else None,
            "operationCreated": False,
        }
    try:
        validate_generation_provenance(db, deck_id, payload.provenance)
    except GenerationProvenanceError as exc:
        raise WorkflowConflictError(code="invalid_generation_provenance", message=str(exc), recoverable=False) from exc
    if defer_instant_provider_release and not worker_owned_instant_release:
        raise ValueError("Deferred provider release is only valid for whole-deck Instant HTML generation.")
    if worker_owned_instant_release:
        if source_readiness_job is not None:
            # Upload-first release retains its exact publisher lineage check.
            _source_readiness_publisher_for_upload(db, deck, source_readiness_job)
        else:
            # Mounted manual generation supports already source-ready decks
            # through the canonical read model without pretending that the
            # command originated from the upload publisher callback.
            workflow_state = get_deck_workflow_state(db, deck_id)
            if not bool((workflow_state or {}).get("canOpenSmartDeck")):
                raise WorkflowConflictError(
                    code="smart_deck_not_ready",
                    message="Finish source processing before starting Smart Deck generation.",
                    recoverable=True,
                    next_action="view_processing",
                )
    else:
        workflow_state = get_deck_workflow_state(db, deck_id)
        can_open_smart_deck = bool((workflow_state or {}).get("canOpenSmartDeck"))
        if not can_open_smart_deck:
            raise WorkflowConflictError(
                code="smart_deck_not_ready",
                message="Finish source processing before starting Smart Deck generation.",
                recoverable=True,
                next_action="view_processing",
            )
    if not worker_owned_instant_release:
        try:
            get_generation_provider_config(db, deck, payload.preferredModel, strict=True, use_case="smart_deck")
        except SmartDeckProviderUnavailableError as exc:
            raise WorkflowConflictError(
                code="provider_not_configured",
                message="Connect an AI provider before generating Smart Deck previews.",
                recoverable=True,
                next_action="configure_provider",
            ) from exc

    selected_slide_ids = {
        slide_id
        for (slide_id,) in db.query(DeckSlide.id).filter(
            DeckSlide.deck_id == deck_id,
            DeckSlide.id.in_(payload.selectedSourceSlideIds),
        ).all()
    }
    if selected_slide_ids != set(payload.selectedSourceSlideIds):
        raise WorkflowConflictError(
            code="selected_slides_invalid",
            message="One or more selected source slides do not belong to this deck.",
            recoverable=True,
        )
    if payload.generationMode == "instant_deck":
        canonical_source_slide_ids = [
            slide_id
            for (slide_id,) in db.query(DeckSlide.id)
            .filter(DeckSlide.deck_id == deck_id)
            .order_by(DeckSlide.slide_index.asc(), DeckSlide.id.asc())
            .all()
        ]
        if payload.selectedSourceSlideIds != canonical_source_slide_ids:
            raise WorkflowConflictError(
                code="instant_deck_source_order_invalid",
                message="Instant Deck generation requires every source slide in canonical order.",
                recoverable=True,
            )
    if payload.activeSourceSlideId and payload.activeSourceSlideId not in set(payload.selectedSourceSlideIds):
        raise WorkflowConflictError(
            code="active_slide_invalid",
            message="The active source slide must be included in the selected source slides.",
            recoverable=True,
        )
    html_operation = None
    operation_created = False
    if payload.outputContract == "full_html_deck.v1":
        try:
            if worker_owned_instant_release:
                validate_durable_enqueue_feasibility(selected_slide_count=len(payload.selectedSourceSlideIds))
            else:
                validate_output_feasibility(selected_slide_count=len(payload.selectedSourceSlideIds))
        except InstantOperationConflict as exc:
            from app.services.llm.instant_html_operation_service import (
                INSTANT_HTML_UNAVAILABLE_REASON,
                INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE,
            )

            raise WorkflowConflictError(
                code=INSTANT_HTML_UNAVAILABLE_REASON,
                message=INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE,
                recoverable=False,
            ) from exc
        if payload.baseDesignVersionId is not None:
            latest_working = (
                db.query(DesignVersion)
                .filter(DesignVersion.deck_id == deck_id, DesignVersion.status != "discarded")
                .order_by(DesignVersion.created_at.desc())
                .first()
            )
            if latest_working is None:
                raise WorkflowConflictError(
                    code="base_design_version_invalid",
                    message="The initial Instant Deck generation must not name a missing base version.",
                    recoverable=False,
                )
            if payload.baseDesignVersionId != latest_working.id:
                raise WorkflowConflictError(
                    code="base_design_version_stale",
                    message="Follow-up Instant Deck generation must start from the latest persisted working version.",
                    recoverable=True,
                )
        try:
            html_operation, operation_created = resolve_operation(
                db,
                deck_id=deck_id,
                user_id=current_user_id,
                idempotency_key=payload.idempotencyKey,
                request_payload=normalized_input,
            )
        except ActiveInstantOperationConflict as exc:
            raise WorkflowConflictError(
                code="instant_generation_in_progress",
                message=str(exc),
                recoverable=True,
            ) from exc
        except InstantOperationConflict as exc:
            raise WorkflowConflictError(code="idempotency_key_conflict", message=str(exc), recoverable=False) from exc
    generation_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=generation_job_type,
        # Manual HTML commands remain blocked until the route confirms quota.
        # Upload-first commands are durably released to the provider-capable
        # Instant worker, which owns provider validation and paid release.
        status=(
            JOB_STATUS_QUEUED
            if html_operation is None or worker_owned_instant_release
            else JOB_STATUS_BLOCKED
        ),
        idempotency_key=payload.idempotencyKey,
        max_attempts=2,
        input_payload=normalized_input,
    )
    generation_job.max_attempts = max(int(generation_job.max_attempts or 1), 3)
    if html_operation is not None:
        # Persist the workflow job row before binding the operation FK so
        # upload-first publisher callbacks cannot reference a not-yet-present
        # workflow_jobs row under PostgreSQL FK enforcement.
        db.flush()
        html_operation.workflow_job_id = generation_job.id
        normalized_job_input = dict(generation_job.input_json or {})
        normalized_job_input["instantOperationId"] = html_operation.id
        # Application-owned policy on new commands only; old jobs retain their
        # exact historical context and never acquire a new paid research stage.
        if settings.instant_html_vc_research_enabled:
            normalized_job_input["publicResearchPolicy"] = "bounded-ai-vc-research.v2"
        if worker_owned_instant_release:
            normalized_job_input["providerReleaseOwner"] = "instant_worker"
        generation_job.input_json = normalized_job_input
    _ensure_generation_pipeline_jobs(
        db,
        deck=deck,
        generation_job=generation_job,
        idempotency_key=payload.idempotencyKey,
        current_user_id=current_user_id,
    )
    db.commit()
    summary = _map_workflow_job_summary(generation_job)
    return {
        "accepted": True,
        "jobId": generation_job.id,
        "jobType": generation_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{generation_job.id}",
        "instantOperationId": html_operation.id if html_operation is not None else None,
        "operationCreated": operation_created,
    }


def _source_readiness_publisher_for_upload(
    db: Session,
    deck: Deck,
    source_workflow_job: WorkflowJob | None,
) -> WorkflowJob:
    publisher = source_workflow_job
    if publisher is None:
        publisher = (
            db.query(WorkflowJob)
            .filter(
                WorkflowJob.deck_id == deck.id,
                WorkflowJob.job_type == JOB_TYPE_DB_PUBLISHER,
                WorkflowJob.status == JOB_STATUS_COMPLETED,
                WorkflowJob.published_phase == "smart_deck_ready",
            )
            .order_by(WorkflowJob.completed_at.desc(), WorkflowJob.created_at.desc())
            .first()
        )
    publisher_input = _coerce_mapping(publisher.input_json) if publisher is not None else {}
    if (
        publisher is None
        or publisher.deck_id != deck.id
        or publisher.job_type != JOB_TYPE_DB_PUBLISHER
        or publisher.status != JOB_STATUS_COMPLETED
        or publisher.published_phase != "smart_deck_ready"
        or str(publisher_input.get("publishTarget") or "smart_deck_ready") != "smart_deck_ready"
    ):
        raise WorkflowConflictError(
            code="smart_deck_not_ready",
            message="The upload-first Instant Deck baseline requires completed source readiness.",
            recoverable=True,
            next_action="view_processing",
        )
    return publisher


def queue_preferred_instant_deck(
    db: Session,
    deck: Deck,
    *,
    source_workflow_job: WorkflowJob | None = None,
) -> dict[str, Any] | None:
    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck.id).order_by(DeckFile.uploaded_at.desc()).first()
    metadata = deck_file.metadata_json if deck_file is not None and isinstance(deck_file.metadata_json, dict) else {}
    if metadata.get("preferredWorkspace") != "instant_deck":
        return None
    if deck_file is None or not deck.user_id:
        raise ValueError("Instant Deck generation requires an owning user and source file.")

    source_publisher = _source_readiness_publisher_for_upload(db, deck, source_workflow_job)

    source_slides = db.query(DeckSlide).filter(DeckSlide.deck_id == deck.id).order_by(
        DeckSlide.slide_index.asc(), DeckSlide.id.asc()
    ).all()
    if not source_slides:
        raise ValueError("Instant Deck generation requires extracted source slides.")

    selected_source_slide_ids = [slide.id for slide in source_slides]
    idempotency_key = f"upload-first-instant-html:{deck.id}:{deck_file.id}:{source_publisher.id}"

    # Durable publisher input is deliberately provider/runtime neutral. Preserve
    # the exact historical request hash only for a canonical upload-first replay;
    # all other idempotency mismatches remain closed in the generic queue owner.
    prompt = UPLOAD_FIRST_INSTANT_DECK_PROMPT
    user_prompt = prompt
    upload_audience = MVP_AUDIENCE
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck.id,
        job_type=JOB_TYPE_INSTANT_DECK_GENERATION,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        existing_input = dict(_coerce_mapping(existing.input_json))
        operation_id = existing_input.pop("instantOperationId", None)
        existing_input.pop("providerReleaseOwner", None)
        persisted_prompt = existing_input.get("prompt")
        persisted_user_prompt = existing_input.get("userPrompt")
        upload_audience = existing_input.get("audience")
        canonical_prompt = (
            persisted_prompt == persisted_user_prompt
            and persisted_prompt in {LEGACY_UPLOAD_FIRST_INSTANT_DECK_PROMPT, PREVIOUS_UPLOAD_FIRST_INSTANT_DECK_PROMPT, GENERAL_UPLOAD_FIRST_INSTANT_DECK_PROMPT, UPLOAD_FIRST_INSTANT_DECK_PROMPT}
        )
        if not canonical_prompt:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The upload-first idempotency key is bound to a different Instant Deck request.",
                recoverable=False,
            )
        replay_payload = WorkflowGenerationRequest(
            prompt=str(persisted_prompt or ""),
            userPrompt=str(persisted_user_prompt or ""),
            selectedSourceSlideIds=selected_source_slide_ids,
            activeSourceSlideId=source_slides[0].id,
            audience=upload_audience,
            generationMode="instant_deck",
            outputContract="full_html_deck.v1",
            idempotencyKey=idempotency_key,
        )
        operation = db.query(InstantDeckOperation).filter(
            InstantDeckOperation.id == operation_id,
            InstantDeckOperation.deck_id == deck.id,
            InstantDeckOperation.user_id == deck.user_id,
            InstantDeckOperation.idempotency_key == idempotency_key,
        ).one_or_none()
        canonical_request = existing_input == _normalized_generation_payload(replay_payload)
        canonical_operation = (
            operation is not None
            and operation.workflow_job_id == existing.id
            and operation.output_contract == "full_html_deck.v1"
            and operation.request_hash == canonical_request_hash(existing_input)
        )
        if not canonical_request or not canonical_operation:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The upload-first idempotency key is bound to a different Instant Deck request.",
                recoverable=False,
            )
        prompt = str(persisted_prompt)
        user_prompt = str(persisted_user_prompt)

    return queue_smart_deck_generation(
        db,
        deck.id,
        current_user_id=deck.user_id,
        payload=WorkflowGenerationRequest(
            prompt=prompt,
            userPrompt=user_prompt,
            selectedSourceSlideIds=selected_source_slide_ids,
            activeSourceSlideId=source_slides[0].id,
            audience=upload_audience,
            generationMode="instant_deck",
            outputContract="full_html_deck.v1",
            idempotencyKey=idempotency_key,
        ),
        defer_instant_provider_release=True,
        source_readiness_job=source_publisher,
    )


def enqueue_upload_first_instant_html_baseline(
    db: Session,
    deck: Deck,
    *,
    source_workflow_job: WorkflowJob,
) -> dict[str, Any] | None:
    """Durably release one upload-bound HTML job to its provider-capable worker."""
    accepted = queue_preferred_instant_deck(db, deck, source_workflow_job=source_workflow_job)
    if accepted is None:
        return None
    operation_id = str(accepted.get("instantOperationId") or "").strip()
    workflow_job_id = str(accepted.get("jobId") or "").strip()
    if not operation_id or not workflow_job_id:
        raise ValueError("Upload-first Instant HTML generation did not create a durable operation.")
    operation = db.query(InstantDeckOperation).filter(InstantDeckOperation.id == operation_id).one()
    workflow_job = db.query(WorkflowJob).filter(WorkflowJob.id == workflow_job_id).one()
    resumable_operation_states = {"enqueue_pending", "charge_reconciling", "queued"}
    if operation.status not in resumable_operation_states:
        summary = _map_workflow_job_summary(workflow_job)
        return {
            **accepted,
            "status": summary["status"],
            "phase": summary["phase"],
            "instantOperationStatus": operation.status,
        }
    summary = _map_workflow_job_summary(workflow_job)
    return {
        **accepted,
        "status": summary["status"],
        "phase": summary["phase"],
        "instantOperationStatus": operation.status,
    }


def queue_failed_slide_generation_retry(
    db: Session,
    deck_id: str,
    *,
    current_user_id: str,
    payload: WorkflowFailedSlideRetryRequest,
) -> dict[str, Any]:
    """Queue a linked retry derived exclusively from persisted failed slides."""
    prior_job = (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.id == payload.priorGenerationJobId,
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.job_type.in_([JOB_TYPE_LLM_GENERATION, JOB_TYPE_INSTANT_DECK_GENERATION]),
        )
        .one_or_none()
    )
    if prior_job is None:
        raise WorkflowConflictError(
            code="prior_generation_not_found",
            message="The prior Smart Deck generation could not be found for this deck.",
            recoverable=False,
        )
    if prior_job.job_type == JOB_TYPE_INSTANT_DECK_GENERATION and (prior_job.input_json or {}).get('outputContract') == 'full_html_deck.v1':
        from app.services.llm.instant_factual_review import queue_saved_review_resume, FactualReviewRequired
        try:
            resumed = queue_saved_review_resume(db, deck_id, current_user_id=current_user_id, workflow_job=prior_job)
        except FactualReviewRequired as exc:
            raise WorkflowConflictError(code='saved_review_resume_unavailable', message=str(exc), recoverable=False) from None
        summary = _map_workflow_job_summary(resumed)
        return {'accepted': True, 'jobId': resumed.id, 'jobType': resumed.job_type,
                'status': summary['status'], 'phase': summary['phase'],
                'workflowStateUrl': f'/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state',
                'jobUrl': f'/api/workflow-jobs/{resumed.id}'}
    persisted_generation = (
        db.query(GenerationJob)
        .filter(GenerationJob.id == prior_job.id, GenerationJob.deck_id == deck_id)
        .one_or_none()
    )
    result = persisted_generation.result_json if persisted_generation and isinstance(persisted_generation.result_json, dict) else None
    failed_slide_ids = list(result.get("failedSlideIds") or []) if result else []
    if not result or result.get("coverageComplete") is not False or not failed_slide_ids:
        raise WorkflowConflictError(
            code="failed_slide_retry_not_available",
            message="The prior generation has no persisted failed slides to retry.",
            recoverable=False,
        )
    prior_input = _coerce_mapping(prior_job.input_json)
    prior_requested = list(result.get("requestedSlideIds") or [])
    prior_completed = set(result.get("completedSlideIds") or [])
    failed_set = set(failed_slide_ids)
    if (
        len(failed_set) != len(failed_slide_ids)
        or failed_set & prior_completed
        or set(prior_requested) != prior_completed | failed_set
    ):
        raise WorkflowConflictError(
            code="failed_slide_retry_coverage_invalid",
            message="The persisted generation coverage is invalid and cannot be retried automatically.",
            recoverable=False,
        )
    retry_input = {
        **prior_input,
        "selectedSourceSlideIds": failed_slide_ids,
        "activeSourceSlideId": failed_slide_ids[0],
        "retryOfGenerationJobId": prior_job.id,
    }
    linked_key = f"failed-slide-retry:{prior_job.id}:{payload.idempotencyKey}"
    retry_job_type = prior_job.job_type
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=retry_job_type,
        idempotency_key=linked_key,
    )
    if existing is not None:
        if _coerce_mapping(existing.input_json) != retry_input:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The retry idempotency key is already bound to a different command.",
                recoverable=False,
            )
        summary = _map_workflow_job_summary(existing)
        return {
            "accepted": True,
            "jobId": existing.id,
            "jobType": existing.job_type,
            "status": summary["status"],
            "phase": summary["phase"],
            "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
            "jobUrl": f"/api/workflow-jobs/{existing.id}",
        }
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")
    retry_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=retry_job_type,
        status=JOB_STATUS_QUEUED,
        idempotency_key=linked_key,
        max_attempts=2,
        input_payload=retry_input,
    )
    _ensure_generation_pipeline_jobs(
        db,
        deck=deck,
        generation_job=retry_job,
        idempotency_key=linked_key,
        current_user_id=current_user_id,
    )
    db.commit()
    summary = _map_workflow_job_summary(retry_job)
    return {
        "accepted": True,
        "jobId": retry_job.id,
        "jobType": retry_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{retry_job.id}",
    }


def queue_apply_design_version(db: Session, deck_id: str, *, current_user_id: str, payload: WorkflowApplyRequest) -> dict[str, Any]:
    from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state

    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")
    workflow_state = get_deck_workflow_state(db, deck_id)
    current_phase = str((workflow_state or {}).get("phase") or "")
    if current_phase not in {"preview_ready", "applied", "export_ready"}:
        raise WorkflowConflictError(
            code="preview_not_ready",
            message="Generate a preview before applying a design version.",
            recoverable=True,
            next_action="open_preview",
        )
    version = db.query(DesignVersion).filter(DesignVersion.deck_id == deck_id, DesignVersion.id == payload.designVersionId).one_or_none()
    if version is None:
        raise ValueError("Design version not found")
    if generation_job_is_instant_deck(version.generation_job):
        try:
            require_publishable_instant_design_version(version)
        except GenerationValidationError as exc:
            raise WorkflowConflictError(
                code="instant_deck_not_publishable",
                message="Regenerate this Instant Deck with complete LLM-grounded slides before applying.",
                recoverable=True,
                next_action="regenerate_instant_deck",
            ) from exc

    normalized_input = _normalized_apply_payload(payload)
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=JOB_TYPE_APPLY_VERSION,
        idempotency_key=payload.idempotencyKey,
    )
    if existing is not None:
        if _coerce_mapping(existing.input_json) != normalized_input:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The idempotency key is already bound to a different apply-design-version request.",
                recoverable=False,
            )
        summary = _map_workflow_job_summary(existing)
        return {
            "accepted": True,
            "jobId": existing.id,
            "jobType": existing.job_type,
            "status": summary["status"],
            "phase": summary["phase"],
            "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
            "jobUrl": f"/api/workflow-jobs/{existing.id}",
        }

    apply_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_APPLY_VERSION,
        status=JOB_STATUS_QUEUED,
        idempotency_key=payload.idempotencyKey,
        max_attempts=1,
        input_payload=normalized_input,
    )
    publisher_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_DB_PUBLISHER,
        status=JOB_STATUS_QUEUED,
        idempotency_key=f"{payload.idempotencyKey}:publisher",
        max_attempts=1,
        input_payload={
            "publishTarget": "applied",
            "applyWorkflowJobId": apply_job.id,
            "requestedByUserId": current_user_id,
            "designVersionId": payload.designVersionId,
        },
    )
    ensure_workflow_dependency(db, job=publisher_job, depends_on_job=apply_job)
    db.commit()
    summary = _map_workflow_job_summary(apply_job)
    return {
        "accepted": True,
        "jobId": apply_job.id,
        "jobType": apply_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{apply_job.id}",
    }


def queue_export(db: Session, deck_id: str, *, current_user_id: str, payload: WorkflowExportRequest) -> dict[str, Any]:
    from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state

    if payload.normalized_type == PROVISIONAL_HTML_EXPORT_TYPE and (payload.format != "html" or not payload.designVersionId):
        raise ValueError("provisional_html export requires format=html and designVersionId.")
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")
    normalized_input = _normalized_export_payload(payload)
    if payload.format == "html":
        try:
            version = resolve_html_export_design_version(
                db,
                deck,
                payload.designVersionId or "",
                export_type=normalized_input["exportType"],
                validate_assets=True,
            )
        except CompiledArtifactRegenerationRequired as exc:
            raise WorkflowConflictError(
                code=exc.code,
                message=exc.message,
                recoverable=True,
                next_action="regenerate",
            ) from exc
        normalized_input["designVersionId"] = version.id
    else:
        _require_complete_generation_coverage_for_export(db, deck_id)
    workflow_state = get_deck_workflow_state(db, deck_id)
    current_phase = str((workflow_state or {}).get("phase") or "")
    if current_phase not in {"preview_ready", "applied", "export_ready"}:
        raise WorkflowConflictError(
            code="export_not_ready",
            message="Generate or apply a design version before exporting.",
            recoverable=True,
            next_action="open_preview",
        )
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=JOB_TYPE_EXPORT,
        idempotency_key=payload.idempotencyKey,
    )
    if existing is not None:
        if _coerce_mapping(existing.input_json) != normalized_input:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The idempotency key is already bound to a different export request.",
                recoverable=False,
            )
        publisher_job = ensure_workflow_job(
            db,
            deck=deck,
            job_type=JOB_TYPE_DB_PUBLISHER,
            status=JOB_STATUS_QUEUED,
            idempotency_key=f"{payload.idempotencyKey}:publisher",
            max_attempts=1,
            input_payload={
                "publishTarget": "export_ready",
                "exportWorkflowJobId": existing.id,
                "requestedByUserId": current_user_id,
                "exportType": normalized_input["exportType"],
                **(
                    {
                        "designVersionId": normalized_input["designVersionId"],
                        "format": normalized_input["format"],
                    }
                    if normalized_input.get("format") == "html"
                    else {}
                ),
            },
        )
        ensure_workflow_dependency(db, job=publisher_job, depends_on_job=existing)
        summary = _map_workflow_job_summary(existing)
        return {
            "accepted": True,
            "jobId": existing.id,
            "jobType": existing.job_type,
            "status": summary["status"],
            "phase": summary["phase"],
            "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
            "jobUrl": f"/api/workflow-jobs/{existing.id}",
        }

    export_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_EXPORT,
        status=JOB_STATUS_QUEUED,
        idempotency_key=payload.idempotencyKey,
        max_attempts=1,
        input_payload=normalized_input,
    )
    export_job.user_id = current_user_id
    publisher_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_DB_PUBLISHER,
        status=JOB_STATUS_QUEUED,
        idempotency_key=f"{payload.idempotencyKey}:publisher",
        max_attempts=1,
        input_payload={
            "publishTarget": "export_ready",
            "exportWorkflowJobId": export_job.id,
            "requestedByUserId": current_user_id,
            "exportType": normalized_input["exportType"],
            **(
                {
                    "designVersionId": normalized_input["designVersionId"],
                    "format": normalized_input["format"],
                }
                if normalized_input.get("format") == "html"
                else {}
            ),
        },
    )
    ensure_workflow_dependency(db, job=publisher_job, depends_on_job=export_job)
    db.commit()
    summary = _map_workflow_job_summary(export_job)
    return {
        "accepted": True,
        "jobId": export_job.id,
        "jobType": export_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{export_job.id}",
    }


def queue_compile_final_deck(db: Session, deck_id: str, *, current_user_id: str, payload: PrepareFullDeckRequest) -> dict[str, Any]:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")

    batch_id = str(payload.batchId or "").strip()
    if not batch_id:
        raise ValueError("batchId is required")

    batch = db.query(DesignBatch).filter(DesignBatch.deck_id == deck_id, DesignBatch.id == batch_id).one_or_none()
    if batch is None:
        raise ValueError("Deck or batch not found")

    normalized_input = _normalized_compile_final_payload(payload, batch_id=batch.id)
    idempotency_key = ":".join(
        [
            deck_id,
            batch.id,
            str(normalized_input.get("latestSlideVersionId") or "latest"),
            str(normalized_input.get("title") or "untitled"),
            JOB_TYPE_COMPILE_FINAL_DECK,
        ]
    )
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=JOB_TYPE_COMPILE_FINAL_DECK,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        summary = _map_workflow_job_summary(existing)
        return {
            "accepted": True,
            "jobId": existing.id,
            "jobType": existing.job_type,
            "status": summary["status"],
            "phase": summary["phase"],
            "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
            "jobUrl": f"/api/workflow-jobs/{existing.id}",
        }

    compile_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_COMPILE_FINAL_DECK,
        status=JOB_STATUS_QUEUED,
        idempotency_key=idempotency_key,
        max_attempts=1,
        input_payload={
            **normalized_input,
            "requestedByUserId": current_user_id,
        },
    )
    db.commit()
    summary = _map_workflow_job_summary(compile_job)
    return {
        "accepted": True,
        "jobId": compile_job.id,
        "jobType": compile_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{compile_job.id}",
    }


def queue_selected_slide_generation(
    db: Session,
    deck_id: str,
    *,
    current_user_id: str,
    payload: WorkflowSelectedSlideGenerationRequest,
) -> dict[str, Any]:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")

    smart_deck_context_job = (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.job_type == JOB_TYPE_SMART_DECK_CONTEXT,
            WorkflowJob.status == JOB_STATUS_COMPLETED,
        )
        .order_by(WorkflowJob.completed_at.desc(), WorkflowJob.created_at.desc())
        .first()
    )
    if smart_deck_context_job is None:
        raise WorkflowConflictError(
            code="smart_deck_context_not_ready",
            message="Selected-slide analysis requires completed Smart Deck context.",
            recoverable=True,
            next_action="Wait for Smart Deck processing to finish, then retry the analysis.",
        )

    normalized_input = _normalized_selected_slide_generation_payload(payload)
    build_selected_slide_batches(
        db,
        deck=deck,
        selected_source_slide_ids=normalized_input["selectedSourceSlideIds"],
        prompt=normalized_input["prompt"],
        partition_count=normalized_input["partitionCount"],
        batch_size=normalized_input["batchSize"],
    )
    existing = get_workflow_job_by_idempotency_key(
        db,
        deck_id=deck_id,
        job_type=JOB_TYPE_SELECTED_SLIDE_GENERATION,
        idempotency_key=payload.idempotencyKey,
    )
    if existing is not None:
        if _coerce_mapping(existing.input_json) != normalized_input:
            raise WorkflowConflictError(
                code="idempotency_key_conflict",
                message="The idempotency key is already bound to a different selected-slide generation request.",
                recoverable=False,
            )
        summary = _map_workflow_job_summary(existing)
        return {
            "accepted": True,
            "jobId": existing.id,
            "jobType": existing.job_type,
            "status": summary["status"],
            "phase": summary["phase"],
            "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
            "jobUrl": f"/api/workflow-jobs/{existing.id}",
        }

    generation_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_SELECTED_SLIDE_GENERATION,
        status=JOB_STATUS_QUEUED,
        idempotency_key=payload.idempotencyKey,
        max_attempts=1,
        input_payload={
            **normalized_input,
            "requestedByUserId": current_user_id,
        },
    )
    db.commit()
    summary = _map_workflow_job_summary(generation_job)
    return {
        "accepted": True,
        "jobId": generation_job.id,
        "jobType": generation_job.job_type,
        "status": summary["status"],
        "phase": summary["phase"],
        "workflowStateUrl": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "jobUrl": f"/api/workflow-jobs/{generation_job.id}",
    }
