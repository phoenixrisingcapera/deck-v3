from __future__ import annotations

from datetime import datetime
import logging
import os
import socket
import traceback

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckExtractionRun, DeckFile, DeckSlide, WorkflowJob
from app.db.session import SessionLocal
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state, transition_deck_state
from app.services.visualizer.slide_read_model import get_deck
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_BLOCKED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_RUNNING,
    JOB_STATUS_TIMED_OUT,
    JOB_TYPE_SOURCE_INGESTION,
    JOB_TYPE_SOURCE_EXTRACTION,
    SOURCE_PIPELINE_JOB_SEQUENCE,
    ensure_pipeline_jobs_for_run,
    get_workflow_job_by_id,
    requeue_pipeline_jobs_for_run,
    workflow_job_phase,
)

logger = logging.getLogger(__name__)

PROCESSING_RUN_TYPE = "deck_processing_queue"
PROCESSING_RUNNING_STATUSES = {"queued", "running", "processing"}
PROCESSING_COMPLETED_STATUSES = {"completed", "ready"}
PROCESSING_MAX_ATTEMPTS = int(os.getenv("DECK_PROCESSING_MAX_ATTEMPTS", "3"))

PROCESSING_STAGE_LABELS = {
    "source_saved": "Source file saved",
    "worker_claimed": "Worker claimed processing job",
    "structure_extraction_running": "Extracting slide text and structure",
    "preview_generation_running": "Generating slide previews",
    "smart_deck_context_ready": "Smart Deck context ready",
    "failed": "Deck processing failed",
}


def _worker_id() -> str:
    return os.getenv("DECK_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"


def _parse_stage_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _metadata(run: DeckExtractionRun) -> dict:
    if isinstance(run.metadata_json, dict):
        return dict(run.metadata_json)
    return {}


def _run_source_checksum(run: DeckExtractionRun) -> str | None:
    checksum = _metadata(run).get("sourceChecksum")
    if isinstance(checksum, str) and checksum.strip():
        return checksum.strip()
    return None


def _require_source_checksum(deck_file: DeckFile) -> str:
    checksum = deck_file.checksum_sha256
    if isinstance(checksum, str) and checksum.strip():
        return checksum.strip()
    raise ValueError("Deck source checksum is required for idempotent processing")


def _idempotency_key(deck_id: str, source_checksum: str, run_type: str = PROCESSING_RUN_TYPE) -> str:
    return f"{deck_id}:{source_checksum}:{run_type}"


def _stage_payload(
    stage: str,
    *,
    next_action: str,
    worker_id: str | None = None,
    extra: dict | None = None,
) -> dict:
    now = datetime.utcnow().isoformat()
    payload = {
        "stage": stage,
        "stageLabel": PROCESSING_STAGE_LABELS.get(stage, stage.replace("_", " ").title()),
        "nextAction": next_action,
        "heartbeatAt": now,
    }
    if worker_id:
        payload["lockedBy"] = worker_id
        payload.setdefault("workerId", worker_id)
    if extra:
        payload.update(extra)
    return payload


def _set_processing_stage(
    run: DeckExtractionRun,
    stage: str,
    *,
    next_action: str,
    worker_id: str | None = None,
    extra: dict | None = None,
) -> None:
    metadata = _metadata(run)
    stage_payload = _stage_payload(stage, next_action=next_action, worker_id=worker_id, extra=extra)
    metadata.update(stage_payload)
    run.metadata_json = metadata
    run.current_stage = stage
    run.current_stage_label = str(stage_payload.get("stageLabel") or PROCESSING_STAGE_LABELS.get(stage) or stage)
    run.next_action = next_action
    run.locked_by = worker_id or metadata.get("lockedBy")
    run.locked_at = _parse_stage_datetime(metadata.get("lockedAt"))
    run.heartbeat_at = _parse_stage_datetime(stage_payload.get("heartbeatAt"))
    if isinstance(metadata.get("attemptCount"), int):
        run.attempt_count = metadata.get("attemptCount")
    if isinstance(metadata.get("maxAttempts"), int):
        run.max_attempts = metadata.get("maxAttempts")


def _find_processing_run_for_source(
    db: Session,
    *,
    deck_id: str,
    source_checksum: str,
    run_type: str = PROCESSING_RUN_TYPE,
    statuses: set[str] | None = None,
) -> DeckExtractionRun | None:
    query = db.query(DeckExtractionRun).filter(
        DeckExtractionRun.deck_id == deck_id,
        DeckExtractionRun.run_type == run_type,
    )
    if statuses is not None:
        query = query.filter(DeckExtractionRun.status.in_(statuses))

    runs = query.order_by(
        DeckExtractionRun.completed_at.desc().nullslast(),
        DeckExtractionRun.created_at.desc(),
    ).all()
    for run in runs:
        if _run_source_checksum(run) == source_checksum:
            return run
    return None


def _find_completed_processing_run(db: Session, deck_id: str, source_checksum: str) -> DeckExtractionRun | None:
    return _find_processing_run_for_source(
        db,
        deck_id=deck_id,
        source_checksum=source_checksum,
        run_type=PROCESSING_RUN_TYPE,
        statuses=PROCESSING_COMPLETED_STATUSES,
    )


def _mark_stale_running_runs_failed(
    db: Session,
    *,
    deck_id: str,
    source_checksum: str,
    worker_id: str | None = None,
) -> None:
    stale_runs = (
        db.query(DeckExtractionRun)
        .filter(
            DeckExtractionRun.deck_id == deck_id,
            DeckExtractionRun.run_type == PROCESSING_RUN_TYPE,
            DeckExtractionRun.status.in_(PROCESSING_RUNNING_STATUSES),
        )
        .all()
    )
    for stale_run in stale_runs:
        stale_checksum = _run_source_checksum(stale_run)
        if stale_checksum == source_checksum:
            continue
        stale_run.status = "failed"
        stale_run.completed_at = datetime.utcnow()
        stale_run.error_message = "Processing run superseded by a newer source checksum."
        _set_processing_stage(
            stale_run,
            "failed",
            next_action="wait_for_latest_processing",
            worker_id=worker_id,
            extra={
                "failureCode": "source_checksum_superseded",
                "sourceChecksum": stale_checksum,
                "supersededBySourceChecksum": source_checksum,
                "idempotencyScope": "deck_id_source_checksum_run_type",
            },
        )


def _reset_processing_run_for_retry(
    db: Session,
    *,
    run: DeckExtractionRun,
    deck: Deck,
    deck_file: DeckFile,
    source_checksum: str,
    requested_by_user_id: str | None,
) -> DeckExtractionRun:
    previous_metadata = _metadata(run)
    previous_attempt_count = int(previous_metadata.get("attemptCount") or 0)
    retry_reset_at = datetime.utcnow().isoformat()

    run.source_file_id = deck_file.id
    run.source_format = deck_file.file_extension
    run.status = "queued"
    run.error_message = None
    run.error_json = None
    run.metrics_json = None
    run.started_at = None
    run.completed_at = None
    run.slide_count = 0
    run.block_count = 0
    run.asset_count = 0
    run.metadata_json = {
        **previous_metadata,
        "requestedByUserId": requested_by_user_id,
        "sourceStoragePath": deck_file.storage_path,
        "sourceChecksum": source_checksum,
        "idempotencyKey": _idempotency_key(deck.id, source_checksum),
        "idempotencyScope": "deck_id_source_checksum_run_type",
        "stage": "source_saved",
        "stageLabel": PROCESSING_STAGE_LABELS["source_saved"],
        "nextAction": "wait_for_worker",
        "attemptCount": 0,
        "previousAttemptCount": previous_attempt_count,
        "maxAttempts": PROCESSING_MAX_ATTEMPTS,
        "heartbeatAt": retry_reset_at,
        "retryResetAt": retry_reset_at,
        "previousStatus": previous_metadata.get("status") or run.status,
    }
    run.current_stage = "source_saved"
    run.current_stage_label = PROCESSING_STAGE_LABELS["source_saved"]
    run.next_action = "wait_for_worker"
    run.attempt_count = 0
    run.max_attempts = PROCESSING_MAX_ATTEMPTS
    run.locked_by = None
    run.locked_at = None
    run.heartbeat_at = _parse_stage_datetime(retry_reset_at)
    requeue_pipeline_jobs_for_run(
        db,
        deck=deck,
        run=run,
        source_checksum=source_checksum,
        max_attempts=PROCESSING_MAX_ATTEMPTS,
    )
    transition_deck_state(
        db,
        deck,
        DeckState.PROCESSING,
        actor_user_id=requested_by_user_id,
        reason="processing_run_requeued_for_source_checksum",
        summary="Deck processing has been requeued for the same source checksum.",
        source_surface="deck_processing_queue",
        source_route=f"/decks/{deck.id}/processing",
        metadata={
            "processingRunId": run.id,
            "sourceChecksum": source_checksum,
            "idempotencyKey": _idempotency_key(deck.id, source_checksum),
            "previousAttemptCount": previous_attempt_count,
        },
    )
    db.commit()
    db.refresh(run)
    return run


def _pipeline_jobs_for_run(
    db: Session,
    *,
    deck: Deck,
    run: DeckExtractionRun,
    source_checksum: str | None,
) -> dict:
    return ensure_pipeline_jobs_for_run(
        db,
        deck=deck,
        run=run,
        source_checksum=source_checksum,
        max_attempts=PROCESSING_MAX_ATTEMPTS,
    )


def _head_workflow_job_for_run(db: Session, run: DeckExtractionRun) -> WorkflowJob | None:
    jobs_by_type = {
        job.job_type: job
        for job in db.query(WorkflowJob)
        .filter(
            WorkflowJob.extraction_run_id == run.id,
            WorkflowJob.job_type.in_(SOURCE_PIPELINE_JOB_SEQUENCE),
        )
        .all()
    }
    for job_type in SOURCE_PIPELINE_JOB_SEQUENCE:
        job = jobs_by_type.get(job_type)
        if job is None:
            continue
        if job.status in {"queued", "failed_retryable", "running"}:
            return job
    for job_type in reversed(SOURCE_PIPELINE_JOB_SEQUENCE):
        job = jobs_by_type.get(job_type)
        if job is not None:
            return job
    return None


def _sync_processing_run_with_head_job(run: DeckExtractionRun, workflow_job: WorkflowJob | None) -> None:
    metadata = _metadata(run)
    if workflow_job is None:
        run.metadata_json = metadata
        return

    phase = workflow_job_phase(workflow_job.job_type, workflow_job.status, output_payload=workflow_job.output_json or {})
    metadata.update(
        {
            "workflowJobId": workflow_job.id,
            "workflowJobType": workflow_job.job_type,
            "workflowJobStatus": workflow_job.status,
            "stage": phase,
            "stageLabel": PROCESSING_STAGE_LABELS.get(phase, str(phase).replace("_", " ").title()),
            "heartbeatAt": (
                workflow_job.heartbeat_at.isoformat()
                if workflow_job.heartbeat_at is not None
                else metadata.get("heartbeatAt")
            ),
        }
    )

    if workflow_job.status == JOB_STATUS_COMPLETED:
        metadata["nextAction"] = "open_smart_deck" if workflow_job.job_type == "db_publisher" else "wait_for_next_stage"
        run.status = "completed" if workflow_job.job_type == "db_publisher" else "processing"
        run.completed_at = workflow_job.completed_at or run.completed_at
        run.error_message = None
    elif workflow_job.status == JOB_STATUS_RUNNING:
        metadata["nextAction"] = "wait_for_worker"
        metadata["lockedBy"] = workflow_job.locked_by
        run.status = "processing"
        run.started_at = workflow_job.started_at or run.started_at
        run.completed_at = None
        run.error_message = None
    elif workflow_job.status in {JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_FAILED_FINAL, JOB_STATUS_BLOCKED, JOB_STATUS_TIMED_OUT}:
        metadata["nextAction"] = "retry_job" if workflow_job.status == JOB_STATUS_FAILED_RETRYABLE else "manual_review"
        metadata["failureCode"] = workflow_job.error_code
        run.status = "failed"
        run.completed_at = workflow_job.failed_at or run.completed_at
        run.error_message = workflow_job.error_message
    else:
        metadata["nextAction"] = "wait_for_worker"
        run.status = "queued"
        run.completed_at = None
        run.error_message = None

    run.metadata_json = metadata
    run.current_stage = str(metadata.get("stage") or phase)
    run.current_stage_label = str(metadata.get("stageLabel") or run.current_stage.replace("_", " ").title())
    run.next_action = str(metadata.get("nextAction") or "wait_for_worker")
    run.attempt_count = workflow_job.attempt_count
    run.max_attempts = workflow_job.max_attempts
    run.locked_by = workflow_job.locked_by
    run.locked_at = workflow_job.started_at
    run.heartbeat_at = workflow_job.heartbeat_at


def enqueue_deck_processing(db: Session, deck_id: str, *, requested_by_user_id: str | None = None) -> dict:
    from app.services.deck_processing.workflow_orchestration import queue_source_extraction

    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=requested_by_user_id)
    workflow_job = get_workflow_job_by_id(db, accepted["jobId"])
    if workflow_job is not None and workflow_job.extraction_run_id:
        run = db.query(DeckExtractionRun).filter(DeckExtractionRun.id == workflow_job.extraction_run_id).one_or_none()
        if run is not None:
            _sync_processing_run_with_head_job(run, workflow_job)
            db.commit()
            db.refresh(run)
            return _map_processing_run(run)
    raise ValueError("Workflow source pipeline did not yield a compatibility processing run.")


def process_queued_deck_run(db: Session, run_id: str, *, worker_id: str | None = None) -> dict:
    worker_id = worker_id or _worker_id()
    run = db.query(DeckExtractionRun).filter(DeckExtractionRun.id == run_id).one_or_none()
    if run is None:
        raise ValueError("Processing run not found")
    deck = db.query(Deck).filter(Deck.id == run.deck_id).one_or_none()
    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == run.deck_id).one_or_none()
    run_checksum = _run_source_checksum(run)
    current_checksum = _require_source_checksum(deck_file) if deck_file is not None else None

    if run_checksum and current_checksum and run_checksum != current_checksum:
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.error_message = "Processing run superseded by a newer source checksum."
        _set_processing_stage(
            run,
            "failed",
            next_action="wait_for_latest_processing",
            worker_id=worker_id,
            extra={
                "failureCode": "source_checksum_superseded",
                "sourceChecksum": run_checksum,
                "supersededBySourceChecksum": current_checksum,
                "idempotencyScope": "deck_id_source_checksum_run_type",
                "workflowExecutionMode": "compatibility_projection_only",
            },
        )
        db.commit()
        db.refresh(run)
        return _map_processing_run(run)

    workflow_job = _head_workflow_job_for_run(db, run)
    if workflow_job is None and deck is not None and run_checksum:
        jobs = _pipeline_jobs_for_run(
            db,
            deck=deck,
            run=run,
            source_checksum=run_checksum,
        )
        workflow_job = jobs.get(JOB_TYPE_SOURCE_INGESTION) or jobs.get(JOB_TYPE_SOURCE_EXTRACTION)

    _sync_processing_run_with_head_job(run, workflow_job)
    metadata = _metadata(run)
    metadata["workflowExecutionMode"] = "compatibility_projection_only"
    run.metadata_json = metadata
    db.commit()
    db.refresh(run)
    return _map_processing_run(run)


def process_queued_deck_run_in_background(run_id: str) -> None:
    db = SessionLocal()
    try:
        process_queued_deck_run(db, run_id)
    finally:
        db.close()
    return


def process_next_queued_deck(db: Session, *, worker_id: str | None = None) -> dict | None:
    # Compatibility adapter only. Durable claim/execution lives on workflow_jobs
    # and dedicated worker roles.
    from app.workers.dispatch.worker_runtime_service import process_next_durable_deck

    return process_next_durable_deck(db, worker_id=worker_id or _worker_id())


def process_deck_upload(db: Session, *, deck_id: str, requested_by_user_id: str | None = None) -> dict:
    from app.services.deck_processing.workflow_orchestration import queue_source_extraction

    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=requested_by_user_id)
    deck_payload = get_deck(db, deck_id)
    processing = {
        "id": accepted["jobId"],
        "runId": accepted["jobId"],
        "deckId": deck_id,
        "runType": accepted["jobType"],
        "workflowId": accepted["workflowId"],
        "workflowPhase": accepted["phase"],
        "workflowStatus": accepted["status"],
        "workflowJobId": accepted["jobId"],
        "workflowJobType": accepted["jobType"],
        "workflowJobStatus": accepted["status"],
        "status": accepted["status"],
        "runStatus": accepted["status"],
        "state": accepted["status"],
        "stage": accepted["phase"],
        "stageLabel": str(accepted["phase"]).replace("_", " ").title(),
        "nextAction": "view_processing",
        "attemptCount": 0,
        "maxAttempts": None,
        "lockedBy": None,
        "lockedAt": None,
        "heartbeatAt": None,
        "slideCount": 0,
        "blockCount": 0,
        "assetCount": 0,
        "workflowStateUrl": accepted["workflowStateUrl"],
        "jobUrl": accepted["jobUrl"],
    }
    return {"processing": processing, "deck": deck_payload}


def _map_processing_run(run: DeckExtractionRun) -> dict:
    metadata = _metadata(run)
    metrics = run.metrics_json if isinstance(run.metrics_json, dict) else {}
    source_workspace = metrics.get("sourceWorkspace") if isinstance(metrics.get("sourceWorkspace"), dict) else None
    source_enrichment = metadata.get("sourceEnrichment") or metrics.get("sourceEnrichment")
    return {
        "id": run.id,
        "workflowId": f"deckwf_{run.deck_id}",
        "workflowPhase": metadata.get("stage"),
        "workflowStatus": metadata.get("workflowJobStatus"),
        "workflowJobId": metadata.get("workflowJobId"),
        "workflowJobType": metadata.get("workflowJobType"),
        "workflowJobStatus": metadata.get("workflowJobStatus"),
        "deckId": run.deck_id,
        "sourceFileId": run.source_file_id,
        "runType": run.run_type,
        "status": run.status,
        "runStatus": run.status,
        "state": canonical_deck_state(run.status).value,
        "stage": run.current_stage or metadata.get("stage"),
        "stageLabel": run.current_stage_label or metadata.get("stageLabel"),
        "nextAction": run.next_action or metadata.get("nextAction"),
        "attemptCount": run.attempt_count if run.attempt_count is not None else metadata.get("attemptCount"),
        "maxAttempts": run.max_attempts if run.max_attempts is not None else metadata.get("maxAttempts"),
        "lockedBy": run.locked_by or metadata.get("lockedBy"),
        "lockedAt": run.locked_at.isoformat() if run.locked_at else metadata.get("lockedAt"),
        "heartbeatAt": run.heartbeat_at.isoformat() if run.heartbeat_at else metadata.get("heartbeatAt"),
        "slideCount": run.slide_count,
        "blockCount": run.block_count,
        "assetCount": run.asset_count,
        "sourceChecksum": metadata.get("sourceChecksum"),
        "idempotencyKey": metadata.get("idempotencyKey"),
        "idempotencyScope": metadata.get("idempotencyScope"),
        "sourceWorkspace": source_workspace,
        "sourceEnrichment": source_enrichment,
        "enrichmentSource": metadata.get("enrichmentSource") or (source_enrichment or {}).get("source"),
        "llmStatus": metadata.get("llmStatus") or (source_enrichment or {}).get("llmStatus"),
        "errorMessage": run.error_message,
        "metadataJson": run.metadata_json,
        "metricsJson": run.metrics_json,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
        "startedAt": run.started_at.isoformat() if run.started_at else None,
        "completedAt": run.completed_at.isoformat() if run.completed_at else None,
    }
