"""Source structure persistence.

Owns: source-extraction persistence (slide/block/asset rows), clearing stale
workspace state before re-extraction.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import (
    AdaptationSuggestion,
    AnalysisFinding,
    AnalysisRun,
    Asset,
    BlockClassification,
    Deck,
    DeckExtractionRun,
    DeckFile,
    DeckGenerationWorkspace,
    DeckLlmArtifact,
    DeckSlide,
    DeckSlideAsset,
    DeckSlideBlock,
    DeckSlideRevision,
    DesignBatch,
    DesignToken,
    DesignVersion,
    GeneratedSlide,
    GeneratedSlideCodeVersion,
    GeneratedSlideSourceLineage,
    GenerationJob,
    SmartDeckMessage,
    SmartDeckPreference,
    SmartDeckWorkspace,
    SmartEditRun,
    SmartEditSuggestion,
)
from app.services.storage.deck_file_service import ensure_pdf_source, get_stored_file_path
from app.services.deck_processing.source_structure_read_model import _load_deck
from app.services.deck_processing.source_extraction import extract_pdf_deck_structure

SMART_DECK_GENERATION_ARTIFACT_TYPES = {
    "smart_deck_generation_context",
    "smart_deck_design_version_manifest",
    "generated_slide_render_schema",
    "generated_slide_code_version",
}


def _clear_existing_structure(db: Session, deck: Deck) -> None:
    # Batch-load identifiers once. Do not traverse lazy slide/block collections:
    # large decks must not turn replacement into an N+1 query path.
    slide_ids = [row.id for row in db.query(DeckSlide.id).filter(DeckSlide.deck_id == deck.id).all()]
    block_ids = [
        row.id
        for row in db.query(DeckSlideBlock.id).filter(DeckSlideBlock.slide_id.in_(slide_ids)).all()
    ] if slide_ids else []
    db.query(DeckGenerationWorkspace).filter(DeckGenerationWorkspace.deck_id == deck.id).delete(synchronize_session=False)
    db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck.id,
        DeckLlmArtifact.artifact_type.in_(SMART_DECK_GENERATION_ARTIFACT_TYPES),
    ).delete(synchronize_session=False)
    generated_slide_ids = [
        item.id for item in db.query(GeneratedSlide.id).filter(GeneratedSlide.deck_id == deck.id).all()
    ]
    db.query(Asset).filter(Asset.deck_id == deck.id).delete(synchronize_session=False)
    if generated_slide_ids:
        db.query(GeneratedSlideCodeVersion).filter(
            GeneratedSlideCodeVersion.generated_slide_id.in_(generated_slide_ids)
        ).delete(synchronize_session=False)
        # This FK is RESTRICT because published lineage is evidence. Source
        # replacement invalidates generated workspace output first, so remove
        # its lineage explicitly before deleting those generated rows.
        db.query(GeneratedSlideSourceLineage).filter(
            GeneratedSlideSourceLineage.generated_slide_id.in_(generated_slide_ids)
        ).delete(synchronize_session=False)
    db.query(SmartDeckMessage).filter(SmartDeckMessage.deck_id == deck.id).delete(synchronize_session=False)
    db.query(SmartDeckPreference).filter(SmartDeckPreference.deck_id == deck.id).delete(synchronize_session=False)
    db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck.id).delete(synchronize_session=False)
    db.query(DesignToken).filter(DesignToken.deck_id == deck.id).delete(synchronize_session=False)
    db.query(GeneratedSlide).filter(GeneratedSlide.deck_id == deck.id).delete(synchronize_session=False)
    db.query(DesignVersion).filter(DesignVersion.deck_id == deck.id).delete(synchronize_session=False)
    db.query(GenerationJob).filter(GenerationJob.deck_id == deck.id).delete(synchronize_session=False)
    db.query(DesignBatch).filter(DesignBatch.deck_id == deck.id).delete(synchronize_session=False)
    # DISABLED: source reprocessing previously deleted AnalysisRun and
    # AnalysisFinding rows. Due Diligence reports are immutable historical
    # artifacts, so reprocessing now detaches obsolete live object FKs while
    # preserving the report-owned target/evidence snapshots.
    # db.query(AnalysisRun).filter(AnalysisRun.deck_id == deck.id).delete(synchronize_session=False)
    # db.query(AnalysisFinding).filter(AnalysisFinding.deck_id == deck.id).delete(synchronize_session=False)
    db.query(AnalysisFinding).filter(AnalysisFinding.deck_id == deck.id).update(
        {AnalysisFinding.slide_id: None, AnalysisFinding.block_id: None},
        synchronize_session=False,
    )
    db.query(AdaptationSuggestion).filter(AdaptationSuggestion.deck_id == deck.id).delete(synchronize_session=False)
    db.query(SmartEditSuggestion).filter(SmartEditSuggestion.deck_id == deck.id).delete(synchronize_session=False)
    db.query(SmartEditRun).filter(SmartEditRun.deck_id == deck.id).delete(synchronize_session=False)
    db.query(DeckSlideRevision).filter(DeckSlideRevision.deck_id == deck.id).delete(synchronize_session=False)
    # UI pointers are live workspace state, not historical evidence. Clear them
    # explicitly so replacement is safe even when a test/database does not
    # enforce ON DELETE SET NULL.
    from app.db.models import DeckWorkspacePreference
    db.query(DeckWorkspacePreference).filter(DeckWorkspacePreference.deck_id == deck.id).update(
        {DeckWorkspacePreference.selected_slide_id: None}, synchronize_session=False
    )
    if block_ids:
        db.query(BlockClassification).filter(BlockClassification.block_id.in_(block_ids)).delete(synchronize_session=False)
    if slide_ids:
        db.query(DeckSlideAsset).filter(DeckSlideAsset.slide_id.in_(slide_ids)).delete(synchronize_session=False)
        db.query(DeckSlideBlock).filter(DeckSlideBlock.slide_id.in_(slide_ids)).delete(synchronize_session=False)
    db.query(DeckSlide).filter(DeckSlide.deck_id == deck.id).delete(synchronize_session=False)


def extract_and_persist_deck_structure(
    db: Session,
    deck_id: str,
    extraction_run: DeckExtractionRun | None = None,
) -> dict:
    deck = _load_deck(db, deck_id)
    if deck is None or deck.file is None:
        raise ValueError("Deck or deck source file not found")

    source_path = get_stored_file_path(deck.file)
    if extraction_run is None:
        extraction_run = DeckExtractionRun(
            id=generate_id("extract"),
            deck_id=deck.id,
            source_file_id=deck.file.id,
            extractor_name="deterministic_v1",
            source_format=source_path.suffix.lower().removeprefix(".") or None,
            status="running",
            started_at=datetime.utcnow(),
            metadata_json={"sourceFilename": deck.file.original_filename or deck.file.filename},
        )
        db.add(extraction_run)
    elif extraction_run.deck_id != deck.id or extraction_run.source_file_id != deck.file.id:
        raise ValueError("Extraction run does not match deck source file.")
    else:
        extraction_run.started_at = extraction_run.started_at or datetime.utcnow()
        extraction_run.status = "running"
        extraction_run.error_message = None
        extraction_run.error_json = None

    if extraction_run.id is None:
        raise ValueError("Missing extraction run identifier.")

    db.add(extraction_run)
    db.flush()

    try:
        pdf_path, converted = ensure_pdf_source(deck.file)
        extracted = extract_pdf_deck_structure(pdf_path)
        if not isinstance(extracted, dict) or not isinstance(extracted.get("slides"), list) or not extracted["slides"]:
            raise ValueError("Deck extraction produced no slides.")

        _clear_existing_structure(db, deck)

        block_count = 0
        asset_count = 0
        partial_error_count = 0
        slides_with_partial_errors = 0
        text_source_counts: dict[str, int] = {}
        asset_type_counts: dict[str, int] = {}
        for slide_payload in extracted["slides"]:
            slide_block_count = len(slide_payload["blocks"])
            slide_asset_count = len(slide_payload["assets"])
            slide_metadata = slide_payload.get("metadataJson") if isinstance(slide_payload.get("metadataJson"), dict) else {}
            extraction_errors = slide_metadata.get("extractionErrors")
            if isinstance(extraction_errors, list) and extraction_errors:
                slides_with_partial_errors += 1
                partial_error_count += len([error for error in extraction_errors if error])
            text_source = str(slide_metadata.get("textSource") or "pdf_text")
            text_source_counts[text_source] = text_source_counts.get(text_source, 0) + 1
            slide = DeckSlide(
                id=generate_id("slide"),
                deck_id=deck.id,
                extraction_run_id=extraction_run.id,
                slide_index=int(slide_payload["slideIndex"]),
                title=str(slide_payload["title"]),
                role=str(slide_payload["role"]),
                raw_text=str(slide_payload["rawText"]),
                narrative_notes=str(slide_payload["narrativeNotes"]),
                source_file_id=deck.file.id,
                source_page_number=int(slide_payload["sourcePageNumber"]),
                thumbnail_path=slide_payload.get("thumbnailPath"),
                thumbnail_mime_type=slide_payload.get("thumbnailMimeType"),
                width_points=slide_payload["widthPoints"],
                height_points=slide_payload["heightPoints"],
                block_count=slide_block_count,
                asset_count=slide_asset_count,
                metadata_json=slide_metadata,
            )
            db.add(slide)
            db.flush()

            for block_payload in slide_payload["blocks"]:
                db.add(
                    DeckSlideBlock(
                        id=generate_id("block"),
                        deck_id=deck.id,
                        slide_id=slide.id,
                        extraction_run_id=extraction_run.id,
                        block_index=int(block_payload["blockIndex"]),
                        raw_text=str(block_payload["rawText"]),
                        normalized_text=str(block_payload["normalizedText"]),
                        block_type=str(block_payload["blockType"]),
                        source_kind=block_payload.get("sourceKind"),
                        metadata_json=block_payload.get("metadataJson"),
                    )
                )
                block_count += 1

            for asset_payload in slide_payload["assets"]:
                asset_type = str(asset_payload["assetType"])
                asset_type_counts[asset_type] = asset_type_counts.get(asset_type, 0) + 1
                db.add(
                    DeckSlideAsset(
                        id=generate_id("asset"),
                        deck_id=deck.id,
                        slide_id=slide.id,
                        extraction_run_id=extraction_run.id,
                        asset_type=asset_type,
                        label=asset_payload.get("label"),
                        mime_type=asset_payload.get("mimeType"),
                        storage_provider=str(asset_payload.get("storageProvider") or "local"),
                        storage_path=asset_payload.get("storagePath"),
                        page_number=asset_payload.get("pageNumber"),
                        width=asset_payload.get("width"),
                        height=asset_payload.get("height"),
                        metadata_json=asset_payload.get("metadataJson"),
                    )
                )
                asset_count += 1

        db.flush()
        db.expire(deck, ["slides"])

        deck.file.page_count = int(extracted["slideCount"])

        extraction_run.source_format = extracted["sourceFormat"]
        extraction_run.status = "completed"
        extraction_run.slide_count = int(extracted["slideCount"])
        extraction_run.block_count = block_count
        extraction_run.asset_count = asset_count
        extraction_run.completed_at = datetime.utcnow()
        extraction_run.metadata_json = {
            **(extraction_run.metadata_json or {}),
            "convertedToPdf": converted,
            "convertedPdf": (deck.file.metadata_json or {}).get("convertedPdf"),
        }
        extraction_run.metrics_json = {
            **(extraction_run.metrics_json or {}),
            "partialErrorCount": partial_error_count,
            "slidesWithPartialErrors": slides_with_partial_errors,
            "textSourceCounts": text_source_counts,
            "assetTypeCounts": asset_type_counts,
        }
        db.flush()
    except Exception as exc:
        extraction_run.status = "failed"
        extraction_run.error_message = str(exc)
        extraction_run.completed_at = datetime.utcnow()
        db.flush()
        raise

    from app.services.deck_processing.source_structure_read_model import get_deck_structure

    return get_deck_structure(db, deck.id)
