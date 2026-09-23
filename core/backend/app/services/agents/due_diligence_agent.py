from __future__ import annotations

from app.services.agents.base import AgentCapability


DUE_DILIGENCE_AGENT = AgentCapability(
    agent_key="due_diligence",
    label="Due Diligence",
    description="Analyze a deck or selected slides and return structured risks, evidence, questions, and IC memo notes.",
    execution="analysis_run",
    allowed_user_roles=("user", "admin", "super_admin"),
    input_schema="DueDiligenceRunRequest",
    output_schema="DueDiligenceWorkspacePayload / structured findings",
    provider_use_case="due_diligence",
    persistence_target="analysis_runs, findings, deck_llm_artifacts",
    review_surface="Due Diligence findings panel",
    user_route="/decks/{deckId}/due-diligence",
    command_route="/api/products/deck-aistack-codes/decks/{deckId}/due-diligence/run",
    required_input_fields=("scope", "question_or_module", "idempotencyKey"),
    workflow_job_type=None,
    artifact_types=("analysis_run", "finding", "source_evidence"),
    debug_fields=("runId", "jobId", "sourceSlideIds", "sourceFactIds", "provider", "model", "guardrailResult"),
    notes=("Due Diligence must not mark the deck READY or mutate generated slides.",),
)
