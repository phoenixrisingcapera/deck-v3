from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "stale_job_rescuer")
os.environ.setdefault("DECK_WORKER_RECOVERY_ONLY", "true")

from app.workers.entrypoints.worker_entrypoint import main

if __name__ == "__main__":
    main()
