from __future__ import annotations

import logging
import os
import time
from typing import Any

from app.core.worker_startup_policy import apply_worker_identity_defaults, validate_worker_environment_before_import

apply_worker_identity_defaults()
validate_worker_environment_before_import()

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.admin.worker_health import record_worker_heartbeat
from app.services.deck_processing_worker_service import recover_stale_processing_runs
from app.workers.dispatch.worker_runtime_service import process_next_durable_deck as process_next_workflow_job

logger = logging.getLogger(__name__)

DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS", "30"))


def process_next_durable_deck(
    *,
    worker_kind: str = "default",
    worker_recovery_only: bool = False,
) -> dict[str, Any] | None:
    # COMPATIBILITY: this legacy module used to return a placeholder without
    # touching the durable queue. Delegate to the canonical dispatcher used by
    # scripts/deck_processing_worker.py so old imports cannot silently pretend
    # to process work. New deployments must continue using that script.
    if worker_recovery_only:
        return {"workerKind": worker_kind, "recoveryOnly": True}
    db = SessionLocal()
    try:
        return process_next_workflow_job(db, worker_id=f"legacy-{worker_kind}")
    finally:
        db.close()


# COMPATIBILITY: the removed DurableWorkerBase made this legacy module
# unimportable. Preserve a small adapter for old imports while delegating every
# queue claim to the canonical dispatcher above.
class DeckQueueWorker:
    def __init__(self, *, worker_kind: str = "default", worker_recovery_only: bool = False) -> None:
        self.worker_kind = worker_kind
        self.worker_recovery_only = worker_recovery_only

    def run(self) -> None:
        while True:
            process_next_durable_deck(worker_kind=self.worker_kind, worker_recovery_only=self.worker_recovery_only)
            recover_stale_processing_runs()
            time.sleep(settings.DECK_WORKER_POLL_INTERVAL_SECONDS)
