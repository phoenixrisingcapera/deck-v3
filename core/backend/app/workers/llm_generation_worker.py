from __future__ import annotations

import os

# Contract token: DECK_WORKER_JOB_TYPES", "llm_generation"
os.environ.setdefault("WORKER_KIND", "llm_generation")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "llm_generation,due_diligence,deck_map_analysis,market_research,media_processing,smart_edit")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
