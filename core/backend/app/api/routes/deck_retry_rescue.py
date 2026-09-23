from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.services.deck_processing.processing_visibility import get_deck_processing_visibility
from app.services.deck_processing.workflow_orchestration import queue_source_extraction
from app.services.admin.failure_tickets import create_failure_ticket

logger = logging.getLogger(__name__)
router = APIRouter(tags=["deck-retry-rescue"])


def _safe_processing_visibility(db: Session, deck_id: str) -> dict | None:
    try:
        return get_deck_processing_visibility(db, deck_id)
    except Exception:
        logger.exception("retry_deck_processing_visibility_failed", extra={"deck_id": deck_id})
        return None


def _processing_can_continue(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    next_action = payload.get("nextAction")
    processing = payload.get("processing") if isinstance(payload.get("processing"), dict) else {}
    upload = payload.get("upload") if isinstance(payload.get("upload"), dict) else {}
    return bool(
        next_action in {"open_smart_deck", "wait"}
        or processing.get("status") in {"queued", "running", "processing", "completed", "ready"}
        or upload.get("sourceSaved") is True
    )


@router.post("/products/deck-aistack-codes/decks/{deck_id}/retry")
def retry_deck_processing_rescue(
    deck_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    deck = get_user_deck_or_404(db, current_user, deck_id)

    try:
        processing = queue_source_extraction(db, deck.id, requested_by_user_id=current_user.id)
        run_id = processing.get("jobId") if isinstance(processing, dict) else None
        run_status = str(processing.get("status") or "") if isinstance(processing, dict) else ""
        visibility = _safe_processing_visibility(db, deck.id)
        return {
            "ok": True,
            "deck_id": deck.id,
            "deckId": deck.id,
            "processing": processing,
            "visibility": visibility,
            "nextAction": (visibility or {}).get("nextAction") or (processing or {}).get("nextAction") or "wait",
        }
    except ValueError as exc:
        db.rollback()
        visibility = _safe_processing_visibility(db, deck.id)
        message = str(exc) or "Deck processing could not be queued."
        logger.warning("retry_deck_processing_rescue_rejected", extra={"deck_id": deck.id, "reason": message})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": message,
                "deckId": deck.id,
                "visibility": visibility,
                "retryable": "source file" not in message.lower(),
            },
        ) from exc
    except Exception as exc:
        db.rollback()
        visibility = _safe_processing_visibility(db, deck.id)
        error_type = exc.__class__.__name__
        logger.exception("retry_deck_processing_rescue_failed", extra={"deck_id": deck.id, "error_type": error_type})

        try:
            create_failure_ticket(
                db,
                {
                    "route": str(request.url.path),
                    "apiPath": str(request.url.path),
                    "statusCode": 202 if _processing_can_continue(visibility) else 503,
                    "errorName": "SmartDeckRetryQueueFailed",
                    "errorMessage": str(exc)[:500] or "Could not queue deck retry processing.",
                    "severity": "medium" if _processing_can_continue(visibility) else "high",
                    "source": "backend",
                    "deckId": deck.id,
                    "context": {"errorType": error_type, "processingVisibility": visibility},
                },
                request=request,
                current_user=current_user,
                commit=True,
            )
        except Exception:
            db.rollback()

        if _processing_can_continue(visibility):
            return {
                "ok": True,
                "warning": "Retry queue failed, but an existing saved/processing deck state is available.",
                "deck_id": deck.id,
                "deckId": deck.id,
                "processingVisibility": visibility,
                "nextAction": visibility.get("nextAction") if isinstance(visibility, dict) else "poll_processing",
                "errorType": error_type,
            }

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Could not queue Smart Deck processing. The source deck is saved, but processing could not start.",
                "deckId": deck.id,
                "visibility": visibility,
                "retryable": True,
                "errorType": error_type,
                "nextAction": "inspect_processing_logs",
            },
        ) from exc
