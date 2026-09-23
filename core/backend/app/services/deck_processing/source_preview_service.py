"""Database-facing source preview pipeline for Upload -> Smart Deck.

Owns: rendering source-page preview images through the preview renderer,
attaching them to existing source slides, and persisting canonical
source_preview assets.
Must not own: source slide creation, deterministic PDF structure extraction,
Smart Deck workspace preparation, or final ready publication.
Stage: miniatures.
Status: KEEP
"""

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import Deck, DeckExtractionRun, DeckFile, DeckSlide
from app.core.config import settings
from app.services.deck_processing.source_preview_persistence import persist_source_preview, source_slide_for_page
from app.services.deck_processing.source_preview_renderer import render_source_preview_page
from app.services.storage.deck_file_service import ensure_pdf_source

PROCESSING_RUN_TYPE = "deck_processing_queue"


def _render_preview_page(
    *,
    fitz,
    source_path: Path,
    page_index: int,
    deck_id: str,
    user_id: str | None,
):
    # PyMuPDF documents/pages are not shared between threads. Opening one
    # document per task keeps rendering thread-safe while storage I/O overlaps.
    document = fitz.open(source_path)
    try:
        return render_source_preview_page(
            fitz=fitz,
            page=document.load_page(page_index),
            deck_id=deck_id,
            user_id=user_id,
            slide_number=page_index + 1,
        )
    finally:
        document.close()


def _require_source_checksum(deck_file: DeckFile) -> str:
    checksum = deck_file.checksum_sha256
    if isinstance(checksum, str) and checksum.strip():
        return checksum.strip()
    raise ValueError("Deck source checksum is required for idempotent preview generation")


def _run_source_checksum(run: DeckExtractionRun) -> str | None:
    metadata = run.metadata_json if isinstance(run.metadata_json, dict) else {}
    checksum = metadata.get("sourceChecksum")
    if isinstance(checksum, str) and checksum.strip():
        return checksum.strip()
    return None


def _find_processing_run_for_source(db: Session, deck_id: str, source_checksum: str) -> DeckExtractionRun | None:
    runs = (
        db.query(DeckExtractionRun)
        .filter(DeckExtractionRun.deck_id == deck_id, DeckExtractionRun.run_type == PROCESSING_RUN_TYPE)
        .order_by(DeckExtractionRun.created_at.desc())
        .all()
    )
    for run in runs:
        if _run_source_checksum(run) == source_checksum:
            return run
    return None


def extract_source_previews(
    db: Session,
    deck_id: str,
) -> dict[str, int | str | bool | None]:
    # This is the DB-facing miniature pipeline. It renders source-page previews,
    # upserts DeckSlide/DeckSlideAsset rows, and never publishes Smart Deck
    # readiness. db_publisher is the only allowed ready-state owner.
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Deck not found")

    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck_id).one_or_none()
    if deck_file is None:
        raise ValueError("Deck file not found")
    source_checksum = _require_source_checksum(deck_file)

    source_path, converted = ensure_pdf_source(deck_file)
    if not source_path.exists():
        raise ValueError("Stored deck file is missing")

    try:
        import fitz
    except ImportError:
        return {"status": "skipped", "slideCount": 0, "reason": "preview_dependency_missing"}

    extraction_run = _find_processing_run_for_source(db, deck.id, source_checksum)
    extraction_run_id = extraction_run.id if extraction_run is not None else None
    existing_source_slides = db.query(DeckSlide).filter(DeckSlide.deck_id == deck.id).count()
    if existing_source_slides <= 0:
        raise ValueError("Source slides are required before rendering miniatures.")
    existing_preview_count = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck.id, DeckSlide.thumbnail_path.isnot(None))
        .count()
    )
    if existing_source_slides > 0 and existing_preview_count >= existing_source_slides:
        return {
            "status": "ready",
            "slideCount": int(existing_preview_count or 0),
            "runId": extraction_run_id,
            "idempotent": True,
        }

    slide_count = 0
    asset_count = 0
    try:
        document = fitz.open(source_path)
        try:
            page_count = int(document.page_count)
        finally:
            document.close()

        # Use existing DeckSlide source_page_number values instead of raw PDF
        # page_count so that blank/empty slides (which have no DeckSlide record)
        # do not cause a missing-slide error during miniature persistence.
        existing_slide_page_numbers = sorted(
            {
                row[0]
                for row in db.query(DeckSlide.source_page_number)
                .filter(DeckSlide.deck_id == deck.id, DeckSlide.source_page_number.isnot(None))
                .all()
            }
        )
        if not existing_slide_page_numbers:
            existing_slide_page_numbers = list(range(1, page_count + 1))
        render_page_indices = [pn - 1 for pn in existing_slide_page_numbers if 1 <= pn <= page_count]

        max_workers = min(settings.deck_preview_parallelism, max(1, len(render_page_indices)))
        # DISABLED: The previous implementation iterated one shared document
        # sequentially and rendered/persisted every page before the final commit.
        # Reason: It delayed first-preview visibility and underused worker I/O.
        # Difference: Each task now opens its own PyMuPDF document, rendering is
        # bounded by DECK_PREVIEW_PARALLELISM, and persistence stays on this DB thread.
        # for page_index, page in enumerate(document):
        #     preview = render_source_preview_page(..., page=page, slide_number=page_index + 1)
        #     persist_source_preview(..., preview=preview)
        # db.commit()
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="deck-preview") as executor:
            futures = {
                executor.submit(
                    _render_preview_page,
                    fitz=fitz,
                    source_path=source_path,
                    page_index=page_index,
                    deck_id=deck.id,
                    user_id=deck.user_id,
                ): page_index
                for page_index in render_page_indices
            }
            for future in as_completed(futures):
                page_index = futures[future]
                preview = future.result()
                slide = source_slide_for_page(
                    db,
                    deck,
                    page_index=page_index,
                )
                persist_source_preview(
                    db,
                    deck=deck,
                    deck_file=deck_file,
                    slide=slide,
                    extraction_run_id=extraction_run_id,
                    source_checksum=source_checksum,
                    preview=preview,
                    converted_to_pdf=converted,
                )
                db.flush()
                slide_count += 1
                asset_count += 1
                # Publish each completed miniature so workflow polling can show
                # previews while the remaining pages are still rendering.
                db.commit()

        deck.slide_count = slide_count
        deck_file.page_count = slide_count
        if extraction_run is not None:
            extraction_run.slide_count = max(int(extraction_run.slide_count or 0), slide_count)
            extraction_run.asset_count = max(int(extraction_run.asset_count or 0), asset_count)
            extraction_run.metrics_json = {
                **(extraction_run.metrics_json or {}),
                "sourceChecksum": source_checksum,
                "previewCount": asset_count,
                "convertedToPdf": converted,
                "previewParallelism": max_workers,
            }
        db.commit()
        return {
            "status": "ready",
            "slideCount": slide_count,
            "runId": extraction_run_id,
            "idempotent": False,
            "previewParallelism": max_workers,
        }
    except Exception as exc:
        db.rollback()
        deck = db.query(Deck).filter(Deck.id == deck_id).one()
        run = db.query(DeckExtractionRun).filter(DeckExtractionRun.id == extraction_run_id).one_or_none() if extraction_run_id else None
        if run is not None:
            run.metrics_json = {
                **(run.metrics_json or {}),
                "previewErrorType": exc.__class__.__name__,
                "previewFailedAt": datetime.utcnow().isoformat(),
            }
        db.commit()
        raise
