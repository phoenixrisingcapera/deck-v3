"""Durable worker runtime for Upload -> Smart Deck jobs.

Owns: worker-kind configuration, claiming policy, heartbeat/recovery behavior,
and dispatch into job handlers.
Must not own: detailed stage business logic, workflow-state presentation, or
the source extraction/preview/workspace algorithms themselves.
Stage: worker execution shell around all workflow jobs.
Status: KEEP
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import logging
import os
import threading
from typing import Iterator

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.core.worker_startup_policy import (
    INSTANT_DECK_PIPELINE_JOB_TYPES,
    LLM_GENERATION_JOB_TYPES,
    SERVICE_WORKER_KINDS as SERVICE_NAME_TO_WORKER_KIND,
)
from app.db.models import Deck, DeckExtractionRun, DeckFile, InstantDeckOperation, SmartEditRun, WorkflowJob, WorkflowJobDependency
from app.services.deck_processing.state_machine import DeckState, transition_deck_state
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_BLOCKED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    JOB_TYPE_APPLY_VERSION,
    JOB_TYPE_BRAND_EXTRACTION,
    JOB_TYPE_DB_PUBLISHER,
    JOB_TYPE_EXPORT,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_SELECTED_SLIDE_GENERATION,
    JOB_TYPE_MINIATURES,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_SCHEMA_VALIDATION,
    JOB_TYPE_SMART_DECK_CONTEXT,
    JOB_TYPE_SOURCE_INGESTION,
    JOB_TYPE_SOURCE_EXTRACTION,
    JOB_TYPE_COMPILE_FINAL_DECK,
    JOB_TYPE_DUE_DILIGENCE,
    JOB_TYPE_DECK_MAP_ANALYSIS,
    JOB_TYPE_MARKET_RESEARCH,
    JOB_TYPE_MEDIA_PROCESSING,
    JOB_TYPE_SMART_EDIT,
    SOURCE_PIPELINE_JOB_SEQUENCE,
    claim_next_workflow_job,
    fail_pipeline_jobs_from_stage,
    get_workflow_job_by_id,
    recover_stale_workflow_jobs,
    set_workflow_job_status,
    workflow_job_dependencies_status,
    workflow_job_phase,
)

logger = logging.getLogger(__name__)


class UnsupportedWorkflowJobType(ValueError):
    code = "unsupported_workflow_job_type"


WORKER_KIND_TO_JOB_TYPE = {
    "source_ingestion": JOB_TYPE_SOURCE_INGESTION,
    "source_extraction": JOB_TYPE_SOURCE_EXTRACTION,
    "miniatures": JOB_TYPE_MINIATURES,
    "brand_extraction": JOB_TYPE_BRAND_EXTRACTION,
    "smart_deck_context": JOB_TYPE_SMART_DECK_CONTEXT,
    "db_publisher": JOB_TYPE_DB_PUBLISHER,
    "llm_generation": JOB_TYPE_LLM_GENERATION,
    "instant_deck_generation": JOB_TYPE_INSTANT_DECK_GENERATION,
    "selected_slide_generation": JOB_TYPE_SELECTED_SLIDE_GENERATION,
    "schema_validation": JOB_TYPE_SCHEMA_VALIDATION,
    "preview_render": JOB_TYPE_PREVIEW_RENDER,
    "apply_version": JOB_TYPE_APPLY_VERSION,
    "compile_final_deck": JOB_TYPE_COMPILE_FINAL_DECK,
    "export": JOB_TYPE_EXPORT,
    "due_diligence": JOB_TYPE_DUE_DILIGENCE,
    "deck_map_analysis": JOB_TYPE_DECK_MAP_ANALYSIS,
    "market_research": JOB_TYPE_MARKET_RESEARCH,
    "media_processing": JOB_TYPE_MEDIA_PROCESSING,
    "smart_edit": JOB_TYPE_SMART_EDIT,
    "stale_job_rescuer": None,
}
"""Maps deployment-level worker kind names to the single job type they claim."""

WORKFLOW_JOB_TYPES = {
    JOB_TYPE_SOURCE_INGESTION,
    JOB_TYPE_SOURCE_EXTRACTION,
    JOB_TYPE_MINIATURES,
    JOB_TYPE_BRAND_EXTRACTION,
    JOB_TYPE_SMART_DECK_CONTEXT,
    JOB_TYPE_DB_PUBLISHER,
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_SELECTED_SLIDE_GENERATION,
    JOB_TYPE_SCHEMA_VALIDATION,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_APPLY_VERSION,
    JOB_TYPE_COMPILE_FINAL_DECK,
    JOB_TYPE_EXPORT,
    JOB_TYPE_DUE_DILIGENCE,
    JOB_TYPE_DECK_MAP_ANALYSIS,
    JOB_TYPE_MARKET_RESEARCH,
    JOB_TYPE_MEDIA_PROCESSING,
    JOB_TYPE_SMART_EDIT,
}

LLM_COMMAND_JOB_TYPES = set(LLM_GENERATION_JOB_TYPES)

GENERATION_PIPELINE_JOB_TYPES = {
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_SCHEMA_VALIDATION,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_DB_PUBLISHER,
}

LEGACY_GENERIC_WORKER_SERVICE_NAMES = {
    "deck-processing-worker",
    "deck-processing-worker-service",
}


def _now() -> datetime:
    return datetime.utcnow()


def _heartbeat_interval_seconds() -> float:
    raw_value = str(os.getenv("DECK_WORKER_HEARTBEAT_SECONDS") or "60").strip()
    try:
        parsed = float(raw_value)
    except ValueError:
        return 60.0
    return max(15.0, parsed)


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def generic_generation_pipeline_worker_enabled() -> bool:
    """Return whether the legacy generic worker may run the generation pipeline.

    This is a break-glass compatibility mode for deployments that still point a
    generic Railway worker service at the durable workflow runtime.
    """
    return _truthy_env("DECK_ENABLE_GENERIC_GENERATION_PIPELINE_WORKER")


def infer_worker_kind_from_service_name(service_name: str | None) -> str | None:
    normalized = str(service_name or "").strip().lower()
    if not normalized:
        return None
    inferred = SERVICE_NAME_TO_WORKER_KIND.get(normalized)
    if inferred:
        return inferred
    if normalized.startswith("worker-"):
        return normalized.removeprefix("worker-").replace("-", "_")
    return None


def worker_kind() -> str | None:
    kind = str(os.getenv("WORKER_KIND") or "").strip().lower().replace("-", "_")
    if kind:
        return kind
    role = str(os.getenv("APP_ROLE") or "").strip().lower().replace("-", "_")
    if role.startswith("worker-"):
        return role.removeprefix("worker-")
    inferred = infer_worker_kind_from_service_name(os.getenv("RAILWAY_SERVICE_NAME"))
    if inferred:
        return inferred
    if role == "worker":
        return None
    return None


def worker_recovery_only() -> bool:
    kind = worker_kind()
    if kind == "stale_job_rescuer":
        return True
    return _truthy_env("DECK_WORKER_RECOVERY_ONLY")


def inferred_generic_service_name() -> str | None:
    service_name = str(os.getenv("RAILWAY_SERVICE_NAME") or "").strip().lower()
    return service_name if service_name in LEGACY_GENERIC_WORKER_SERVICE_NAMES else None


@contextmanager
def _workflow_job_heartbeat(job_id: str, worker_id: str) -> Iterator[None]:
    stop_event = threading.Event()
    interval_seconds = _heartbeat_interval_seconds()

    def _heartbeat_loop() -> None:
        from app.db.session import SessionLocal

        while not stop_event.wait(interval_seconds):
            heartbeat_db = SessionLocal()
            try:
                heartbeat_job = get_workflow_job_by_id(heartbeat_db, job_id)
                if heartbeat_job is None or heartbeat_job.status != JOB_STATUS_RUNNING:
                    heartbeat_db.rollback()
                    return
                set_workflow_job_status(
                    heartbeat_db,
                    job=heartbeat_job,
                    status=heartbeat_job.status,
                    worker_id=worker_id,
                    heartbeat_only=True,
                )
                heartbeat_db.commit()
            except Exception:
                heartbeat_db.rollback()
                return
            finally:
                heartbeat_db.close()

    thread = threading.Thread(
        target=_heartbeat_loop,
        name=f"workflow-heartbeat-{job_id}",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=min(interval_seconds, 5.0))


def configured_worker_job_types() -> set[str]:
    """Resolve which job types this worker instance is allowed to claim.

    `DECK_WORKER_JOB_TYPES` is still supported for multi-job Railway services,
    but production debugging is easier when each service claims one job type.
    """
    kind = worker_kind()
    configured: set[str] = set()
    if kind:
        mapped = WORKER_KIND_TO_JOB_TYPE.get(kind)
        if mapped is None and kind != "stale_job_rescuer":
            if not os.getenv("DECK_WORKER_JOB_TYPES"):
                raise RuntimeError(f"Unsupported worker kind: {kind}")
        if mapped is not None:
            configured.add(mapped)
    legacy_configured = {
        value.strip()
        for value in str(os.getenv("DECK_WORKER_JOB_TYPES") or "").split(",")
        if value.strip()
    }
    if legacy_configured:
        configured |= legacy_configured
    # The existing LLM worker is the canonical execution service for bounded
    # Smart Deck commands. Include intelligence and media processing without
    # creating new services or queue systems, even when its legacy env still
    # names only llm_generation.
    if kind == "llm_generation":
        configured |= LLM_COMMAND_JOB_TYPES
    unknown = configured - WORKFLOW_JOB_TYPES
    if unknown:
        raise RuntimeError(f"Unsupported workflow job types: {', '.join(sorted(unknown))}")
    if worker_recovery_only():
        return configured or set(WORKFLOW_JOB_TYPES)
    if inferred_generic_service_name() and generic_generation_pipeline_worker_enabled():
        configured |= set(GENERATION_PIPELINE_JOB_TYPES)
    if not configured:
        if _truthy_env("DECK_WORKER_ALLOW_ALL_JOB_TYPES"):
            return set(WORKFLOW_JOB_TYPES)
        raise RuntimeError(
            "DECK_WORKER_JOB_TYPES must be configured for non-recovery workers. "
            "Production workers should claim a dedicated job_type."
        )
    if (
        len(configured) > 1
        and configured != LLM_COMMAND_JOB_TYPES
        and not (kind == "instant_deck_pipeline" and configured == set(INSTANT_DECK_PIPELINE_JOB_TYPES))
        and not _truthy_env("DECK_WORKER_ALLOW_MULTI_JOB_TYPES")
    ):
        raise RuntimeError(
            "Production workers should claim exactly one workflow job_type. "
            "Set DECK_WORKER_ALLOW_MULTI_JOB_TYPES=true only for an explicit break-glass worker."
        )
    return configured


def _configured_job_types() -> set[str]:
    return configured_worker_job_types()


def _job_payload(job: WorkflowJob) -> dict:
    return dict(job.input_json or {})


def _job_output(job: WorkflowJob) -> dict:
    return dict(job.output_json or {})


def _dependency_jobs(db: Session, job: WorkflowJob) -> list[WorkflowJob]:
    dependencies = (
        db.query(WorkflowJobDependency)
        .filter(WorkflowJobDependency.job_id == job.id)
        .order_by(WorkflowJobDependency.created_at.asc())
        .all()
    )
    jobs: list[WorkflowJob] = []
    for dependency in dependencies:
        upstream = db.query(WorkflowJob).filter(WorkflowJob.id == dependency.depends_on_job_id).one_or_none()
        if upstream is not None:
            jobs.append(upstream)
    return jobs


def _dependency_output(db: Session, job: WorkflowJob, job_type: str) -> dict:
    for dependency_job in _dependency_jobs(db, job):
        if dependency_job.job_type == job_type:
            return _job_output(dependency_job)
    return {}


def _processing_run(job: WorkflowJob, db: Session) -> DeckExtractionRun | None:
    if job.job_type == JOB_TYPE_DB_PUBLISHER:
        publish_target = str(_job_payload(job).get("publishTarget") or "smart_deck_ready").strip()
        if publish_target != "smart_deck_ready":
            # Preview/apply/export publishers own generation publication only.
            # They must never manufacture or mutate source-extraction lineage.
            return None
    if job.extraction_run_id:
        run = db.query(DeckExtractionRun).filter(DeckExtractionRun.id == job.extraction_run_id).one_or_none()
        if run is not None:
            return run

    if job.job_type not in {
        JOB_TYPE_SOURCE_EXTRACTION,
        JOB_TYPE_MINIATURES,
        JOB_TYPE_BRAND_EXTRACTION,
        JOB_TYPE_SMART_DECK_CONTEXT,
        JOB_TYPE_DB_PUBLISHER,
    }:
        return None

    deck = db.query(Deck).filter(Deck.id == job.deck_id).one_or_none()
    if deck is None:
        return None
    deck_file = (
        db.query(DeckFile)
        .filter(DeckFile.deck_id == deck.id)
        .order_by(DeckFile.uploaded_at.desc())
        .first()
    )
    source_file_id = deck_file.id if deck_file is not None else None

    run = DeckExtractionRun(
        id=generate_id("process"),
        deck_id=deck.id,
        source_file_id=source_file_id,
        run_type="deck_processing_queue",
        extractor_name="workflow_source_pipeline",
        extractor_version="v2",
        source_format=deck_file.file_extension if deck_file is not None else None,
        status="queued",
        metadata_json={
            "stage": "workflow_compatibility_created",
            "stageLabel": "Workflow compatibility created",
            "nextAction": "wait_for_worker",
            "workflowJobId": job.id,
            "workflowJobType": job.job_type,
        },
    )
    db.add(run)
    db.flush()
    job.extraction_run_id = run.id
    return run


def _deck(job: WorkflowJob, db: Session) -> Deck:
    deck = db.query(Deck).filter(Deck.id == job.deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")
    return deck


def _failure_status_for_job(job: WorkflowJob) -> str:
    return JOB_STATUS_FAILED_FINAL if int(job.attempt_count or 0) >= int(job.max_attempts or 1) else JOB_STATUS_FAILED_RETRYABLE


def _failure_status_for_exception(job: WorkflowJob, exc: Exception) -> str:
    from app.services.llm.generation_service import SmartDeckProviderUnavailableError
    from app.services.llm.instant_html_operation_service import InstantOperationConflict
    if isinstance(exc, (InstantOperationConflict, SmartDeckProviderUnavailableError, UnsupportedWorkflowJobType)):
        return JOB_STATUS_FAILED_FINAL
    from app.services.llm.provider_errors import is_non_retryable_provider_error
    from app.services.rendering.html_deck_compiler import HtmlDeckCompileError

    if is_non_retryable_provider_error(exc) or isinstance(exc, HtmlDeckCompileError):
        return JOB_STATUS_FAILED_FINAL
    return _failure_status_for_job(job)


_TERMINAL_INSTANT_OPERATION_STATUSES = frozenset(
    {
        "artifact_ready",
        "budget_exhausted",
        "charge_failed",
        "completed",
        "failed_final",
        "manual_reconciliation_required",
    }
)


def _terminal_instant_operation_for_job(db: Session, job: WorkflowJob) -> InstantDeckOperation | None:
    """Return terminal operation truth that forbids retrying the same command."""

    if job.job_type != JOB_TYPE_INSTANT_DECK_GENERATION:
        return None
    operation = (
        db.query(InstantDeckOperation)
        .filter(
            InstantDeckOperation.workflow_job_id == job.id,
            InstantDeckOperation.deck_id == job.deck_id,
        )
        .one_or_none()
    )
    if operation is None or operation.status not in _TERMINAL_INSTANT_OPERATION_STATUSES:
        return None
    return operation


def _mark_run_stage(run: DeckExtractionRun, *, stage: str, next_action: str, worker_id: str, extra: dict | None = None) -> None:
    metadata = dict(run.metadata_json or {})
    metadata.update(
        {
            "stage": stage,
            "stageLabel": stage.replace("_", " ").title(),
            "nextAction": next_action,
            "lockedBy": worker_id,
            "workerId": worker_id,
            "heartbeatAt": _now().isoformat(),
        }
    )
    if extra:
        metadata.update(extra)
    run.metadata_json = metadata


def _source_pipeline_jobs(db: Session, run: DeckExtractionRun) -> dict[str, WorkflowJob]:
    jobs = {
        job.job_type: job
        for job in db.query(WorkflowJob)
        .filter(WorkflowJob.extraction_run_id == run.id, WorkflowJob.job_type.in_(SOURCE_PIPELINE_JOB_SEQUENCE[1:]))
        .all()
    }
    return jobs


def _mark_source_pipeline_failed(
    db: Session,
    *,
    run: DeckExtractionRun,
    first_failed_job_type: str,
    worker_id: str,
    error_code: str,
    error_message: str,
) -> None:
    jobs = _source_pipeline_jobs(db, run)
    if jobs:
        fail_pipeline_jobs_from_stage(
            db,
            jobs=jobs,
            first_failed_job_type=first_failed_job_type,
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
        )


def process_workflow_job(db: Session, job_id: str, *, worker_id: str) -> dict:
    """Run one claimed job and persist only redacted provider-boundary failures."""
    # A failed provider/storage operation must not poison the session used for
    # the next claimed job. Reset only the current unit-of-work before reading
    # the next job; no product state is lost because claims are committed.
    db.rollback()
    job = get_workflow_job_by_id(db, job_id)
    if job is None:
        raise ValueError("Workflow job not found")

    from app.services.llm.instant_html_operation_service import InstantProviderAttestationUnavailable

    try:
        from app.workers.dispatch.job_handlers import get_workflow_job_handler

        handler = get_workflow_job_handler(job.job_type)
        if handler is None:
            logger.error(
                "unsupported_workflow_job_type",
                extra={
                    "workflow_job_id": job.id,
                    "deck_id": job.deck_id,
                    "job_type": job.job_type,
                    "worker_id": worker_id,
                },
            )
            raise UnsupportedWorkflowJobType(f"Unsupported workflow job type: {job.job_type}")
        with _workflow_job_heartbeat(job.id, worker_id):
            handler(db, job, worker_id=worker_id)
    except InstantProviderAttestationUnavailable:
        # Attestation can expire between claim and the final locked charge
        # gate. Put the Instant job back exactly as it was before claim so a
        # process-level outage never spends a customer retry or terminalizes
        # an otherwise valid operation.
        db.rollback()
        refreshed = get_workflow_job_by_id(db, job_id)
        if refreshed is not None and refreshed.status == JOB_STATUS_RUNNING:
            consumed_attempt = int(refreshed.attempt_count or 0)
            set_workflow_job_status(
                db,
                job=refreshed,
                status=JOB_STATUS_QUEUED,
                message="Instant provider readiness changed after claim; job preserved for a later worker cycle.",
            )
            refreshed.attempt_count = max(0, consumed_attempt - 1)
            refreshed.error_code = None
            refreshed.error_message = None
            db.commit()
        return {
            "id": refreshed.id if refreshed is not None else job_id,
            "deckId": refreshed.deck_id if refreshed is not None else job.deck_id,
            "jobType": refreshed.job_type if refreshed is not None else job.job_type,
            "status": refreshed.status if refreshed is not None else JOB_STATUS_QUEUED,
            "phase": (
                workflow_job_phase(
                    refreshed.job_type,
                    refreshed.status,
                    output_payload=_job_output(refreshed),
                )
                if refreshed is not None
                else "queued"
            ),
        }
    except Exception as exc:
        db.rollback()
        refreshed = get_workflow_job_by_id(db, job_id)
        if refreshed is not None and refreshed.status == JOB_STATUS_RUNNING:
            if isinstance(exc, UnsupportedWorkflowJobType):
                safe_message = "This workflow job type is not supported by the active product worker."
                set_workflow_job_status(
                    db,
                    job=refreshed,
                    status=JOB_STATUS_FAILED_FINAL,
                    worker_id=worker_id,
                    message=safe_message,
                    error_code=exc.code,
                    error_message=safe_message,
                    output_payload={
                        "phase": "failed_final",
                        "recoverable": False,
                        "nextAction": None,
                        "failureStage": "worker_dispatch",
                    },
                )
                db.commit()
                raise
            from app.services.llm.provider_errors import is_non_retryable_provider_error, is_provider_capacity_error

            non_retryable_provider_failure = is_non_retryable_provider_error(exc)
            from app.services.rendering.html_deck_compiler import HtmlDeckCompileError
            from app.services.llm.full_html_generation_service import FullHtmlOperationDeadlineError

            deterministic_compile_failure = isinstance(exc, HtmlDeckCompileError)
            operation_deadline_failure = isinstance(exc, FullHtmlOperationDeadlineError)
            failure_status = _failure_status_for_exception(refreshed, exc)
            terminal_instant_operation = _terminal_instant_operation_for_job(db, refreshed)
            if terminal_instant_operation is not None:
                # The operation owns provider/charge replay eligibility. A
                # workflow retry cannot revive a charge-failed, exhausted,
                # completed, or manual-reconciliation operation.
                failure_status = JOB_STATUS_FAILED_FINAL
            if refreshed.job_type in {JOB_TYPE_PREVIEW_RENDER, JOB_TYPE_DB_PUBLISHER}:
                # Instant HTML downstream failures invalidate the paid operation;
                # the operation service no-ops for legacy/non-HTML versions.
                failure_payload = _job_payload(refreshed)
                instant_operation_id = str(failure_payload.get("instantOperationId") or "").strip()
                if instant_operation_id:
                    from app.services.llm.instant_html_operation_service import terminalize_operation_by_id

                    terminalize_operation_by_id(
                        db,
                        instant_operation_id,
                        reason=f"{refreshed.job_type}_failed",
                        defer_release=refreshed.job_type == JOB_TYPE_PREVIEW_RENDER,
                    )
                    failure_status = JOB_STATUS_FAILED_FINAL
                design_version_id = str((failure_payload.get("designVersionId") or "")).strip()
                if not design_version_id:
                    dependency_output = _dependency_output(db, refreshed, JOB_TYPE_PREVIEW_RENDER if refreshed.job_type == JOB_TYPE_DB_PUBLISHER else JOB_TYPE_SCHEMA_VALIDATION)
                    design_version_id = str(dependency_output.get("designVersionId") or "").strip()
                if design_version_id and not instant_operation_id:
                    from app.services.llm.instant_html_operation_service import terminalize_operation_for_design_version

                    terminalized = terminalize_operation_for_design_version(
                        db,
                        design_version_id,
                        reason=f"{refreshed.job_type}_failed",
                        defer_release=refreshed.job_type == JOB_TYPE_PREVIEW_RENDER,
                    )
                    if terminalized is not None:
                        failure_status = JOB_STATUS_FAILED_FINAL
            provider_capacity_failure = is_provider_capacity_error(exc)
            provider_boundary_failure = refreshed.job_type in {JOB_TYPE_LLM_GENERATION, JOB_TYPE_INSTANT_DECK_GENERATION, JOB_TYPE_SMART_EDIT}
            from app.services.llm.generation_service import GenerationValidationError

            generation_validation_failure = isinstance(exc, GenerationValidationError)
            from app.services.llm.generation_service import SmartDeckProviderUnavailableError

            provider_not_configured = isinstance(exc, SmartDeckProviderUnavailableError)
            from app.services.llm.instant_html_operation_service import (
                INSTANT_CONTEXT_PREPARATION_FAILURE_REASONS,
                INSTANT_CONTEXT_PREPARATION_SAFE_MESSAGE,
                INSTANT_HTML_UNAVAILABLE_REASON,
                INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE,
                InstantOperationConflict,
            )

            instant_html_unavailable = isinstance(exc, InstantOperationConflict)
            from app.services.llm.deck_map_analysis_service import DeckMapMalformedJsonError
            from app.services.rendering.render_proof_service import RenderProofRequired

            deck_map_malformed_json = isinstance(exc, DeckMapMalformedJsonError)
            render_proof_failure = isinstance(exc, RenderProofRequired)
            terminal_instant_reason = (
                str(terminal_instant_operation.terminal_reason or "instant_operation_terminal")
                if terminal_instant_operation is not None
                else None
            )
            safe_error_message = (
                DeckMapMalformedJsonError.safe_message
                if deck_map_malformed_json
                else "The Instant Deck operation could not reserve product quota and cannot retry the same command. Check usage quota before starting another redesign."
                if terminal_instant_reason in {"product_quota_rejected", "quota_reservation_cancelled"}
                else INSTANT_CONTEXT_PREPARATION_SAFE_MESSAGE
                if terminal_instant_reason in INSTANT_CONTEXT_PREPARATION_FAILURE_REASONS
                else INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE
                if terminal_instant_operation is not None
                else "AI provider capacity is temporarily unavailable. Retry after capacity recovers or connect another provider."
                if provider_capacity_failure
                else "AI provider request failed and cannot be retried. Check provider access, quota, and request configuration."
                if non_retryable_provider_failure
                else "Connect an AI provider before generating Smart Deck previews."
                if provider_not_configured
                else INSTANT_HTML_UNAVAILABLE_SAFE_MESSAGE
                if instant_html_unavailable
                else "Full HTML generation exceeded its operation deadline. Reconcile the same durable job before considering another command."
                if operation_deadline_failure
                else "Full HTML deck compilation failed deterministic factuality and evidence validation; the generated output cannot be safely published."
                if deterministic_compile_failure
                else "Smart Deck output remains blocked by factuality or evidence validation."
                if generation_validation_failure
                else str(exc)
                if render_proof_failure
                else "AI provider request failed unexpectedly. Retry later or contact support if the problem persists."
                if provider_boundary_failure
                else "Workflow job failed unexpectedly. Inspect the durable job state and service logs."
            )
            set_workflow_job_status(
                db,
                job=refreshed,
                status=failure_status,
                worker_id=worker_id,
                message=safe_error_message,
                error_code=(
                    DeckMapMalformedJsonError.code
                    if deck_map_malformed_json
                    else terminal_instant_reason
                    if terminal_instant_reason is not None
                    else "provider_temporarily_unavailable"
                    if provider_capacity_failure
                    else "provider_not_configured"
                    if provider_not_configured
                    else INSTANT_HTML_UNAVAILABLE_REASON
                    if instant_html_unavailable
                    else "preview_render_failed"
                    if render_proof_failure
                    else getattr(exc, "code", f"{refreshed.job_type}_failed")
                ),
                error_message=safe_error_message,
                output_payload={
                    "phase": "failed_final" if failure_status == JOB_STATUS_FAILED_FINAL else "failed_retryable",
                    "recoverable": DeckMapMalformedJsonError.recoverable if deck_map_malformed_json else provider_capacity_failure,
                    "nextAction": DeckMapMalformedJsonError.next_action if deck_map_malformed_json else "check_usage_quota" if terminal_instant_reason in {"product_quota_rejected", "quota_reservation_cancelled"} else "retry_generation" if terminal_instant_reason in INSTANT_CONTEXT_PREPARATION_FAILURE_REASONS else "check_instant_html_configuration" if terminal_instant_operation is not None else "configure_provider_or_retry" if provider_capacity_failure else "configure_provider" if provider_not_configured else "check_instant_html_configuration" if instant_html_unavailable else "check_provider_configuration" if non_retryable_provider_failure else "check_status" if operation_deadline_failure else "review_generated_deck" if deterministic_compile_failure else None,
                    "validationFailure": (
                        exc.to_summary() if generation_validation_failure
                        else {
                            "code": exc.code,
                            "issues": exc.issues,
                            "generationStage": "deterministic_candidate_validation",
                            "retryAction": "Start a new Instant Deck redesign; the failed output was not published.",
                        }
                        if deterministic_compile_failure else None
                    ),
                    "failureStage": (
                        "preview_render" if render_proof_failure
                        else "generation_compiler" if deterministic_compile_failure
                        else "worker" if refreshed.job_type == JOB_TYPE_SMART_EDIT else None
                    ),
                },
            )
            if refreshed.job_type == JOB_TYPE_SMART_EDIT:
                run_id = str((refreshed.input_json or {}).get("runId") or "")
                smart_edit_run = db.query(SmartEditRun).filter(SmartEditRun.id == run_id).one_or_none()
                if smart_edit_run is not None:
                    smart_edit_run.status = "failed_final" if failure_status == JOB_STATUS_FAILED_FINAL else "failed_retryable"
                    smart_edit_run.error_code = str(refreshed.error_code or f"{refreshed.job_type}_failed")
                    smart_edit_run.error_message = safe_error_message
            if refreshed.job_type == JOB_TYPE_DB_PUBLISHER and failure_status == JOB_STATUS_FAILED_FINAL:
                deck = db.query(Deck).filter(Deck.id == refreshed.deck_id).one_or_none()
                if deck is not None:
                    transition_deck_state(
                        db,
                        deck,
                        DeckState.FAILED,
                        reason="workflow_db_publisher_failed",
                        summary=f"Workflow publisher failed: {exc}",
                        source_surface="workflow_db_publisher",
                        source_route=f"/decks/{deck.id}/workflow",
                        metadata={"workflowJobId": refreshed.id, "workerId": worker_id},
                    )
            db.commit()
        raise

    refreshed = get_workflow_job_by_id(db, job_id)
    if refreshed is None:
        raise ValueError("Workflow job disappeared after processing.")
    return {
        "id": refreshed.id,
        "deckId": refreshed.deck_id,
        "jobType": refreshed.job_type,
        "status": refreshed.status,
        "phase": workflow_job_phase(refreshed.job_type, refreshed.status, output_payload=_job_output(refreshed)),
    }


def recover_stale_processing_runs(db: Session, *, worker_id: str) -> dict:
    return recover_stale_workflow_jobs(
        db,
        worker_id=worker_id,
        job_types=_configured_job_types(),
        stale_after_seconds=int(os.getenv("DECK_WORKER_STALE_AFTER_SECONDS", "900")),
        recovery_limit=int(os.getenv("DECK_WORKER_STALE_RECOVERY_LIMIT", "25")),
    )


def process_next_durable_deck(
    db: Session, *, worker_id: str, instant_claims_enabled: bool | None = None,
) -> dict | None:
    job_types = _configured_job_types()
    if "instant_deck_generation" in job_types:
        from app.core.config import settings
        from app.services.llm.openai_provider import instant_openai_model_access_attested

        attested = instant_openai_model_access_attested(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        ) if instant_claims_enabled is None else instant_claims_enabled
        if not attested:
            # Defense in depth for alternate/local loops: never claim Instant
            # work when the canonical process attestation is unavailable. A
            # mixed-role compatibility worker may still claim provider-free work.
            job_types = job_types - {"instant_deck_generation"}
            if not job_types:
                return None
    job = claim_next_workflow_job(db, worker_id=worker_id, job_types=job_types)
    if job is None:
        return None
    return process_workflow_job(db, job.id, worker_id=worker_id)
