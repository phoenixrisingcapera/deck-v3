from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.smart_deck import (
    SmartDeckPreferenceResponse,
    SmartDeckWorkspaceResponse,
    UpdateSmartDeckSessionStateInput,
)
from app.services.llm.generation_service import (
    get_instant_deck_workspace,
    update_smart_deck_selection,
)
from app.services.visual_intelligence.persistence import visual_intelligence_status
from app.services.visual_intelligence.review.deck_review import vision_review_status

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["instant-deck"])


@router.get("/{deck_id}/ai-vc-runs/latest/visual-direction")
def latest_visual_direction(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = visual_intelligence_status(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visual direction is not ready")
    return payload


@router.get("/{deck_id}/ai-vc-runs/latest/vision-review")
def latest_vision_review(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = vision_review_status(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision review is not ready")
    return payload


@router.get("/{deck_id}/instant-deck", response_model=SmartDeckWorkspaceResponse)
def instant_deck_workspace(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckWorkspaceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        workspace = get_instant_deck_workspace(db, deck_id)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Instant Deck workspace is temporarily unavailable.",
        ) from exc
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckWorkspaceResponse(**workspace)


@router.patch("/{deck_id}/instant-deck/session-state", response_model=SmartDeckPreferenceResponse)
def update_instant_deck_session_state(
    deck_id: str,
    payload: UpdateSmartDeckSessionStateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckPreferenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        session_state = update_smart_deck_selection(db, deck_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if session_state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckPreferenceResponse(**session_state)
