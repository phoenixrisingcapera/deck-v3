from __future__ import annotations

from app.services.agents.base import AgentCapability


INSTANT_DECK_AGENT = AgentCapability(
    agent_key="instant_deck",
    label="Instant Deck",
    description="Run an instant whole-deck investor-ready redesign from the canonical Smart Deck workflow.",
    execution="workflow",
    allowed_user_roles=("user", "admin", "super_admin"),
    input_schema="WorkflowGenerationRequest",
    output_schema="DesignVersion + GeneratedSlides",
    provider_use_case="smart_deck",
    persistence_target="workflow_jobs, design_versions, generated_slides, smart_deck_messages",
    review_surface="GeneratedBatchSaveCard",
    user_route="/decks/{deckId}/instant-deck",
    command_route="/api/products/deck-aistack-codes/decks/{deckId}/workflows/smart-deck-generation",
    required_input_fields=("prompt", "selectedSourceSlideIds", "idempotencyKey", "generationMode"),
    workflow_job_type="instant_deck_generation",
    job_chain=("instant_deck_generation", "schema_validation", "preview_render", "db_publisher"),
    artifact_types=("design_version", "generated_slide", "render_schema", "preview_asset"),
    debug_fields=(
        "workflowJobId",
        "artifactIds",
        "selectedSourceSlideIds",
        "provider",
        "model",
        "generationMode",
        "schemaValidationResult",
        "previewRenderResult",
        "dbPublisherResult",
    ),
    notes=(
        "Instant Deck remains a compatibility redirect into canonical Smart Deck.",
        "Deploy worker-instant-deck-generation if Instant Deck should have its own Railway worker service boundary.",
    ),
)
