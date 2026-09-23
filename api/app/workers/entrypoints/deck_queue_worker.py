from __future__ import annotations

import logging
import os
import signal
import socket
import time

from app.core.railway_env import apply_railway_env_aliases
from app.core.worker_startup_policy import apply_worker_identity_defaults, validate_worker_environment_before_import


apply_railway_env_aliases()
apply_worker_identity_defaults()
validate_worker_environment_before_import()

from app.db.session import SessionLocal
from app.workers.dispatch.worker_runtime_service import (
    configured_worker_job_types,
    process_next_durable_deck,
    recover_stale_processing_runs,
    worker_kind,
    worker_recovery_only,
)
from app.services.admin.worker_health import record_worker_heartbeat
from app.core.config import settings

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("deck_queue_worker")

POLL_INTERVAL_SECONDS = int(os.getenv("DECK_WORKER_POLL_INTERVAL_SECONDS", "10"))
HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS", "30"))
WORKER_ID = os.getenv("DECK_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
STOP_REQUESTED = False
LAST_HEARTBEAT_AT = 0.0
LAST_CLAIMED_JOB_ID: str | None = None
LAST_CLAIMED_JOB_TYPE: str | None = None


def _configured_job_types_csv() -> str:
    return ",".join(sorted(configured_worker_job_types()))


def _worker_kind_label() -> str:
    return worker_kind() or "worker"


def _refresh_instant_provider_attestation(*, force: bool = False) -> bool | None:
    """Own the Instant worker's passive provider-readiness lifecycle."""
    if "instant_deck_generation" not in configured_worker_job_types():
        return None
    from app.services.llm.openai_provider import (
        fail_instant_openai_model_access_attestation,
        refresh_instant_openai_model_access_attestation,
    )

    try:
        return refresh_instant_openai_model_access_attestation(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            force=force,
        )
    except Exception as exc:
        # Keep startup and polling alive even if the refresh implementation or
        # a test/runtime adapter fails outside its normal fail-closed boundary.
        return fail_instant_openai_model_access_attestation(exc)


def _request_stop(signum, frame) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    logger.info("deck_worker_stop_requested", extra={"signal": signum, "worker_id": WORKER_ID})


def _record_heartbeat(*, force: bool = False, status: str = "alive", last_error: str | None = None) -> None:
    global LAST_HEARTBEAT_AT
    now = time.monotonic()
    if not force and now - LAST_HEARTBEAT_AT < HEARTBEAT_INTERVAL_SECONDS:
        return
    try:
        record_worker_heartbeat(
            worker_id=WORKER_ID,
            status=status,
            last_claimed_job_id=LAST_CLAIMED_JOB_ID,
            last_claimed_job_type=LAST_CLAIMED_JOB_TYPE,
            last_error=last_error,
            metadata={
                "pollIntervalSeconds": POLL_INTERVAL_SECONDS,
                "configuredJobTypes": _configured_job_types_csv(),
                "workerKind": _worker_kind_label(),
            },
            commit=True,
        )
        LAST_HEARTBEAT_AT = now
    except Exception:
        logger.exception("deck_worker_heartbeat_failed", extra={"worker_id": WORKER_ID})


def _recover_stale_runs() -> dict:
    db = SessionLocal()
    try:
        result = recover_stale_processing_runs(db, worker_id=WORKER_ID)
        from app.services.llm.instant_html_operation_service import (
            reconcile_artifact_cleanup_tasks,
            purge_expired_raw_artifacts,
            reconcile_charging_operations,
            reconcile_enqueue_pending_operations,
            reconcile_release_pending_operations,
            reconcile_expired_manual_provider_operations,
        )
        result["instantHtmlChargeReconciled"] = reconcile_charging_operations(db)
        result["instantHtmlEnqueueReconciled"] = reconcile_enqueue_pending_operations(db)
        result["instantHtmlReleaseReconciled"] = reconcile_release_pending_operations(db)
        result["instantHtmlManualReconciled"] = reconcile_expired_manual_provider_operations(db)
        result["instantHtmlArtifactCleanupReconciled"] = reconcile_artifact_cleanup_tasks(
            db, worker_id="deck-queue-maintenance", limit=25
        )
        result["instantHtmlRawPurged"] = purge_expired_raw_artifacts(db)
        from app.services.rendering.export_service import reconcile_pending_export_handoffs

        result["exportHandoffsReconciled"] = reconcile_pending_export_handoffs(db, limit=10)
        return result
    except Exception:
        logger.exception("deck_worker_stale_recovery_failed", extra={"worker_id": WORKER_ID})
        return {"recovered": 0, "timedOut": 0}
    finally:
        db.close()


def run_once() -> bool:
    global LAST_CLAIMED_JOB_ID, LAST_CLAIMED_JOB_TYPE
    if worker_recovery_only():
        recovery = _recover_stale_runs()
        _record_heartbeat(force=True, status="alive")
        logger.info(
            "deck_worker_recovered_stale_jobs",
            extra={
                "worker_id": WORKER_ID,
                "recovered": recovery.get("recovered", 0),
                "timed_out": recovery.get("timedOut", 0),
            },
        )
        return False

    instant_attested = _refresh_instant_provider_attestation()

    db = SessionLocal()
    try:
        result = process_next_durable_deck(
            db, worker_id=WORKER_ID, instant_claims_enabled=instant_attested,
        )
        if result is None:
            _record_heartbeat()
            return False

        LAST_CLAIMED_JOB_ID = str(result.get("id") or "") or LAST_CLAIMED_JOB_ID
        LAST_CLAIMED_JOB_TYPE = str(result.get("jobType") or "") or LAST_CLAIMED_JOB_TYPE
        _record_heartbeat(force=True)
        logger.info(
            "deck_worker_processed_job",
            extra={
                "workflow_job_id": result.get("id"),
                "deck_id": result.get("deckId"),
                "job_type": result.get("jobType"),
                "status": result.get("status"),
                "phase": result.get("phase"),
                "worker_id": WORKER_ID,
            },
        )
        return True
    except Exception as exc:
        safe_error = "Workflow job failed; inspect the durable job state."
        _record_heartbeat(force=True, status="error", last_error=safe_error)
        logger.error("deck_worker_job_failed", extra={"worker_id": WORKER_ID, "errorType": exc.__class__.__name__})
        return False
    finally:
        db.close()


def main() -> None:
    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    provider_attested = _refresh_instant_provider_attestation(force=True)
    logger.info(
        "deck_worker_started",
        extra={
            "poll_interval_seconds": POLL_INTERVAL_SECONDS,
            "worker_id": WORKER_ID,
            "configured_job_types": _configured_job_types_csv(),
            "recovery_only": worker_recovery_only(),
            "instant_provider_attested": provider_attested,
        },
    )

    _record_heartbeat(force=True, status="started")

    while not STOP_REQUESTED:
        processed = run_once()
        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)

    _record_heartbeat(force=True, status="stopped")
    logger.info("deck_worker_stopped", extra={"worker_id": WORKER_ID})


if __name__ == "__main__":
    main()
