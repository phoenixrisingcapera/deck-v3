"""Deck media library service.

Owns: CRUD orchestration for deck-scoped media assets, storage persistence,
workflow job creation, and authenticated content delivery.
Must not own: image processing logic, worker execution, or LLM context assembly.
Stage: service layer between API routes and storage/worker infrastructure.
Status: KEEP
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckMediaAsset, User, WorkflowJob
from app.schemas.deck_media import DeckMediaAssetResponse, DeckMediaListResponse
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_FAILED_RETRYABLE,
    JOB_STATUS_QUEUED,
    JOB_TYPE_MEDIA_PROCESSING,
    ensure_workflow_job,
)
from app.services.storage.artifact_storage import get_upload_storage

logger = logging.getLogger(__name__)

ALLOWED_MEDIA_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

MAX_MEDIA_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_MEDIA_PER_DECK = 50


def _validate_media_file(mime_type: str, size_bytes: int) -> None:
    """Validate media file type and size."""
    if mime_type not in ALLOWED_MEDIA_MIME_TYPES:
        raise ValueError(f"Unsupported media type: {mime_type}. Allowed: PNG, JPEG, WebP")
    if size_bytes > MAX_MEDIA_FILE_SIZE_BYTES:
        raise ValueError(f"Media file too large: {size_bytes} bytes. Maximum: {MAX_MEDIA_FILE_SIZE_BYTES} bytes")


def _build_storage_path(deck_id: str, asset_id: str, filename: str) -> str:
    """Build deck-namespaced storage path for media asset."""
    safe_filename = Path(filename).name
    return f"users/decks/{deck_id}/media/{asset_id}/original/{safe_filename}"


def _compute_sha256(payload: bytes) -> str:
    """Compute SHA-256 hash of payload."""
    return hashlib.sha256(payload).hexdigest()


def _serialize_media_asset(asset: DeckMediaAsset, *, content_url: str, thumbnail_url: str | None = None) -> DeckMediaAssetResponse:
    """Serialize a media asset to API response format."""
    return DeckMediaAssetResponse(
        id=asset.id,
        deckId=asset.deck_id,
        role=asset.role,
        label=asset.label,
        status=asset.status,
        originalFilename=asset.original_filename,
        mimeType=asset.mime_type,
        sizeBytes=asset.size_bytes,
        sha256=asset.sha256,
        width=asset.width,
        height=asset.height,
        caption=asset.caption,
        altText=asset.alt_text,
        ocrText=asset.ocr_text,
        dominantColors=asset.dominant_colors_json.get("colors") if asset.dominant_colors_json else None,
        llmEnabled=asset.llm_enabled,
        errorCode=asset.error_code,
        errorMessage=asset.error_message,
        contentUrl=content_url,
        thumbnailUrl=thumbnail_url,
        workflowJobId=asset.workflow_job_id,
        createdAt=asset.created_at.isoformat(),
        updatedAt=asset.updated_at.isoformat(),
        processedAt=asset.processed_at.isoformat() if asset.processed_at else None,
        archivedAt=asset.archived_at.isoformat() if asset.archived_at else None,
    )


async def upload_deck_media(
    db: Session,
    *,
    deck_id: str,
    user: User,
    file: UploadFile,
    role: str,
    label: str | None = None,
) -> tuple[DeckMediaAsset, WorkflowJob]:
    """Upload a media asset and queue processing job.

    Returns the created asset and workflow job.
    """
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")

    # Check per-deck quota
    existing_count = db.query(DeckMediaAsset).filter(
        DeckMediaAsset.deck_id == deck_id,
        DeckMediaAsset.status != "archived",
    ).count()
    if existing_count >= MAX_MEDIA_PER_DECK:
        raise ValueError(f"Media quota exceeded: maximum {MAX_MEDIA_PER_DECK} assets per deck")

    # Read file content
    payload = await file.read()
    size_bytes = len(payload)
    mime_type = file.content_type or "application/octet-stream"

    # Validate file
    _validate_media_file(mime_type, size_bytes)

    # Compute hash
    sha256 = _compute_sha256(payload)

    # Create asset record
    asset_id = generate_id("media")
    storage = get_upload_storage()
    storage_path = _build_storage_path(deck_id, asset_id, file.filename or "upload")

    # Write and promote before queueing so workers on another Railway instance
    # can resolve the object from shared storage.
    stored = storage.write_bytes(storage_path, payload)
    storage.promote(stored)

    asset = DeckMediaAsset(
        id=asset_id,
        deck_id=deck_id,
        workspace_id=deck.workspace_id,
        uploaded_by_user_id=user.id,
        role=role,
        label=label,
        status="queued",
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        storage_provider=storage.provider,
        storage_path=storage_path,
        size_bytes=size_bytes,
        sha256=sha256,
    )
    db.add(asset)
    db.flush()

    # Create workflow job
    job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_MEDIA_PROCESSING,
        input_payload={
            "mediaId": asset.id,
            "storagePath": storage_path,
            "sha256": sha256,
            "mimeType": mime_type,
            "role": role,
        },
        idempotency_key=f"{deck_id}:{sha256}:media_processing:v1",
        priority=50,
    )

    asset.workflow_job_id = job.id
    db.commit()

    logger.info(
        "Uploaded media asset %s for deck %s with job %s",
        asset.id,
        deck_id,
        job.id,
    )

    return asset, job


def list_deck_media(
    db: Session,
    *,
    deck_id: str,
    include_archived: bool = False,
    cursor: str | None = None,
    limit: int = 50,
) -> DeckMediaListResponse:
    """List media assets for a deck with pagination."""
    query = db.query(DeckMediaAsset).filter(DeckMediaAsset.deck_id == deck_id)

    if not include_archived:
        query = query.filter(DeckMediaAsset.status != "archived")

    if cursor:
        cursor_asset = db.query(DeckMediaAsset).filter(DeckMediaAsset.id == cursor).one_or_none()
        if cursor_asset:
            query = query.filter(DeckMediaAsset.created_at < cursor_asset.created_at)

    assets = query.order_by(DeckMediaAsset.created_at.desc()).limit(limit + 1).all()

    has_next = len(assets) > limit
    items = assets[:limit]
    next_cursor = items[-1].id if has_next and items else None

    # Build counts
    counts_query = db.query(DeckMediaAsset.status, func.count(DeckMediaAsset.id)).filter(
        DeckMediaAsset.deck_id == deck_id
    ).group_by(DeckMediaAsset.status).all()
    counts = {status: count for status, count in counts_query}

    # Serialize items
    serialized_items = []
    for asset in items:
        content_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{asset.id}/content"
        thumbnail_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{asset.id}/thumbnail" if asset.status == "ready" else None
        serialized_items.append(_serialize_media_asset(asset, content_url=content_url, thumbnail_url=thumbnail_url))

    return DeckMediaListResponse(
        deckId=deck_id,
        items=serialized_items,
        counts=counts,
        nextCursor=next_cursor,
    )


def get_deck_media_asset(
    db: Session,
    *,
    deck_id: str,
    media_id: str,
) -> DeckMediaAsset | None:
    """Get a single media asset by ID, ensuring it belongs to the deck."""
    return (
        db.query(DeckMediaAsset)
        .filter(DeckMediaAsset.id == media_id, DeckMediaAsset.deck_id == deck_id)
        .one_or_none()
    )


def get_deck_media_file(
    db: Session,
    *,
    deck_id: str,
    media_id: str,
) -> tuple[Path, str] | None:
    """Get the file path and MIME type for a media asset."""
    asset = get_deck_media_asset(db, deck_id=deck_id, media_id=media_id)
    if asset is None or asset.status == "archived":
        return None

    storage = get_upload_storage()
    path = storage.resolve_path(asset.storage_path)
    if path is None or not path.exists():
        return None

    return path, asset.mime_type


def archive_deck_media_asset(
    db: Session,
    *,
    deck_id: str,
    media_id: str,
    reason: str | None = None,
) -> DeckMediaAsset | None:
    """Soft-delete a media asset by marking it archived."""
    asset = get_deck_media_asset(db, deck_id=deck_id, media_id=media_id)
    if asset is None:
        return None

    asset.status = "archived"
    asset.archived_at = datetime.utcnow()
    asset.llm_enabled = False
    if reason:
        metadata = dict(asset.metadata_json or {})
        metadata["archiveReason"] = reason
        asset.metadata_json = metadata

    db.commit()
    logger.info("Archived media asset %s for deck %s", media_id, deck_id)
    return asset


def retry_deck_media_asset(
    db: Session,
    *,
    deck_id: str,
    media_id: str,
) -> tuple[DeckMediaAsset, WorkflowJob] | None:
    """Retry a failed media asset by creating a new workflow job."""
    asset = get_deck_media_asset(db, deck_id=deck_id, media_id=media_id)
    if asset is None or asset.status not in {"failed_retryable", "failed_final"}:
        return None

    # Reset status
    asset.status = "queued"
    asset.error_code = None
    asset.error_message = None
    asset.processed_at = None

    # Create new job
    deck = db.query(Deck).filter(Deck.id == deck_id).one()
    job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_MEDIA_PROCESSING,
        input_payload={
            "mediaId": asset.id,
            "storagePath": asset.storage_path,
            "sha256": asset.sha256,
            "mimeType": asset.mime_type,
            "role": asset.role,
        },
        idempotency_key=f"{deck_id}:{asset.sha256}:media_processing:retry:{generate_id('retry')}",
        priority=50,
    )

    asset.workflow_job_id = job.id
    db.commit()

    logger.info("Retried media asset %s for deck %s with job %s", media_id, deck_id, job.id)
    return asset, job


def patch_deck_media_asset(
    db: Session,
    *,
    deck_id: str,
    media_id: str,
    label: str | None = None,
    role: str | None = None,
    llm_enabled: bool | None = None,
) -> DeckMediaAsset | None:
    """Update media asset metadata."""
    asset = get_deck_media_asset(db, deck_id=deck_id, media_id=media_id)
    if asset is None:
        return None

    if label is not None:
        asset.label = label
    if role is not None:
        asset.role = role
    if llm_enabled is not None:
        asset.llm_enabled = llm_enabled

    db.commit()
    logger.info("Patched media asset %s for deck %s", media_id, deck_id)
    return asset
