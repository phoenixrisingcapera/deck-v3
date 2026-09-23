from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Deck, DesignBatch


def _status_for_iteration(batch_status: str) -> str:
    if batch_status == "failed":
        return "failed"
    if batch_status == "reviewed":
        return "accepted"
    if batch_status == "completed":
        return "ready_for_review"
    if batch_status == "running":
        return "draft"
    return batch_status or "draft"


def _label_for_iteration(batch: DesignBatch) -> str:
    if batch.batch_name:
        return batch.batch_name
    if batch.audience_label:
        return batch.audience_label
    if batch.scope_type == "selected_slides":
        return "Selected slides"
    return "Whole deck"


def get_deck_iterations(db: Session, deck_id: str, limit: int = 8) -> dict | None:
    deck = db.query(Deck.id).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None

    batches = (
        db.query(DesignBatch)
        .filter(DesignBatch.deck_id == deck_id, DesignBatch.status != "archived")
        .order_by(DesignBatch.created_at.desc())
        .limit(min(max(limit, 1), 8))
        .all()
    )

    iterations = [
        {
            "id": batch.id,
            "deckId": batch.deck_id,
            "iterationNumber": batch.batch_number,
            "label": _label_for_iteration(batch),
            "scope": batch.scope_type,
            "slideCount": batch.selected_slide_count,
            "status": _status_for_iteration(batch.status),
            "createdAt": batch.created_at.isoformat(),
            "updatedAt": (batch.updated_at or batch.created_at).isoformat(),
            "batchId": batch.id,
        }
        for batch in batches
    ]

    return {
        "deckId": deck_id,
        "activeIterationId": iterations[0]["id"] if iterations else None,
        "iterations": iterations,
    }
