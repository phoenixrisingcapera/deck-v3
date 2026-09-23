"""Durable media processing runtime.

Owns: bounded image validation, metadata extraction, and safe degradation.
Must not own: storage persistence, workflow job lifecycle, or LLM context assembly.
Stage: worker handler for media_processing jobs.
Status: KEEP
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import DeckMediaAsset, WorkflowJob
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED_FINAL,
    JOB_STATUS_FAILED_RETRYABLE,
    set_workflow_job_status,
)
from app.services.storage.artifact_storage import get_upload_storage

logger = logging.getLogger(__name__)

MAX_IMAGE_PIXELS = 25_000_000  # 25 megapixels
MAX_IMAGE_DIMENSION = 10_000  # pixels


def _validate_image_dimensions(width: int, height: int) -> None:
    """Validate image dimensions are within safe bounds."""
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid dimensions: {width}x{height}")
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError(f"Image too large: {width}x{height} exceeds {MAX_IMAGE_DIMENSION}px limit")
    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"Image too large: {width * height} pixels exceeds {MAX_IMAGE_PIXELS} limit")


def _extract_image_metadata(payload: bytes, mime_type: str) -> dict:
    """Extract image metadata using PIL with bounded resource usage.

    Returns dict with width, height, and optional dominant colors.
    """
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

        image = Image.open(BytesIO(payload))
        image.verify()

        # Reopen for metadata extraction
        image = Image.open(BytesIO(payload))
        width, height = image.size

        _validate_image_dimensions(width, height)

        # Extract dominant colors (simplified)
        dominant_colors = []
        try:
            if image.mode in ("RGB", "RGBA"):
                # Sample a small region for color extraction
                small = image.copy()
                small.thumbnail((50, 50))
                colors = small.getcolors(maxcolors=1000)
                if colors:
                    # Sort by frequency and take top 5
                    sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)[:5]
                    for _, color in sorted_colors:
                        if len(color) >= 3:
                            r, g, b = color[:3]
                            dominant_colors.append(f"#{r:02x}{g:02x}{b:02x}")
        except Exception as color_error:
            logger.warning("Failed to extract dominant colors: %s", color_error)

        return {
            "width": width,
            "height": height,
            "dominantColors": dominant_colors,
        }
    except ImportError:
        logger.warning("PIL not available; skipping image metadata extraction")
        return {}
    except Exception as error:
        raise ValueError(f"Failed to decode image: {error}") from error


def handle_media_processing(db: Session, job: WorkflowJob, *, worker_id: str) -> None:
    """Process a media asset: validate, extract metadata, mark ready.

    This is a bounded deterministic processor. Vision/AI enrichment is deferred
    to a future phase to keep MVP simple and reliable.
    """
    input_payload = job.input_json or {}
    media_id = input_payload.get("mediaId")
    storage_path = input_payload.get("storagePath")
    expected_sha256 = input_payload.get("sha256")
    mime_type = input_payload.get("mimeType")

    if not media_id or not storage_path:
        raise ValueError("Missing required media processing inputs")

    # Load asset
    asset = db.query(DeckMediaAsset).filter(DeckMediaAsset.id == media_id).one_or_none()
    if asset is None:
        raise ValueError(f"Media asset not found: {media_id}")

    # Verify asset belongs to job's deck
    if asset.deck_id != job.deck_id:
        raise ValueError(f"Media asset {media_id} does not belong to deck {job.deck_id}")

    # Check if archived during processing
    if asset.status == "archived":
        logger.info("Media asset %s archived during processing; skipping", media_id)
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            output_payload={"skipped": True, "reason": "archived_during_processing"},
        )
        return

    # Update status to processing
    asset.status = "processing"
    db.commit()

    try:
        # Load from storage
        storage = get_upload_storage()
        resolved_path = storage.resolve_path(storage_path)
        if resolved_path is None or not resolved_path.exists():
            raise ValueError(f"Storage path not found: {storage_path}")

        payload = resolved_path.read_bytes()

        # Verify checksum
        import hashlib
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValueError(f"Checksum mismatch: expected {expected_sha256}, got {actual_sha256}")

        # Extract metadata
        metadata = _extract_image_metadata(payload, mime_type or asset.mime_type)

        # Update asset with metadata
        asset.width = metadata.get("width")
        asset.height = metadata.get("height")
        if metadata.get("dominantColors"):
            asset.dominant_colors_json = {"colors": metadata["dominantColors"]}
        asset.processing_version = "media-v1"
        asset.processed_at = datetime.utcnow()
        asset.status = "ready"

        # Complete job
        set_workflow_job_status(
            db,
            job=job,
            status=JOB_STATUS_COMPLETED,
            worker_id=worker_id,
            output_payload={
                "mediaId": media_id,
                "width": asset.width,
                "height": asset.height,
                "processingVersion": asset.processing_version,
            },
        )

        db.commit()
        logger.info(
            "Processed media asset %s: %dx%d, %d bytes",
            media_id,
            asset.width or 0,
            asset.height or 0,
            asset.size_bytes,
        )

    except Exception as error:
        db.rollback()
        logger.exception("Failed to process media asset %s: %s", media_id, error)

        # Refresh asset
        asset = db.query(DeckMediaAsset).filter(DeckMediaAsset.id == media_id).one_or_none()
        if asset is None:
            raise

        # Determine failure status
        is_retryable = not isinstance(error, ValueError) or "decode" in str(error).lower()
        failure_status = JOB_STATUS_FAILED_RETRYABLE if is_retryable else JOB_STATUS_FAILED_FINAL

        asset.status = "failed_retryable" if is_retryable else "failed_final"
        asset.error_code = "media_processing_failed"
        asset.error_message = str(error)[:500]

        set_workflow_job_status(
            db,
            job=job,
            status=failure_status,
            worker_id=worker_id,
            error_code="media_processing_failed",
            error_message=str(error)[:500],
            output_payload={"phase": "failed_final" if not is_retryable else "failed_retryable"},
        )

        db.commit()
        raise
