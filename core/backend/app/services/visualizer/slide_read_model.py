"""Visualizer slide read model.

Owns read-only deck, slide, block, preview URL, and visualizer-facing payloads
used by routes and UI consumers.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session, selectinload

from app.db.models import AdaptationSuggestion, AnalysisFinding, Deck, DeckFile, DeckLlmArtifact, DeckSlide, DeckSlideBlock, DeckSlideRevision, DesignToken, SmartEditSuggestion, Workspace
from app.services.storage.signed_urls import get_bucket_artifact_service
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.state_machine import canonical_deck_state
from app.services.storage.artifact_storage import get_upload_storage
from app.services.deck_processing.workspace_summary_service import resolve_workspace_for_user


def _soft_delete_workspace_intake_decks(db: Session, workspace: Workspace | None) -> list[str]:
    from app.services.deck_processing.workspace_summary_service import soft_delete_old_intake_decks

    return soft_delete_old_intake_decks(db, workspace)


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _deck_state(deck: Deck) -> str:
    return canonical_deck_state(deck.status).value


def _is_soft_deleted(deck: Deck) -> bool:
    metadata = deck.metadata_json or {}
    return bool(metadata.get("soft_deleted_at"))


def _map_deck(deck: Deck) -> dict:
    state = _deck_state(deck)
    return {
        "id": deck.id,
        "workspace_id": deck.workspace_id,
        "title": deck.title,
        "audience": deck.audience,
        "purpose": deck.purpose,
        "status": state,
        "state": state,
        "deckStatus": state,
        "summary": deck.summary,
        "created_at": deck.created_at,
        "updated_at": deck.updated_at,
    }


def _map_file(file: DeckFile | None) -> dict | None:
    if file is None:
        return None
    return {
        "id": file.id,
        "deck_id": file.deck_id,
        "filename": file.original_filename or file.filename,
        "stored_filename": file.filename,
        "mime_type": file.mime_type,
        "size": file.size,
        "storage_path": file.storage_path,
        "uploaded_at": _iso(file.uploaded_at),
    }


def _signed_upload_url(storage_path: str | None) -> str | None:
    if not storage_path:
        return None
    try:
        return get_upload_storage().create_signed_get_url(storage_path)
    except Exception:
        return None


def _signed_artifact_url(storage_path: str | None) -> str | None:
    if not storage_path:
        return None
    try:
        return get_bucket_artifact_service().create_signed_url_sync(key=storage_path)
    except Exception:
        return None


def _map_slide(slide: DeckSlide) -> dict:
    preview_asset = next(
        (
            asset
            for asset in sorted(slide.assets, key=lambda item: item.created_at, reverse=True)
            if asset.asset_type == "source_preview" and asset.storage_path
        ),
        None,
    )
    preview_url = f"/api/decks/{slide.deck_id}/slides/{slide.id}/preview" if preview_asset else None
    signed_preview_url = _signed_upload_url(preview_asset.storage_path) if preview_asset else None
    resolved_preview_url = signed_preview_url or preview_url
    return {
        "id": slide.id,
        "deck_id": slide.deck_id,
        "deckId": slide.deck_id,
        "slide_index": slide.slide_index,
        "slideIndex": slide.slide_index,
        "slide_number": slide.slide_number or slide.source_page_number or slide.slide_index,
        "slideNumber": slide.slide_number or slide.source_page_number or slide.slide_index,
        "title": slide.title,
        "role": slide.role,
        "raw_text": slide.raw_text,
        "rawText": slide.raw_text,
        "extractedText": slide.raw_text,
        "narrative_notes": slide.narrative_notes,
        "narrativeNotes": slide.narrative_notes,
        "summary": slide.summary,
        "status": "ready" if preview_asset else "pending",
        "previewUrl": resolved_preview_url,
        "preview_url": resolved_preview_url,
        "previewImageUrl": resolved_preview_url,
        "thumbnailUrl": resolved_preview_url,
        "signedPreviewUrl": signed_preview_url,
        "signedThumbnailUrl": signed_preview_url,
        "previewProxyUrl": preview_url,
        "previewWidth": preview_asset.width if preview_asset else None,
        "previewHeight": preview_asset.height if preview_asset else None,
        "previewMimeType": preview_asset.mime_type if preview_asset else slide.thumbnail_mime_type,
    }


def _map_llm_artifact(artifact: DeckLlmArtifact) -> dict:
    storage_path = artifact.bucket_payload_key
    if not storage_path and isinstance(artifact.payload_json, dict):
        storage_path = artifact.payload_json.get("storagePath")
    return {
        "id": artifact.id,
        "deckId": artifact.deck_id,
        "artifactType": artifact.artifact_type,
        "artifactKey": artifact.artifact_key,
        "schemaVersion": artifact.schema_version,
        "status": artifact.status,
        "summary": artifact.summary,
        "bucketPayloadKey": storage_path,
        "signedUrl": _signed_artifact_url(storage_path),
        "metricsJson": artifact.metrics_json,
        "createdAt": _iso(artifact.created_at),
        "updatedAt": _iso(artifact.updated_at),
    }


def _map_block(block: DeckSlideBlock) -> dict:
    return {
        "id": block.id,
        "slide_id": block.slide_id,
        "block_index": block.block_index,
        "raw_text": block.raw_text,
        "normalized_text": block.normalized_text,
        "block_type": block.block_type,
        "position": block.position,
        "style": block.style,
    }


def _map_finding(finding: AnalysisFinding) -> dict:
    return {
        "id": finding.id,
        "deck_id": finding.deck_id,
        "slide_id": finding.slide_id,
        "block_id": finding.block_id,
        "title": finding.title,
        "detail": finding.detail,
        "severity": finding.severity,
        "category": finding.category,
    }


def _map_adaptation_suggestion(suggestion: AdaptationSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "deck_id": suggestion.deck_id,
        "slide_id": suggestion.slide_id,
        "block_id": suggestion.block_id,
        "title": suggestion.title,
        "reason": suggestion.reason,
        "suggested_text": suggestion.suggested_text,
        "status": suggestion.status,
        "audience": suggestion.audience,
    }


def _map_smart_edit_suggestion(suggestion: SmartEditSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "run_id": suggestion.run_id,
        "deck_id": suggestion.deck_id,
        "slide_id": suggestion.slide_id,
        "block_id": suggestion.block_id,
        "original_text": suggestion.original_text,
        "suggested_text": suggestion.suggested_text,
        "reason": suggestion.reason,
        "risk_level": suggestion.risk_level,
        "status": suggestion.status,
    }


def _map_revision(revision: DeckSlideRevision) -> dict:
    return {
        "id": revision.id,
        "deck_id": revision.deck_id,
        "slide_id": revision.slide_id,
        "block_id": revision.block_id,
        "previous_text": revision.previous_text,
        "next_text": revision.next_text,
        "reason": revision.reason,
        "created_at": _iso(revision.created_at),
    }


def list_decks(db: Session, user_id: str | None = None, include_all: bool = False) -> list[dict]:
    if user_id is not None:
        workspace = resolve_workspace_for_user(db, user_id)
        if workspace is not None:
            _soft_delete_workspace_intake_decks(db, workspace)

    query = db.query(Deck)
    if user_id is not None and not include_all:
        query = query.join(Workspace, Workspace.id == Deck.workspace_id).filter(
            (Deck.user_id == user_id) | (Workspace.user_id == user_id)
        )
    return [
        _map_deck(deck)
        for deck in query.order_by(Deck.updated_at.desc(), Deck.created_at.desc()).all()
        if not _is_soft_deleted(deck)
    ]


def get_deck(db: Session, deck_id: str) -> dict | None:
    deck = (
        db.query(Deck)
        .options(
            selectinload(Deck.file),
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.slides).selectinload(DeckSlide.assets),
            selectinload(Deck.llm_artifacts),
        )
        .filter(Deck.id == deck_id)
        .one_or_none()
    )
    if deck is None:
        return None

    return {
        "deck": _map_deck(deck),
        "file": _map_file(deck.file),
        "slides": [_map_slide(slide) for slide in sorted(deck.slides, key=lambda item: item.slide_index)],
        "llm_artifacts": [
            _map_llm_artifact(artifact)
            for artifact in sorted(deck.llm_artifacts, key=lambda item: item.created_at, reverse=True)
        ],
        "llmArtifacts": [
            _map_llm_artifact(artifact)
            for artifact in sorted(deck.llm_artifacts, key=lambda item: item.created_at, reverse=True)
        ],
        "findings": get_findings(db, deck.id),
        "suggestions": get_suggestions(db, deck.id),
        "smart_edit_suggestions": [
            _map_smart_edit_suggestion(item)
            for item in db.query(SmartEditSuggestion)
            .filter(SmartEditSuggestion.deck_id == deck.id)
            .order_by(SmartEditSuggestion.id.asc())
            .all()
        ],
        "revisions": [
            _map_revision(item)
            for item in db.query(DeckSlideRevision)
            .filter(DeckSlideRevision.deck_id == deck.id)
            .order_by(DeckSlideRevision.created_at.desc())
            .all()
        ],
    }


def get_status(db: Session, deck_id: str) -> dict | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None
    workflow = get_deck_workflow_state(db, deck_id)
    if workflow is None:
        state = _deck_state(deck)
        return {"status": state, "state": state, "deckStatus": state, "updated_at": deck.updated_at}

    workflow_status = str(workflow.get("status") or _deck_state(deck))
    return {
        "status": workflow_status,
        "state": workflow_status,
        "deckStatus": workflow_status,
        "phase": workflow.get("phase"),
        "nextAction": workflow.get("nextAction"),
        "blockingReason": workflow.get("blockingReason"),
        "workflowId": workflow.get("workflowId"),
        "updated_at": workflow.get("updatedAt") or deck.updated_at,
        "activeJob": workflow.get("activeJob"),
    }


def get_slides(db: Session, deck_id: str) -> list[dict]:
    return [
        _map_slide(slide)
        for slide in db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck_id)
        .options(selectinload(DeckSlide.assets))
        .order_by(DeckSlide.slide_index.asc())
        .all()
    ]


def get_blocks(db: Session, deck_id: str, slide_id: str) -> list[dict]:
    return [
        _map_block(block)
        for block in db.query(DeckSlideBlock)
        .join(DeckSlide, DeckSlide.id == DeckSlideBlock.slide_id)
        .filter(DeckSlide.deck_id == deck_id, DeckSlide.id == slide_id)
        .order_by(DeckSlideBlock.block_index.asc())
        .all()
    ]


def get_findings(db: Session, deck_id: str) -> list[dict]:
    return [
        _map_finding(finding)
        for finding in db.query(AnalysisFinding)
        .filter(AnalysisFinding.deck_id == deck_id)
        .order_by(AnalysisFinding.severity.desc(), AnalysisFinding.title.asc())
        .all()
    ]


def get_suggestions(db: Session, deck_id: str) -> list[dict]:
    return [
        _map_adaptation_suggestion(suggestion)
        for suggestion in db.query(AdaptationSuggestion)
        .filter(AdaptationSuggestion.deck_id == deck_id)
        .order_by(AdaptationSuggestion.title.asc())
        .all()
    ]


SMART_DECK_ASSISTANT_ARTIFACT_TYPE = "smart_deck_assistant_run"
SMART_DECK_ASSISTANT_ARTIFACT_STORAGE_VERSION = "smart-deck-assistant-artifact.v1"


def _map_design_token(token: DesignToken) -> dict:
    return {
        "id": token.id,
        "name": token.name,
        "value": token.value,
        "type": token.type,
        "description": token.description,
        "createdAt": _iso(token.created_at) or "",
        "updatedAt": _iso(token.updated_at) or "",
    }


def load_deck_llm_artifact_payload(artifact: DeckLlmArtifact) -> dict:
    payload = artifact.payload_json or {}
    if not isinstance(payload, dict):
        return {}
    if payload.get("artifactStorageVersion") != SMART_DECK_ASSISTANT_ARTIFACT_STORAGE_VERSION:
        return payload
    storage_path = payload.get("storagePath")
    if not isinstance(storage_path, str):
        return {}
    try:
        payload_bytes = get_bucket_artifact_service().get_bytes_sync(key=storage_path)
    except Exception:
        return {}
    return json.loads(payload_bytes.decode("utf-8"))


def list_design_tokens(db: Session, deck_id: str) -> dict | None:
    if db.query(Deck.id).filter(Deck.id == deck_id).first() is None:
        return None
    tokens = db.query(DesignToken).filter(DesignToken.deck_id == deck_id).order_by(DesignToken.created_at.desc()).all()
    return {"designTokens": [_map_design_token(token) for token in tokens]}


__all__ = [
    "get_blocks",
    "get_deck",
    "get_findings",
    "get_slides",
    "get_status",
    "get_suggestions",
    "list_decks",
    "list_design_tokens",
    "load_deck_llm_artifact_payload",
]
