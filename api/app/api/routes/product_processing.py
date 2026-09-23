from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.services.deck_processing.processing_status_service import get_deck_processing_status

router = APIRouter(prefix="/products/deck-aistack-codes", tags=["product-processing"])


@router.get("/decks/{deck_id}/processing")
def deck_processing_status(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """User-safe processing status for the Smart Deck loader.

    Returns clean UI state only. Admin diagnostics live under
    /api/admin/decks/{deck_id}/processing-health.
    """

    deck = get_user_deck_or_404(db, current_user, deck_id)
    status = get_deck_processing_status(db, deck.id)
    if status is None:
        raise HTTPException(status_code=404, detail="Deck processing state not found.")
    return status
