from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.save_confirmation import SaveConfirmationResponse
from app.schemas.shell import DeckSlideWithBlocksResponse


class GeneratedDeckMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    audience: str
    purpose: str
    theme: Literal["dark", "light", "auto"]


class GeneratedSlideLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canvas: Literal["16:9"]
    composition: Literal[
        "hero",
        "two_column",
        "three_cards",
        "timeline",
        "metric_grid",
        "quote",
        "image_left",
        "image_right",
        "simple_text",
    ]
    safe_margin_px: int = Field(ge=32, le=96)


class GeneratedSlideBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal[
        "heading",
        "subheading",
        "body",
        "metric",
        "caption",
        "quote",
        "image_placeholder",
        "shape",
        "button_label",
    ]
    text: str
    role: Literal["primary", "secondary", "supporting", "decorative"]
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    w: float = Field(ge=1, le=100)
    h: float = Field(ge=1, le=100)


class GeneratedSlide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    slide_type: Literal[
        "cover",
        "problem",
        "solution",
        "market",
        "product",
        "traction",
        "business_model",
        "competition",
        "team",
        "financials",
        "roadmap",
        "ask",
        "generic",
    ]
    status: Literal["ok", "needs_review", "failed"]
    title: str
    layout: GeneratedSlideLayout
    blocks: list[GeneratedSlideBlock] = Field(min_length=1, max_length=12)
    speaker_notes: str
    design_rationale: str
    quality_flags: list[
        Literal[
            "ok",
            "text_too_dense",
            "low_contrast_risk",
            "image_collision_risk",
            "needs_human_review",
        ]
    ]


class GeneratedDeckQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: float = Field(ge=0, le=1)
    warnings: list[str]


class GeneratedDeckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "partial", "failed"]
    deck: GeneratedDeckMetadata
    slides: list[GeneratedSlide] = Field(min_length=1, max_length=20)
    quality: GeneratedDeckQuality


class GenerateSlidesRequest(BaseModel):
    prompt: str = Field(min_length=1)
    scopeType: Literal["whole_deck", "selected_slides"] = "whole_deck"
    selectedSlideIds: list[str] = Field(default_factory=list)
    audience: str | None = None
    purpose: str | None = None
    theme: Literal["dark", "light", "auto"] = "auto"


class GeneratedSlideVersionResponse(BaseModel):
    id: str
    generationRunId: str
    sourceSlideId: str | None = None
    slideIndex: int
    sourceSlideTitle: str | None = None
    versionNumber: int
    title: str
    status: str
    generatedSlide: GeneratedSlide
    createdAt: str
    updatedAt: str


class SlideFeedbackEventResponse(BaseModel):
    id: str
    slideVersionId: str
    generationRunId: str | None = None
    sourceSlideId: str | None = None
    eventType: str
    notes: str | None = None
    payload: dict | None = None
    createdAt: str


class DeckWorkspaceDeckResponse(BaseModel):
    id: str
    workspaceId: str
    title: str
    audience: str
    purpose: str
    status: str
    summary: str
    createdAt: str
    updatedAt: str
    generationStatus: str
    generationMode: str
    latestGenerationRunId: str | None = None


class DeckWorkspaceModelResponse(BaseModel):
    deck: DeckWorkspaceDeckResponse
    slides: list[DeckSlideWithBlocksResponse]
    versions: list[GeneratedSlideVersionResponse]
    feedback: list[SlideFeedbackEventResponse]


class DeckWorkspaceRouteResponse(BaseModel):
    workspace: DeckWorkspaceModelResponse
    latestConfirmation: SaveConfirmationResponse | None = None


class GenerateSlidesRouteResponse(BaseModel):
    runId: str
    workspace: DeckWorkspaceModelResponse


class SubmitSlideFeedbackRequest(BaseModel):
    slideVersionId: str
    eventType: Literal["accepted", "rejected", "edited", "viewed"]
    notes: str | None = None
    applyToWorkspace: bool = False


class SubmitSlideFeedbackRouteResponse(BaseModel):
    feedback: SlideFeedbackEventResponse
    workspace: DeckWorkspaceModelResponse
