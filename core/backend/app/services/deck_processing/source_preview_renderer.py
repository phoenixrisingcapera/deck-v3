from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.core.security import generate_id
from app.services.storage.deck_file_service import get_upload_root
from app.services.storage.artifact_storage import LocalUploadStorage, StoredUpload, get_upload_storage, promote_upload

PREVIEW_MIME_TYPE = "image/png"


@dataclass(frozen=True)
class SourceSlidePreview:
    path: Path
    relative_path: str
    storage_provider: str
    width: int
    height: int
    checksum_sha256: str
    size: int


def _local_preview_output_path(storage_path: str) -> Path | None:
    # Remote storage resolve_path() fetches existing objects. Rendering needs a
    # writable local cache path before promotion to the configured upload store.
    return LocalUploadStorage().resolve_path(storage_path)


def _deck_asset_prefix(*, deck_id: str, user_id: str | None) -> str:
    return f"users/{user_id or 'unknown-user'}/decks/{deck_id}"


def _render_pdf_page(fitz, page, output_path: Path) -> SourceSlidePreview:
    # 144 DPI gives small, readable source mirrors without storing full-resolution pages.
    storage = get_upload_storage()
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(output_path)
    payload = output_path.read_bytes()
    return SourceSlidePreview(
        path=output_path,
        relative_path=str(output_path.relative_to(get_upload_root())),
        storage_provider=storage.provider,
        width=int(pixmap.width),
        height=int(pixmap.height),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
    )


def _promote_preview(preview: SourceSlidePreview) -> SourceSlidePreview:
    stored = promote_upload(
        StoredUpload(provider=preview.storage_provider, storage_path=preview.relative_path, path=preview.path)
    )
    return SourceSlidePreview(
        path=stored.path,
        relative_path=stored.storage_path,
        storage_provider=stored.provider,
        width=preview.width,
        height=preview.height,
        checksum_sha256=preview.checksum_sha256,
        size=preview.size,
    )


def render_source_preview_page(
    *,
    fitz,
    page,
    deck_id: str,
    user_id: str | None,
    slide_number: int,
) -> SourceSlidePreview:
    output_storage_path = (
        f"{_deck_asset_prefix(deck_id=deck_id, user_id=user_id)}/previews/"
        f"slide-{slide_number:04d}-{generate_id('preview')}.png"
    )
    output_path = _local_preview_output_path(output_storage_path)
    if output_path is None:
        raise ValueError("Preview storage path is invalid")
    return _promote_preview(_render_pdf_page(fitz, page, output_path))
