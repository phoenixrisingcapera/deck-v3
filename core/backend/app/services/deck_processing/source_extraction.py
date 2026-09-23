"""Deterministic PDF structure extraction for Upload -> Smart Deck.

Owns: in-memory extraction of page metadata, text, OCR fallback, embedded image
assets, and optional thumbnail payloads from a PDF source.
Must not own: database persistence, workflow readiness, Smart Deck workspace
preparation, or canonical source preview rendering.
Stage: source_extraction parsing layer before DB persistence.
Status: KEEP
"""

from __future__ import annotations

from pathlib import Path

from app.services.deck_extractors import (
    build_slide_blocks,
    extract_pdf_embedded_image_assets,
    extract_pdf_image_metadata,
    extract_pdf_page_ocr_text,
    extract_pdf_page_metadata,
    extract_pdf_vector_colors_by_page,
    extract_pdf_font_usage_by_page,
    extract_pdf_text_by_page,
)
from app.observability.tracing import start_span


def _asset_prefix_from_source_path(pdf_path: Path) -> str | None:
    parts = pdf_path.as_posix().split("/")
    for index in range(len(parts) - 3):
        if parts[index] == "users" and parts[index + 2] == "decks":
            return "/".join(parts[index : index + 4])
    return None


def extract_pdf_deck_structure(pdf_path: Path) -> dict:
    # Source extraction owns structure only. The worker miniatures stage is the
    # canonical source preview/thumbnail pipeline.
    asset_prefix = _asset_prefix_from_source_path(pdf_path)
    with start_span("deck.extract.pdf.metadata", attributes={"source_path": str(pdf_path)}):
        page_metadata = extract_pdf_page_metadata(pdf_path)

    page_numbers = [int(page["pageNumber"]) for page in page_metadata]
    try:
        vector_colors_by_page = extract_pdf_vector_colors_by_page(pdf_path)
    except Exception:
        vector_colors_by_page = {}

    try:
        font_usage_by_page = extract_pdf_font_usage_by_page(pdf_path)
    except Exception:
        font_usage_by_page = {}

    page_text: dict[int, str] = {}
    page_text_source: dict[int, str] = {}
    page_errors: dict[int, list[str]] = {page_number: [] for page_number in page_numbers}
    for page_number in page_numbers:
        try:
            with start_span("deck.extract.pdf.text", attributes={"page_number": page_number}):
                text_items = extract_pdf_text_by_page(pdf_path, [page_number])
            page_text[page_number] = text_items[0]["text"] if text_items else ""
            page_text_source[page_number] = "pdf_text"
        except Exception as exc:
            page_text[page_number] = ""
            page_text_source[page_number] = "pdf_text"
            page_errors.setdefault(page_number, []).append(f"text:{exc}")

        if not page_text[page_number].strip():
            try:
                with start_span("deck.extract.pdf.ocr", attributes={"page_number": page_number}):
                    ocr_text = extract_pdf_page_ocr_text(pdf_path, page_number)
                if ocr_text.strip():
                    page_text[page_number] = ocr_text
                    page_text_source[page_number] = "pdf_ocr"
            except Exception as exc:
                page_errors.setdefault(page_number, []).append(f"ocr:{exc}")

    try:
        with start_span("deck.extract.pdf.images", attributes={"page_count": len(page_numbers)}):
            image_metadata = extract_pdf_image_metadata(pdf_path)
    except Exception as exc:
        image_metadata = {}
        for page_number in page_numbers:
            page_errors.setdefault(page_number, []).append(f"image_metadata:{exc}")

    try:
        with start_span("deck.extract.pdf.embedded_images", attributes={"page_count": len(page_numbers)}):
            embedded_image_assets = extract_pdf_embedded_image_assets(pdf_path, asset_prefix=asset_prefix)
    except Exception as exc:
        embedded_image_assets = {}
        for page_number in page_numbers:
            page_errors.setdefault(page_number, []).append(f"embedded_images:{exc}")

    slides: list[dict] = []
    for page in page_metadata:
        page_number = int(page["pageNumber"])
        block_payload = build_slide_blocks(
            page_text.get(page_number, ""),
            page_number,
            source_kind=page_text_source.get(page_number, "pdf_text"),
        )
        assets: list[dict] = []
        thumbnail_path = None

        assets.extend(embedded_image_assets.get(page_number, []))

        slides.append(
            {
                "slideIndex": page_number,
                "sourcePageNumber": page_number,
                "title": block_payload["title"],
                "role": "unknown",
                "rawText": block_payload["rawText"],
                "narrativeNotes": "Extracted deterministically from the uploaded source deck.",
                "widthPoints": page.get("widthPoints"),
                "heightPoints": page.get("heightPoints"),
                "thumbnailPath": thumbnail_path,
                "thumbnailMimeType": "image/png" if thumbnail_path else None,
                "metadataJson": {
                    "embeddedImageCount": image_metadata.get(page_number, {}).get("embeddedImageCount", 0),
                    "extractor": "pdf_deterministic_v1",
                    "textSource": page_text_source.get(page_number, "pdf_text"),
                    "extractionErrors": page_errors.get(page_number, []),
                    "vectorColors": vector_colors_by_page.get(page_number, []),
                    "fontUsage": font_usage_by_page.get(page_number, []),
                    "vectorColorSource": "pymupdf_pdf_drawings" if vector_colors_by_page.get(page_number) else None,
                },
                "blocks": block_payload["blocks"],
                "assets": assets,
            }
        )

    return {
        "sourceFormat": "pdf",
        "slideCount": len(slides),
        "slides": slides,
    }
