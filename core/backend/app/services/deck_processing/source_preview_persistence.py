from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckFile, DeckSlide, DeckSlideAsset
from app.services.deck_processing.source_preview_renderer import PREVIEW_MIME_TYPE, SourceSlidePreview
from app.services.storage.artifact_storage import get_upload_storage


def _delete_replaced_storage_path(storage_path: str | None, replacement_path: str) -> None:
    if not storage_path or storage_path == replacement_path:
        return
    try:
        get_upload_storage().delete(storage_path)
    except Exception:
        # A stale preview object must not block retry replacement. The database
        # row is still moved to the canonical latest preview path below.
        pass


def source_slide_for_page(
    db: Session,
    deck: Deck,
    *,
    page_index: int,
) -> DeckSlide:
    slide_number = page_index + 1
    slide = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck.id, DeckSlide.source_page_number == slide_number)
        .one_or_none()
    )
    if slide is None:
        raise ValueError(
            f"Source slide {slide_number} is missing. Run source_extraction before miniatures."
        )
    return slide


def persist_source_preview(
    db: Session,
    *,
    deck: Deck,
    deck_file: DeckFile,
    slide: DeckSlide,
    extraction_run_id: str | None,
    source_checksum: str,
    preview: SourceSlidePreview,
    converted_to_pdf: bool,
) -> DeckSlideAsset:
    # Miniatures only enriches source slides with preview artifacts. The source
    # extraction stage owns slide creation, text, title, blocks, and structure.
    for old_path in {slide.thumbnail_path, slide.rendered_image_path}:
        _delete_replaced_storage_path(old_path, preview.relative_path)

    slide.thumbnail_path = preview.relative_path
    slide.thumbnail_mime_type = PREVIEW_MIME_TYPE
    slide.rendered_image_path = preview.relative_path
    slide.asset_count = max(slide.asset_count or 0, 1)
    slide.metadata_json = {
        **(slide.metadata_json or {}),
        "preview": {
            "status": "ready",
            "storageProvider": preview.storage_provider,
            "storagePath": preview.relative_path,
            "width": preview.width,
            "height": preview.height,
            "mimeType": PREVIEW_MIME_TYPE,
            "sha256": preview.checksum_sha256,
        },
        "extractor": "pymupdf_preview_v1",
        "convertedToPdf": converted_to_pdf,
        "sourceChecksum": deck_file.checksum_sha256,
    }

    asset = (
        db.query(DeckSlideAsset)
        .filter(
            DeckSlideAsset.deck_id == deck.id,
            DeckSlideAsset.slide_id == slide.id,
            DeckSlideAsset.asset_type == "source_preview",
        )
        .one_or_none()
    )
    if asset is None:
        asset = DeckSlideAsset(
            id=generate_id("asset"),
            deck_id=deck.id,
            slide_id=slide.id,
            asset_type="source_preview",
        )
        db.add(asset)
    else:
        _delete_replaced_storage_path(asset.storage_path, preview.relative_path)

    filename = Path(preview.relative_path).name
    asset.extraction_run_id = extraction_run_id
    asset.asset_kind = "slide_preview"
    asset.storage_provider = preview.storage_provider
    asset.label = f"Slide {slide.slide_number or slide.slide_index} preview"
    asset.mime_type = PREVIEW_MIME_TYPE
    asset.storage_path = preview.relative_path
    asset.filename = filename
    asset.page_number = slide.source_page_number
    asset.width = preview.width
    asset.height = preview.height
    asset.file_size_bytes = preview.size
    asset.sha256 = preview.checksum_sha256
    asset.metadata_json = {
        "generatedFrom": "pymupdf",
        "canonicalSourcePreview": True,
        "sourceChecksum": source_checksum,
    }
    return asset
