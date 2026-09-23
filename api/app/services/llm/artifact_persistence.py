from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Deck
from app.services.storage.signed_urls import get_bucket_artifact_service


CANONICAL_LLM_ARTIFACT_FILENAMES = {
    "smart_deck_source_facts": "source_facts.json",
    "smart_deck_generation_plan": "generation_plan.json",
    "generated_slide_render_schema": "render_schema.json",
    "smart_deck_generation_critique": "critique.json",
    "smart_edit_source_facts": "smart_edits.json",
    "smart_edit_plan": "smart_edits.json",
    "smart_edit_critique": "smart_edits.json",
    "smart_edit_repair": "smart_edits.json",
}


def canonical_llm_artifact_key(*, user_id: str | None, deck_id: str, filename: str) -> str:
    return f"users/{user_id or 'unknown-user'}/decks/{deck_id}/llm/{filename}"


def persist_canonical_llm_artifact(
    db: Session,
    *,
    deck_id: str,
    artifact_type: str,
    payload: dict,
) -> dict | None:
    filename = CANONICAL_LLM_ARTIFACT_FILENAMES.get(artifact_type)
    if not filename:
        return None

    user_id = db.query(Deck.user_id).filter(Deck.id == deck_id).scalar()
    storage_path = canonical_llm_artifact_key(user_id=user_id, deck_id=deck_id, filename=filename)
    get_bucket_artifact_service().put_json_sync(key=storage_path, data=payload)
    return {
        "storageProvider": settings.upload_storage_backend,
        "storagePath": storage_path,
        "filename": filename,
        "contentType": "application/json",
    }
