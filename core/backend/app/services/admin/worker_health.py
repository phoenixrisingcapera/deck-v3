from __future__ import annotations

from datetime import datetime, timedelta
import os
import time

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import AgentTelemetryEvent
from app.db.session import AiSessionLocal
from app.services.admin.agent_telemetry import redact_telemetry_value

WORKER_RUN_TYPE = "deck_processing_worker"
WORKER_HEARTBEAT_EVENT = "worker_heartbeat"
WORKER_ERROR_CATEGORIES = frozenset(
    {
        "core_database_failed",
        "queue_claim_failed",
        "job_dispatch_failed",
        "job_handler_failed",
        "recovery_failed",
        "worker_cycle_failed",
    }
)


def worker_heartbeat_ttl_seconds() -> int:
    return int(os.getenv("DECK_WORKER_HEARTBEAT_TTL_SECONDS", "180"))


def _is_retryable_heartbeat_error(error: Exception) -> bool:
    message = str(error).lower()
    return "deadlock detected" in message or "lock timeout" in message or "could not serialize access" in message


def sanitize_worker_error_category(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in WORKER_ERROR_CATEGORIES else "worker_cycle_failed" if normalized else None


def _heartbeat_event(
    *,
    worker_id: str,
    status: str,
    claimed_id: str | None,
    last_claimed_job_type: str | None,
    error_category: str | None,
    metadata: dict | None,
    created_at: datetime,
) -> AgentTelemetryEvent:
    return AgentTelemetryEvent(
        id=generate_id("wkhb"),
        run_type=WORKER_RUN_TYPE,
        event_name=WORKER_HEARTBEAT_EVENT,
        event_level="error" if error_category else "info",
        status=status,
        run_id=claimed_id,
        error_message_redacted=error_category,
        metadata_json={
            **redact_telemetry_value(metadata or {}),
            "workerId": worker_id,
            "lastClaimedJobId": claimed_id,
            "lastClaimedRunId": claimed_id,
            "lastClaimedJobType": last_claimed_job_type,
        },
        created_at=created_at,
    )


def record_worker_heartbeat(
    db: Session | None = None,
    *,
    worker_id: str,
    status: str = "alive",
    last_claimed_job_id: str | None = None,
    last_claimed_run_id: str | None = None,
    last_claimed_job_type: str | None = None,
    last_error: str | None = None,
    metadata: dict | None = None,
    commit: bool = True,
) -> dict:
    del db  # Heartbeat telemetry is AI-owned and must never fall back to core DB.
    now = datetime.utcnow()
    claimed_id = last_claimed_job_id or last_claimed_run_id
    error_category = sanitize_worker_error_category(last_error)
    if not commit:
        raise ValueError("Worker heartbeat persistence cannot be disabled.")
    if not str(os.getenv("AI_DATABASE_URL", "")).strip():
        return {
            "workerId": worker_id,
            "status": status,
            "lastClaimedJobId": claimed_id,
            "lastClaimedRunId": claimed_id,
            "lastClaimedJobType": last_claimed_job_type,
            "lastError": error_category,
            "lastSeenAt": None,
        }

    telemetry_db = AiSessionLocal()
    try:
        telemetry_db.add(
            _heartbeat_event(
                worker_id=worker_id,
                status=status,
                claimed_id=claimed_id,
                last_claimed_job_type=last_claimed_job_type,
                error_category=error_category,
                metadata=metadata,
                created_at=now,
            )
        )
        for attempt in range(3):
            try:
                telemetry_db.commit()
                break
            except OperationalError as exc:
                telemetry_db.rollback()
                if not _is_retryable_heartbeat_error(exc) or attempt == 2:
                    raise
                telemetry_db.add(
                    _heartbeat_event(
                        worker_id=worker_id,
                        status=status,
                        claimed_id=claimed_id,
                        last_claimed_job_type=last_claimed_job_type,
                        error_category=error_category,
                        metadata=metadata,
                        created_at=now,
                    )
                )
                time.sleep(0.1 * (attempt + 1))
    finally:
        telemetry_db.close()
    return {
        "workerId": worker_id,
        "status": status,
        "lastClaimedJobId": claimed_id,
        "lastClaimedRunId": claimed_id,
        "lastClaimedJobType": last_claimed_job_type,
        "lastError": error_category,
        "lastSeenAt": now.isoformat(),
    }


def get_latest_worker_heartbeat(db: Session) -> dict:
    del db  # Heartbeat telemetry is AI-owned and must never fall back to core DB.
    if not str(os.getenv("AI_DATABASE_URL", "")).strip():
        return {
            "ok": False,
            "status": "missing",
            "message": "No worker heartbeat has been recorded yet.",
            "lastSeenAt": None,
            "workerId": None,
        }

    telemetry_db = AiSessionLocal()
    try:
        event = (
            telemetry_db.query(AgentTelemetryEvent)
            .filter(
                AgentTelemetryEvent.run_type == WORKER_RUN_TYPE,
                AgentTelemetryEvent.event_name == WORKER_HEARTBEAT_EVENT,
            )
            .order_by(AgentTelemetryEvent.created_at.desc())
            .first()
        )
    except OperationalError:
        telemetry_db.rollback()
        event = None
    finally:
        telemetry_db.close()
    if event is None:
        return {
            "ok": False,
            "status": "missing",
            "message": "No worker heartbeat has been recorded yet.",
            "lastSeenAt": None,
            "workerId": None,
        }

    metadata = event.metadata_json if isinstance(event.metadata_json, dict) else {}
    age_seconds = max(0, int((datetime.utcnow() - event.created_at).total_seconds()))
    stale = event.created_at < datetime.utcnow() - timedelta(seconds=worker_heartbeat_ttl_seconds())
    result = {
        "ok": not stale and event.status != "error",
        "status": "stale" if stale else event.status or "unknown",
        "message": "Worker heartbeat is fresh." if not stale else "Worker heartbeat is stale.",
        "lastSeenAt": event.created_at.isoformat(),
        "ageSeconds": age_seconds,
        "ttlSeconds": worker_heartbeat_ttl_seconds(),
        "workerId": metadata.get("workerId"),
        "lastClaimedJobId": metadata.get("lastClaimedJobId") or metadata.get("lastClaimedRunId") or event.run_id,
        "lastClaimedRunId": metadata.get("lastClaimedJobId") or metadata.get("lastClaimedRunId") or event.run_id,
        "lastClaimedJobType": metadata.get("lastClaimedJobType"),
        "lastError": event.error_message_redacted,
    }
    return result
