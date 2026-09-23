"""Deck media context builder for LLM integration.

Owns: building bounded, same-deck, ready-media context for Smart Deck generation
and Smart Edit. Returns stable media IDs and metadata, not raw storage paths or
base64 data.
Must not own: media upload, processing, or storage.
Stage: shared context builder consumed by generation and editing services.
Status: KEEP
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models import DeckMediaAsset

logger = logging.getLogger(__name__)

MAX_MEDIA_CONTEXT_ASSETS = 8
MAX_MEDIA_CONTEXT_BYTES = 50 * 1024 * 1024  # 50 MB total


def build_deck_media_context(
    db: Session,
    *,
    deck_id: str,
    roles: list[str] | None = None,
    limit: int = MAX_MEDIA_CONTEXT_ASSETS,
) -> dict:
    """Build bounded media context for LLM consumption.

    Returns only ready, non-archived, LLM-enabled assets from the same deck.
    Does not include raw storage paths, signed URLs, or base64 data.
    """
    query = db.query(DeckMediaAsset).filter(
        DeckMediaAsset.deck_id == deck_id,
        DeckMediaAsset.status == "ready",
        DeckMediaAsset.archived_at.is_(None),
        DeckMediaAsset.llm_enabled.is_(True),
    )

    if roles:
        query = query.filter(DeckMediaAsset.role.in_(roles))

    assets = query.order_by(DeckMediaAsset.created_at.desc()).limit(limit).all()

    # Build context items
    items = []
    total_bytes = 0
    for asset in assets:
        if total_bytes + asset.size_bytes > MAX_MEDIA_CONTEXT_BYTES:
            logger.warning(
                "Media context byte limit reached for deck %s; truncating at %d assets",
                deck_id,
                len(items),
            )
            break

        item = {
            "id": asset.id,
            "role": asset.role,
            "mimeType": asset.mime_type,
            "width": asset.width,
            "height": asset.height,
            "caption": asset.caption,
            "altText": asset.alt_text,
            "ocrText": asset.ocr_text,
            "dominantColors": asset.dominant_colors_json.get("colors") if asset.dominant_colors_json else None,
            "label": asset.label,
        }
        items.append(item)
        total_bytes += asset.size_bytes

    return {
        "schemaVersion": "deck-media-context.v1",
        "deckId": deck_id,
        "assetCount": len(items),
        "totalBytes": total_bytes,
        "assets": items,
    }
