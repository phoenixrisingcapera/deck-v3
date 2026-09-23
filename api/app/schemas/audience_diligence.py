from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AudienceDiligenceRequest(BaseModel):
    selectedAudience: str | None = None
    audience: str | None = None
    conversionGoal: str | None = None
    userInstruction: str | None = None
    preferredModel: str | None = None


class AudienceDiligenceResponse(BaseModel):
    artifactId: str | None = None
    deckId: str
    status: str
    selectedAudience: str
    audiencePriorities: list[str] = Field(default_factory=list)
    audienceObjections: list[dict[str, Any]] = Field(default_factory=list)
    audienceDecisionCriteria: list[str] = Field(default_factory=list)
    currentDeckFit: str
    currentDeckFitScore: int = 0
    currentDeckFitReason: str = ""
    deckDiagnosis: dict[str, Any] = Field(default_factory=dict)
    financialInsights: dict[str, Any] = Field(default_factory=dict)
    narrativeShift: str = ""
    deckImplementationPlan: dict[str, Any] = Field(default_factory=dict)
    slideLevelInstructions: list[dict[str, Any]] = Field(default_factory=list)
    missingEvidence: list[Any] = Field(default_factory=list)
    smartDeckInstruction: dict[str, Any] = Field(default_factory=dict)
    smartEditInstructions: list[dict[str, Any]] = Field(default_factory=list)
    requiresReview: bool = True
    result: dict[str, Any] | None = None
    createdAt: str | None = None
