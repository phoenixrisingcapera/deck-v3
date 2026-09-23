"""Workflow job-type to runtime-handler registry.

Owns: the minimal routing table from job_type to the concrete runtime module.
Must not own: business logic, persistence rules, or fallback orchestration.
Stage: dispatch seam between claimed jobs and stage runtimes.
Status: KEEP
"""

from __future__ import annotations

from collections.abc import Callable
from app.services.deck_processing.workflow_jobs import (
    JOB_TYPE_APPLY_VERSION,
    JOB_TYPE_BRAND_EXTRACTION,
    JOB_TYPE_DB_PUBLISHER,
    JOB_TYPE_EXPORT,
    JOB_TYPE_INSTANT_DECK_GENERATION,
    JOB_TYPE_LLM_GENERATION,
    JOB_TYPE_SELECTED_SLIDE_GENERATION,
    JOB_TYPE_MINIATURES,
    JOB_TYPE_PREVIEW_RENDER,
    JOB_TYPE_SCHEMA_VALIDATION,
    JOB_TYPE_SMART_DECK_CONTEXT,
    JOB_TYPE_SOURCE_EXTRACTION,
    JOB_TYPE_SOURCE_INGESTION,
    JOB_TYPE_COMPILE_FINAL_DECK,
    JOB_TYPE_DUE_DILIGENCE,
    JOB_TYPE_DECK_MAP_ANALYSIS,
    JOB_TYPE_MARKET_RESEARCH,
    JOB_TYPE_MEDIA_PROCESSING,
    JOB_TYPE_SMART_EDIT,
)

def get_workflow_job_handler(job_type: str) -> Callable[..., None] | None:
    """Resolve a workflow job type to its concrete runtime handler.

    Keep business logic out of this router; duplicate behavior should be moved
    into a service module and shared by the runtime handlers instead.
    """
    if job_type == JOB_TYPE_SOURCE_INGESTION:
        from app.workers.runtime.source_pipeline_runtime import handle_source_ingestion

        return handle_source_ingestion
    if job_type == JOB_TYPE_SOURCE_EXTRACTION:
        from app.workers.runtime.source_pipeline_runtime import handle_source_extraction

        return handle_source_extraction
    if job_type == JOB_TYPE_MINIATURES:
        from app.workers.runtime.source_pipeline_runtime import handle_miniatures

        return handle_miniatures
    if job_type == JOB_TYPE_BRAND_EXTRACTION:
        from app.workers.runtime.source_pipeline_runtime import handle_brand_extraction

        return handle_brand_extraction
    if job_type == JOB_TYPE_SMART_DECK_CONTEXT:
        from app.workers.runtime.source_pipeline_runtime import handle_smart_deck_context

        return handle_smart_deck_context
    if job_type == JOB_TYPE_LLM_GENERATION:
        from app.workers.runtime.generation_runtime import handle_llm_generation

        return handle_llm_generation
    if job_type == JOB_TYPE_INSTANT_DECK_GENERATION:
        from app.workers.runtime.generation_runtime import handle_instant_deck_generation

        return handle_instant_deck_generation
    if job_type == JOB_TYPE_SELECTED_SLIDE_GENERATION:
        from app.workers.runtime.selected_slide_generation_runtime import handle_selected_slide_generation

        return handle_selected_slide_generation
    if job_type == JOB_TYPE_SCHEMA_VALIDATION:
        from app.workers.runtime.generation_runtime import handle_schema_validation

        return handle_schema_validation
    if job_type == JOB_TYPE_PREVIEW_RENDER:
        from app.workers.runtime.generation_runtime import handle_preview_render

        return handle_preview_render
    if job_type == JOB_TYPE_APPLY_VERSION:
        from app.workers.runtime.generation_runtime import handle_apply_version

        return handle_apply_version
    if job_type == JOB_TYPE_COMPILE_FINAL_DECK:
        from app.workers.runtime.generation_runtime import handle_compile_final_deck

        return handle_compile_final_deck
    if job_type == JOB_TYPE_DB_PUBLISHER:
        from app.workers.runtime.publisher_runtime import handle_db_publisher

        return handle_db_publisher
    if job_type == JOB_TYPE_EXPORT:
        from app.workers.runtime.publisher_runtime import handle_export

        return handle_export
    if job_type == JOB_TYPE_DUE_DILIGENCE:
        from app.workers.runtime.due_diligence_runtime import handle_due_diligence

        return handle_due_diligence
    if job_type == JOB_TYPE_DECK_MAP_ANALYSIS:
        from app.workers.runtime.deck_intelligence_runtime import handle_deck_map_analysis

        return handle_deck_map_analysis
    if job_type == JOB_TYPE_MARKET_RESEARCH:
        from app.workers.runtime.deck_intelligence_runtime import handle_market_research

        return handle_market_research
    if job_type == JOB_TYPE_MEDIA_PROCESSING:
        from app.workers.runtime.media_runtime import handle_media_processing

        return handle_media_processing
    if job_type == JOB_TYPE_SMART_EDIT:
        from app.workers.runtime.smart_edit_runtime import handle_smart_edit

        return handle_smart_edit
    return None
