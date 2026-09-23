from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.smart_deck_subjects import SmartDeckDeckType, SmartDeckSubject


class SmartDeckAgentSubjectDetection(BaseModel):
    subject: SmartDeckSubject
    confidence: float = Field(ge=0.0, le=1.0)
    matchedTerms: list[str] = Field(default_factory=list)


class SmartDeckAgentGenerateInput(BaseModel):
    deckId: str
    deckType: SmartDeckDeckType = "unknown"
    audience: str | None = None
    preferredModel: str | None = None
    selectedSlideIds: list[str] = Field(default_factory=list)
    selectedElementId: str | None = None
    selectedSubject: SmartDeckSubject | None = None
    detectedSubjects: list[SmartDeckAgentSubjectDetection] = Field(default_factory=list)
    actionId: str | None = None
    actionPrompt: str | None = None
    userPrompt: str = Field(min_length=1)
    latestBatchId: str | None = None
