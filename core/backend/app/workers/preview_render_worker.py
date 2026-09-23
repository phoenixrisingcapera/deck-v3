from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "preview_render")
os.environ.setdefault("DECK_WORKER_JOB_TYPES", "preview_render")

from app.workers.render_role_security import validate_render_worker_secret_contract

validate_render_worker_secret_contract()

from app.workers.entrypoints.deck_queue_worker import main

if __name__ == "__main__":
    main()
