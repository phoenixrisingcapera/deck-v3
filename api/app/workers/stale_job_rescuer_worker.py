from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "stale_job_rescuer")

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
