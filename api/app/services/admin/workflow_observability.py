from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import WorkflowJob, WorkflowJobArtifact
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
    list_workflow_jobs_for_deck,
    workflow_job_phase,
)

CLAIMABLE_JOB_STATUSES = {JOB_STATUS_QUEUED, JOB_STATUS_FAILED_RETRYABLE}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _job_error(job: dict[str, Any]) -> dict[str, Any] | None:
    error = job.get("error")
    return error if isinstance(error, dict) and error else None


def _job_summary(job: WorkflowJob) -> dict[str, Any]:
    output = job.output_json if isinstance(job.output_json, dict) else {}
    return {
        "jobId": job.id,
        "jobType": job.job_type,
        "status": job.status,
        "phase": workflow_job_phase(job.job_type, job.status, output_payload=output),
        "attemptCount": int(job.attempt_count or 0),
        "maxAttempts": int(job.max_attempts or 0),
        "queuedAt": job.queued_at.isoformat() if job.queued_at else None,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "heartbeatAt": job.heartbeat_at.isoformat() if job.heartbeat_at else None,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
        "failedAt": job.failed_at.isoformat() if job.failed_at else None,
        "workerId": job.locked_by,
        "error": (
            {
                "code": job.error_code or f"{job.job_type}_failed",
                "message": job.error_message,
                "recoverable": job.status == JOB_STATUS_FAILED_RETRYABLE,
            }
            if job.error_message
            else None
        ),
    }


def _queue_position(active_job: dict[str, Any] | None, jobs: list[WorkflowJob]) -> int | None:
    if not isinstance(active_job, dict):
        return None
    job_id = str(active_job.get("jobId") or "")
    if not job_id:
        return None
    active_model = next((job for job in jobs if job.id == job_id), None)
    if active_model is None or active_model.status not in CLAIMABLE_JOB_STATUSES:
        return None

    earlier = 0
    active_created = active_model.created_at
    for job in jobs:
        if job.id == active_model.id or job.job_type != active_model.job_type or job.status not in CLAIMABLE_JOB_STATUSES:
            continue
        if job.created_at <= active_created:
            earlier += 1
    return earlier


def _latest_job_by_type(jobs: list[WorkflowJob]) -> dict[str, WorkflowJob]:
    latest: dict[str, WorkflowJob] = {}
    for job in jobs:
        latest.setdefault(job.job_type, job)
    return latest


def _surface_status(job: WorkflowJob | None, *, ready_phases: set[str] | None = None) -> dict[str, Any]:
    if job is None:
        return {"status": "pending", "phase": None, "jobId": None, "error": None}
    summary = _job_summary(job)
    phase = str(summary.get("phase") or "")
    status = "ready" if ready_phases and phase in ready_phases else str(summary.get("status") or "pending")
    return {
        "status": status,
        "phase": phase or None,
        "jobId": summary["jobId"],
        "workerId": summary["workerId"],
        "error": summary["error"],
        "attemptCount": summary["attemptCount"],
        "maxAttempts": summary["maxAttempts"],
    }


def get_admin_deck_workflow_processing(db: Session, deck_id: str) -> dict[str, Any] | None:
    workflow = get_deck_workflow_state(db, deck_id)
    if workflow is None:
        return None

    jobs = list_workflow_jobs_for_deck(db, deck_id)
    latest_by_type = _latest_job_by_type(jobs)
    latest_jobs = [_job_summary(job) for job in jobs[:25]]
    latest_jobs.sort(key=lambda item: _parse_dt(item.get("queuedAt")) or datetime.min, reverse=True)

    active_job = workflow.get("activeJob") if isinstance(workflow.get("activeJob"), dict) else None
    failed_jobs = [job for job in latest_jobs if _job_error(job)]
    last_error = failed_jobs[0]["error"] if failed_jobs else None

    artifacts = (
        db.query(WorkflowJobArtifact)
        .filter(WorkflowJobArtifact.deck_id == deck_id)
        .order_by(WorkflowJobArtifact.created_at.desc())
        .limit(50)
        .all()
    )
    artifact_counts: dict[str, int] = {}
    for artifact in artifacts:
        artifact_counts[artifact.artifact_type] = artifact_counts.get(artifact.artifact_type, 0) + 1

    pipeline = {
        job_type: _job_summary(job)
        for job_type, job in latest_by_type.items()
    }

    return {
        "deckId": deck_id,
        "workflowId": workflow.get("workflowId"),
        "status": workflow.get("status"),
        "phase": workflow.get("phase"),
        "nextAction": workflow.get("nextAction"),
        "blockingReason": workflow.get("blockingReason"),
        "worker": {
            "currentJobId": active_job.get("jobId") if active_job else None,
            "currentJobType": active_job.get("jobType") if active_job else None,
            "currentWorkerId": active_job.get("workerId") if active_job else None,
        },
        "queue": {
            "position": _queue_position(active_job, jobs),
            "claimableCount": sum(1 for job in jobs if job.status in CLAIMABLE_JOB_STATUSES),
            "runningCount": sum(1 for job in jobs if job.status == JOB_STATUS_RUNNING),
        },
        "lastError": last_error,
        "artifactStatus": {
            "status": "ready" if artifact_counts else "pending",
            "artifactCounts": artifact_counts,
        },
        "brandStatus": _surface_status(latest_by_type.get("brand_extraction"), ready_phases={"source_ready"}),
        "miniatureStatus": _surface_status(latest_by_type.get("miniatures"), ready_phases={"source_ready"}),
        "llmStatus": _surface_status(
            latest_by_type.get("instant_deck_generation") or latest_by_type.get("llm_generation"),
            ready_phases={"generation_running", "preview_ready"},
        ),
        "chatStatus": {
            "status": "ready" if bool((workflow.get("smartDeck") or {}).get("ready")) else "pending",
            "workspaceId": (workflow.get("smartDeck") or {}).get("workspaceId"),
        },
        "visualizerStatus": _surface_status(latest_by_type.get("preview_render"), ready_phases={"preview_ready"}),
        "exportStatus": _surface_status(latest_by_type.get("export"), ready_phases={"export_ready"}),
        "pipeline": pipeline,
        "latestJobs": latest_jobs,
        "workflowState": workflow,
    }
