from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


EvidenceClass = Literal[
    "COMPANY_SOURCE", "EXTERNAL_RESEARCH", "VC_INFERENCE",
    "DERIVED_CALCULATION", "MANAGEMENT_PROJECTION", "PRODUCT_KNOWLEDGE",
]
RetrievalPurpose = Literal[
    "problem_severity", "customer_buyer", "market_context", "market_size", "why_now",
    "competitor_landscape", "substitutes", "differentiation", "business_model_benchmark",
    "pricing", "customer_economics", "acquisition_dynamics", "sales_motion", "retention",
    "margins", "scalability", "capital_intensity", "regulatory_context", "defensibility",
    "comparable_outcomes", "funding_outcomes", "major_risks", "milestones",
    "investor_objections", "financial_potential", "company_fact", "company_hypothesis",
    "design_guidance", "visual_chart_guidance", "visual_diagram_guidance",
    "visual_composition_guidance", "visual_financial_guidance", "visual_market_guidance",
    "visual_rhythm_guidance", "historical_company_context",
    "investment_screening", "team_assessment", "traction_interpretation",
    "business_model_analysis", "financing_dynamics", "investment_objections",
    "portfolio_value_creation",
]


class ResearchBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_searches: int = Field(default=1, ge=0, le=6)
    max_sources: int = Field(default=3, ge=0, le=24)
    max_tokens: int = Field(default=2200, ge=0, le=16000)
    max_cost_cents: float | None = Field(default=None, gt=0)
    max_runtime_seconds: int = Field(default=90, ge=1, le=600)


class ResearchTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    purpose: RetrievalPurpose
    question: str = Field(min_length=5, max_length=600)
    required_evidence_types: list[str] = Field(default_factory=list)
    preferred_sources: list[str] = Field(default_factory=list)
    importance: Literal["critical", "high", "medium", "low"] = "medium"
    budget: ResearchBudget = Field(default_factory=ResearchBudget)


class EvidenceNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    evidence_class: EvidenceClass
    claim: str
    source_ids: list[str] = Field(default_factory=list)
    supports: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"


class CalculationNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    formula: str
    value: float
    unit: str
    assumption_ids: list[str]
    calculation_ids: list[str] = Field(default_factory=list)
    evidence_class: Literal["DERIVED_CALCULATION"] = "DERIVED_CALCULATION"


class EvidenceEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    target_id: str
    relation: Literal["SUPPORTED_BY", "DERIVED_FROM", "CONTRADICTS", "BASED_ON", "USES", "USED_BY"]


class RunResearchBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_searches: int = Field(ge=0, le=6)
    max_sources: int = Field(ge=0, le=24)
    max_tokens: int = Field(ge=0, le=64000)
    max_cost_cents: float | None = Field(default=None, gt=0)
    max_runtime_seconds: int = Field(ge=1, le=1200)
    used_searches: int = Field(default=0, ge=0)
    used_sources: int = Field(default=0, ge=0)
    used_tokens: int = Field(default=0, ge=0)
    used_cost_cents: float = Field(default=0, ge=0)
    used_runtime_seconds: int = Field(default=0, ge=0)

    def reserve(self, task: ResearchBudget) -> "RunResearchBudget":
        updated = self.model_copy(update={
            "used_searches": self.used_searches + task.max_searches,
            "used_sources": self.used_sources + task.max_sources,
            "used_tokens": self.used_tokens + task.max_tokens,
            # Cost is settled from actual usage. A task with no configured cap
            # reserves no artificial dollars while the other finite bounds
            # (searches, sources, tokens and runtime) remain enforced.
            "used_cost_cents": self.used_cost_cents + float(task.max_cost_cents or 0),
            "used_runtime_seconds": self.used_runtime_seconds + task.max_runtime_seconds,
        })
        if (updated.used_searches > updated.max_searches or updated.used_sources > updated.max_sources
                or updated.used_tokens > updated.max_tokens
                or (updated.max_cost_cents is not None and updated.used_cost_cents > updated.max_cost_cents)
                or updated.used_runtime_seconds > updated.max_runtime_seconds):
            raise ValueError("Research task exceeds the remaining run-level budget")
        return updated


class DeckSlidePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = ""
    index: int = Field(ge=1, le=40)
    role: str
    objective: str
    headline_direction: str = ""
    key_message: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    visual_primitive: str = ""
    visual_intent: str = ""
    investor_belief: str = ""
    evidence_shape: str = ""
    copy_budget_words: int = Field(default=55, ge=5, le=180)


class DeckArchitecture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["deck-architecture.v1"] = "deck-architecture.v1"
    core_thesis: str
    recommended_slide_count: int = Field(ge=1, le=40)
    rationale: str
    slides: list[DeckSlidePlan] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def count_matches_authored_slides(self) -> "DeckArchitecture":
        if self.recommended_slide_count != len(self.slides):
            raise ValueError("recommended_slide_count must equal the model-authored slide list")
        return self


class InvestmentCommitteeReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    missing_proof: list[str] = Field(default_factory=list)
    investor_objections: list[str] = Field(default_factory=list)
    recommended_changes: list[str] = Field(default_factory=list)
    advisory: list[str] = Field(default_factory=list)
    important: list[str] = Field(default_factory=list)
    critical_for_fundraising: list[str] = Field(default_factory=list)
    publication_blocking: Literal[False] = False
    next_action: str = "Produce the strongest credible deck and show what must be proven next."


class PublicCompanyDescriptor(BaseModel):
    """The only source-derived company context permitted to reach web search.

    The descriptor deliberately excludes names, metrics, customers and verbatim
    source passages. It is persisted so an operator can audit exactly what left
    the private authoring boundary.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["public-company-descriptor.v2"] = "public-company-descriptor.v2"
    category: str = Field(min_length=2, max_length=120)
    customer_type: str = Field(min_length=2, max_length=160)
    product_type: str = Field(min_length=2, max_length=180)
    industry_context: str = Field(
        default="business operations and software adoption",
        min_length=2,
        max_length=320,
    )
    geography: str = Field(default="unknown", min_length=2, max_length=80)
    industry_dimensions: list[str] = Field(default_factory=list, max_length=12)
    workflow_dimensions: list[str] = Field(default_factory=list, max_length=12)
    reporting_periods: list[str] = Field(default_factory=list, max_length=8)
    safe_for_external_search: Literal[True] = True
    excluded_private_fields: list[str] = Field(default_factory=lambda: [
        "company metrics", "customer names", "private revenue", "confidential source text",
    ])


class ResearchFindingImpact(BaseModel):
    """Model-authored decision about whether verified research changes the thesis.

    This is strategic interpretation, not a new factual lane.  Every decision
    retains the external evidence IDs that the application can validate.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    disposition: Literal["use", "reject"]
    affects: list[Literal[
        "thesis", "positioning", "market_discussion", "investor_objection",
    ]] = Field(min_length=1, max_length=4)
    explanation: str = Field(min_length=1, max_length=800)
    qualification: str = Field(min_length=1, max_length=500)


class ResearchSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai-vc-research-synthesis.v1"] = "ai-vc-research-synthesis.v1"
    category_definition: list[dict[str, Any]] = Field(default_factory=list)
    market_structure: list[dict[str, Any]] = Field(default_factory=list)
    market_attractiveness: list[dict[str, Any]] = Field(default_factory=list)
    why_now: list[dict[str, Any]] = Field(default_factory=list)
    competitors: list[dict[str, Any]] = Field(default_factory=list)
    incumbent_boundaries: list[dict[str, Any]] = Field(default_factory=list)
    customer_economics: list[dict[str, Any]] = Field(default_factory=list)
    business_model_benchmarks: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    comparables: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    strongest_findings: list[dict[str, Any]] = Field(default_factory=list)
    finding_impacts: list[ResearchFindingImpact] = Field(default_factory=list, max_length=24)


class NarrativeGapAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ai-vc-narrative-gap-analysis.v1"] = "ai-vc-narrative-gap-analysis.v1"
    investor_beliefs: list[dict[str, Any]] = Field(default_factory=list)
    supported_beliefs: list[dict[str, Any]] = Field(default_factory=list)
    externally_supported_beliefs: list[dict[str, Any]] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    source_sections_to_omit: list[str] = Field(default_factory=list)
    researched_insights_to_elevate: list[dict[str, Any]] = Field(default_factory=list)
    recommended_changes: list[str] = Field(default_factory=list)


MemoryType = Literal[
    "company_fact", "company_positioning", "accepted_strategy", "rejected_positioning",
    "investor_objection", "fundraising_goal", "brand_preference", "visual_preference",
    "research_fact",
]


class AIVCMemoryRecord(BaseModel):
    """Typed long-term memory contract; product knowledge stays outside this lane."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    company_identity: str
    deck_id: str | None = None
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=4000)
    source_artifact_id: str
    effective_period: str | None = Field(default=None, max_length=120)
    superseded_by: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    created_at: datetime | None = None
    expires_at: date | None = None


class AIVCState(TypedDict, total=False):
    schema_version: str
    deck_id: str
    operation_id: str
    company_intelligence: dict[str, Any]
    research_tasks: list[dict[str, Any]]
    external_research: dict[str, Any]
    evidence_nodes: list[dict[str, Any]]
    financial_model: dict[str, Any]
    investment_memo: dict[str, Any]
    ic_review: dict[str, Any]
    narrative_strategy: dict[str, Any]
    deck_architecture: dict[str, Any]
    narrative_gap_analysis: dict[str, Any]
    evidence_gaps: list[str]
    gaps: list[dict[str, Any]]
    research_iterations: int
    max_research_iterations: int
    additional_reasoning_calls: int
    max_additional_reasoning_calls: int
    budget_remaining_cents: float | None
    next_action: str
