from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


DueDiligenceAudience = Literal[
    "seed_vc",
    "series_a_vc",
    "growth_equity",
    "angel",
    "corporate",
    "lp",
    "investment_committee",
    "family_office",
    "fund_partner",
    "institutional",
]


class DueDiligenceDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    score: float
    status: str
    findings: list[str] = Field(default_factory=list)


class DueDiligenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    claimText: str = Field(
        default="",
        alias="claim_text",
        validation_alias=AliasChoices("claimText", "claim_text"),
        serialization_alias="claim_text",
    )
    claimType: str = Field(
        default="evidence_gap",
        alias="claim_type",
        validation_alias=AliasChoices("claimType", "claim_type"),
        serialization_alias="claim_type",
    )
    slideId: str | None = Field(
        default=None,
        alias="slide_id",
        validation_alias=AliasChoices("slideId", "slide_id"),
        serialization_alias="slide_id",
    )
    slideTitle: str | None = Field(
        default=None,
        alias="slide_title",
        validation_alias=AliasChoices("slideTitle", "slide_title"),
        serialization_alias="slide_title",
    )
    blockId: str | None = None
    fieldKey: str | None = None
    findingDetail: str | None = None
    evidence: dict[str, Any] | None = None
    validationVerdict: str | None = None
    evidenceStatus: str = Field(
        default="missing",
        alias="evidence_status",
        validation_alias=AliasChoices("evidenceStatus", "evidence_status"),
        serialization_alias="evidence_status",
    )
    riskLevel: Literal["high", "medium", "low"] = Field(
        default="low",
        alias="risk_level",
        validation_alias=AliasChoices("riskLevel", "risk_level"),
        serialization_alias="risk_level",
    )
    confidence: float = 0.45
    recommendedAction: str = Field(
        default="verify",
        alias="recommended_action",
        validation_alias=AliasChoices("recommendedAction", "recommended_action"),
        serialization_alias="recommended_action",
    )


class AudienceFit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: str
    fitScore: int = Field(
        default=0,
        alias="fit_score",
        validation_alias=AliasChoices("fitScore", "fit_score"),
        serialization_alias="fit_score",
    )
    strengths: list[str] = Field(default_factory=list, validation_alias=AliasChoices("strengths"))
    weaknesses: list[str] = Field(default_factory=list, validation_alias=AliasChoices("weaknesses"))
    likelyQuestions: list[str] = Field(
        default_factory=list,
        alias="likely_questions",
        validation_alias=AliasChoices("likelyQuestions", "likely_questions"),
        serialization_alias="likely_questions",
    )


class DueDiligenceIcmemo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis: str
    reasonsToBelieve: list[str] = Field(
        default_factory=list,
        alias="reasons_to_believe",
        validation_alias=AliasChoices("reasonsToBelieve", "reasons_to_believe"),
        serialization_alias="reasons_to_believe",
    )
    mainRisks: list[str] = Field(
        default_factory=list,
        alias="main_risks",
        validation_alias=AliasChoices("mainRisks", "main_risks"),
        serialization_alias="main_risks",
    )
    recommendation: str = Field(alias="recommendation")


class DueDiligenceLpView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fundReturnPotential: Literal["low", "medium", "high"] = Field(
        alias="fund_return_potential",
        validation_alias=AliasChoices("fundReturnPotential", "fund_return_potential"),
        serialization_alias="fund_return_potential",
    )
    portfolioFit: Literal["low", "medium", "strong", "high"] = Field(
        alias="portfolio_fit",
        validation_alias=AliasChoices("portfolioFit", "portfolio_fit"),
        serialization_alias="portfolio_fit",
    )
    followOnReservePressure: Literal["low", "medium", "high"] = Field(
        alias="follow_on_reserve_pressure",
        validation_alias=AliasChoices("followOnReservePressure", "follow_on_reserve_pressure"),
        serialization_alias="follow_on_reserve_pressure",
    )
    exitPathwayClarity: Literal["low", "medium", "high"] = Field(
        alias="exit_pathway_clarity",
        validation_alias=AliasChoices("exitPathwayClarity", "exit_pathway_clarity"),
        serialization_alias="exit_pathway_clarity",
    )
    concern: str | None = None


class DueDiligenceRiskItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: str
    category: str
    severity: Literal["high", "medium", "low"]
    evidence: str
    mitigation: str


class DueDiligenceMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    version: str | None = None
    source: str | None = None


class DueDiligenceWorkspacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    class AnalysisRunSummary(BaseModel):
        model_config = ConfigDict(extra="forbid")

        id: str
        status: str
        reportId: str | None = None
        audience: str | None = None
        degraded: bool = False
        provider: str | None = None
        model: str | None = None
        promptVersion: str | None = None
        validationVerdict: str | None = None
        createdAt: str = Field(
            alias="created_at",
            validation_alias=AliasChoices("createdAt", "created_at"),
            serialization_alias="created_at",
        )

    deckId: str = Field(
        alias="deck_id",
        validation_alias=AliasChoices("deckId", "deck_id"),
        serialization_alias="deck_id",
    )
    runId: str | None = Field(
        default=None,
        alias="run_id",
        validation_alias=AliasChoices("runId", "run_id"),
        serialization_alias="run_id",
    )
    analysisRunCount: int = Field(
        default=0,
        alias="analysis_run_count",
        validation_alias=AliasChoices("analysisRunCount", "analysis_run_count"),
        serialization_alias="analysis_run_count",
    )
    latestAnalysisRunAt: str | None = Field(
        default=None,
        alias="latest_analysis_run_at",
        validation_alias=AliasChoices("latestAnalysisRunAt", "latest_analysis_run_at"),
        serialization_alias="latest_analysis_run_at",
    )
    recentAnalysisRuns: list[AnalysisRunSummary] = Field(
        default_factory=list,
        alias="recent_analysis_runs",
        validation_alias=AliasChoices("recentAnalysisRuns", "recent_analysis_runs"),
        serialization_alias="recent_analysis_runs",
    )
    status: str
    selectedAudience: str = Field(
        alias="selected_audience",
        validation_alias=AliasChoices("selectedAudience", "selected_audience"),
        serialization_alias="selected_audience",
    )
    summary: dict
    domains: list[DueDiligenceDomain] = Field(default_factory=list)
    claims: list[DueDiligenceClaim] = Field(default_factory=list)
    audienceFit: AudienceFit = Field(
        alias="audience_fit",
        validation_alias=AliasChoices("audienceFit", "audience_fit"),
        serialization_alias="audience_fit",
    )
    icMemo: DueDiligenceIcmemo = Field(
        alias="ic_memo",
        validation_alias=AliasChoices("icMemo", "ic_memo"),
        serialization_alias="ic_memo",
    )
    lpView: DueDiligenceLpView = Field(
        alias="lp_view",
        validation_alias=AliasChoices("lpView", "lp_view"),
        serialization_alias="lp_view",
    )
    riskRegister: list[DueDiligenceRiskItem] = Field(
        default_factory=list,
        alias="risk_register",
        validation_alias=AliasChoices("riskRegister", "risk_register"),
        serialization_alias="risk_register",
    )
    diligenceWorkspace: dict[str, Any] | None = Field(
        default=None,
        alias="diligence_workspace",
        validation_alias=AliasChoices("diligenceWorkspace", "diligence_workspace"),
        serialization_alias="diligence_workspace",
    )
    knowledgeMetadata: dict[str, Any] | DueDiligenceMetadata | None = Field(
        default=None,
        alias="knowledgeMetadata",
        validation_alias=AliasChoices("knowledgeMetadata", "knowledge_metadata"),
        serialization_alias="knowledgeMetadata",
    )
    slideClassification: list[dict[str, Any]] | None = Field(
        default=None,
        alias="slide_classification",
        validation_alias=AliasChoices("slideClassification", "slide_classification"),
        serialization_alias="slide_classification",
    )
    audienceDiligence: dict[str, Any] | None = Field(
        default=None,
        alias="audience_diligence",
        validation_alias=AliasChoices("audienceDiligence", "audience_diligence"),
        serialization_alias="audience_diligence",
    )
    deckImplementationPlan: dict[str, Any] | None = Field(
        default=None,
        alias="deck_implementation_plan",
        validation_alias=AliasChoices("deckImplementationPlan", "deck_implementation_plan"),
        serialization_alias="deck_implementation_plan",
    )
    slideLevelInstructions: list[dict[str, Any]] | None = Field(
        default=None,
        alias="slide_level_instructions",
        validation_alias=AliasChoices("slideLevelInstructions", "slide_level_instructions"),
        serialization_alias="slide_level_instructions",
    )
    smartDeckInstruction: dict[str, Any] | None = Field(
        default=None,
        alias="smart_deck_instruction",
        validation_alias=AliasChoices("smartDeckInstruction", "smart_deck_instruction"),
        serialization_alias="smart_deck_instruction",
    )
    smartEditInstructions: list[dict[str, Any]] | None = Field(
        default=None,
        alias="smart_edit_instructions",
        validation_alias=AliasChoices("smartEditInstructions", "smart_edit_instructions"),
        serialization_alias="smart_edit_instructions",
    )
    conversation: "DueDiligenceConversation | None" = None


class DueDiligenceRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: DueDiligenceAudience = "seed_vc"
    runMode: Literal["full_review"] = "full_review"
    idempotencyKey: str = Field(min_length=1, max_length=255)


class DueDiligenceCommandAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = True
    jobId: str
    jobType: Literal["due_diligence"]
    status: Literal["queued", "running", "completed", "failed_retryable", "failed_final", "blocked", "timed_out"]
    phase: Literal["due_diligence_queued", "due_diligence_running", "due_diligence_ready", "failed_retryable", "failed_final", "needs_manual_review"]
    workflowStateUrl: str
    jobUrl: str
    reportUrl: str


class DueDiligenceChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(min_length=1, max_length=16000)


class DueDiligenceChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[DueDiligenceChatMessage] = Field(min_length=1, max_length=50)
    audience: str | None = Field(default=None, max_length=120)
    # Compatibility: legacy clients may omit the key. The route returns the
    # generated value so subsequent retries can retain an exact identity.
    clientExchangeKey: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._:-]+$")
    conversationId: str | None = Field(default=None, max_length=120)


class DueDiligenceChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    provider: str | None = None
    model: str | None = None
    conversationId: str
    messageId: str
    clientExchangeKey: str
    replayed: bool = False


class DueDiligenceChatPendingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["diligence_chat_pending"] = "diligence_chat_pending"
    message: str = "This exchange is still being processed. Retry later with the same clientExchangeKey."
    retryable: Literal[True] = True
    clientExchangeKey: str


class DueDiligenceConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messageId: str
    role: Literal["user", "assistant"]
    content: str
    clientExchangeKey: str
    createdAt: str | None = None
    provider: str | None = None
    model: str | None = None


class DueDiligenceConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversationId: str
    audience: str
    messages: list[DueDiligenceConversationMessage] = Field(default_factory=list)


__all__ = [
    "DueDiligenceClaim",
    "DueDiligenceChatMessage",
    "DueDiligenceChatRequest",
    "DueDiligenceChatResponse",
    "DueDiligenceDomain",
    "DueDiligenceIcmemo",
    "DueDiligenceLpView",
    "DueDiligenceRiskItem",
    "DueDiligenceRunRequest",
    "DueDiligenceCommandAcceptedResponse",
    "DueDiligenceWorkspacePayload",
    "AudienceFit",
]
