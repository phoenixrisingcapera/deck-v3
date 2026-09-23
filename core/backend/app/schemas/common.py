from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DeckStatus = Literal[
    "pending",
    "uploaded",
    "processing",
    "ready",
    "failed",
]

SuggestionStatus = Literal["pending", "accepted", "rejected", "edited", "applied"]


class Timestamped(BaseModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None
