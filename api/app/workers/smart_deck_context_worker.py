from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "smart_deck_context")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "smart_deck_context")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
