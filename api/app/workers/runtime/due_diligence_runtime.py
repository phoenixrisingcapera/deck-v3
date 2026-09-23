"""Durable runtime for one complete Due Diligence report command."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DiligenceReport, User, WorkflowJob
from app.services.deck_processing.deck_mutation_service import analyse_deck
from app.services.deck_processing.workflow_jobs import JOB_STATUS_COMPLETED, JOB_STATUS_TIMED_OUT, set_workflow_job_status
from app.services.llm.operation_deadline import OperationDeadline, OperationDeadlineExceeded
from app.services.platform.billing.ai_usage_quota_service import actual_tokens_from_usage, reconcile_ai_operation_budget, reserve_ai_operation_budget
from app.core.config import settings


def _report_for_job(db: Session, job: WorkflowJob) -> DiligenceReport | None:
    return (
        db.query(DiligenceReport)
        .filter(
            DiligenceReport.deck_id == job.deck_id,
            DiligenceReport.workflow_job_id == job.id,
        )
        .order_by(DiligenceReport.created_at.desc())
        .first()
    )


def handle_due_diligence(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Run canonical analysis once and correlate its immutable report to the job."""
    payload = dict(job.input_json or {})
    audience = str(payload.get("audience") or "").strip()
    if not audience:
        raise ValueError("Due Diligence audience is required")
    if payload.get("runMode") != "full_review":
        raise ValueError("Unsupported Due Diligence run mode")

    # Stale recovery can resume after report persistence but before the job's
    # final status commit. Reuse that report rather than creating history twice.
    report = _report_for_job(db, job)
    if report is None:
        user = db.get(User, job.user_id) if job.user_id else None
        if user is None:
            raise ValueError("Due Diligence job requires an owning user")
        reservation_key = f"due-diligence:{job.id}"
        reserve_ai_operation_budget(
            db,
            user,
            operation="due_diligence",
            reservation_key=reservation_key,
            estimated_tokens=120_000,
            daily_limit=settings.ai_daily_generation_quota,
        )
        deadline = OperationDeadline.after(240)
        usage: dict = {}
        try:
            analyse_deck(db, job.deck_id, audience=audience, workflow_job_id=job.id, deadline=deadline, usage_sink=usage)
        except OperationDeadlineExceeded:
            reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
            set_workflow_job_status(db, job=job, status=JOB_STATUS_TIMED_OUT, worker_id=worker_id, message="Due Diligence exceeded its operation deadline.", output_payload={"phase": "timed_out", "errorCode": "operation_deadline_exceeded"})
            db.commit()
            return
        except Exception:
            reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
            raise
        reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
        report = _report_for_job(db, job)
    if report is None:
        raise RuntimeError("Due Diligence analysis did not persist a report")
    if report.status != "completed" or report.degraded:
        raise RuntimeError("Due Diligence analysis completed without trustworthy provider output")

    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Due Diligence report persisted.",
        output_payload={
            "phase": "due_diligence_ready",
            "analysisRunId": report.analysis_run_id,
            "reportId": report.id,
            "audience": report.audience,
            "reportUrl": f"/api/products/deck-aistack-codes/decks/{job.deck_id}/due-diligence?audience={report.audience}",
        },
    )
    db.commit()
