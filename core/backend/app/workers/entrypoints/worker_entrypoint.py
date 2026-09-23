"""Canonical per-kind worker entrypoint.

Per-kind wrapper files (apply_version_worker.py, export_worker.py, etc.) set
WORKER_KIND and DECK_WORKER_JOB_TYPES in os.environ before importing this
module, then call main().

This avoids duplicating the import-and-call pattern in every wrapper file.
"""

from __future__ import annotations


def main() -> None:
    from app.workers.entrypoints.deck_queue_worker import main as _queue_main

    _queue_main()
