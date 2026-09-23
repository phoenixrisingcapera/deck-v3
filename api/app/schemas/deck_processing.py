from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeckProcessingPhaseResponse(BaseModel):
    key: str
    label: str
    status: str
    startedAt: str | None = None
    completedAt: str | None = None
    error: dict[str, Any] | None = None


class SmartDeckProcessingStartResponse(BaseModel):
    worker_required: bool
    background_started: bool
    next_action: str
    processing_status_url: str


class DeckProcessingVisibilityResponse(BaseModel):
    nextAction: str
    canOpenSmartDeck: bool = False
    canRetry: bool = False
    canRemove: bool = False
    phases: list[DeckProcessingPhaseResponse] = Field(default_factory=list)
    processingStatusUrl: str | None = None
    smartDeckUrl: str | None = None
    retryUrl: str | None = None
    workflowPhase: str | None = None
    recoveryCount: int | None = None
    lastRecoveredAt: str | None = None
    lastRecoveredBy: str | None = None
    publishedPhase: str | None = None
    publishedAt: str | None = None
    requiresManualReview: bool = False
    finalFailureReason: str | None = None


# ============================================================================
# Science-backed deterministic pipeline schemas
# ============================================================================


class MaterializedDeckStateResponse(BaseModel):
    """Single source of truth for deck processing state."""
    model_config = ConfigDict(extra="forbid")

    deckId: str
    sourceVersionId: str | None = None
    status: str
    extractionStatus: str
    currentStage: str
    slideCount: int = 0
    blockCount: int = 0
    assetCount: int = 0
    hasThumbnails: bool = False
    hasStructuredJson: bool = False
    hasEmbeddings: bool = False
    canOpenSmartDeck: bool = False
    canOpenSmartEdit: bool = False
    canOpenDueDiligence: bool = False
    nextAction: str | None = None
    warningsJson: list[str] | None = None
    errorsJson: list[str] | None = None
    lastExtractionAt: str | None = None
    lastGenerationAt: str | None = None
    updatedAt: str | None = None


class DeckBlockPositionResponse(BaseModel):
    """Block position within a slide."""
    model_config = ConfigDict(extra="forbid")

    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None


class DeckBlockStyleResponse(BaseModel):
    """Block style information."""
    model_config = ConfigDict(extra="forbid")

    fontFamily: str | None = None
    fontSize: str | None = None
    fontWeight: str | None = None
    color: str | None = None


class DeckBlockResponse(BaseModel):
    """Single block within a slide."""
    model_config = ConfigDict(extra="forbid")

    id: str
    blockKey: str
    blockType: str
    blockKind: str
    text: str | None = None
    positionJson: DeckBlockPositionResponse = Field(default_factory=DeckBlockPositionResponse)
    styleJson: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    persistentFieldKey: str | None = None
    isEditable: bool = False
    isGenerated: bool = False


class DeckSlideResponse(BaseModel):
    """Single slide in the deck."""
    model_config = ConfigDict(extra="forbid")

    id: str
    slideNumber: int
    title: str
    role: str
    thumbnailPath: str | None = None
    renderedImagePath: str | None = None
    widthPoints: float | None = None
    heightPoints: float | None = None
    blockCount: int = 0
    blocks: list[DeckBlockResponse] = Field(default_factory=list)


class DeckMapResponse(BaseModel) :
    """Full deck map with slides, blocks, and assets."""
    model_config = ConfigDict(extra="forbid")

    deckId: str
    title: str | None = None
    status: str
    sourceVersionId: str | None = None
    slideCount: int = 0
    slides: list[DeckSlideResponse] = Field(default_factory=list)


class EditorViewResponse(BaseModel):
    """Editor view with blocks, positions, styles, and persistent field keys."""
    model_config = ConfigDict(extra="forbid")

    deckId: str
    title: str | None = None
    status: str
    sourceVersionId: str | None = None
    slideCount: int = 0
    slides: list[DeckSlideResponse] = Field(default_factory=list)
