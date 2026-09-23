from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.deck import SuggestionPatch


class AnalysisFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    deckId: str = Field(alias="deck_id")
    slideId: str = Field(alias="slide_id")
    blockId: str | None = Field(default=None, alias="block_id")
    title: str
    detail: str
    severity: Literal["high", "medium", "low"]
    category: str


class AnalysisFindingsRouteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[AnalysisFindingResponse] = Field(default_factory=list)


class AdaptationSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    deckId: str = Field(alias="deck_id")
    slideId: str = Field(alias="slide_id")
    blockId: str | None = Field(default=None, alias="block_id")
    title: str
    reason: str
    suggestedText: str = Field(alias="suggested_text")
    status: Literal["pending", "accepted", "rejected", "edited", "applied"]
    audience: str


class AdaptationSuggestionsRouteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[AdaptationSuggestionResponse] = Field(default_factory=list)

__all__ = [
    "AdaptationSuggestionResponse",
    "AdaptationSuggestionsRouteResponse",
    "AnalysisFindingResponse",
    "AnalysisFindingsRouteResponse",
    "SuggestionPatch",
]
