from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Deck, DesignVersion, WorkflowJob, WorkflowJobDependency
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.workflow_orchestration import queue_source_extraction
from app.services.admin.readiness_diagnostics import get_smart_deck_readiness
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_BLOCKED,
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_RUNNING,
    JOB_STATUS_QUEUED,
    JOB_STATUS_COMPLETED,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_SCHEMA_VALIDATION,
    set_workflow_job_status,
)


def retry_deck_processing(db: Session, deck_id: str, *, requested_by_user_id: str | None) -> dict[str, Any] | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None
    readiness_before = get_smart_deck_readiness(db, deck_id)
    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=requested_by_user_id)
    readiness_after = get_smart_deck_readiness(db, deck_id)
    return {
        "deckId": deck_id,
        "action": "retry_processing",
        "changed": True,
        "accepted": accepted,
        "readinessBefore": readiness_before,
        "readinessAfter": readiness_after,
        "message": "Deck processing was requeued through the canonical source pipeline.",
    }


def prepare_smart_deck(db: Session, deck_id: str, *, requested_by_user_id: str | None) -> dict[str, Any] | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None
    readiness_before = get_smart_deck_readiness(db, deck_id)
    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=requested_by_user_id)
    readiness_after = get_smart_deck_readiness(db, deck_id)
    return {
        "deckId": deck_id,
        "action": "prepare_smart_deck",
        "changed": True,
        "accepted": accepted,
        "readinessBefore": readiness_before,
        "readinessAfter": readiness_after,
        "message": "Smart Deck preparation was requeued through the canonical source pipeline.",
    }


def repair_missing_artifacts(db: Session, deck_id: str, *, requested_by_user_id: str | None) -> dict[str, Any] | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None
    readiness_before = get_smart_deck_readiness(db, deck_id)
    workflow_before = get_deck_workflow_state(db, deck_id) or {}
    missing_before = list(workflow_before.get("missingArtifacts") or [])
    if not missing_before:
        return {
            "deckId": deck_id,
            "action": "repair_missing_artifacts",
            "changed": False,
            "accepted": None,
            "missingArtifactsBefore": [],
            "missingArtifactsAfter": [],
            "readinessBefore": readiness_before,
            "readinessAfter": readiness_before,
            "message": "No missing workflow artifacts were detected for this deck.",
        }
    accepted = queue_source_extraction(db, deck_id, requested_by_user_id=requested_by_user_id)
    readiness_after = get_smart_deck_readiness(db, deck_id)
    workflow_after = get_deck_workflow_state(db, deck_id) or {}
    return {
        "deckId": deck_id,
        "action": "repair_missing_artifacts",
        "changed": True,
        "accepted": accepted,
        "missingArtifactsBefore": missing_before,
        "missingArtifactsAfter": list(workflow_after.get("missingArtifacts") or []),
        "readinessBefore": readiness_before,
        "readinessAfter": readiness_after,
        "message": "Missing workflow artifacts triggered a source pipeline repair run.",
    }


def requeue_stale_deck_jobs(db: Session, deck_id: str, *, requested_by_user_id: str | None) -> dict[str, Any] | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None
    readiness_before = get_smart_deck_readiness(db, deck_id)
    stale_after_seconds = int(os.getenv("DECK_WORKER_STALE_AFTER_SECONDS", "900"))
    cutoff = datetime.utcnow() - timedelta(seconds=stale_after_seconds)
    worker_id = f"admin:{requested_by_user_id or 'system'}"
    recovered_job_ids: list[str] = []

    jobs = (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.status == JOB_STATUS_RUNNING,
        )
        .order_by(WorkflowJob.heartbeat_at.asc().nullsfirst(), WorkflowJob.created_at.asc())
        .all()
    )
    for job in jobs:
        heartbeat = job.heartbeat_at or job.updated_at or job.started_at or job.created_at
        lease_expired = job.locked_until is not None and job.locked_until <= datetime.utcnow()
        heartbeat_expired = heartbeat is not None and heartbeat <= cutoff
        if not lease_expired and not heartbeat_expired:
            continue
        output_payload = dict(job.output_json or {})
        output_payload.update(
            {
                "staleRecoveredAt": datetime.utcnow().isoformat(),
                "staleRecoveredBy": worker_id,
                "previousLockedBy": job.locked_by,
                "recoveryReason": "admin_requeue_stale_deck_jobs",
            }
        )
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_QUEUED,
            message="Admin requeued stale workflow job for deck recovery.",
            output_payload=output_payload,
        )
        recovered_job_ids.append(job.id)

    if recovered_job_ids:
        db.commit()

    readiness_after = get_smart_deck_readiness(db, deck_id)
    return {
        "deckId": deck_id,
        "action": "requeue_stale_jobs",
        "changed": bool(recovered_job_ids),
        "recoveredJobIds": recovered_job_ids,
        "recoveredJobCount": len(recovered_job_ids),
        "readinessBefore": readiness_before,
        "readinessAfter": readiness_after,
        "message": (
            "Stale workflow jobs were requeued for this deck."
            if recovered_job_ids
            else "No stale running workflow jobs were found for this deck."
        ),
    }


def recover_dependency_output_job(
    db: Session,
    deck_id: str,
    job_id: str,
    *,
    requested_by_user_id: str | None,
) -> dict[str, Any] | None:
    # Serialize recovery per deck and lock the target so a worker cannot claim
    # it between eligibility validation and the queued transition.
    deck = db.query(Deck).filter(Deck.id == deck_id).with_for_update().one_or_none()
    job = (
        db.query(WorkflowJob)
        .filter(WorkflowJob.id == job_id, WorkflowJob.deck_id == deck_id)
        .with_for_update()
        .one_or_none()
    )
    if deck is None or job is None:
        return None

    base = {
        "deckId": deck_id,
        "jobId": job.id,
        "jobType": job.job_type,
        "action": "recover_dependency_output",
        "changed": False,
    }

    required_dependency_types = {
        JOB_TYPE_SCHEMA_VALIDATION: (JOB_TYPE_LLM_GENERATION, JOB_TYPE_INSTANT_DECK_GENERATION),
        JOB_TYPE_PREVIEW_RENDER: JOB_TYPE_SCHEMA_VALIDATION,
    }
    required_dependency_type = required_dependency_types.get(job.job_type)
    if (
        job.status != JOB_STATUS_BLOCKED
        or job.error_code != "dependency_output_missing"
        or required_dependency_type is None
    ):
        return {
            **base,
            "reason": "job_not_eligible",
            "message": "Only blocked schema-validation or preview-render jobs with dependency_output_missing can be recovered.",
        }

    dependencies = db.query(WorkflowJobDependency).filter(WorkflowJobDependency.job_id == job.id).all()
    required_upstreams: list[WorkflowJob] = []
    required_dependency_job_types = required_dependency_type if isinstance(required_dependency_type, tuple) else (required_dependency_type,)
    for dependency in dependencies:
        candidate = (
            db.query(WorkflowJob)
            .filter(WorkflowJob.id == dependency.depends_on_job_id)
            .with_for_update()
            .one_or_none()
        )
        if candidate is None:
            return {
                **base,
                "reason": "required_dependency_missing",
                "message": "A required workflow dependency is missing; manual review is required.",
            }
        if candidate.deck_id != deck_id:
            return {
                **base,
                "reason": "cross_deck_upstream_job",
                "upstreamJobId": candidate.id,
                "message": "A required upstream workflow job belongs to another deck and cannot be recovered here.",
            }
        if candidate.status != JOB_STATUS_COMPLETED:
            return {
                **base,
                "reason": "required_dependency_incomplete",
                "upstreamJobId": candidate.id,
                "upstreamStatus": candidate.status,
                "message": "A required upstream job has not completed; manual review is required.",
            }
        if candidate.job_type in required_dependency_job_types:
            required_upstreams.append(candidate)

    if not required_upstreams:
        return {
            **base,
            "reason": "required_dependency_missing",
            "message": f"The required {'/'.join(required_dependency_job_types)} dependency is still missing; manual review is required.",
        }
    if len(required_upstreams) != 1:
        return {
            **base,
            "reason": "ambiguous_required_dependencies",
            "upstreamJobIds": [candidate.id for candidate in required_upstreams],
            "message": "Multiple completed upstream jobs match the required dependency; manual review is required.",
        }
    upstream = required_upstreams[0]

    design_version_id = str((upstream.output_json or {}).get("designVersionId") or "").strip()
    if not design_version_id:
        return {
            **base,
            "reason": "dependency_output_still_missing",
            "upstreamJobId": upstream.id,
            "message": "The completed upstream job still has no designVersionId; manual review is required.",
        }

    design_version = db.query(DesignVersion).filter(DesignVersion.id == design_version_id).one_or_none()
    if design_version is None:
        return {
            **base,
            "reason": "design_version_not_found",
            "upstreamJobId": upstream.id,
            "designVersionId": design_version_id,
            "message": "The upstream designVersionId does not identify a persisted design version; manual review is required.",
        }
    if design_version.deck_id != deck_id:
        return {
            **base,
            "reason": "cross_deck_design_version",
            "upstreamJobId": upstream.id,
            "designVersionId": design_version_id,
            "message": "The upstream design version belongs to another deck and cannot be recovered here.",
        }

    active_jobs = (
        db.query(WorkflowJob)
        .filter(
            WorkflowJob.deck_id == deck_id,
            WorkflowJob.job_type == job.job_type,
            WorkflowJob.id != job.id,
            WorkflowJob.status.in_((JOB_STATUS_QUEUED, JOB_STATUS_RUNNING, JOB_STATUS_FAILED_RETRYABLE)),
        )
        .with_for_update()
        .all()
    )
    for active_job in active_jobs:
        active_dependencies = (
            db.query(WorkflowJobDependency)
            .filter(WorkflowJobDependency.job_id == active_job.id)
            .all()
        )
        for active_dependency in active_dependencies:
            active_upstream = (
                db.query(WorkflowJob)
                .filter(WorkflowJob.id == active_dependency.depends_on_job_id)
                .one_or_none()
            )
            if (
                active_upstream is not None
                and active_upstream.job_type in required_dependency_job_types
                and str((active_upstream.output_json or {}).get("designVersionId") or "").strip() == design_version_id
            ):
                return {
                    **base,
                    "reason": "equivalent_job_active",
                    "activeJobId": active_job.id,
                    "designVersionId": design_version_id,
                    "message": "An equivalent downstream job is already active for this design version.",
                }

    worker_id = f"admin:{requested_by_user_id or 'system'}"
    recovered_at = datetime.utcnow()
    recovery_count = int(job.recovery_count or 0) + 1
    output_payload = dict(job.output_json or {})
    output_payload.update(
        {
            "phase": "schema_validation_queued" if job.job_type == JOB_TYPE_SCHEMA_VALIDATION else "preview_render_queued",
            "dependencyOutputRecoveredAt": recovered_at.isoformat(),
            "dependencyOutputRecoveredBy": worker_id,
            "dependencyOutputRecoveryCount": recovery_count,
            "recoveredDesignVersionId": design_version_id,
            "recoveredFromJobId": upstream.id,
        }
    )
    job.error_code = None
    job.error_message = None
    job.recovery_count = recovery_count
    job.last_recovered_at = recovered_at
    job.last_recovered_by = worker_id
    set_workflow_job_status(
        db,
        job=job,
        status=JOB_STATUS_QUEUED,
        message="Admin requeued workflow job after validating recovered dependency output.",
        output_payload=output_payload,
    )
    # The route adds the security audit record before committing this workflow
    # transition so both pieces of evidence are atomic.
    db.flush()
    db.refresh(job)
    return {
        **base,
        "changed": True,
        "reason": "dependency_output_recovered",
        "status": job.status,
        "upstreamJobId": upstream.id,
        "designVersionId": design_version_id,
        "recoveryCount": recovery_count,
        "message": "Dependency output was validated and the blocked workflow job was requeued.",
    }
