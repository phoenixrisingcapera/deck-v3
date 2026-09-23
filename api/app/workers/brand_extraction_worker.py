from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "brand_extraction")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "brand_extraction")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
