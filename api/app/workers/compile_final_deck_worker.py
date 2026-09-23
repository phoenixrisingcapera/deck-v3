from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "compile_final_deck")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "compile_final_deck")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
