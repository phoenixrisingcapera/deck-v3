"""Smart Deck Media Library contracts.

Owns: strict Pydantic schemas for deck-scoped media upload, list, detail,
status, archive, retry, and authenticated content delivery.
Must not own: business logic, storage, or worker processing.
Stage: API contract between frontend proxies and backend media routes.
Status: KEEP
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DeckMediaRole = Literal["logo", "board_picture", "deck_picture"]

DeckMediaStatus = Literal[
    "queued",
    "processing",
    "ready",
    "failed_retryable",
    "failed_final",
    "archived",
]


class DeckMediaAssetResponse(BaseModel):
    """Single media asset as returned by list and detail endpoints."""

    id: str
    deckId: str
    role: DeckMediaRole
    label: str | None = None
    status: DeckMediaStatus
    originalFilename: str
    mimeType: str
    sizeBytes: int
    sha256: str | None = None
    width: int | None = None
    height: int | None = None
    caption: str | None = None
    altText: str | None = None
    ocrText: str | None = None
    dominantColors: list[str] | None = None
    llmEnabled: bool = True
    errorCode: str | None = None
    errorMessage: str | None = None
    contentUrl: str
    thumbnailUrl: str | None = None
    workflowJobId: str | None = None
    createdAt: str
    updatedAt: str
    processedAt: str | None = None
    archivedAt: str | None = None

    model_config = ConfigDict(extra="forbid")


class DeckMediaListResponse(BaseModel):
    """Paginated list of deck media assets."""

    deckId: str
    items: list[DeckMediaAssetResponse] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    nextCursor: str | None = None

    model_config = ConfigDict(extra="forbid")


class DeckMediaUploadResponse(BaseModel):
    """Response after successful media upload and job queueing."""

    media: DeckMediaAssetResponse
    processing: dict | None = None

    model_config = ConfigDict(extra="forbid")


class DeckMediaArchiveRequest(BaseModel):
    """Request body for archiving a media asset."""

    reason: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class DeckMediaPatchRequest(BaseModel):
    """Request body for updating media metadata."""

    label: str | None = Field(default=None, max_length=255)
    role: DeckMediaRole | None = None
    llmEnabled: bool | None = None

    model_config = ConfigDict(extra="forbid")
