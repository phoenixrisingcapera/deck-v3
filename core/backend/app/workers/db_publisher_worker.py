from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "db_publisher")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "db_publisher")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
