from __future__ import annotations

from datetime import datetime

from app.core.security import generate_id
from app.db.models import DeckSaveConfirmation


def map_save_confirmation(record: DeckSaveConfirmation) -> dict:
    return {
        "id": record.id,
        "deck_id": record.deck_id,
        "workspace_id": record.workspace_id,
        "user_id": record.user_id,
        "event_type": record.event_type,
        "entity_type": record.entity_type,
        "entity_id": record.entity_id,
        "tone": record.tone,
        "title": record.title,
        "message": record.message,
        "cta_label": record.cta_label,
        "cta_href": record.cta_href,
        "source_surface": record.source_surface,
        "source_route": record.source_route,
        "created_at": record.created_at.isoformat(),
        "metadata": record.metadata_json,
    }


def build_save_confirmation(
    *,
    deck_id: str,
    event_type: str,
    entity_type: str,
    title: str,
    message: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    entity_id: str | None = None,
    tone: str = "success",
    cta_label: str | None = None,
    cta_href: str | None = None,
    source_surface: str | None = None,
    source_route: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": generate_id("confirm"),
        "deck_id": deck_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "tone": tone,
        "title": title,
        "message": message,
        "cta_label": cta_label,
        "cta_href": cta_href,
        "source_surface": source_surface,
        "source_route": source_route,
        "created_at": datetime.utcnow().isoformat(),
        "metadata": metadata or None,
    }


def record_save_confirmation(
    db,
    *,
    deck_id: str,
    event_type: str,
    entity_type: str,
    title: str,
    message: str,
    workspace_id: str | None = None,
    user_id: str | None = None,
    entity_id: str | None = None,
    tone: str = "success",
    cta_label: str | None = None,
    cta_href: str | None = None,
    source_surface: str | None = None,
    source_route: str | None = None,
    dedupe_key: str | None = None,
    metadata: dict | None = None,
) -> DeckSaveConfirmation:
    payload = build_save_confirmation(
        deck_id=deck_id,
        event_type=event_type,
        entity_type=entity_type,
        title=title,
        message=message,
        workspace_id=workspace_id,
        user_id=user_id,
        entity_id=entity_id,
        tone=tone,
        cta_label=cta_label,
        cta_href=cta_href,
        source_surface=source_surface,
        source_route=source_route,
        metadata=metadata,
    )
    record = DeckSaveConfirmation(
        id=payload["id"],
        deck_id=payload["deck_id"],
        workspace_id=payload["workspace_id"],
        user_id=payload["user_id"],
        event_type=payload["event_type"],
        entity_type=payload["entity_type"],
        entity_id=payload["entity_id"],
        title=payload["title"],
        message=payload["message"],
        tone=payload["tone"],
        cta_label=payload["cta_label"],
        cta_href=payload["cta_href"],
        status="confirmed",
        source_surface=payload["source_surface"],
        source_route=payload["source_route"],
        dedupe_key=dedupe_key,
        metadata_json=payload["metadata"],
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.flush()
    return record


def get_latest_save_confirmation_for_deck(db, deck_id: str) -> DeckSaveConfirmation | None:
    return (
        db.query(DeckSaveConfirmation)
        .filter(DeckSaveConfirmation.deck_id == deck_id)
        .order_by(DeckSaveConfirmation.created_at.desc())
        .first()
    )
