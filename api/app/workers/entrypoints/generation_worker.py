from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "llm_generation")
if not os.getenv("DECK_WORKER_JOB_TYPES"):
    os.environ["DECK_WORKER_JOB_TYPES"] = os.environ["WORKER_KIND"]

from app.workers.entrypoints.worker_entrypoint import main

if __name__ == "__main__":
    main()
