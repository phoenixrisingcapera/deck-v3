from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_id
from app.core.utils import safe_filename
from app.db.models import Deck, DeckFile, DeckInputSource
from app.services.storage.deck_file_service import compute_file_sha256
from app.services.storage.deck_file_service import compute_sha256
from app.services.deck_processing.state_machine import DeckState, transition_deck_state
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.visualizer.slide_read_model import get_deck
from app.services.storage.upload_scan import scan_upload_path
from app.services.storage.upload_security import LimitedUpload, MAX_DECK_UPLOAD_SIZE_BYTES, require_supported_deck_upload
from app.services.storage.artifact_storage import get_upload_storage, promote_upload
from app.services.deck_processing.workflow_jobs import (
    JOB_STATUS_COMPLETED,
    JOB_TYPE_SOURCE_INGESTION,
    build_workflow_job_idempotency_key,
    ensure_workflow_job,
    record_workflow_artifact,
    set_workflow_job_status,
)

logger = logging.getLogger(__name__)


def _extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return suffix if suffix else ".bin"



def deck_storage_prefix(user_id: str | None, deck_id: str) -> str:
    return f"users/{user_id or 'unknown-user'}/decks/{deck_id}"


def _source_storage_path(*, user_id: str | None, deck_id: str, upload_id: str, filename: str) -> str:
    return f"{deck_storage_prefix(user_id, deck_id)}/source/{upload_id}/{safe_filename(filename)}"


def _require_deck_storage_path(deck: Deck, storage_path: str) -> None:
    expected_prefix = f"{deck_storage_prefix(deck.user_id, deck.id)}/"
    if not storage_path.startswith(expected_prefix):
        raise ValueError("Upload storage path does not belong to this deck")


def _map_file(deck_file: DeckFile) -> dict[str, str | int | None]:
    return {
        "id": deck_file.id,
        "deck_id": deck_file.deck_id,
        "filename": deck_file.original_filename or deck_file.filename,
        "stored_filename": deck_file.filename,
        "mime_type": deck_file.mime_type,
        "size": deck_file.size,
        "storage_path": deck_file.storage_path,
        "uploaded_at": deck_file.uploaded_at.isoformat() if deck_file.uploaded_at else None,
    }


def _sync_source_ingestion_job(
    db: Session,
    *,
    deck: Deck,
    deck_file: DeckFile,
    source: DeckInputSource,
    ingestion_mode: str,
    extra_metadata: dict | None = None,
) -> None:
    source_checksum = deck_file.checksum_sha256 or deck_file.storage_path or deck_file.id
    job = ensure_workflow_job(
        db,
        deck=deck,
        job_type=JOB_TYPE_SOURCE_INGESTION,
        status="queued",
        max_attempts=1,
        idempotency_key=build_workflow_job_idempotency_key(
            deck_id=deck.id,
            source_checksum=source_checksum,
            job_type=JOB_TYPE_SOURCE_INGESTION,
        ),
        input_payload={
            "deckId": deck.id,
            "sourceInputId": source.id,
            "deckFileId": deck_file.id,
            "ingestionMode": ingestion_mode,
            "storagePath": deck_file.storage_path,
        },
    )
    if deck_file.storage_path:
        record_workflow_artifact(
            db,
            job=job,
            artifact_type="deck_source_file",
            storage_key=deck_file.storage_path,
            content_hash=deck_file.checksum_sha256,
            metadata={
                "mimeType": deck_file.mime_type,
                "size": deck_file.size,
                "originalFilename": deck_file.original_filename or deck_file.filename,
            },
        )
    output_payload = {
        "deckFileId": deck_file.id,
        "sourceInputId": source.id,
        "storagePath": deck_file.storage_path,
        "mimeType": deck_file.mime_type,
        "checksumSha256": deck_file.checksum_sha256,
        "ingestionMode": ingestion_mode,
    }
    if extra_metadata:
        output_payload["metadata"] = extra_metadata
    merged_output = dict(job.output_json or {})
    merged_output.update(output_payload)
    job.output_json = merged_output


def attach_upload(
    db: Session,
    deck_id: str,
    filename: str,
    mime_type: str,
    payload: bytes,
) -> dict[str, str | int | None] | None:
    require_supported_deck_upload(filename, mime_type)
    if len(payload) > MAX_DECK_UPLOAD_SIZE_BYTES:
        raise ValueError("Deck uploads must be 200MB or smaller")

    storage = get_upload_storage()
    temporary_path = storage.root() / storage.generated_name("upload_tmp", ".tmp")
    temporary_path.write_bytes(payload)
    return attach_limited_upload(
        db,
        deck_id,
        filename,
        mime_type,
        LimitedUpload(path=temporary_path, size=len(payload), checksum_sha256=compute_sha256(payload)),
    )


def attach_limited_upload(
    db: Session,
    deck_id: str,
    filename: str,
    mime_type: str,
    upload: LimitedUpload,
) -> dict[str, str | int | None] | None:
    require_supported_deck_upload(filename, mime_type)
    if upload.size > MAX_DECK_UPLOAD_SIZE_BYTES:
        upload.path.unlink(missing_ok=True)
        raise ValueError("Deck uploads must be 200MB or smaller")

    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        upload.path.unlink(missing_ok=True)
        return None

    storage = get_upload_storage()
    stored_filename = _source_storage_path(
        user_id=deck.user_id,
        deck_id=deck.id,
        upload_id=generate_id("upload"),
        filename=filename,
    )
    stored = storage.move_file(upload.path, stored_filename)
    try:
        security_scan = scan_upload_path(stored.path)
        stored = promote_upload(stored)
    except Exception:
        storage.delete(stored.storage_path)
        raise

    persisted_storage_provider = stored.provider
    persisted_storage_path = stored.storage_path

    deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck.id).one_or_none()
    if deck_file is None:
        deck_file = DeckFile(
            id=generate_id("file"),
            deck_id=deck.id,
            filename=stored_filename,
            original_filename=filename,
            file_extension=_extension(filename).removeprefix("."),
            mime_type=mime_type,
            size=upload.size,
            storage_provider=persisted_storage_provider,
            storage_path=persisted_storage_path,
            checksum_sha256=upload.checksum_sha256,
            metadata_json={"securityScan": security_scan},
        )
        db.add(deck_file)
    else:
        deck_file.filename = stored_filename
        deck_file.original_filename = filename
        deck_file.file_extension = _extension(filename).removeprefix(".")
        deck_file.mime_type = mime_type
        deck_file.size = upload.size
        deck_file.storage_provider = persisted_storage_provider
        deck_file.storage_path = persisted_storage_path
        deck_file.checksum_sha256 = upload.checksum_sha256
        deck_file.metadata_json = {"securityScan": security_scan}

    source = (
        db.query(DeckInputSource)
        .filter(DeckInputSource.deck_id == deck.id, DeckInputSource.source_type == "uploaded_deck")
        .order_by(DeckInputSource.created_at.desc())
        .first()
    )
    if source is None:
        source = DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type="uploaded_deck",
            label="Uploaded deck",
        )
        db.add(source)

    source.original_filename = filename
    source.mime_type = mime_type
    source.storage_path = stored.storage_path
    source.status = "ready"
    _sync_source_ingestion_job(
        db,
        deck=deck,
        deck_file=deck_file,
        source=source,
        ingestion_mode="direct_upload",
        extra_metadata={"securityScan": security_scan},
    )

    deck.original_filename = filename
    transition_deck_state(
        db,
        deck,
        DeckState.UPLOADED,
        actor_user_id=deck.user_id,
        reason="limited_upload_saved",
        summary=f"Saved original source deck {filename}. Extraction can continue in the background.",
        source_surface="deck_upload",
        source_route=f"/decks/{deck.id}/upload",
        metadata={"filename": filename, "storagePath": stored.storage_path},
    )

    db.commit()
    db.refresh(deck_file)
    return _map_file(deck_file)


def create_deck_upload_url(
    db: Session,
    *,
    deck_id: str,
    filename: str,
    mime_type: str,
    size: int | None = None,
) -> dict:
    require_supported_deck_upload(filename, mime_type)
    if size is not None and size > MAX_DECK_UPLOAD_SIZE_BYTES:
        raise ValueError("Deck uploads must be 200MB or smaller")

    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise LookupError("Deck not found")

    storage = get_upload_storage()
    upload_id = generate_id("upload")
    storage_path = _source_storage_path(user_id=deck.user_id, deck_id=deck.id, upload_id=upload_id, filename=filename)
    try:
        upload_url = storage.create_signed_put_url(
            storage_path,
            content_type=mime_type,
            expires_in=settings.deck_aistack_signed_url_ttl_seconds,
        )
    except NotImplementedError as exc:
        raise RuntimeError("Presigned browser uploads require S3-compatible upload storage") from exc

    return {
        "deckId": deck.id,
        "uploadId": upload_id,
        "storagePath": storage_path,
        "uploadUrl": upload_url,
        "method": "PUT",
        "headers": {"Content-Type": mime_type},
        "expiresIn": settings.deck_aistack_signed_url_ttl_seconds,
        "maxSizeBytes": MAX_DECK_UPLOAD_SIZE_BYTES,
    }


def complete_deck_upload(
    db: Session,
    *,
    deck_id: str,
    storage_path: str,
    filename: str,
    mime_type: str,
    size: int | None = None,
    preferred_workspace: str = "smart_deck",
    website_url: str | None = None,
) -> dict:
    require_supported_deck_upload(filename, mime_type)
    from app.services.brand.website_context import normalize_website_url
    if website_url is not None and (not isinstance(website_url, str) or len(website_url) > 2048):
        raise ValueError("Company website URL is invalid")
    confirmed_website = normalize_website_url(website_url)
    if website_url and not confirmed_website:
        raise ValueError("Company website URL is invalid")
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise LookupError("Deck not found")
    _require_deck_storage_path(deck, storage_path)
    preferred_workspace_value = "instant_deck" if preferred_workspace == "instant_deck" else "smart_deck"
    website_source = None
    if confirmed_website:
        website_source = db.query(DeckInputSource).filter_by(
            deck_id=deck.id, source_type="company_website"
        ).order_by(DeckInputSource.created_at.desc()).first()
        if website_source is not None and (website_source.external_url or website_source.text_value) != confirmed_website:
            raise ValueError("Upload completion cannot replace an existing company website")

    storage = get_upload_storage()
    metadata = None
    resolved_path = None
    try:
        metadata = storage.object_metadata(storage_path)
        object_size = int(metadata.get("contentLength") or size or 0)
        if object_size > MAX_DECK_UPLOAD_SIZE_BYTES:
            raise ValueError("Deck uploads must be 200MB or smaller")

        resolved_path = storage.resolve_path(storage_path)
        if resolved_path is None or not resolved_path.exists():
            raise FileNotFoundError(storage_path)
        security_scan = scan_upload_path(resolved_path)
        checksum = compute_file_sha256(resolved_path)
        stored_filename = Path(storage_path).name

        deck_file = db.query(DeckFile).filter(DeckFile.deck_id == deck.id).one_or_none()
        if deck_file is None:
            deck_file = DeckFile(
                id=generate_id("file"),
                deck_id=deck.id,
                filename=stored_filename,
                original_filename=filename,
                file_extension=_extension(filename).removeprefix("."),
                mime_type=mime_type,
                size=object_size,
                storage_provider=storage.provider,
                storage_path=storage_path,
                checksum_sha256=checksum,
                metadata_json={
                    "uploadMode": "presigned_put",
                    "preferredWorkspace": preferred_workspace_value,
                    "objectMetadata": metadata,
                    "securityScan": security_scan,
                    "completedAt": datetime.utcnow().isoformat(),
                },
            )
            db.add(deck_file)
        else:
            deck_file.filename = stored_filename
            deck_file.original_filename = filename
            deck_file.file_extension = _extension(filename).removeprefix(".")
            deck_file.mime_type = mime_type
            deck_file.size = object_size
            deck_file.storage_provider = storage.provider
            deck_file.storage_path = storage_path
            deck_file.checksum_sha256 = checksum
            deck_file.metadata_json = {
                **(deck_file.metadata_json or {}),
                "uploadMode": "presigned_put",
                "preferredWorkspace": preferred_workspace_value,
                "objectMetadata": metadata,
                "securityScan": security_scan,
                "completedAt": datetime.utcnow().isoformat(),
            }

        source = (
            db.query(DeckInputSource)
            .filter(DeckInputSource.deck_id == deck.id, DeckInputSource.source_type == "uploaded_deck")
            .order_by(DeckInputSource.created_at.desc())
            .first()
        )
        if source is None:
            source = DeckInputSource(
                id=generate_id("source"),
                deck_id=deck.id,
                source_type="uploaded_deck",
                label="Uploaded deck",
            )
            db.add(source)

        source.original_filename = filename
        source.mime_type = mime_type
        source.storage_path = storage_path
        source.status = "ready"
        # Match multipart intake: persist explicit public website evidence in
        # the same transaction, before extraction/brand/generation are queued.
        if confirmed_website:
            if website_source is None:
                db.add(DeckInputSource(id=generate_id("source"), deck_id=deck.id,
                    source_type="company_website", label="Company website",
                    external_url=confirmed_website, text_value=confirmed_website, status="ready"))
        _sync_source_ingestion_job(
            db,
            deck=deck,
            deck_file=deck_file,
            source=source,
            ingestion_mode="presigned_put",
            extra_metadata={"objectMetadata": metadata, "securityScan": security_scan},
        )

        deck.original_filename = filename
        deck.source_type = "uploaded_deck"
        transition_deck_state(
            db,
            deck,
            DeckState.UPLOADED,
            actor_user_id=deck.user_id,
            reason="presigned_upload_completed",
            summary=f"Saved original source deck {filename}. Processing is ready to start.",
            source_surface="presigned_deck_upload",
            source_route=f"/decks/{deck.id}/upload-complete",
            metadata={"filename": filename, "storagePath": storage_path, "objectMetadata": metadata},
        )

        db.commit()
        db.refresh(deck_file)
        processing = None
        queue_failure_ticket_id: str | None = None
        queue_failure_message: str | None = None
        try:
            from app.services.deck_processing.workflow_orchestration import queue_source_extraction

            processing = queue_source_extraction(db, deck.id, requested_by_user_id=deck.user_id)
        except Exception as exc:
            queue_failure_message = str(exc) or "Workflow processing could not be queued."
            try:
                ticket = create_failure_ticket(
                    db,
                    {
                        "apiPath": "/api/products/deck-aistack-codes/decks/upload-completion",
                        "statusCode": 503,
                        "errorName": exc.__class__.__name__,
                        "errorMessage": queue_failure_message,
                        "severity": "high",
                        "source": "backend",
                        "deckId": deck.id,
                        "context": {
                            "deckId": deck.id,
                            "fileName": filename,
                            "failureStage": "upload_completion_queue_failed",
                            "stage": "upload_completion_queue_failed",
                            "nextAction": "manual_review",
                            "retryable": True,
                        },
                    },
                    commit=True,
                )
                queue_failure_ticket_id = ticket.id
            except Exception:
                db.rollback()
            logger.warning(
                "Queued processing after upload completion failed",
                extra={"deck_id": deck.id, "error_type": exc.__class__.__name__},
            )

        response = {"file": _map_file(deck_file), "object": metadata, "deck": get_deck(db, deck.id)["deck"]}
        if isinstance(processing, dict):
            response["processing"] = processing
        if queue_failure_message is not None:
            response["queueError"] = queue_failure_message
            response["queueFailureTicketId"] = queue_failure_ticket_id
            response["processing"] = {
                "status": "failed",
                "slideCount": 0,
                "message": queue_failure_message,
                "errorMessage": queue_failure_message,
                "failureTicketId": queue_failure_ticket_id,
                "nextAction": "manual_review",
                "canRetry": True,
            }
        return response
    except Exception:
        try:
            storage.delete(storage_path)
        except Exception:
            pass
        raise
