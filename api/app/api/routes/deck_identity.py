from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.shell import DeckGraphResponse
from app.services.platform.shell.shell_service import get_deck_graph

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["deck-identity"])


@router.get("/{deck_id}/graph", response_model=DeckGraphResponse)
def deck_graph(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckGraphResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    graph = get_deck_graph(db, deck_id)
    if graph is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DeckGraphResponse(**graph)
