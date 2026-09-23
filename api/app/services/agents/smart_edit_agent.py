from __future__ import annotations

from app.services.agents.base import AgentCapability


SMART_EDIT_AGENT = AgentCapability(
    agent_key="smart_edit",
    label="Smart Edit",
    description="Refine an existing generated slide or selected element with a focused instruction.",
    execution="variation_job",
    allowed_user_roles=("user", "admin", "super_admin"),
    input_schema="SmartEditCreate or ElementVariationJobRequest",
    output_schema="SmartEditSuggestion or ElementVersion/DesignVersion",
    provider_use_case="smart_edit",
    persistence_target="smart_edit_runs, smart_edit_suggestions, generated_slide_element_versions, design_versions",
    review_surface="Smart Edit suggestion card / GeneratedBatchSaveCard",
    user_route="/decks/{deckId}/smart-edit",
    command_route="/api/decks/{deckId}/generated-slides/{generatedSlideId}/elements/{elementId}/variation-jobs",
    required_input_fields=("generatedSlideId", "selectedElementId", "instruction"),
    workflow_job_type=None,
    artifact_types=("smart_edit_suggestion", "element_version", "design_version"),
    debug_fields=("generatedSlideId", "selectedElementId", "designVersionId", "provider", "model", "guardrailResult"),
    notes=(
        "Legacy block suggestion route remains /api/decks/{deckId}/smart-edit.",
        "Generated slide element edits should use the element variation endpoint.",
    ),
)
