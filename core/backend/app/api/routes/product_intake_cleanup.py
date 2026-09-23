from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Deck, User, Workspace
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state
from app.services.deck_processing.workspace_summary_service import resolve_workspace_for_user

router = APIRouter(prefix="/products/deck-aistack-codes", tags=["products"])

AUTO_SOFT_DELETE_STATES = {DeckState.UPLOADED.value, DeckState.PROCESSING.value, DeckState.FAILED.value}


class DeckIntakeCleanupRequest(BaseModel):
    workspace_id: str | None = None
    workspaceId: str | None = None
    intake_run_id: str | None = None
    intakeRunId: str | None = None
    current_deck_ids: list[str] = Field(default_factory=list)
    currentDeckIds: list[str] = Field(default_factory=list)
    reason: str | None = None


def _is_soft_deleted(deck: Deck) -> bool:
    metadata = deck.metadata_json or {}
    return bool(metadata.get("soft_deleted_at"))


def _current_deck_ids(payload: DeckIntakeCleanupRequest) -> set[str]:
    return {
        str(deck_id).strip()
        for deck_id in [*payload.current_deck_ids, *payload.currentDeckIds]
        if str(deck_id).strip()
    }


def _request_intake_run_id(payload: DeckIntakeCleanupRequest) -> str | None:
    value = payload.intake_run_id or payload.intakeRunId
    if not value:
        return None
    normalized = value.strip()
    return normalized or None


def _deck_intake_run_id(deck: Deck) -> str | None:
    metadata = deck.metadata_json or {}
    value = metadata.get("intake_run_id") or metadata.get("intakeRunId")
    return str(value).strip() if value else None


def _eligible_for_auto_soft_delete(deck: Deck) -> bool:
    if canonical_deck_state(deck.status).value not in AUTO_SOFT_DELETE_STATES:
        return False
    return True


def _resolve_workspace(db: Session, current_user: User, workspace_id: str | None) -> Workspace | None:
    if current_user.role == "super_admin" and workspace_id:
        return db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if workspace_id:
        return (
            db.query(Workspace)
            .filter(Workspace.id == workspace_id, Workspace.user_id == current_user.id)
            .first()
        )
    return resolve_workspace_for_user(db, current_user.id)


@router.post("/decks/intake-cleanup")
def cleanup_other_intake_decks(
    payload: DeckIntakeCleanupRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    workspace_id = payload.workspace_id or payload.workspaceId
    workspace = _resolve_workspace(db, current_user, workspace_id)
    if workspace is None:
        return {"ok": True, "soft_deleted_deck_ids": [], "softDeletedDeckIds": [], "softDeletedCount": 0}

    current_deck_ids = _current_deck_ids(payload)
    current_intake_run_id = _request_intake_run_id(payload)
    soft_deleted_deck_ids: list[str] = []
    soft_deleted_at = datetime.utcnow().isoformat()
    reason = payload.reason or "other_intake_run_cleanup"

    decks = db.query(Deck).filter(Deck.workspace_id == workspace.id).order_by(Deck.updated_at.desc()).all()
    for deck in decks:
        if deck.id in current_deck_ids:
            continue
        if current_intake_run_id and _deck_intake_run_id(deck) == current_intake_run_id:
            continue
        if _is_soft_deleted(deck):
            continue
        if not _eligible_for_auto_soft_delete(deck):
            continue

        metadata = dict(deck.metadata_json or {})
        metadata.update(
            {
                "soft_deleted_at": soft_deleted_at,
                "soft_deleted_reason": reason,
                "soft_deleted_source_surface": "deck_intake_cleanup",
                "soft_deleted_current_deck_ids": sorted(current_deck_ids),
                "soft_deleted_current_intake_run_id": current_intake_run_id,
            }
        )
        deck.metadata_json = metadata
        soft_deleted_deck_ids.append(deck.id)

    if soft_deleted_deck_ids:
        db.commit()

    return {
        "ok": True,
        "soft_deleted_deck_ids": soft_deleted_deck_ids,
        "softDeletedDeckIds": soft_deleted_deck_ids,
        "softDeletedCount": len(soft_deleted_deck_ids),
    }
