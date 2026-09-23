from __future__ import annotations

from app.services.agents.base import AgentCapability


SMART_DECK_AGENT = AgentCapability(
    agent_key="smart_deck",
    label="Smart Deck",
    description="Generate reviewable deck or slide iterations from selected source slides.",
    execution="workflow",
    allowed_user_roles=("user", "admin", "super_admin"),
    input_schema="WorkflowGenerationRequest",
    output_schema="DesignVersion + GeneratedSlides",
    provider_use_case="smart_deck",
    persistence_target="workflow_jobs, design_versions, generated_slides, smart_deck_messages",
    review_surface="GeneratedBatchSaveCard",
    user_route="/decks/{deckId}/smart-deck",
    command_route="/api/products/deck-aistack-codes/decks/{deckId}/workflows/smart-deck-generation",
    required_input_fields=("prompt", "selectedSourceSlideIds", "idempotencyKey"),
    workflow_job_type="llm_generation",
    job_chain=("llm_generation", "schema_validation", "preview_render", "db_publisher"),
    artifact_types=("design_version", "generated_slide", "render_schema", "preview_asset"),
    debug_fields=(
        "workflowJobId",
        "artifactIds",
        "sourceFactIds",
        "selectedSourceSlideIds",
        "provider",
        "model",
        "guardrailResult",
        "schemaValidationResult",
        "previewRenderResult",
        "dbPublisherResult",
    ),
    notes=("Normal users should see Generate iteration, not worker controls.",),
)
