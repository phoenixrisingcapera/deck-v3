"""Science-backed deterministic deck extraction pipeline.

This module implements the core engineering lesson from the paper:
- Use deterministic extraction for structure
- Use computer vision/rendered previews for layout
- Use schema-validated JSON as the product contract
- Persist every slide/block/artifact before LLM
- Use LLM only for semantic enrichment

Pipeline stages:
1. Source preprocessing
2. Slide/page rendering
3. Content block marking
4. Layout geometry extraction
5. Block/source matching
6. Structured deck JSON preparation
7. Database persistence
8. Optional LLM semantic enrichment
"""

from __future__ import annotations

import json
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    ArtifactObject,
    Deck,
    DeckExtractionRun,
    DeckFile,
    DeckSlide,
    DeckSlideBlock,
    DeckSlideAsset,
    MaterializedDeckState,
    SourceExtractionJob,
    WorkflowJob,
)
from app.core.security import generate_id
from app.services.deck_processing.source_extraction import extract_pdf_deck_structure
from app.services.deck_processing.source_structure_persistence import _clear_existing_structure
from app.services.llm.instant_html_operation_service import (
    complete_artifact_cleanup_tasks,
    register_artifact_cleanup_tasks,
)
from app.services.storage.artifact_storage import get_upload_storage
from app.services.storage.deck_file_service import (
    _deck_storage_prefix,
    _storage_for_file,
    ensure_pdf_source,
    get_stored_file_path,
)


# Pipeline stages in order
PIPELINE_STAGES = [
    "uploaded",
    "source_validated",
    "pages_rendered",
    "blocks_detected",
    "structure_extracted",
    "json_persisted",
    "slides_persisted",
    "blocks_persisted",
    "artifacts_persisted",
    "materialized",
    "smart_deck_ready",
]


class SourceFileLineageError(ValueError):
    """Fail-closed source identity error raised before extraction persistence."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class SourceExtractionError(ValueError):
    """Neutral extraction failure safe for durable workflow state."""

    code = "source_extraction_failed"

    def __init__(self, message: str = "Source extraction failed safely; retry source processing.") -> None:
        super().__init__(message)


def sanitize_source_extraction_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, SourceFileLineageError):
        return exc.code, str(exc)[:240]
    if isinstance(exc, SourceExtractionError):
        return exc.code, str(exc)[:240]
    return SourceExtractionError.code, "Source extraction failed safely; retry source processing."


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _exact_sha256(value: object) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if _SHA256_PATTERN.fullmatch(normalized) else None


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_active_workflow_job_lease(
    db: Session,
    *,
    deck_id: str,
    workflow_job_id: str,
    worker_id: str,
    attempt_count: int,
) -> WorkflowJob:
    job = (
        db.query(WorkflowJob)
        .filter(WorkflowJob.id == workflow_job_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    now = datetime.utcnow()
    if (
        job is None
        or job.deck_id != deck_id
        or job.job_type != "source_extraction"
        or job.status != "running"
        or job.locked_by != worker_id
        or int(job.attempt_count or 0) != int(attempt_count)
        or job.locked_until is None
        or job.locked_until <= now
    ):
        raise SourceFileLineageError(
            "source_extraction_lease_lost",
            "Source extraction ownership is no longer active; the current worker must stop.",
        )
    return job


def _require_active_workflow_fence(
    db: Session,
    *,
    deck_id: str,
    extraction_run_id: str,
    workflow_job_id: str,
    worker_id: str,
    attempt_count: int,
) -> WorkflowJob:
    job = _require_active_workflow_job_lease(
        db,
        deck_id=deck_id,
        workflow_job_id=workflow_job_id,
        worker_id=worker_id,
        attempt_count=attempt_count,
    )
    if job.extraction_run_id != extraction_run_id:
        raise SourceFileLineageError(
            "source_extraction_lease_lost",
            "Source extraction ownership is no longer active; the current worker must stop.",
        )
    return job


def _require_authoritative_source_file(
    db: Session,
    *,
    deck_id: str,
    extraction_run_id: str,
    lock: bool,
) -> tuple[Deck, DeckExtractionRun, DeckFile, Path, bool]:
    """Resolve only the source explicitly bound to the canonical workflow run."""
    deck_query = db.query(Deck).filter(Deck.id == deck_id)
    deck = (deck_query.with_for_update() if lock else deck_query).one_or_none()
    if deck is None:
        raise SourceFileLineageError("source_file_wrong_deck", "The requested deck is unavailable.")
    run_query = db.query(DeckExtractionRun).filter(DeckExtractionRun.id == extraction_run_id)
    extraction_run = (run_query.with_for_update() if lock else run_query).one_or_none()
    if extraction_run is None or extraction_run.deck_id != deck_id:
        raise SourceFileLineageError(
            "source_file_wrong_deck",
            "The extraction run does not belong to the requested deck; restart source processing for this deck.",
        )
    if extraction_run.status not in {"queued", "running"}:
        raise SourceFileLineageError(
            "source_extraction_run_terminal",
            "The extraction run is no longer active; start or claim a current source processing run.",
        )
    if not extraction_run.source_file_id:
        raise SourceFileLineageError(
            "source_file_identity_missing",
            "The extraction run has no source file identity; restart processing from the upload stage.",
        )

    source_query = db.query(DeckFile).filter(DeckFile.id == extraction_run.source_file_id)
    source_file = (source_query.with_for_update() if lock else source_query).one_or_none()
    if source_file is None:
        raise SourceFileLineageError(
            "source_file_identity_missing",
            "The extraction run source file no longer exists; upload the source again before retrying.",
        )
    if source_file.deck_id != deck_id:
        raise SourceFileLineageError(
            "source_file_wrong_deck",
            "The extraction run source file belongs to another deck; restart source processing for this deck.",
        )

    file_checksum = _exact_sha256(source_file.checksum_sha256)
    if file_checksum is None:
        raise SourceFileLineageError(
            "source_file_checksum_missing",
            "The authoritative source checksum is missing; upload the source again before retrying.",
        )
    run_metadata = extraction_run.metadata_json if isinstance(extraction_run.metadata_json, dict) else {}
    raw_run_checksum = run_metadata.get("sourceChecksum")
    run_checksum = _exact_sha256(raw_run_checksum)
    if raw_run_checksum in {None, ""}:
        raise SourceFileLineageError(
            "source_run_checksum_missing",
            "The extraction run checksum is missing; restart source processing from the upload stage.",
        )
    if run_checksum is None:
        raise SourceFileLineageError(
            "source_run_checksum_invalid",
            "The extraction run checksum is invalid; start a new source processing run.",
        )
    if run_checksum != file_checksum:
        raise SourceFileLineageError(
            "source_file_identity_ambiguous",
            "The uploaded source changed after this extraction run was created; start a new source processing run.",
        )
    try:
        resolved_path = Path(get_stored_file_path(source_file))
        backing_checksum = _hash_file(resolved_path)
    except Exception as exc:
        raise SourceFileLineageError(
            "source_file_bytes_unavailable",
            "The authoritative source bytes are unavailable; restore or upload the source before retrying.",
        ) from exc
    if backing_checksum != file_checksum:
        raise SourceFileLineageError(
            "source_file_bytes_changed",
            "The stored source bytes do not match the authoritative checksum; upload the source again.",
        )

    if lock:
        newer_run = db.query(DeckExtractionRun.id).filter(
            DeckExtractionRun.deck_id == deck_id,
            DeckExtractionRun.source_file_id == source_file.id,
            DeckExtractionRun.extractor_name == "workflow_source_pipeline",
            DeckExtractionRun.id != extraction_run.id,
            or_(
                DeckExtractionRun.created_at > extraction_run.created_at,
                and_(
                    DeckExtractionRun.created_at == extraction_run.created_at,
                    DeckExtractionRun.id > extraction_run.id,
                ),
            ),
        ).first()
        if newer_run is not None:
            raise SourceFileLineageError(
                "source_extraction_run_superseded",
                "A newer source processing run superseded this run; continue with the current run.",
            )
    return deck, extraction_run, source_file, resolved_path, False


def _compute_checksum(data: bytes) -> str:
    """Compute SHA256 checksum of data."""
    return hashlib.sha256(data).hexdigest()


def _compute_json_checksum(data: dict) -> str:
    """Compute SHA256 checksum of JSON data."""
    json_bytes = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()


def _create_source_extraction_job(
    db: Session,
    deck_id: str,
    stage: str,
    source_version_id: str | None = None,
    idempotency_key: str | None = None,
) -> SourceExtractionJob:
    """Create a new source extraction job for a specific stage."""
    job = SourceExtractionJob(
        deck_id=deck_id,
        source_version_id=source_version_id,
        stage=stage,
        status="queued",
        idempotency_key=idempotency_key,
        attempt_count=0,
        max_attempts=3,
    )
    db.add(job)
    db.flush()
    return job


def _update_materialized_state(
    db: Session,
    deck_id: str,
    **kwargs: Any,
) -> MaterializedDeckState:
    """Update or create the materialized deck state."""
    state = db.query(MaterializedDeckState).filter(
        MaterializedDeckState.deck_id == deck_id
    ).first()
    
    if state is None:
        state = MaterializedDeckState(deck_id=deck_id)
        db.add(state)
    
    for key, value in kwargs.items():
        if hasattr(state, key):
            setattr(state, key, value)
    
    state.updated_at = datetime.utcnow()
    db.flush()
    return state


def _persist_artifact(
    db: Session,
    deck_id: str,
    artifact_type: str,
    content: dict | list | bytes,
    source_version_id: str | None = None,
    content_type: str = "application/json",
    metadata: dict | None = None,
    artifact_id: str | None = None,
    created_storage_keys: list[str] | None = None,
) -> ArtifactObject:
    """Persist an artifact to object storage and create a database record."""
    storage = get_upload_storage()
    
    if isinstance(content, (dict, list)):
        content_bytes = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    elif isinstance(content, bytes):
        content_bytes = content
    else:
        content_bytes = str(content).encode("utf-8")
    
    checksum = _compute_checksum(content_bytes)
    
    # Generate storage key
    storage_key = f"workspaces/{deck_id}/artifacts/{artifact_type}/{checksum[:16]}.json"
    
    # Persist through the canonical storage contract, then promote remote-backed
    # uploads. Content-addressed keys make an existing artifact reusable.
    existing_path = storage.resolve_path(storage_key)
    if existing_path is None or not existing_path.is_file():
        stored = storage.write_bytes(storage_key, content_bytes)
        storage.promote(stored)
        if created_storage_keys is not None:
            created_storage_keys.append(storage_key)
    
    # Create artifact record
    artifact = ArtifactObject(
        id=artifact_id or generate_id("artifact"),
        deck_id=deck_id,
        source_version_id=source_version_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        storage_provider=storage.provider,
        content_type=content_type,
        checksum_sha256=checksum,
        size_bytes=len(content_bytes),
        metadata_json=metadata or {},
    )
    db.add(artifact)
    db.flush()
    
    return artifact


def _artifact_storage_key(deck_id: str, content: dict | list) -> str:
    content_bytes = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
    return f"workspaces/{deck_id}/artifacts/{{artifact_type}}/{_compute_checksum(content_bytes)[:16]}.json"


def _stage_artifact_cleanup(db: Session, *, deck_id: str, artifacts: list[tuple[str, dict]]) -> list[str]:
    storage = get_upload_storage()
    prospective_keys = [
        _artifact_storage_key(deck_id, content).format(artifact_type=artifact_type)
        for artifact_type, content in artifacts
    ]
    new_keys = [key for key in prospective_keys if not storage.object_exists(key)]
    if new_keys:
        register_artifact_cleanup_tasks(
            db,
            deck_id=deck_id,
            operation_id=None,
            attempt_id=None,
            storage_keys=new_keys,
        )
    return new_keys


def _stage_storage_cleanup_keys(db: Session, *, deck_id: str, storage_keys: list[str]) -> list[str]:
    unique_keys = list(dict.fromkeys(key for key in storage_keys if key))
    if unique_keys:
        register_artifact_cleanup_tasks(
            db,
            deck_id=deck_id,
            operation_id=None,
            attempt_id=None,
            storage_keys=unique_keys,
        )
    return unique_keys


def _complete_failed_artifact_cleanup(db: Session, storage_keys: list[str]) -> None:
    if not storage_keys:
        return
    storage = get_upload_storage()
    deleted: list[str] = []
    for storage_key in storage_keys:
        try:
            storage.delete(storage_key)
            if not storage.object_exists(storage_key):
                deleted.append(storage_key)
        except Exception:
            # The already-committed promotion_pending cleanup task remains for
            # the canonical reconciler; never persist storage exception detail.
            continue
    if not deleted:
        return
    from app.db.models import InstantDeckArtifactCleanupTask
    now = datetime.utcnow()
    try:
        db.query(InstantDeckArtifactCleanupTask).filter(
            InstantDeckArtifactCleanupTask.storage_key.in_(deleted)
        ).update(
            {
                InstantDeckArtifactCleanupTask.status: "completed",
                InstantDeckArtifactCleanupTask.completed_at: now,
                InstantDeckArtifactCleanupTask.locked_by: None,
                InstantDeckArtifactCleanupTask.locked_at: None,
            },
            synchronize_session=False,
        )
        db.commit()
    except Exception:
        # Object deletion already succeeded. A pending row is harmless and the
        # idempotent reconciler can confirm absence later; never mask the source
        # extraction failure with cleanup bookkeeping detail.
        db.rollback()


def _persist_slides(
    db: Session,
    deck_id: str,
    source_version_id: str,
    source_file_id: str,
    slides_data: list[dict],
) -> list[DeckSlide]:
    """Persist extracted slides to the database."""
    slides = []
    
    for slide_data in slides_data:
        slide_index = slide_data.get("slideIndex", 0)
        source_page_number = slide_data.get("sourcePageNumber") or slide_index
        slide = DeckSlide(
            id=generate_id("slide"),
            deck_id=deck_id,
            extraction_run_id=source_version_id,
            source_file_id=source_file_id,
            slide_index=slide_index,
            slide_number=slide_index,
            page_index=slide_data.get("sourcePageNumber"),
            source_page_number=source_page_number,
            title=slide_data.get("title", ""),
            role=slide_data.get("role", "unknown"),
            raw_text=slide_data.get("rawText", ""),
            narrative_notes=slide_data.get("narrativeNotes", ""),
            width_points=slide_data.get("widthPoints"),
            height_points=slide_data.get("heightPoints"),
            thumbnail_path=slide_data.get("thumbnailPath"),
            thumbnail_mime_type=slide_data.get("thumbnailMimeType"),
            block_count=len(slide_data.get("blocks", [])),
            asset_count=len(slide_data.get("assets", [])),
            metadata_json=slide_data.get("metadataJson", {}),
        )
        db.add(slide)
        slides.append(slide)
    
    db.flush()
    return slides


def _persist_blocks(
    db: Session,
    deck_id: str,
    source_version_id: str,
    slides: list[DeckSlide],
    slides_data: list[dict],
) -> list[DeckSlideBlock]:
    """Persist extracted blocks to the database."""
    blocks = []
    
    for slide, slide_data in zip(slides, slides_data):
        blocks_data = slide_data.get("blocks", [])
        
        for block_index, block_data in enumerate(blocks_data):
            # Parse position JSON
            position_json = block_data.get("positionJson", {})
            style_json = block_data.get("styleJson", {})
            
            raw_text = block_data.get("text") or block_data.get("rawText") or ""
            normalized_text = block_data.get("normalizedText") or raw_text.lower().strip()
            block = DeckSlideBlock(
                id=generate_id("block"),
                deck_id=deck_id,
                slide_id=slide.id,
                extraction_run_id=source_version_id,
                block_index=block_index,
                raw_text=raw_text,
                normalized_text=normalized_text,
                block_type=block_data.get("blockType", "text"),
                block_kind=block_data.get("blockKind", "text"),
                extraction_stage="structured",
                extraction_source=block_data.get("sourceKind", "pdf_text"),
                text=raw_text,
                bbox_left=position_json.get("x"),
                bbox_top=position_json.get("y"),
                bbox_width=position_json.get("width"),
                bbox_height=position_json.get("height"),
                font_family=style_json.get("fontFamily"),
                font_size=style_json.get("fontSize"),
                font_weight=style_json.get("fontWeight"),
                color_hex=style_json.get("color"),
                style_json=style_json,
                confidence=block_data.get("confidence", 1.0),
                metadata_json=block_data.get("metadataJson", {}),
            )
            db.add(block)
            blocks.append(block)
    
    db.flush()
    return blocks


def _persist_assets(
    db: Session,
    deck_id: str,
    source_version_id: str,
    slides: list[DeckSlide],
    slides_data: list[dict],
) -> list[DeckSlideAsset]:
    """Persist extracted assets to the database."""
    assets = []
    
    for slide, slide_data in zip(slides, slides_data):
        assets_data = slide_data.get("assets", [])
        
        for asset_data in assets_data:
            asset = DeckSlideAsset(
                id=generate_id("asset"),
                deck_id=deck_id,
                slide_id=slide.id,
                extraction_run_id=source_version_id,
                asset_type=asset_data.get("assetType", "image"),
                asset_kind=asset_data.get("assetKind"),
                storage_provider=asset_data.get("storageProvider", "local"),
                label=asset_data.get("label"),
                mime_type=asset_data.get("mimeType"),
                storage_path=asset_data.get("storagePath"),
                filename=asset_data.get("filename"),
                page_number=asset_data.get("pageNumber"),
                width=asset_data.get("width"),
                height=asset_data.get("height"),
                file_size_bytes=asset_data.get("fileSizeBytes"),
                sha256=asset_data.get("sha256"),
                metadata_json=asset_data.get("metadataJson", {}),
            )
            db.add(asset)
            assets.append(asset)
    
    db.flush()
    return assets


def extract_source_deck(
    db: Session,
    deck_id: str,
    *,
    extraction_run: DeckExtractionRun,
    workflow_job_id: str,
    worker_id: str,
    attempt_count: int,
    created_storage_keys: list[str] | None = None,
) -> dict:
    """Main entry point for deterministic deck extraction.
    
    This function implements the science-backed pipeline:
    1. Load source file metadata
    2. Convert/render source to page images if needed
    3. Extract slide/page count
    4. Extract text blocks where possible
    5. Extract image/shape/chart placeholders where possible
    6. Produce position_json for each detected block
    7. Produce style_json when available
    8. Save structured_deck_json to object storage
    9. Save extraction_report_json to object storage
    10. Persist slides and blocks to DB
    11. Update materialized deck state
    
    Args:
        db: Database session
        deck_id: ID of the deck to extract
        
    Returns:
        Dictionary with extraction results
    """
    if not extraction_run.id:
        raise SourceFileLineageError(
            "source_file_identity_missing",
            "The extraction run identity is missing; restart processing from the upload stage.",
        )
    tracked_keys = created_storage_keys if created_storage_keys is not None else []

    _require_active_workflow_fence(
        db,
        deck_id=deck_id,
        extraction_run_id=extraction_run.id,
        workflow_job_id=workflow_job_id,
        worker_id=worker_id,
        attempt_count=attempt_count,
    )

    # Validate authoritative DB identity and backing bytes before mutating any
    # run/materialized state, writing artifacts, or replacing source rows.
    deck, source_version, deck_file, resolved_source_path, compatibility = _require_authoritative_source_file(
        db,
        deck_id=deck_id,
        extraction_run_id=extraction_run.id,
        lock=True,
    )
    extraction_path = resolved_source_path
    original_file_metadata = dict(deck_file.metadata_json or {}) if isinstance(deck_file.metadata_json, dict) else deck_file.metadata_json
    converted_metadata: dict | None = None
    converted_cleanup_keys: list[str] = []
    try:
        if resolved_source_path.suffix.lower() in {".ppt", ".pptx"}:
            source_checksum = _exact_sha256(deck_file.checksum_sha256)
            if source_checksum is None:
                raise SourceFileLineageError(
                    "source_file_checksum_missing",
                    "The authoritative source checksum is missing; upload the source again before retrying.",
                )
            deck_prefix = _deck_storage_prefix(deck_file)
            prospective_converted_key = (
                f"{deck_prefix}/converted/{deck_file.id}_{source_checksum[:16]}.pdf"
                if deck_prefix
                else f"converted/{deck_file.id}_{source_checksum[:16]}.pdf"
            )
            conversion_storage = _storage_for_file(deck_file)
            if not conversion_storage.object_exists(prospective_converted_key):
                # The deterministic conversion key is known before
                # ensure_pdf_source can promote. Durable cleanup ownership must
                # exist first so process death cannot orphan the object.
                converted_cleanup_keys = _stage_storage_cleanup_keys(
                    db, deck_id=deck_id, storage_keys=[prospective_converted_key]
                )
                tracked_keys.extend(converted_cleanup_keys)
                _require_active_workflow_fence(
                    db,
                    deck_id=deck_id,
                    extraction_run_id=extraction_run.id,
                    workflow_job_id=workflow_job_id,
                    worker_id=worker_id,
                    attempt_count=attempt_count,
                )
                deck, source_version, deck_file, resolved_source_path, compatibility = _require_authoritative_source_file(
                    db,
                    deck_id=deck_id,
                    extraction_run_id=extraction_run.id,
                    lock=True,
                )
                original_file_metadata = (
                    dict(deck_file.metadata_json or {})
                    if isinstance(deck_file.metadata_json, dict)
                    else deck_file.metadata_json
                )
            extraction_path, _converted = ensure_pdf_source(deck_file)
            current_metadata = deck_file.metadata_json if isinstance(deck_file.metadata_json, dict) else {}
            candidate = current_metadata.get("convertedPdf")
            if isinstance(candidate, dict):
                converted_metadata = dict(candidate)
                converted_key = str(candidate.get("storagePath") or "").strip()
                # Never let durable cleanup staging publish conversion metadata
                # ahead of the source replacement commit.
                deck_file.metadata_json = original_file_metadata
                if converted_key != prospective_converted_key:
                    if converted_key:
                        try:
                            conversion_storage.delete(converted_key)
                        except Exception:
                            pass
                    raise SourceExtractionError("Converted source identity changed unexpectedly; retry source processing.")
        extraction_result = extract_pdf_deck_structure(Path(extraction_path))
    except SourceFileLineageError:
        raise
    except Exception as exc:
        raise SourceExtractionError() from exc
    slides_data = extraction_result.get("slides") if isinstance(extraction_result, dict) else None
    if not isinstance(slides_data, list) or not slides_data:
        raise SourceExtractionError("Source extraction produced no usable slides; retry with a supported source.")
    # Conversion helpers may annotate the ORM source row. Do not let cleanup
    # staging commit those annotations ahead of the atomic replacement commit.
    deck_file.metadata_json = original_file_metadata

    duplicate_source_page = db.query(
        DeckSlide.source_file_id,
        DeckSlide.source_page_number,
        func.count(DeckSlide.id),
    ).filter(
        DeckSlide.deck_id == deck_id,
        DeckSlide.source_file_id.is_not(None),
        DeckSlide.source_page_number.is_not(None),
    ).group_by(
        DeckSlide.source_file_id,
        DeckSlide.source_page_number,
    ).having(func.count(DeckSlide.id) > 1).first()
    if duplicate_source_page is not None:
        raise SourceFileLineageError(
            "source_page_duplicate_legacy",
            "Duplicate legacy source pages require explicit repair before source processing can continue.",
        )
    incoming_pages = [int(item.get("sourcePageNumber") or item.get("slideIndex") or 0) for item in slides_data]
    if sorted(incoming_pages) != list(range(1, len(slides_data) + 1)):
        raise SourceFileLineageError(
            "source_page_duplicate_input",
            "The extracted source must contain each source page marker exactly once.",
        )

    now = datetime.utcnow()
    structured_artifact_id = generate_id("artifact")
    report_artifact_id = generate_id("artifact")
    structured_deck_json = {
        "deckId": deck_id,
        "sourceVersionId": source_version.id,
        "sourceFormat": extraction_result.get("sourceFormat", "pdf"),
        "slideCount": len(slides_data),
        "slides": slides_data,
        "extractedAt": now.isoformat(),
        "extractor": "science_backed_v1",
    }
    expected_block_count = sum(len(item.get("blocks", [])) for item in slides_data)
    expected_asset_count = sum(len(item.get("assets", [])) for item in slides_data)
    extraction_report = {
        "deckId": deck_id,
        "sourceVersionId": source_version.id,
        "status": "completed",
        "slideCount": len(slides_data),
        "blockCount": expected_block_count,
        "assetCount": expected_asset_count,
        "structuredJsonArtifactId": structured_artifact_id,
        "completedAt": now.isoformat(),
    }

    # Durable cleanup ownership is committed before external object writes. It
    # contains no run/materialized success state. Re-lock and revalidate after
    # that staging commit so concurrent/superseded runs cannot cross the fence.
    cleanup_keys = _stage_artifact_cleanup(
        db,
        deck_id=deck_id,
        artifacts=[("structured_deck_json", structured_deck_json), ("extraction_report", extraction_report)],
    )
    _require_active_workflow_fence(
        db,
        deck_id=deck_id,
        extraction_run_id=extraction_run.id,
        workflow_job_id=workflow_job_id,
        worker_id=worker_id,
        attempt_count=attempt_count,
    )
    deck, source_version, deck_file, resolved_source_path, compatibility = _require_authoritative_source_file(
        db,
        deck_id=deck_id,
        extraction_run_id=extraction_run.id,
        lock=True,
    )

    source_version.metadata_json = {
        **(source_version.metadata_json or {}),
        "sourceChecksum": _exact_sha256(deck_file.checksum_sha256),
    }
    source_version.status = "running"
    source_version.started_at = source_version.started_at or now
    source_version.current_stage = "source_validated"
    source_version.current_stage_label = "Source validation completed"

    # Canonical replacement invalidates all mutable downstream workspace state,
    # detaches immutable diligence snapshots, and deletes old source structure
    # before inserting the exact new page set.
    _clear_existing_structure(db, deck)
    structured_json_artifact = _persist_artifact(
        db,
        deck_id,
        "structured_deck_json",
        structured_deck_json,
        source_version_id=source_version.id,
        content_type="application/json",
        metadata={"extractor": "science_backed_v1"},
        artifact_id=structured_artifact_id,
        created_storage_keys=tracked_keys,
    )
    slides = _persist_slides(db, deck_id, source_version.id, deck_file.id, slides_data)
    blocks = _persist_blocks(db, deck_id, source_version.id, slides, slides_data)
    assets = _persist_assets(db, deck_id, source_version.id, slides, slides_data)
    extraction_report_artifact = _persist_artifact(
        db,
        deck_id,
        "extraction_report",
        extraction_report,
        source_version_id=source_version.id,
        content_type="application/json",
        artifact_id=report_artifact_id,
        created_storage_keys=tracked_keys,
    )

    source_version.status = "completed"
    source_version.slide_count = len(slides)
    source_version.block_count = len(blocks)
    source_version.asset_count = len(assets)
    source_version.current_stage = "completed"
    source_version.current_stage_label = "Extraction completed"
    source_version.error_message = None
    source_version.completed_at = now
    _update_materialized_state(
        db,
        deck_id,
        status="ready",
        extraction_status="completed",
        current_stage="materialized",
        source_version_id=source_version.id,
        slide_count=len(slides),
        block_count=len(blocks),
        asset_count=len(assets),
        has_thumbnails=bool(any(slide.thumbnail_path for slide in slides)),
        has_structured_json=True,
        can_open_smart_deck=True,
        can_open_smart_edit=True,
        can_open_due_diligence=True,
        next_action=None,
        warnings_json=[],
        errors_json=[],
        extraction_report_artifact_id=extraction_report_artifact.id,
        structured_json_artifact_id=structured_json_artifact.id,
        last_extraction_at=now,
    )
    deck.status = "ready"
    deck.slide_count = len(slides)
    complete_artifact_cleanup_tasks(db, cleanup_keys)
    _require_active_workflow_fence(
        db,
        deck_id=deck_id,
        extraction_run_id=source_version.id,
        workflow_job_id=workflow_job_id,
        worker_id=worker_id,
        attempt_count=attempt_count,
    )
    db.flush()
    return {
        "success": True,
        "sourceVersionId": source_version.id,
        "slideCount": len(slides),
        "blockCount": len(blocks),
        "assetCount": len(assets),
        "structuredJsonArtifactId": structured_json_artifact.id,
        "extractionReportArtifactId": extraction_report_artifact.id,
        "convertedPdfMetadata": converted_metadata,
        "convertedStorageKeys": converted_cleanup_keys,
    }


def get_materialized_state(
    db: Session,
    deck_id: str,
) -> dict | None:
    """Get the current materialized state of a deck."""
    state = db.query(MaterializedDeckState).filter(
        MaterializedDeckState.deck_id == deck_id
    ).first()
    
    if not state:
        return None
    
    return {
        "deckId": state.deck_id,
        "sourceVersionId": state.source_version_id,
        "status": state.status,
        "extractionStatus": state.extraction_status,
        "currentStage": state.current_stage,
        "slideCount": state.slide_count,
        "blockCount": state.block_count,
        "assetCount": state.asset_count,
        "hasThumbnails": state.has_thumbnails,
        "hasStructuredJson": state.has_structured_json,
        "hasEmbeddings": state.has_embeddings,
        "canOpenSmartDeck": state.can_open_smart_deck,
        "canOpenSmartEdit": state.can_open_smart_edit,
        "canOpenDueDiligence": state.can_open_due_diligence,
        "nextAction": state.next_action,
        "warningsJson": state.warnings_json,
        "errorsJson": state.errors_json,
        "lastExtractionAt": state.last_extraction_at.isoformat() if state.last_extraction_at else None,
        "lastGenerationAt": state.last_generation_at.isoformat() if state.last_generation_at else None,
        "updatedAt": state.updated_at.isoformat() if state.updated_at else None,
    }


def get_deck_map(
    db: Session,
    deck_id: str,
) -> dict | None:
    """Get the deck map with slides, blocks, and assets."""
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        return None
    
    # Get the active source version
    source_version = db.query(DeckExtractionRun).filter(
        DeckExtractionRun.deck_id == deck_id,
        DeckExtractionRun.status == "completed",
    ).order_by(DeckExtractionRun.created_at.desc()).first()
    
    if not source_version:
        return None
    
    # Get slides
    slides = db.query(DeckSlide).filter(
        DeckSlide.deck_id == deck_id,
        DeckSlide.extraction_run_id == source_version.id,
    ).order_by(DeckSlide.slide_index).all()
    
    # Get blocks for each slide
    slides_data = []
    for slide in slides:
        blocks = db.query(DeckSlideBlock).filter(
            DeckSlideBlock.slide_id == slide.id,
        ).order_by(DeckSlideBlock.block_index).all()
        
        blocks_data = []
        for block in blocks:
            blocks_data.append({
                "id": block.id,
                "blockKey": f"slide_{slide.slide_index}.block_{block.block_index}",
                "blockType": block.block_type,
                "blockKind": block.block_kind,
                "text": block.text,
                "positionJson": {
                    "x": block.bbox_left,
                    "y": block.bbox_top,
                    "width": block.bbox_width,
                    "height": block.bbox_height,
                },
                "styleJson": block.style_json or {},
                "confidence": block.confidence,
            })
        
        slides_data.append({
            "id": slide.id,
            "slideNumber": slide.slide_number,
            "title": slide.title,
            "role": slide.role,
            "thumbnailPath": slide.thumbnail_path,
            "renderedImagePath": slide.rendered_image_path,
            "widthPoints": slide.width_points,
            "heightPoints": slide.height_points,
            "blockCount": len(blocks_data),
            "blocks": blocks_data,
        })
    
    return {
        "deckId": deck.id,
        "title": deck.title,
        "status": deck.status,
        "sourceVersionId": source_version.id,
        "slideCount": len(slides_data),
        "slides": slides_data,
    }


def get_editor_view(
    db: Session,
    deck_id: str,
) -> dict | None:
    """Get the editor view with blocks, positions, and styles."""
    deck_map = get_deck_map(db, deck_id)
    if not deck_map:
        return None
    
    # Enrich with additional editor metadata
    for slide in deck_map.get("slides", []):
        for block in slide.get("blocks", []):
            # Add persistent field key if available
            block["persistentFieldKey"] = f"slide_{slide['slideNumber']}.{block['blockType']}"
            block["isEditable"] = True
            block["isGenerated"] = False
    
    return deck_map
