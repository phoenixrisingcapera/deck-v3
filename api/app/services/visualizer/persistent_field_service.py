from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.visualizer.generated_deck_read_model import apply_field_change, get_editable_field, list_editable_fields, preview_field_change


PERSISTENT_FIELD_ARTIFACT_TYPE = "persistent_field_change_request"
PERSISTENT_FIELD_SCHEMA_VERSION = "persistent-field-change-request.v1"


def _latest_saved_field_change(db: Session, deck_id: str, field_key: str) -> DeckLlmArtifact | None:
    return (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == PERSISTENT_FIELD_ARTIFACT_TYPE,
            DeckLlmArtifact.artifact_key == field_key,
            DeckLlmArtifact.status == "saved",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )


def _serialize_saved_field_change(artifact: DeckLlmArtifact | None) -> dict | None:
    if artifact is None:
        return None
    payload = artifact.payload_json if isinstance(artifact.payload_json, dict) else {}
    return {
        "artifactId": artifact.id,
        "fieldKey": payload.get("fieldKey") or artifact.artifact_key,
        "nextValue": payload.get("nextValue") or payload.get("value") or "",
        "status": artifact.status,
        "summary": artifact.summary,
        "savedAt": artifact.created_at.isoformat() if isinstance(artifact.created_at, datetime) else None,
    }


def list_persistent_fields(db: Session, deck_id: str) -> dict | None:
    payload = list_editable_fields(db, deck_id)
    if payload is None:
        return None
    fields = []
    for field in payload.get("fields", []):
        field_key = str(field.get("fieldKey") or "")
        latest_saved = _serialize_saved_field_change(_latest_saved_field_change(db, deck_id, field_key))
        fields.append({
            **field,
            "savedDraft": latest_saved,
            "versioningEnabled": True,
            "updateMode": "review_required",
        })
    return {
        "deckId": deck_id,
        "fields": fields,
        "schemaVersion": "persistent-fields.v1",
    }


def get_persistent_field(db: Session, deck_id: str, field_key: str) -> dict | None:
    field = get_editable_field(db, deck_id, field_key)
    if field is None:
        return None
    latest_saved = _serialize_saved_field_change(_latest_saved_field_change(db, deck_id, field_key))
    return {
        **field,
        "savedDraft": latest_saved,
        "versioningEnabled": True,
        "updateMode": "review_required",
        "schemaVersion": "persistent-field.v1",
    }


def preview_persistent_field_change(db: Session, deck_id: str, field_key: str, value: str) -> dict | None:
    preview = preview_field_change(db, deck_id, field_key, value)
    if preview is None:
        return None
    latest_saved = _serialize_saved_field_change(_latest_saved_field_change(db, deck_id, field_key))
    preview["savedDraft"] = latest_saved
    preview["schemaVersion"] = "persistent-field-preview.v1"
    return preview


def save_persistent_field_change(db: Session, deck_id: str, field_key: str, value: str) -> dict | None:
    field = get_editable_field(db, deck_id, field_key)
    if field is None:
        return None

    latest_saved = _latest_saved_field_change(db, deck_id, field_key)
    if latest_saved is not None:
        latest_saved.status = "superseded"
        db.add(latest_saved)

    artifact = DeckLlmArtifact(
        id=generate_id("artifact"),
        deck_id=deck_id,
        artifact_type=PERSISTENT_FIELD_ARTIFACT_TYPE,
        artifact_key=field_key,
        schema_version=PERSISTENT_FIELD_SCHEMA_VERSION,
        status="saved",
        summary=f"Saved draft for {field.get('label') or field_key}",
        payload_json={
            "fieldKey": field_key,
            "label": field.get("label"),
            "nextValue": value,
            "savedFrom": "smart_edit_field_sync",
        },
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return {
        "schemaVersion": "persistent-field-save.v1",
        "saved": True,
        "deckId": deck_id,
        "fieldKey": field_key,
        "value": value,
        "savedDraft": _serialize_saved_field_change(artifact),
        "message": "Field draft saved for review. No deck content has been mutated yet.",
    }


def apply_persistent_field_change(db: Session, deck_id: str, field_key: str, value: str | None = None) -> dict | None:
    next_value = value
    saved_artifact = _latest_saved_field_change(db, deck_id, field_key)
    if not next_value and saved_artifact is not None:
        payload = saved_artifact.payload_json if isinstance(saved_artifact.payload_json, dict) else {}
        next_value = str(payload.get("nextValue") or payload.get("value") or "")
    if next_value is None:
        return None

    applied = apply_field_change(db, deck_id, field_key, next_value)
    if applied is None:
        return None

    if saved_artifact is not None:
        saved_artifact.status = "applied"
        db.add(saved_artifact)
        db.commit()

    return {
        **applied,
        "schemaVersion": "persistent-field-apply.v1",
        "appliedDraft": _serialize_saved_field_change(saved_artifact),
    }
