from __future__ import annotations

from pydantic import BaseModel, Field


class AudienceConversionSlideAction(BaseModel):
    slideId: str | None = None
    slideTitle: str | None = None
    currentRole: str | None = None
    audienceNeed: str
    objection: str | None = None
    action: str
    evidenceNeeded: list[str] = Field(default_factory=list)
    priority: str = "medium"


class AudienceConversionDeckVersion(BaseModel):
    title: str | None = None
    audience: str | None = None
    summary: str | None = None
    generationPrompt: str | None = None


class AudienceConversionPlan(BaseModel):
    targetAudience: str
    audiencePriorities: list[str] = Field(default_factory=list)
    likelyObjections: list[str] = Field(default_factory=list)
    decisionCriteria: list[str] = Field(default_factory=list)
    deckConversionPlan: dict = Field(default_factory=dict)
    slideLevelActions: list[AudienceConversionSlideAction] = Field(default_factory=list)
    missingEvidence: list[str] = Field(default_factory=list)
    recommendedDeckVersion: AudienceConversionDeckVersion = Field(default_factory=AudienceConversionDeckVersion)
    requiresReview: bool = True
    system: dict = Field(default_factory=dict)


class AudienceConversionWorkflowResponse(BaseModel):
    runId: str
    deckId: str
    status: str
    conversion: AudienceConversionPlan | None = None
    cached: bool = False
