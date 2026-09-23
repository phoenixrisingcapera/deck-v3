from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "source_extraction")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "source_extraction")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
