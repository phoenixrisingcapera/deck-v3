from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings

DECK_WORKER_JOB_TYPES = {
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "brand_extraction",
    "smart_deck_context",
    "db_publisher",
    "llm_generation",
    "instant_deck_generation",
    # COMPATIBILITY: selected-slide generation is the canonical job-type name
    # used by the current workflow contract and worker verifier.
    "selected_slide_generation",
    # DISABLED: older naming left here as a compatibility alias while the
    # runtime finishes converging on selected_slide_generation.
    "llm_parallelization",
    "schema_validation",
    "preview_render",
    "apply_version",
    "compile_final_deck",
    "export",
}

SERVICE_NAME_TO_WORKER_KIND: dict[str, str] = {
    "source_ingestion": "source_ingestion",
    "source_extraction": "source_extraction",
    "miniatures": "miniatures",
    "brand_extraction": "brand_extraction",
    "smart_deck_context": "smart_deck_context",
    "db_publisher": "db_publisher",
    "llm_generation": "llm_generation",
    "instant_deck_generation": "instant_deck_generation",
    "selected_slide_generation": "selected_slide_generation",
    "llm_parallelization": "llm_parallelization",
    "schema_validation": "schema_validation",
    "preview_render": "preview_render",
    "apply_version": "apply_version",
    "compile_final_deck": "compile_final_deck",
    "export": "export",
}

WORKER_KIND_TO_JOB_TYPE: dict[str, str] = {
    "source_ingestion": "source_ingestion",
    "source_extraction": "source_extraction",
    "miniatures": "miniatures",
    "brand_extraction": "brand_extraction",
    "smart_deck_context": "smart_deck_context",
    "db_publisher": "db_publisher",
    "llm_generation": "llm_generation",
    "instant_deck_generation": "instant_deck_generation",
    "selected_slide_generation": "selected_slide_generation",
    "llm_parallelization": "llm_parallelization",
    "schema_validation": "schema_validation",
    "preview_render": "preview_render",
    "apply_version": "apply_version",
    "compile_final_deck": "compile_final_deck",
    "export": "export",
}

DECK_WORKER_STALE_AFTER_SECONDS: int = getattr(settings, "DECK_WORKER_STALE_AFTER_SECONDS", 300)

logger = logging.getLogger(__name__)


def recover_stale_processing_runs(db: Session | None = None) -> int:
    return 0


def claim_next_processing_run(db: Session) -> dict | None:
    return None
