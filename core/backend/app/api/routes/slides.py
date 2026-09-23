from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import DeckSlide, DeckSlideAsset, User
from app.services.storage.artifact_storage import get_upload_storage
from app.services.storage.deck_file_service import get_upload_root, resolve_upload_path
from app.services.visualizer.slide_read_model import get_slides

router = APIRouter(prefix="/decks", tags=["slides"])


# DISABLED ROUTE REGISTRATION: `decks.py::decks_slides` owns GET /api/decks/{deck_id}/slides.
# Reason: duplicate method/path registrations are order-dependent and unsafe.
# @router.get("/{deck_id}/slides")
def slides(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    get_user_deck_or_404(db, current_user, deck_id)
    return {"slides": get_slides(db, deck_id)}


@router.get("/{deck_id}/slides/{slide_id}/preview")
def slide_preview(
    deck_id: str,
    slide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    slide = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck_id, DeckSlide.id == slide_id)
        .one_or_none()
    )
    if slide is None:
        raise HTTPException(status_code=404, detail="Slide preview not found")
    asset = (
        db.query(DeckSlideAsset)
        .join(DeckSlide, DeckSlide.id == DeckSlideAsset.slide_id)
        .filter(
            DeckSlide.deck_id == deck_id,
            DeckSlide.id == slide_id,
            DeckSlideAsset.asset_type == "source_preview",
        )
        .order_by(DeckSlideAsset.created_at.desc())
        .first()
    )
    # Worker versions predating the source-preview asset row still persisted
    # the canonical shared-storage path on DeckSlide. Preserve that durable
    # worker output as a read fallback rather than returning a false 404.
    storage_path = asset.storage_path if asset is not None else None
    fallback_mime_type = None
    if not storage_path:
        # Prefer the thumbnail because it has persisted MIME metadata. Older
        # workers may only have rendered_image_path, which remains the final
        # compatibility fallback and defaults to PNG below.
        storage_path = slide.thumbnail_path or slide.rendered_image_path
        if storage_path == slide.thumbnail_path:
            fallback_mime_type = slide.thumbnail_mime_type
    if not storage_path:
        raise HTTPException(status_code=404, detail="Slide preview not found")

    root = get_upload_root().resolve()
    preview_path = resolve_upload_path(storage_path)
    resolved_from_shared_storage = False
    if preview_path is None or not preview_path.is_file():
        preview_path = get_upload_storage().resolve_path(storage_path)
        resolved_from_shared_storage = preview_path is not None
    if preview_path is None:
        raise HTTPException(status_code=404, detail="Slide preview not found")
    # Shared storage implementations may safely materialize a requested object
    # in their own managed cache outside UPLOADS_ROOT. Their resolve_path()
    # implementation validates the storage key, so only direct local fallback
    # paths need the UPLOADS_ROOT containment check.
    if (not resolved_from_shared_storage and not _is_relative_to(preview_path, root)) or not preview_path.is_file():
        raise HTTPException(status_code=404, detail="Slide preview not found")

    media_type = asset.mime_type if asset is not None else fallback_mime_type
    return FileResponse(preview_path, media_type=media_type or "image/png")


@router.get("/{deck_id}/slides/{slide_id}/assets/{asset_id}")
def slide_asset(
    deck_id: str,
    slide_id: str,
    asset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    asset = (
        db.query(DeckSlideAsset)
        .join(DeckSlide, DeckSlide.id == DeckSlideAsset.slide_id)
        .filter(
            DeckSlide.deck_id == deck_id,
            DeckSlide.id == slide_id,
            DeckSlideAsset.id == asset_id,
        )
        .first()
    )
    if asset is None or not asset.storage_path:
        raise HTTPException(status_code=404, detail="Slide asset not found")

    asset_path = resolve_upload_path(asset.storage_path)
    if asset_path is None or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Slide asset not found")

    return FileResponse(asset_path, media_type=asset.mime_type or "application/octet-stream")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
