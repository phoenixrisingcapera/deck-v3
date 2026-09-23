from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import SmartEditRun, User, WorkflowJob
from app.services.deck_processing.workflow_jobs import JOB_STATUS_COMPLETED, JOB_STATUS_TIMED_OUT, set_workflow_job_status
from app.services.llm.operation_deadline import OperationDeadline, OperationDeadlineExceeded
from app.services.llm.smart_edit_service import execute_reviewable_smart_edit_patch
from app.services.platform.billing.ai_usage_quota_service import actual_tokens_from_usage, reconcile_ai_operation_budget, reserve_ai_operation_budget
from app.core.config import settings


def handle_smart_edit(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    run_id = str((job.input_json or {}).get("runId") or "")
    if not run_id:
        raise ValueError("Smart Edit job requires runId")
    # A persisted terminal result wins before any new reservation/provider work.
    existing_run = db.query(SmartEditRun).filter(SmartEditRun.id == run_id).one()
    if existing_run.status in {"completed", "no_change", "accepted", "rejected", "applied"}:
        result = execute_reviewable_smart_edit_patch(db, run_id=run_id)
        set_workflow_job_status(db, job=job, status=JOB_STATUS_COMPLETED, worker_id=worker_id, message="Smart Edit result persisted.", output_payload={"runId": run_id, "suggestionId": result.get("suggestionId"), "artifactId": result.get("artifactId"), "resultStatus": existing_run.status})
        db.commit()
        return
    user = db.get(User, job.user_id) if job.user_id else None
    if user is None:
        raise ValueError("Smart Edit job requires an owning user")
    reservation_key = f"smart-edit:{job.id}"
    reserve_ai_operation_budget(db, user, operation="smart_edit", reservation_key=reservation_key, estimated_tokens=40_000, daily_limit=settings.ai_daily_generation_quota)
    deadline = OperationDeadline.after(240)
    usage: dict = {}
    try:
        result = execute_reviewable_smart_edit_patch(db, run_id=run_id, deadline=deadline, usage_sink=usage)
    except OperationDeadlineExceeded:
        reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
        run = db.query(SmartEditRun).filter(SmartEditRun.id == run_id).one()
        run.status = "timed_out"
        run.error_code = "operation_deadline_exceeded"
        run.error_message = "Smart Edit exceeded its operation deadline."
        set_workflow_job_status(db, job=job, status=JOB_STATUS_TIMED_OUT, worker_id=worker_id, message=run.error_message, output_payload={"runId": run_id, "phase": "timed_out"})
        db.commit()
        return
    except Exception:
        reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
        raise
    reconcile_ai_operation_budget(db, reservation_key=reservation_key, actual_tokens=actual_tokens_from_usage(usage))
    run = db.query(SmartEditRun).filter(SmartEditRun.id == run_id).one()
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_COMPLETED,
        worker_id=worker_id,
        message="Smart Edit result persisted.",
        output_payload={
            "runId": run_id,
            "suggestionId": result.get("suggestionId"),
            "artifactId": result.get("artifactId"),
            "resultStatus": run.status,
        },
    )
    db.commit()
