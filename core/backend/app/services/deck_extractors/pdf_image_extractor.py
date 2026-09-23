from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, TypedDict

from app.services.storage.artifact_storage import StoredUpload, get_upload_storage, promote_upload

MAX_IMAGES_PER_PDF = 200
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class PdfImageExtractionError(ValueError):
    """Raised when embedded PDF image extraction cannot safely continue."""


class ExtractedImageAsset(TypedDict):
    assetType: str
    label: str
    mimeType: str
    storageProvider: str
    storagePath: str
    pageNumber: int
    width: int | None
    height: int | None
    metadataJson: dict[str, Any]


def _validate_pdf_path(pdf_path: Path) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        raise PdfImageExtractionError(f"Expected PDF file, got directory or special file: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise PdfImageExtractionError(f"Expected PDF file, got: {pdf_path}")


def _load_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise PdfImageExtractionError("Embedded PDF image extraction requires PyMuPDF to be installed") from exc
    return fitz


def _mime_type_for_extension(extension: str) -> str:
    if extension in {"jpg", "jpeg"}:
        return "image/jpeg"
    return mimetypes.types_map.get(f".{extension}", "application/octet-stream")


def _storage_path_for_image(*, asset_prefix: str | None, page_number: int, checksum: str, extension: str) -> str:
    clean_prefix = asset_prefix.strip("/") if asset_prefix else ""
    relative_path = f"pdf-assets/extracted-images/{page_number}/{checksum}.{extension}"
    return f"{clean_prefix}/{relative_path}" if clean_prefix else relative_path


def extract_pdf_image_metadata(pdf_path: Path) -> dict[int, dict]:
    # Metadata and extraction intentionally use the same engine so page image
    # counts match the assets that extract_pdf_embedded_image_assets can produce.
    _validate_pdf_path(pdf_path)
    fitz = _load_fitz()

    page_lookup: dict[int, dict] = {}
    try:
        with fitz.open(pdf_path) as document:
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                seen_xrefs: set[int] = set()
                for image_info in page.get_images(full=True):
                    xref = int(image_info[0])
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)
                if seen_xrefs:
                    page_lookup[page_index + 1] = {"embeddedImageCount": len(seen_xrefs)}
    except Exception as exc:
        raise PdfImageExtractionError(str(exc) or "unknown PyMuPDF image metadata error") from exc

    return page_lookup


def extract_pdf_embedded_image_assets(pdf_path: Path, *, asset_prefix: str | None = None) -> dict[int, list[ExtractedImageAsset]]:
    # Returns source assets for slide reconstruction; it does not persist DB rows.
    # pdf_deck_extraction_service attaches this payload to the extracted slide structure.
    _validate_pdf_path(pdf_path)
    fitz = _load_fitz()

    storage = get_upload_storage()
    page_lookup: dict[int, list[ExtractedImageAsset]] = {}
    extracted_count = 0

    try:
        with fitz.open(pdf_path) as document:
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                page_number = page_index + 1
                seen_xrefs: set[int] = set()
                for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                    xref = int(image_info[0])
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)

                    if extracted_count >= MAX_IMAGES_PER_PDF:
                        raise PdfImageExtractionError(f"PDF embedded image limit exceeded: {MAX_IMAGES_PER_PDF}")

                    extracted = document.extract_image(xref)
                    payload = extracted.get("image")
                    if not payload:
                        continue
                    # Bound memory/storage blast radius for hostile or accidental huge PDFs.
                    if len(payload) > MAX_IMAGE_BYTES:
                        raise PdfImageExtractionError(f"Embedded image exceeds size limit: {len(payload)} bytes")

                    extension = str(extracted.get("ext") or "bin").lower().strip(".") or "bin"
                    mime_type = _mime_type_for_extension(extension)
                    checksum = hashlib.sha256(payload).hexdigest()
                    storage_path = _storage_path_for_image(
                        asset_prefix=asset_prefix,
                        page_number=page_number,
                        checksum=checksum,
                        extension=extension,
                    )
                    reused_existing = False
                    try:
                        stored = promote_upload(storage.write_bytes(storage_path, payload))
                    except FileExistsError:
                        stored_path = storage.resolve_path(storage_path)
                        if stored_path is None:
                            raise
                        stored = StoredUpload(provider=storage.provider, storage_path=storage_path, path=stored_path)
                        reused_existing = True

                    extracted_count += 1
                    page_lookup.setdefault(page_number, []).append(
                        {
                            "assetType": "embedded_image",
                            "label": f"Slide {page_number} image {image_index}",
                            "mimeType": mime_type,
                            "storageProvider": stored.provider,
                            "storagePath": stored.storage_path,
                            "pageNumber": page_number,
                            "width": extracted.get("width"),
                            "height": extracted.get("height"),
                            "metadataJson": {
                                "generatedFrom": "pymupdf",
                                "role": "source_pdf_image",
                                "xref": xref,
                                "sourceImageIndex": image_index,
                                "source": {
                                    "pdfPath": str(pdf_path),
                                    "extractor": "pymupdf",
                                    "pageIndex": page_index,
                                    "imageIndex": image_index,
                                },
                                "sha256": checksum,
                                "deduplicationKey": checksum,
                                "assetSource": "uploaded_pdf",
                                "renderLayer": "source_asset",
                                "usableForSlideReconstruction": True,
                                "deduplicatedStorage": reused_existing,
                            },
                        }
                    )
    except PdfImageExtractionError:
        raise
    except Exception as exc:
        raise PdfImageExtractionError(str(exc) or "unknown PyMuPDF embedded image extraction error") from exc

    return page_lookup
