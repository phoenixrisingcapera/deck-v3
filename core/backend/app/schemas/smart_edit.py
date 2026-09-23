from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.deck import SmartEditCreate


class SmartEditRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    deck_id: str
    slide_id: str
    block_id: str
    instruction: str
    audience_type: str
    created_at: str


class SmartEditSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    deck_id: str
    slide_id: str
    block_id: str
    original_text: str
    suggested_text: str
    reason: str
    risk_level: str
    status: str


class SmartEditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: SmartEditRunResponse
    suggestion: SmartEditSuggestionResponse


class SmartEditSuggestionRouteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion: SmartEditSuggestionResponse

__all__ = [
    "SmartEditCreate",
    "SmartEditResponse",
    "SmartEditRunResponse",
    "SmartEditSuggestionResponse",
    "SmartEditSuggestionRouteResponse",
]
