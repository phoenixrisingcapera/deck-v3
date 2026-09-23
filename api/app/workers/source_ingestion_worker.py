from __future__ import annotations

import os

# COMPATIBILITY ENTRYPOINT: keep the legacy worker filename alive for Railway
# wiring and structural verifiers while delegating all real work to the shared
# entrypoint module.
os.environ.setdefault("WORKER_KIND", "source_ingestion")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "source_ingestion")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
