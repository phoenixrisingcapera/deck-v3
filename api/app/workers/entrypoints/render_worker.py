from __future__ import annotations

import os

os.environ.setdefault("WORKER_KIND", "preview_render")
if not os.getenv("DECK_WORKER_JOB_TYPES"):
    os.environ["DECK_WORKER_JOB_TYPES"] = os.environ["WORKER_KIND"]


from app.workers.render_role_security import validate_render_worker_secret_contract

validate_render_worker_secret_contract()

from app.workers.entrypoints.worker_entrypoint import main

if __name__ == "__main__":
    main()
