"""Canonical Instant Deck processing services.

Pipeline construction is owned by ``workflow_jobs.ensure_pipeline_jobs_for_run``.
This package initializer intentionally performs no runtime monkey-patching.
"""

from app.services.deck_processing.workflow_jobs import SOURCE_PIPELINE_JOB_SEQUENCE


CANONICAL_SOURCE_PIPELINE_JOB_SEQUENCE = SOURCE_PIPELINE_JOB_SEQUENCE


__all__ = ["CANONICAL_SOURCE_PIPELINE_JOB_SEQUENCE"]
