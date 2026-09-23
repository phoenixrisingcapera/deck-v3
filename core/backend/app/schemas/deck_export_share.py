from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeckExportShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expiresInDays: int | None = Field(default=None, ge=1, le=365)


class DeckExportShareItem(BaseModel):
    shareId: str
    deckId: str
    exportId: str
    designVersionId: str
    status: str
    createdAt: datetime
    expiresAt: datetime | None = None
    revokedAt: datetime | None = None
    lastAccessedAt: datetime | None = None
    accessCount: int = Field(ge=0)


class DeckExportShareCreated(DeckExportShareItem):
    # Returned once. Only its digest is persisted by the backend.
    shareToken: str
    publicPath: str


class DeckExportShareList(BaseModel):
    shares: list[DeckExportShareItem] = Field(default_factory=list)
