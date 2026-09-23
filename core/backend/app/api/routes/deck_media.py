"""Deck media library API routes.

Owns: HTTP endpoints for uploading, listing, retrieving, archiving, retrying,
and patching deck-scoped media assets.
Must not own: business logic, storage, or worker processing.
Stage: API layer between frontend proxies and media service.
Status: KEEP
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.deck_media import (
    DeckMediaArchiveRequest,
    DeckMediaAssetResponse,
    DeckMediaListResponse,
    DeckMediaPatchRequest,
    DeckMediaUploadResponse,
)
from app.services.media.deck_media_service import (
    archive_deck_media_asset,
    get_deck_media_asset,
    get_deck_media_file,
    list_deck_media,
    patch_deck_media_asset,
    retry_deck_media_asset,
    upload_deck_media,
    _serialize_media_asset,
)

router = APIRouter(prefix="/products/deck-aistack-codes/decks", tags=["deck-media"])


@router.post("/{deck_id}/media", response_model=DeckMediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media(
    deck_id: str,
    file: UploadFile = File(...),
    role: str = Form(...),
    label: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckMediaUploadResponse:
    """Upload a media asset (logo, board picture, or deck picture) to the deck."""
    get_user_deck_or_404(db, current_user, deck_id)

    # Validate role
    if role not in {"logo", "board_picture", "deck_picture"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be: logo, board_picture, or deck_picture",
        )

    try:
        asset, job = await upload_deck_media(
            db,
            deck_id=deck_id,
            user=current_user,
            file=file,
            role=role,
            label=label,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    content_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{asset.id}/content"
    serialized = _serialize_media_asset(asset, content_url=content_url)

    return DeckMediaUploadResponse(
        media=serialized,
        processing={
            "jobId": job.id,
            "jobType": job.job_type,
            "status": job.status,
        },
    )


@router.get("/{deck_id}/media", response_model=DeckMediaListResponse)
def list_media(
    deck_id: str,
    include_archived: bool = False,
    cursor: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckMediaListResponse:
    """List media assets for a deck with pagination."""
    get_user_deck_or_404(db, current_user, deck_id)

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit must be between 1 and 100")

    return list_deck_media(
        db,
        deck_id=deck_id,
        include_archived=include_archived,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{deck_id}/media/{media_id}", response_model=DeckMediaAssetResponse)
def get_media(
    deck_id: str,
    media_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckMediaAssetResponse:
    """Get a single media asset by ID."""
    get_user_deck_or_404(db, current_user, deck_id)

    asset = get_deck_media_asset(db, deck_id=deck_id, media_id=media_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    content_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{media_id}/content"
    thumbnail_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{media_id}/thumbnail" if asset.status == "ready" else None
    return _serialize_media_asset(asset, content_url=content_url, thumbnail_url=thumbnail_url)


@router.get("/{deck_id}/media/{media_id}/content")
def get_media_content(
    deck_id: str,
    media_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Get the binary content of a media asset."""
    get_user_deck_or_404(db, current_user, deck_id)

    file_info = get_deck_media_file(db, deck_id=deck_id, media_id=media_id)
    if file_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media content not found")

    path, media_type = file_info
    return FileResponse(path, media_type=media_type)


@router.get("/{deck_id}/media/{media_id}/thumbnail")
def get_media_thumbnail(
    deck_id: str,
    media_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Get the thumbnail of a media asset.

    For MVP, returns the original content. Thumbnail generation is deferred
    to a future phase.
    """
    get_user_deck_or_404(db, current_user, deck_id)

    asset = get_deck_media_asset(db, deck_id=deck_id, media_id=media_id)
    if asset is None or asset.status != "ready":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not available")

    file_info = get_deck_media_file(db, deck_id=deck_id, media_id=media_id)
    if file_info is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media content not found")

    path, media_type = file_info
    return FileResponse(path, media_type=media_type)


@router.patch("/{deck_id}/media/{media_id}", response_model=DeckMediaAssetResponse)
def patch_media(
    deck_id: str,
    media_id: str,
    request: DeckMediaPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckMediaAssetResponse:
    """Update media asset metadata (label, role, llmEnabled)."""
    get_user_deck_or_404(db, current_user, deck_id)

    asset = patch_deck_media_asset(
        db,
        deck_id=deck_id,
        media_id=media_id,
        label=request.label,
        role=request.role,
        llm_enabled=request.llmEnabled,
    )

    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    content_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{media_id}/content"
    thumbnail_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{media_id}/thumbnail" if asset.status == "ready" else None
    return _serialize_media_asset(asset, content_url=content_url, thumbnail_url=thumbnail_url)


@router.post("/{deck_id}/media/{media_id}/archive", response_model=DeckMediaAssetResponse)
def archive_media(
    deck_id: str,
    media_id: str,
    request: DeckMediaArchiveRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckMediaAssetResponse:
    """Archive (soft-delete) a media asset."""
    get_user_deck_or_404(db, current_user, deck_id)

    reason = request.reason if request else None
    asset = archive_deck_media_asset(
        db,
        deck_id=deck_id,
        media_id=media_id,
        reason=reason,
    )

    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found")

    content_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{media_id}/content"
    return _serialize_media_asset(asset, content_url=content_url)


@router.post("/{deck_id}/media/{media_id}/retry", response_model=DeckMediaUploadResponse)
def retry_media(
    deck_id: str,
    media_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckMediaUploadResponse:
    """Retry a failed media asset by creating a new processing job."""
    get_user_deck_or_404(db, current_user, deck_id)

    result = retry_deck_media_asset(
        db,
        deck_id=deck_id,
        media_id=media_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media asset is not in a retryable state",
        )

    asset, job = result
    content_url = f"/api/products/deck-aistack-codes/decks/{deck_id}/media/{media_id}/content"
    serialized = _serialize_media_asset(asset, content_url=content_url)

    return DeckMediaUploadResponse(
        media=serialized,
        processing={
            "jobId": job.id,
            "jobType": job.job_type,
            "status": job.status,
        },
    )
