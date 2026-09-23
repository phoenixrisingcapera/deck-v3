from __future__ import annotations

from pydantic import BaseModel, Field


class DueDiligenceWorkflowClaim(BaseModel):
    claim: str
    slideId: str | None = None
    slideTitle: str | None = None
    evidenceStatus: str
    riskLevel: str
    confidence: str = "medium"
    sourceFactIds: list[str] = Field(default_factory=list)


class DueDiligenceWorkflowRisk(BaseModel):
    risk: str
    category: str
    severity: str
    evidenceStatus: str
    investorQuestion: str
    mitigation: str | None = None


class DueDiligenceWorkflowReport(BaseModel):
    deckId: str
    claims: list[DueDiligenceWorkflowClaim] = Field(default_factory=list)
    unsupportedClaims: list[str] = Field(default_factory=list)
    evidenceStatusSummary: dict = Field(default_factory=dict)
    risks: list[DueDiligenceWorkflowRisk] = Field(default_factory=list)
    investorQuestions: list[str] = Field(default_factory=list)
    icMemoSummary: str
    clientRequestList: list[str] = Field(default_factory=list)
    system: dict = Field(default_factory=dict)


class DueDiligenceWorkflowResponse(BaseModel):
    runId: str
    deckId: str
    status: str
    report: DueDiligenceWorkflowReport | None = None
    cached: bool = False
