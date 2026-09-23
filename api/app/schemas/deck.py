from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import DeckStatus, SuggestionStatus

LEGACY_DECK_STATUS_MAP = {
    "saved": "uploaded",
    "source_saved": "uploaded",
    "preparing": "processing",
    "starting": "processing",
    "queued": "processing",
    "running": "processing",
    "parsing": "processing",
    "structuring": "processing",
    "extracting_blocks": "processing",
    "classifying_blocks": "processing",
    "analysing": "processing",
    "analyzing": "processing",
    "adapting": "processing",
    "workspace_ready": "ready",
    "completed": "ready",
    "reviewed": "ready",
    "dead_letter": "failed",
    "error": "failed",
}


def _canonical_status(value: str) -> str:
    raw_value = str(value or "pending").strip().lower()
    return LEGACY_DECK_STATUS_MAP.get(raw_value, raw_value)


class DeckCreate(BaseModel):
    title: str
    audience: str
    purpose: str
    workspace_id: str | None = None


class DeckSummary(BaseModel):
    id: str
    title: str
    audience: str
    purpose: str
    status: DeckStatus
    summary: str
    created_at: datetime
    updated_at: datetime
    slide_count: int | None = None
    thumbnail_url: str | None = None
    preview_url: str | None = None
    first_slide_id: str | None = None
    original_filename: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def canonicalize_status(cls, value: str) -> str:
        return _canonical_status(value)


class SlideBlockPatch(BaseModel):
    text: str


class SuggestionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SuggestionStatus
    edited_text: str | None = Field(default=None, max_length=4000)

    @field_validator("edited_text")
    @classmethod
    def clean_edited_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = "".join(ch for ch in value.strip() if ch == "\n" or ch == "\t" or ord(ch) >= 32)
        return cleaned or None


SMART_EDIT_AUDIENCE_TYPES = {
    "vc_investor",
    "angel_investor",
    "investment_committee",
    "corporate_venture",
    "grant_funder",
    "accelerator",
    "acquirer",
    "strategic_partner",
}


class SmartEditCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slide_id: str = Field(min_length=1, max_length=128)
    block_id: str = Field(min_length=1, max_length=128)
    instruction: str = Field(min_length=8, max_length=800)
    audience_type: str = Field(min_length=1, max_length=64)

    @field_validator("slide_id", "block_id", "instruction", "audience_type")
    @classmethod
    def strip_control_characters(cls, value: str) -> str:
        cleaned = "".join(ch for ch in value.strip() if ch == "\n" or ch == "\t" or ord(ch) >= 32)
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned

    @field_validator("audience_type")
    @classmethod
    def validate_audience_type(cls, value: str) -> str:
        if value not in SMART_EDIT_AUDIENCE_TYPES:
            raise ValueError("unsupported due diligence audience")
        return value


class ExportCreate(BaseModel):
    """Frontend/backend export contract.

    `type` is the canonical field. `exportType` is accepted for compatibility
    with the current Svelte export page and older product-route callers.
    """

    model_config = ConfigDict(extra="allow")

    type: str | None = Field(default=None, min_length=1, max_length=80)
    exportType: str | None = Field(default=None, min_length=1, max_length=80)
    format: Literal["html"] | None = None
    designVersionId: str | None = Field(default=None, min_length=1, max_length=120)
    includeFindings: bool = True
    includeSuggestions: bool = True
    includeSmartEdits: bool = True
    includeRejected: bool = False
    clientEventId: str | None = Field(default=None, max_length=128)
    sourceSurface: str | None = Field(default="export_page", max_length=80)
    sessionId: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] | None = None

    @property
    def normalized_type(self) -> str | None:
        return self.type or self.exportType


class DeckExportListItem(BaseModel):
    id: str
    deckId: str
    type: str
    format: str | None = None
    designVersionId: str | None = None
    createdAt: str
    downloadUrl: str
    detailUrl: str


class DeckExportListResponse(BaseModel):
    exports: list[DeckExportListItem] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    hasMore: bool


class SavedResponseSourceLink(BaseModel):
    label: str = Field(min_length=1, max_length=300)
    url: str | None = Field(default=None, max_length=2048)


class SavedResponseSourceGroup(BaseModel):
    sourceType: str = Field(min_length=1, max_length=120)
    links: list[SavedResponseSourceLink] = Field(default_factory=list, max_length=50)


class SavedResponseExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slideId: str = Field(min_length=1, max_length=128)
    promptSlug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    assistantArtifactId: str = Field(min_length=1, max_length=128)


class SavedResponseExportPreview(BaseModel):
    id: str
    deckId: str
    slideId: str
    promptSlug: str
    markdownContent: str
    sourceGroups: list[SavedResponseSourceGroup] = Field(default_factory=list)
    createdAt: datetime


class SavedResponseExportListItem(BaseModel):
    id: str
    deckId: str
    slideId: str
    slideNumber: int
    slideTitle: str
    promptSlug: str
    createdAt: datetime


class SavedResponseExportListGroup(BaseModel):
    slideId: str
    slideNumber: int
    slideTitle: str
    items: list[SavedResponseExportListItem] = Field(default_factory=list)


class SavedResponseExportListResponse(BaseModel):
    groups: list[SavedResponseExportListGroup] = Field(default_factory=list)
