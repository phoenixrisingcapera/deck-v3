"""Workflow job contract for Upload -> Smart Deck.

Owns: job type constants, source-pipeline ordering, dependency wiring,
idempotency keys, status transitions, and publisher-only final phase rules.
Must not own: worker business logic, PDF/preview processing, or frontend-facing
workflow-state presentation.
Stage: pipeline contract and orchestration primitives.
Status: KEEP
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckExtractionRun, DeckFile, WorkflowJob, WorkflowJobArtifact, WorkflowJobDependency, WorkflowJobEvent

JOB_TYPE_SOURCE_INGESTION = "source_ingestion"
JOB_TYPE_SOURCE_EXTRACTION = "source_extraction"
JOB_TYPE_MINIATURES = "miniatures"
JOB_TYPE_BRAND_EXTRACTION = "brand_extraction"
JOB_TYPE_SMART_DECK_CONTEXT = "smart_deck_context"
JOB_TYPE_DB_PUBLISHER = "db_publisher"
JOB_TYPE_LLM_GENERATION = "llm_generation"
JOB_TYPE_INSTANT_DECK_GENERATION = "instant_deck_generation"
JOB_TYPE_SELECTED_SLIDE_GENERATION = "selected_slide_generation"
JOB_TYPE_SCHEMA_VALIDATION = "schema_validation"
JOB_TYPE_PREVIEW_RENDER = "preview_render"
JOB_TYPE_APPLY_VERSION = "apply_version"
JOB_TYPE_COMPILE_FINAL_DECK = "compile_final_deck"
JOB_TYPE_EXPORT = "export"
JOB_TYPE_DUE_DILIGENCE = "due_diligence"
JOB_TYPE_MEDIA_PROCESSING = "media_processing"
JOB_TYPE_DECK_MAP_ANALYSIS = "deck_map_analysis"
JOB_TYPE_MARKET_RESEARCH = "market_research"
JOB_TYPE_SMART_EDIT = "smart_edit"

SOURCE_PIPELINE_JOB_SEQUENCE = [
    JOB_TYPE_SOURCE_INGESTION,
    JOB_TYPE_SOURCE_EXTRACTION,
    JOB_TYPE_MINIATURES,
    JOB_TYPE_SMART_DECK_CONTEXT,
    JOB_TYPE_DB_PUBLISHER,
    JOB_TYPE_BRAND_EXTRACTION,
]
"""Canonical source pipeline order.

Brand extraction intentionally remains a separate working stage. Smart Deck
context depends on extracted slides/miniatures, then db_publisher marks the deck
openable; brand extraction enriches visual constraints without blocking the core
source workspace unless future requirements make it mandatory.
"""

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED_RETRYABLE = "failed_retryable"
JOB_STATUS_FAILED_FINAL = "failed_final"
JOB_STATUS_BLOCKED = "blocked"
JOB_STATUS_TIMED_OUT = "timed_out"

CLAIMABLE_JOB_STATUSES = {
    JOB_STATUS_QUEUED,
    JOB_STATUS_FAILED_RETRYABLE,
}

TERMINAL_JOB_STATUSES = {
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_BLOCKED,
    JOB_STATUS_TIMED_OUT,
}

PUBLISHABLE_WORKFLOW_PHASES = {
    "ai_vc_understanding",
    "ai_vc_research",
    "ai_vc_analysis",
    "visual_direction",
    "visual_asset_planning",
    "narrative_reconstruction",
    "smart_deck_ready",
    "preview_ready",
    "applied",
    "export_ready",
}

PREVIEW_PUBLISHER_SUPERSEDED_TERMINAL_REASON = "preview_publisher_superseded"
PUBLISHER_DISPOSITION_SUPERSEDED_NOOP = "superseded_noop"


def workflow_job_is_superseded_publisher_noop(job: WorkflowJob) -> bool:
    """Return whether a completed publisher explicitly performed no publication."""
    if job.job_type != JOB_TYPE_DB_PUBLISHER:
        return False
    output = job.output_json if isinstance(job.output_json, dict) else {}
    return bool(
        getattr(job, "terminal_reason", None) == PREVIEW_PUBLISHER_SUPERSEDED_TERMINAL_REASON
        or output.get("publisherDisposition") == PUBLISHER_DISPOSITION_SUPERSEDED_NOOP
        or output.get("superseded") is True
    )


def _now() -> datetime:
    return datetime.utcnow()


def build_workflow_job_idempotency_key(
    *,
    deck_id: str,
    source_checksum: str | None,
    job_type: str,
    extraction_run_id: str | None = None,
) -> str:
    parts = [deck_id, source_checksum or "no-checksum", job_type]
    if extraction_run_id:
        parts.append(extraction_run_id)
    return ":".join(parts)


def _append_event(
    db: Session,
    *,
    job: WorkflowJob,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    message: str | None,
    metadata: dict | None = None,
) -> WorkflowJobEvent:
    event = WorkflowJobEvent(
        id=generate_id("wje"),
        job_id=job.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        message=message,
        metadata_json=metadata,
    )
    db.add(event)
    return event


def workflow_job_phase(job_type: str, status: str, *, output_payload: dict | None = None) -> str:
    """Translate job type/status into the frontend-visible workflow phase."""
    if status == JOB_STATUS_FAILED_RETRYABLE:
        return "failed_retryable"
    if status in {JOB_STATUS_FAILED_FINAL, JOB_STATUS_TIMED_OUT}:
        return "failed_final"
    if status == JOB_STATUS_BLOCKED:
        return "needs_manual_review"

    output_payload = output_payload if isinstance(output_payload, dict) else {}
    internal_phase_aliases = {
        "generating_slides": "generation_running",
        "saving_design_version": "schema_validation_queued",
    }
    published_phase = output_payload.get("publishedPhase")
    if isinstance(published_phase, str) and published_phase.strip():
        # DISABLED: return published_phase.strip() allowed persisted internal stages to break the public schema.
        return internal_phase_aliases.get(published_phase.strip(), published_phase.strip())
    published_phase = output_payload.get("phase")
    if isinstance(published_phase, str) and published_phase.strip():
        # DISABLED: return published_phase.strip() allowed persisted internal stages to break the public schema.
        return internal_phase_aliases.get(published_phase.strip(), published_phase.strip())
    if job_type == JOB_TYPE_SOURCE_INGESTION:
        if status == JOB_STATUS_QUEUED:
            return "source_ingestion_queued"
        if status == JOB_STATUS_RUNNING:
            return "source_ingestion_running"
        return "source_file_saved"
    if job_type == JOB_TYPE_SOURCE_EXTRACTION:
        if status == JOB_STATUS_QUEUED:
            return "source_extraction_queued"
        if status == JOB_STATUS_RUNNING:
            return "source_extraction_running"
        return "source_ready"
    if job_type == JOB_TYPE_MINIATURES:
        if status == JOB_STATUS_QUEUED:
            return "miniatures_queued"
        if status == JOB_STATUS_RUNNING:
            return "miniatures_running"
        return "source_ready"
    if job_type == JOB_TYPE_BRAND_EXTRACTION:
        if status == JOB_STATUS_QUEUED:
            return "brand_extraction_queued"
        if status == JOB_STATUS_RUNNING:
            return "brand_extraction_running"
        return "source_ready"
    if job_type == JOB_TYPE_SMART_DECK_CONTEXT:
        if status == JOB_STATUS_QUEUED:
            return "smart_deck_context_queued"
        if status == JOB_STATUS_RUNNING:
            return "smart_deck_context_running"
        return "source_ready"
    if job_type == JOB_TYPE_LLM_GENERATION:
        if status == JOB_STATUS_QUEUED:
            return "generation_queued"
        if status == JOB_STATUS_RUNNING:
            return "generation_running"
        return "preview_ready"
    if job_type == JOB_TYPE_INSTANT_DECK_GENERATION:
        if status == JOB_STATUS_QUEUED:
            return "generation_queued"
        if status == JOB_STATUS_RUNNING:
            return "generation_running"
        return "preview_ready"
    if job_type == JOB_TYPE_SELECTED_SLIDE_GENERATION:
        if status == JOB_STATUS_QUEUED:
            return "selected_slide_generation_queued"
        if status == JOB_STATUS_RUNNING:
            return "selected_slide_generation_running"
        return "selected_slide_generation_ready"
    if job_type == JOB_TYPE_SCHEMA_VALIDATION:
        if status == JOB_STATUS_QUEUED:
            return "schema_validation_queued"
        if status == JOB_STATUS_RUNNING:
            return "schema_validation_running"
        return "preview_ready"
    if job_type == JOB_TYPE_PREVIEW_RENDER:
        if status == JOB_STATUS_QUEUED:
            return "preview_render_queued"
        if status == JOB_STATUS_RUNNING:
            return "preview_render_running"
        return "preview_ready"
    if job_type == JOB_TYPE_APPLY_VERSION:
        if status == JOB_STATUS_QUEUED:
            return "apply_queued"
        if status == JOB_STATUS_RUNNING:
            return "apply_running"
        return "applied"
    if job_type == JOB_TYPE_COMPILE_FINAL_DECK:
        if status == JOB_STATUS_QUEUED:
            return "compile_final_queued"
        if status == JOB_STATUS_RUNNING:
            return "compile_final_running"
        # Final compilation publishes a concrete compiled deck instead of a
        # preview/apply/export state, so it gets its own ready phase token.
        return "compiled_deck_ready"
    if job_type == JOB_TYPE_EXPORT:
        if status == JOB_STATUS_QUEUED:
            return "export_queued"
        if status == JOB_STATUS_RUNNING:
            return "export_running"
        return "export_ready"
    if job_type == JOB_TYPE_DUE_DILIGENCE:
        if status == JOB_STATUS_QUEUED:
            return "due_diligence_queued"
        if status == JOB_STATUS_RUNNING:
            return "due_diligence_running"
        return "due_diligence_ready"
    if job_type == JOB_TYPE_MEDIA_PROCESSING:
        if status == JOB_STATUS_QUEUED:
            return "media_processing_queued"
        if status == JOB_STATUS_RUNNING:
            return "media_processing_running"
        return "media_ready"
    if job_type == JOB_TYPE_DECK_MAP_ANALYSIS:
        if status == JOB_STATUS_QUEUED:
            return "deck_map_analysis_queued"
        if status == JOB_STATUS_RUNNING:
            return "deck_map_analysis_running"
        return "deck_map_analysis_ready"
    if job_type == JOB_TYPE_MARKET_RESEARCH:
        if status == JOB_STATUS_QUEUED:
            return "market_research_queued"
        if status == JOB_STATUS_RUNNING:
            return "market_research_running"
        return "market_research_ready"
    if job_type == JOB_TYPE_SMART_EDIT:
        if status == JOB_STATUS_QUEUED:
            return "smart_edit_queued"
        if status == JOB_STATUS_RUNNING:
            return "smart_edit_running"
        return "smart_edit_ready"
    if job_type == JOB_TYPE_DB_PUBLISHER and status == JOB_STATUS_RUNNING:
        target = output_payload.get("publishTarget") or output_payload.get("requestedPhase") or "smart_deck_ready"
        return str(target)

    return "upload_accepted"


def workflow_job_progress(status: str) -> int:
    if status == JOB_STATUS_QUEUED:
        return 0
    if status == JOB_STATUS_RUNNING:
        return 45
    if status == JOB_STATUS_FAILED_RETRYABLE:
        return 65
    return 100


def ensure_workflow_job(
    db: Session,
    *,
    deck: Deck,
    job_type: str,
    status: str = JOB_STATUS_QUEUED,
    extraction_run: DeckExtractionRun | None = None,
    idempotency_key: str | None = None,
    priority: int = 50,
    max_attempts: int = 2,
    input_payload: dict | None = None,
) -> WorkflowJob:
    query = db.query(WorkflowJob).filter(
        WorkflowJob.deck_id == deck.id,
        WorkflowJob.job_type == job_type,
    )
    if extraction_run is not None:
        query = query.filter(WorkflowJob.extraction_run_id == extraction_run.id)
    if idempotency_key is not None:
        query = query.filter(WorkflowJob.idempotency_key == idempotency_key)
    job = query.order_by(WorkflowJob.created_at.desc()).first()
    if job is not None:
        if job.workspace_id is None:
            job.workspace_id = deck.workspace_id
        if job.user_id is None:
            job.user_id = deck.user_id
        if extraction_run is not None and job.extraction_run_id is None:
            job.extraction_run_id = extraction_run.id
        if input_payload:
            merged = dict(job.input_json or {})
            merged.update(input_payload)
            job.input_json = merged
        return job

    now_dt = _now()
    job = WorkflowJob(
        id=generate_id("job"),
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        user_id=deck.user_id,
        extraction_run_id=extraction_run.id if extraction_run is not None else None,
        job_type=job_type,
        status=status,
        priority=priority,
        idempotency_key=idempotency_key,
        input_json=input_payload,
        attempt_count=0,
        max_attempts=max_attempts,
        recovery_count=0,
        queued_at=now_dt if status == JOB_STATUS_QUEUED else None,
        heartbeat_at=now_dt if status in {JOB_STATUS_QUEUED, JOB_STATUS_RUNNING} else None,
    )
    db.add(job)
    _append_event(
        db,
        job=job,
        event_type="created",
        from_status=None,
        to_status=status,
        message=f"{job_type} job created.",
        metadata={"idempotencyKey": idempotency_key},
    )
    return job


def ensure_workflow_dependency(
    db: Session,
    *,
    job: WorkflowJob,
    depends_on_job: WorkflowJob,
    dependency_type: str = "requires_completion",
) -> WorkflowJobDependency:
    existing = (
        db.query(WorkflowJobDependency)
        .filter(
            WorkflowJobDependency.job_id == job.id,
            WorkflowJobDependency.depends_on_job_id == depends_on_job.id,
            WorkflowJobDependency.dependency_type == dependency_type,
        )
        .one_or_none()
    )
    if existing is not None:
        return existing
    dependency = WorkflowJobDependency(
        id=generate_id("wjd"),
        job_id=job.id,
        depends_on_job_id=depends_on_job.id,
        dependency_type=dependency_type,
    )
    db.add(dependency)
    return dependency


def set_workflow_job_status(
    db: Session,
    *,
    job: WorkflowJob,
    status: str,
    worker_id: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    output_payload: dict | None = None,
    terminal_reason: str | None = None,
    published_phase: str | None = None,
    heartbeat_only: bool = False,
) -> WorkflowJob:
    now_dt = _now()
    previous_status = job.status

    if published_phase:
        if job.job_type != JOB_TYPE_DB_PUBLISHER:
            raise ValueError("Only db_publisher jobs may publish final workflow phases.")
        if status != JOB_STATUS_COMPLETED:
            raise ValueError("published_phase can only be recorded when a workflow job completes.")
        if published_phase not in PUBLISHABLE_WORKFLOW_PHASES:
            raise ValueError(f"Unsupported published workflow phase: {published_phase}")

    if heartbeat_only:
        job.heartbeat_at = now_dt
        if worker_id:
            job.locked_by = worker_id
            job.locked_until = now_dt + timedelta(minutes=15)
        return job

    job.status = status
    job.updated_at = now_dt
    job.heartbeat_at = now_dt

    if status == JOB_STATUS_QUEUED:
        job.queued_at = now_dt
        job.started_at = None
        job.completed_at = None
        job.failed_at = None
        job.terminal_reason = None
        job.published_phase = None
        job.published_at = None
        job.locked_by = None
        job.locked_until = None
    elif status == JOB_STATUS_RUNNING:
        job.started_at = job.started_at or now_dt
        if previous_status != JOB_STATUS_RUNNING:
            job.attempt_count = int(job.attempt_count or 0) + 1
        job.terminal_reason = None
        job.published_phase = None
        job.published_at = None
        job.locked_by = worker_id
        job.locked_until = now_dt + timedelta(minutes=15)
        job.failed_at = None
        job.completed_at = None
    elif status == JOB_STATUS_COMPLETED:
        job.completed_at = now_dt
        job.failed_at = None
        job.error_code = None
        job.error_message = None
        job.terminal_reason = terminal_reason
        job.locked_until = None
        if published_phase:
            job.published_phase = published_phase
            job.published_at = now_dt
    elif status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_BLOCKED, JOB_STATUS_TIMED_OUT}:
        job.failed_at = now_dt
        job.error_code = error_code
        job.error_message = error_message or message
        job.terminal_reason = terminal_reason or error_code
        job.published_phase = None
        job.published_at = None
        job.locked_until = None

    if worker_id:
        job.locked_by = worker_id
    if output_payload is not None:
        merged = dict(job.output_json or {})
        if published_phase:
            merged["publishedPhase"] = published_phase
        merged.update(output_payload)
        job.output_json = merged

    _append_event(
        db,
        job=job,
        event_type=status,
        from_status=previous_status,
        to_status=status,
        message=message,
        metadata={"workerId": worker_id, "errorCode": error_code, "terminalReason": terminal_reason, "publishedPhase": published_phase},
    )
    return job


def record_workflow_artifact(
    db: Session,
    *,
    job: WorkflowJob,
    artifact_type: str,
    storage_key: str,
    content_hash: str | None = None,
    metadata: dict | None = None,
) -> WorkflowJobArtifact:
    existing = (
        db.query(WorkflowJobArtifact)
        .filter(
            WorkflowJobArtifact.job_id == job.id,
            WorkflowJobArtifact.artifact_type == artifact_type,
            WorkflowJobArtifact.storage_key == storage_key,
        )
        .one_or_none()
    )
    if existing is not None:
        existing.content_hash = content_hash or existing.content_hash
        if metadata:
            merged = dict(existing.metadata_json or {})
            merged.update(metadata)
            existing.metadata_json = merged
        return existing

    artifact = WorkflowJobArtifact(
        id=generate_id("wja"),
        job_id=job.id,
        deck_id=job.deck_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        content_hash=content_hash,
        metadata_json=metadata,
    )
    db.add(artifact)
    return artifact


def source_pipeline_stage_order(*, instant_upload: bool) -> tuple[str, ...]:
    """Return the exact source stages created for the selected product path."""
    return (
        JOB_TYPE_SOURCE_EXTRACTION,
        *(() if instant_upload else (JOB_TYPE_MINIATURES,)),
        *(() if instant_upload else (JOB_TYPE_SMART_DECK_CONTEXT,)),
        JOB_TYPE_DB_PUBLISHER,
        JOB_TYPE_BRAND_EXTRACTION,
    )


def ensure_pipeline_jobs_for_run(
    db: Session,
    *,
    deck: Deck,
    run: DeckExtractionRun,
    source_checksum: str | None,
    max_attempts: int,
) -> dict[str, WorkflowJob]:
    """Create or reuse all source-pipeline jobs and wire their dependencies."""
    jobs: dict[str, WorkflowJob] = {}
    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck.id).order_by(DeckFile.uploaded_at.desc()).first()
    deck_file_metadata = deck_file.metadata_json if deck_file is not None and isinstance(deck_file.metadata_json, dict) else {}
    instant_upload = deck_file_metadata.get("preferredWorkspace") == "instant_deck"
    # Instant Deck consumes canonical extracted source directly. Do not create
    # the legacy source_v1 Smart Deck workspace/enrichment job for that path.
    # Keep the legacy stage isolated for non-Instant callers until their router
    # surface is removed separately.
    stage_order = source_pipeline_stage_order(instant_upload=instant_upload)
    ingestion_payload = {
        "deckId": deck.id,
        "sourceChecksum": source_checksum,
        "processingRunId": run.id,
        "sourceFileId": run.source_file_id,
    }
    ingestion_job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_SOURCE_INGESTION,
        status=JOB_STATUS_QUEUED,
        max_attempts=1,
        idempotency_key=build_workflow_job_idempotency_key(
            deck_id=deck.id,
            source_checksum=source_checksum,
            job_type=JOB_TYPE_SOURCE_INGESTION,
        ),
        input_payload=ingestion_payload,
    )
    if run.id and ingestion_job.extraction_run_id is None:
        ingestion_job.extraction_run_id = run.id
    merged_output = dict(ingestion_job.output_json or {})
    merged_output.update(
        {
            "sourceFileId": run.source_file_id,
            "sourceChecksum": source_checksum,
            "processingRunId": run.id,
        }
    )
    ingestion_job.output_json = merged_output
    jobs[JOB_TYPE_SOURCE_INGESTION] = ingestion_job

    previous_job: WorkflowJob | None = ingestion_job
    publisher_job: WorkflowJob | None = None
    for job_type in stage_order:
        input_payload = {
            "deckId": deck.id,
            "sourceChecksum": source_checksum,
            "processingRunId": run.id,
        }
        if job_type == JOB_TYPE_DB_PUBLISHER:
            input_payload["publishTarget"] = "smart_deck_ready"
        priority = 50
        if job_type == JOB_TYPE_SMART_DECK_CONTEXT:
            priority = 70
        elif job_type == JOB_TYPE_DB_PUBLISHER:
            priority = 80
        elif job_type == JOB_TYPE_BRAND_EXTRACTION:
            priority = 30
        job = ensure_workflow_job(
            db,
            deck=deck,
            job_type=job_type,
            status=JOB_STATUS_QUEUED,
            priority=priority,
            max_attempts=max_attempts,
            idempotency_key=build_workflow_job_idempotency_key(
                deck_id=deck.id,
                source_checksum=source_checksum,
                job_type=job_type,
            ),
            input_payload=input_payload,
        )
        if run.id and job.extraction_run_id is None:
            job.extraction_run_id = run.id
        jobs[job_type] = job
        dependency_source = publisher_job if job_type == JOB_TYPE_BRAND_EXTRACTION else previous_job
        if instant_upload and job_type == JOB_TYPE_DB_PUBLISHER:
            dependency_source = jobs[JOB_TYPE_SOURCE_EXTRACTION]
            # Reusing a pre-change run must not retain its old thumbnail gate.
            obsolete_ids = db.query(WorkflowJob.id).filter(
                WorkflowJob.deck_id == deck.id,
                WorkflowJob.extraction_run_id == run.id,
                WorkflowJob.job_type.in_([JOB_TYPE_MINIATURES, JOB_TYPE_SMART_DECK_CONTEXT]),
            )
            db.query(WorkflowJobDependency).filter(
                WorkflowJobDependency.job_id == job.id,
                WorkflowJobDependency.depends_on_job_id.in_(obsolete_ids),
                WorkflowJobDependency.dependency_type == "requires_completion",
            ).delete(synchronize_session=False)
        if dependency_source is not None:
            ensure_workflow_dependency(db, job=job, depends_on_job=dependency_source)
        if job_type != JOB_TYPE_BRAND_EXTRACTION:
            previous_job = job
        if job_type == JOB_TYPE_DB_PUBLISHER:
            publisher_job = job
    return jobs


def requeue_pipeline_jobs_for_run(
    db: Session,
    *,
    deck: Deck,
    run: DeckExtractionRun,
    source_checksum: str | None,
    max_attempts: int,
) -> dict[str, WorkflowJob]:
    jobs = ensure_pipeline_jobs_for_run(
        db,
        deck=deck,
        run=run,
        source_checksum=source_checksum,
        max_attempts=max_attempts,
    )
    for job_type, job in jobs.items():
        if job.status == JOB_STATUS_COMPLETED and job_type != JOB_TYPE_DB_PUBLISHER:
            continue
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_QUEUED,
            message=f"{job_type} job requeued for retry.",
        )
        job.error_code = None
        job.error_message = None
        job.failed_at = None
        job.completed_at = None
    return jobs


def fail_pipeline_jobs_from_stage(
    db: Session,
    *,
    jobs: dict[str, WorkflowJob],
    first_failed_job_type: str,
    worker_id: str | None,
    error_code: str,
    error_message: str,
) -> None:
    started = False
    for job_type in SOURCE_PIPELINE_JOB_SEQUENCE[1:]:
        if job_type == first_failed_job_type:
            started = True
        if not started:
            continue
        job = jobs.get(job_type)
        if job is None or job.status == JOB_STATUS_COMPLETED:
            continue
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_FAILED_FINAL,
            worker_id=worker_id,
            message=error_message,
            error_code=error_code,
            error_message=error_message,
            output_payload={"failureCode": error_code},
        )


def get_workflow_job_by_id(db: Session, job_id: str) -> WorkflowJob | None:
    return db.query(WorkflowJob).filter(WorkflowJob.id == job_id).one_or_none()


def get_workflow_job_by_idempotency_key(
    db: Session,
    *,
    deck_id: str,
    job_type: str,
    idempotency_key: str,
) -> WorkflowJob | None:
    return (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.job_type == job_type,
            WorkflowJob.idempotency_key == idempotency_key,
        )
        .order_by(WorkflowJob.created_at.desc())
        .first()
    )


def list_workflow_jobs_for_deck(db: Session, deck_id: str) -> list[WorkflowJob]:
    return (
        db.query(WorkflowJob)
        .filter(WorkflowJob.deck_id == deck_id)
        .order_by(WorkflowJob.created_at.desc(), WorkflowJob.updated_at.desc(), WorkflowJob.id.desc())
        .all()
    )


GENERATION_ROOT_JOB_TYPES = {JOB_TYPE_LLM_GENERATION, JOB_TYPE_INSTANT_DECK_GENERATION}


def latest_generation_root_and_chain(
    jobs: list[WorkflowJob],
    *,
    generation_root_job_type: str | None = None,
) -> tuple[WorkflowJob | None, list[WorkflowJob]]:
    """Return the newest matching generation root and jobs carrying its lineage."""
    allowed_root_types = (
        {generation_root_job_type}
        if generation_root_job_type is not None
        else GENERATION_ROOT_JOB_TYPES
    )
    roots = [job for job in jobs if job.job_type in allowed_root_types]
    if all(getattr(job, "created_at", None) is not None and getattr(job, "updated_at", None) is not None for job in roots):
        roots.sort(key=lambda job: (job.created_at, job.updated_at, job.id), reverse=True)
    generation_root = roots[0] if roots else None
    if generation_root is None:
        return None, []

    chain: list[WorkflowJob] = []
    for job in jobs:
        input_payload = job.input_json if isinstance(job.input_json, dict) else {}
        output_payload = job.output_json if isinstance(job.output_json, dict) else {}
        input_generation_job_id = input_payload.get("generationWorkflowJobId")
        output_generation_job_id = output_payload.get("generationWorkflowJobId")
        if (
            input_generation_job_id
            and output_generation_job_id
            and input_generation_job_id != output_generation_job_id
        ):
            continue
        generation_job_id = input_generation_job_id or output_generation_job_id
        if job.id == generation_root.id or generation_job_id == generation_root.id:
            chain.append(job)
    return generation_root, chain


def workflow_job_dependencies_status(db: Session, job: WorkflowJob) -> tuple[bool, bool]:
    dependencies = db.query(WorkflowJobDependency).filter(WorkflowJobDependency.job_id == job.id).all()
    if not dependencies:
        return True, False

    blocked = False
    for dependency in dependencies:
        upstream = db.query(WorkflowJob).filter(WorkflowJob.id == dependency.depends_on_job_id).one_or_none()
        if upstream is None:
            return False, True
        if upstream.status in {JOB_STATUS_FAILED_FINAL, JOB_STATUS_TIMED_OUT, JOB_STATUS_BLOCKED}:
            return False, True
        if upstream.status != JOB_STATUS_COMPLETED:
            return False, blocked
    return True, blocked


def workflow_job_dependencies_have_required_output(db: Session, job: WorkflowJob) -> tuple[bool, str | None]:
    """Validate stage-specific output required from completed dependencies.

    Completion alone is insufficient for generation pipeline stages created by
    older deployments or interrupted writes. Keeping this check at the claim
    boundary prevents workers from consuming malformed downstream jobs.
    """
    required_output_by_job_type = {
        JOB_TYPE_SCHEMA_VALIDATION: ((JOB_TYPE_LLM_GENERATION, JOB_TYPE_INSTANT_DECK_GENERATION), "designVersionId"),
        JOB_TYPE_PREVIEW_RENDER: (JOB_TYPE_SCHEMA_VALIDATION, "designVersionId"),
    }
    requirement = required_output_by_job_type.get(job.job_type)
    if requirement is None:
        return True, None

    required_dependency_type, required_key = requirement
    required_dependency_types = (
        required_dependency_type
        if isinstance(required_dependency_type, tuple)
        else (required_dependency_type,)
    )
    dependencies = db.query(WorkflowJobDependency).filter(WorkflowJobDependency.job_id == job.id).all()
    for dependency in dependencies:
        upstream = db.query(WorkflowJob).filter(WorkflowJob.id == dependency.depends_on_job_id).one_or_none()
        if upstream is None or upstream.job_type not in required_dependency_types:
            continue
        if upstream.status != JOB_STATUS_COMPLETED:
            return False, None
        if (upstream.output_json or {}).get(required_key):
            return True, None
        return False, f"Completed {'/'.join(required_dependency_types)} dependency is missing {required_key}."
    return False, f"Required {'/'.join(required_dependency_types)} dependency is missing."


def next_ready_dependent_job(db: Session, completed_job_id: str) -> WorkflowJob | None:
    dependencies = (
        db.query(WorkflowJobDependency)
        .filter(WorkflowJobDependency.depends_on_job_id == completed_job_id)
        .order_by(WorkflowJobDependency.created_at.asc())
        .all()
    )
    for dependency in dependencies:
        candidate = db.query(WorkflowJob).filter(WorkflowJob.id == dependency.job_id).one_or_none()
        if candidate is None or candidate.status not in CLAIMABLE_JOB_STATUSES:
            continue
        ready, blocked = workflow_job_dependencies_status(db, candidate)
        if blocked and not ready:
            continue
        if ready:
            return candidate
    return None


def claim_next_workflow_job(
    db: Session,
    *,
    worker_id: str,
    job_types: set[str] | None = None,
) -> WorkflowJob | None:
    query = db.query(WorkflowJob).filter(WorkflowJob.status.in_(CLAIMABLE_JOB_STATUSES))
    if job_types:
        query = query.filter(WorkflowJob.job_type.in_(job_types))
    query = query.order_by(WorkflowJob.priority.desc(), WorkflowJob.created_at.asc())
    try:
        candidates = query.with_for_update(skip_locked=True).all()
    except Exception:
        candidates = query.all()

    for candidate in candidates:
        if candidate.status == JOB_STATUS_FAILED_RETRYABLE:
            if int(candidate.attempt_count or 0) >= int(candidate.max_attempts or 1):
                set_workflow_job_status(
                    db,
                    job=candidate,
                    status=JOB_STATUS_FAILED_FINAL,
                    worker_id=worker_id,
                    message="Workflow job exhausted its retry attempts.",
                    error_code=candidate.error_code or "retry_attempts_exhausted",
                    error_message=candidate.error_message or "Workflow job exhausted its retry attempts.",
                    output_payload={"phase": "failed_final", "recoverable": False, "nextAction": "manual_review"},
                )
                db.commit()
                continue
            retry_delay = _workflow_retry_backoff_seconds(int(candidate.attempt_count or 0))
            if candidate.updated_at and candidate.updated_at > _now() - timedelta(seconds=retry_delay):
                continue
        ready, blocked = workflow_job_dependencies_status(db, candidate)
        if blocked and not ready:
            set_workflow_job_status(
                db,
                job=candidate,
                status=JOB_STATUS_BLOCKED,
                worker_id=worker_id,
                message="Workflow job is blocked by a failed dependency.",
                error_code="dependency_failed",
                error_message="A required upstream workflow job failed.",
                output_payload={"phase": "needs_manual_review"},
            )
            db.commit()
            continue
        if not ready:
            continue
        required_output_ready, required_output_error = workflow_job_dependencies_have_required_output(db, candidate)
        if required_output_error:
            set_workflow_job_status(
                db,
                job=candidate,
                status=JOB_STATUS_BLOCKED,
                worker_id=worker_id,
                message="Workflow job is blocked by incomplete dependency output.",
                error_code="dependency_output_missing",
                error_message=required_output_error,
                output_payload={"phase": "needs_manual_review"},
            )
            db.commit()
            continue
        if not required_output_ready:
            continue
        set_workflow_job_status(
            db,
            job=candidate,
            status=JOB_STATUS_RUNNING,
            worker_id=worker_id,
            message=f"{candidate.job_type} worker claimed job.",
        )
        db.commit()
        db.refresh(candidate)
        return candidate
    return None


def _workflow_retry_backoff_seconds(attempt_count: int) -> int:
    """Keep transient provider retries from exhausting all attempts immediately."""
    return min(300, 60 * (2 ** max(0, attempt_count - 1)))


def recover_stale_workflow_jobs(
    db: Session,
    *,
    worker_id: str,
    job_types: set[str] | None = None,
    stale_after_seconds: int = 900,
    recovery_limit: int = 25,
) -> dict[str, int]:
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    now_dt = _now()
    query = db.query(WorkflowJob).filter(WorkflowJob.status == JOB_STATUS_RUNNING)
    if job_types:
        query = query.filter(WorkflowJob.job_type.in_(job_types))
    jobs = query.order_by(WorkflowJob.heartbeat_at.asc().nullsfirst(), WorkflowJob.created_at.asc()).limit(recovery_limit).all()

    recovered = 0
    timed_out = 0
    for job in jobs:
        heartbeat = job.heartbeat_at or job.updated_at or job.started_at or job.created_at or now_dt
        lease_expired = job.locked_until is not None and job.locked_until <= now_dt
        heartbeat_expired = heartbeat <= cutoff
        if not lease_expired and not heartbeat_expired:
            continue
        recovery_reason = "worker_lease_expired" if lease_expired else "worker_heartbeat_expired"
        if int(job.attempt_count or 0) >= int(job.max_attempts or 1):
            set_workflow_job_status(
                db,
                job=job,
                status=JOB_STATUS_TIMED_OUT,
                worker_id=worker_id,
                message="Workflow job timed out after stale worker heartbeat and max attempts.",
                error_code="worker_timeout",
                error_message="Worker heartbeat expired and maximum attempts were reached.",
                output_payload={"phase": "needs_manual_review", "timedOut": True, "recoveryReason": recovery_reason},
                terminal_reason=recovery_reason,
            )
            timed_out += 1
            continue
        output_payload = dict(job.output_json or {})
        recovery_count = int(job.recovery_count or 0) + 1
        job.recovery_count = recovery_count
        job.last_recovered_at = now_dt
        job.last_recovered_by = worker_id
        output_payload.update(
            {
                "staleRecoveredAt": now_dt.isoformat(),
                "staleRecoveredBy": worker_id,
                "previousLockedBy": job.locked_by,
                "recoveryCount": recovery_count,
                "recoveryReason": recovery_reason,
            }
        )
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_QUEUED,
            message="Workflow job requeued after stale worker lease.",
            output_payload=output_payload,
        )
        recovered += 1

    if recovered or timed_out:
        db.commit()
    return {"recovered": recovered, "timedOut": timed_out}
