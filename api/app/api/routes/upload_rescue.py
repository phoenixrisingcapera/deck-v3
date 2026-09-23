from __future__ import annotations

import logging
import hashlib
import json
import unicodedata
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.core.config import settings
from app.core.security import generate_id
from app.core.utils import safe_filename
from app.db.models import Deck, DeckFile, DeckInputSource, DeckUploadRequest, User, Workspace
from app.schemas.workspace_summary import FirstDeckUploadResponse
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.brand.company_profile import upsert_company_profile
from app.services.brand.website_context import normalize_website_url
from app.services.deck_processing.workflow_orchestration import queue_source_extraction
from app.services.deck_processing.workspace_summary_service import build_existing_upload_response
from app.services.storage.upload_readiness import get_upload_failure_diagnostic_summary
from app.services.storage.upload_scan import (
    UploadScanInfectedError,
    UploadScannerUnavailableError,
    scan_upload_path,
)
from app.services.storage.upload_security import require_supported_deck_upload, stream_limited_upload
from app.services.storage.artifact_storage import LocalUploadStorage, get_upload_storage, promote_upload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload-rescue"])
PRODUCT_API_PREFIX = "/api/products/deck-aistack-codes"
# Contract marker retained for clients that inspect the manual-start receipt.
# "next_action": "create_smart_deck"


def _workspace_for_user(db: Session, user: User, workspace_id: str | None) -> Workspace:
    query = db.query(Workspace).filter(Workspace.user_id == user.id)
    workspace = query.filter(Workspace.id == workspace_id).first() if workspace_id else query.order_by(Workspace.created_at.asc()).first()
    if workspace is not None:
        return workspace

    display_name = (user.name or user.email or "Deck").split("@")[0].split()[0]
    workspace = Workspace(id=generate_id("ws"), name=f"{display_name}'s Workspace", user_id=user.id)
    db.add(workspace)
    db.flush()
    return workspace


UPLOAD_CLIENT_ID_PREFIX = "upload-"
AUXILIARY_UPLOAD_MAX_BYTES = 25 * 1024 * 1024


def _require_upload_client_request_hash(request: Request) -> str:
    raw = request.headers.get("x-request-id", "").strip()
    candidate = raw[len(UPLOAD_CLIENT_ID_PREFIX):] if raw.startswith(UPLOAD_CLIENT_ID_PREFIX) else ""
    try:
        parsed = UUID(candidate)
    except (ValueError, AttributeError):
        parsed = None
    if parsed is None or parsed.version != 4 or str(parsed) != candidate.lower():
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Upload request identity is invalid. Start a new upload action.",
                "failureCategory": "deck_upload_request_id_invalid",
                "recoverable": True,
            },
        )
    return hashlib.sha256(candidate.lower().encode("ascii")).hexdigest()


def _normalize_intent_text(value: str | None, *, default: str | None = None) -> str | None:
    selected = value if value is not None and value.strip() else default
    if selected is None:
        return None
    return unicodedata.normalize("NFC", selected.replace("\r\n", "\n").replace("\r", "\n").strip())


def _normalize_intent_lines(value: str | None) -> list[str]:
    normalized = _normalize_intent_text(value)
    return [item.strip() for item in (normalized or "").split("\n") if item.strip()]


def _canonical_upload_intent(
    *,
    deck_checksum: str,
    source_filename: str,
    source_content_type: str,
    workspace_id: str,
    preferred_workspace: str,
    company_name: str | None,
    website_url: str | None,
    audience: str | None,
    purpose: str | None,
    founder_name: str | None,
    notes: str | None,
    team_notes: str | None,
    linkedin_urls: str | None,
    supporting_urls: str | None,
    brand_guide_checksum: str | None,
    brand_guide_filename: str | None,
    logo_checksum: str | None,
    logo_filename: str | None,
) -> dict:
    return {
        "audience": _normalize_intent_text(audience, default="Investment Committee"),
        "brandGuideSha256": brand_guide_checksum,
        "brandGuideFilename": _normalize_intent_text(Path(brand_guide_filename).name if brand_guide_filename else None),
        "companyName": _normalize_intent_text(company_name),
        "deckSha256": deck_checksum,
        "founderName": _normalize_intent_text(founder_name),
        "linkedinUrls": _normalize_intent_lines(linkedin_urls),
        "logoSha256": logo_checksum,
        "logoFilename": _normalize_intent_text(Path(logo_filename).name if logo_filename else None),
        "notes": _normalize_intent_text(notes),
        "preferredWorkspace": preferred_workspace,
        "purpose": _normalize_intent_text(purpose, default="Initial diligence review"),
        "supportingUrls": _normalize_intent_lines(supporting_urls),
        "sourceContentType": source_content_type.split(";", 1)[0].strip().lower(),
        "sourceFilename": _normalize_intent_text(Path(source_filename).name),
        "teamNotes": _normalize_intent_text(team_notes),
        "websiteUrl": _normalize_intent_text(website_url),
        "workspaceId": workspace_id,
    }


def _hash_upload_intent(canonical: dict) -> str:
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _persist_upload_brand_intent(
    db: Session,
    *,
    workspace: Workspace,
    deck: Deck,
    canonical_intent: dict,
) -> None:
    """Join upload identity to the existing canonical source/brand records."""
    raw_website_url = canonical_intent.get("websiteUrl")
    website_url = normalize_website_url(raw_website_url)
    if raw_website_url and website_url is None:
        raise ValueError("Company website URL is invalid.")
    if website_url:
        db.add(DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type="company_website",
            label="Company website",
            external_url=website_url,
            text_value=website_url,
            status="ready",
        ))
    upsert_company_profile(
        db,
        workspace,
        deck,
        canonical_intent.get("companyName"),
        website_url,
        canonical_intent.get("founderName"),
        canonical_intent.get("teamNotes"),
        list(canonical_intent.get("linkedinUrls") or []),
        canonical_intent.get("notes"),
    )


def _upload_intent_hash(**fields) -> str:
    return _hash_upload_intent(_canonical_upload_intent(**fields))


def _upload_request_replay(
    db: Session,
    *,
    user_id: str,
    workspace_id: str,
    client_request_hash: str,
) -> tuple[DeckUploadRequest, Deck, DeckFile] | None:
    return (
        db.query(DeckUploadRequest, Deck, DeckFile)
        .join(Deck, Deck.id == DeckUploadRequest.deck_id)
        .join(DeckFile, DeckFile.id == DeckUploadRequest.deck_file_id)
        .filter(
            DeckUploadRequest.user_id == user_id,
            DeckUploadRequest.workspace_id == workspace_id,
            DeckUploadRequest.client_request_hash == client_request_hash,
        )
        .one_or_none()
    )


def _require_matching_upload_replay(
    replay: tuple[DeckUploadRequest, Deck, DeckFile],
    *,
    intent_hash: str,
) -> tuple[Deck, DeckFile]:
    coordination, replay_deck, replay_file = replay
    if coordination.intent_hash != intent_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This upload request ID is already bound to a different upload payload.",
                "failureCategory": "deck_upload_idempotency_conflict",
                "recoverable": False,
            },
        )
    return replay_deck, replay_file


def _ensure_app_db_user(db: Session, user: User) -> User:
    """Mirror the authenticated user into the app DB for app-owned FKs.
    
    Returns the user that should be used (either existing or newly created).
    Handles the case where a user with the same email already exists with a different ID.
    """
    existing_by_id = db.get(User, user.id)
    if existing_by_id is not None:
        return existing_by_id
    
    existing_by_email = db.query(User).filter(User.email == user.email).first()
    if existing_by_email is not None:
        return existing_by_email
    
    db.add(
        User(
            id=user.id,
            email=user.email,
            name=user.name,
            password_hash=user.password_hash,
            role=user.role,
        )
    )
    db.flush()
    return user



def _title_from_filename(filename: str, company_name: str | None) -> str:
    if company_name and company_name.strip():
        return f"{company_name.strip()} deck"
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return stem or "Uploaded deck"


def _storage_diagnostics() -> dict:
    return {
        "storageBackend": settings.upload_storage_backend,
        "hasStorageBucket": bool(settings.upload_storage_s3_bucket),
        "hasStorageRegion": bool(settings.upload_storage_s3_region),
        "hasStorageEndpoint": bool(settings.upload_storage_s3_endpoint_url),
        "hasRailwayBucketAccessKey": bool(settings.railway_bucket_access_key),
        "hasRailwayBucketSecretKey": bool(settings.railway_bucket_secret_key),
        "hasEffectiveS3AccessKey": bool(settings.effective_s3_access_key),
        "hasEffectiveS3SecretKey": bool(settings.effective_s3_secret_key),
    }


def _upload_warning(exc: Exception, *, warning: str, phase: str, fallback_provider: str | None = None) -> dict:
    payload = {
        "warning": warning,
        "phase": phase,
        "failureCategory": phase,
    }
    if fallback_provider:
        payload["fallbackProvider"] = fallback_provider
    return payload


def _upload_storage_with_fallback() -> tuple[object, dict | None]:
    try:
        return get_upload_storage(), None
    except Exception as exc:
        if settings.is_production:
            logger.error("upload_storage_config_failed", extra={"failure_category": "deck_upload_storage_config"})
            raise RuntimeError("deck_upload_storage_config") from exc
        warning = _upload_warning(
            exc,
            warning="upload_storage_config_failed_using_local_fallback",
            phase="upload_storage_config",
            fallback_provider="local",
        )
        logger.warning("upload_storage_local_fallback", extra={"failure_category": "deck_upload_storage_config"})
        return LocalUploadStorage(), warning


def _upload_save_diagnostics() -> dict:
    readiness = get_upload_failure_diagnostic_summary()
    return {
        "storageDiagnostics": _storage_diagnostics(),
        "uploadReadiness": readiness,
        "missingRequiredChecks": readiness.get("missingRequiredChecks", []),
        "warningChecks": readiness.get("warningChecks", []),
        "acceptedVariableGroups": readiness.get("acceptedVariableGroups", {}),
    }


def _upload_save_failure_detail(request: Request, exc: Exception, ticket_id: str | None) -> dict:
    return {
        "message": "Deck upload could not be saved. Please retry with a new upload action.",
        "failureCategory": "deck_upload_save",
        "requestId": getattr(request.state, "request_id", None),
        "ticketId": ticket_id,
        "recoverable": True,
    }


@router.get("/products/deck-aistack-codes/upload-readiness")
def upload_readiness() -> dict:
    return {
        "ok": True,
        **_upload_save_diagnostics(),
    }


def _workspace_response(workspace: Workspace, deck: Deck, deck_file: DeckFile) -> dict:
    deck_summary = {
        "id": deck.id,
        "title": deck.title,
        "audience": deck.audience,
        "purpose": deck.purpose,
        "status": deck.status,
        "summary": deck.summary or "Saved original source deck.",
        "created_at": deck.created_at,
        "updated_at": deck.updated_at,
        "slide_count": deck.slide_count,
        "thumbnail_url": None,
        "preview_url": None,
        "first_slide_id": None,
        "original_filename": deck_file.original_filename,
    }
    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "deck_count": 1,
        "active_deck_id": deck.id,
        "latest_decks": [deck_summary],
        "processing_deck_count": 0,
        "ready_deck_count": 0,
        "export_count": 0,
        "first_time_templates": [],
    }


def _record_failure_ticket(
    db: Session,
    request: Request,
    current_user: User,
    exc: Exception,
    *,
    content_type: str,
) -> str | None:
    try:
        ticket = create_failure_ticket(
            db,
            {
                "apiPath": request.url.path,
                "statusCode": 503,
                "errorName": "DeckUploadFailure",
                "errorMessage": "Deck upload failed before persistence completed.",
                "errorStack": None,
                "severity": "critical",
                "source": "backend",
                "context": {
                    "phase": "upload_rescue_route",
                    "failureCategory": "deck_upload_save",
                    "contentType": content_type,
                    **_storage_diagnostics(),
                    **_upload_save_diagnostics(),
                },
            },
            request=request,
            current_user=current_user,
            commit=True,
        )
        return ticket.id
    except Exception:
        db.rollback()
        return None


def _apply_source_workflow_repair_result(
    payload: dict,
    *,
    message: str | None,
    ticket_id: str | None,
) -> dict:
    if not message:
        payload.setdefault('queueError', None)
        payload.setdefault('queueFailureTicketId', None)
        return payload

    processing = payload.get('processing') if isinstance(payload.get('processing'), dict) else {}
    payload['processing'] = {
        **processing,
        'status': 'failed',
        'phase': 'source_queue_failed',
        'message': message,
        'errorMessage': message,
        'failureTicketId': ticket_id,
        'nextAction': 'manual_review',
        'canRetry': True,
    }
    payload['deck_extraction_status'] = 'failed'
    payload['status'] = 'failed'
    payload['state'] = 'failed'
    payload['deckStatus'] = 'failed'
    payload['next_action'] = 'retry_job'
    payload['next_step_message'] = 'This upload needs attention before Instant Deck can continue.'
    payload['queueError'] = message
    payload['queueFailureTicketId'] = ticket_id
    return payload


def _ensure_source_workflow(
    db: Session,
    *,
    deck: Deck,
    current_user: User,
    request: Request,
) -> tuple[dict | None, str | None, str | None]:
    """Idempotently repair the post-persistence source-queue boundary."""
    try:
        return queue_source_extraction(
            db,
            deck.id,
            requested_by_user_id=deck.user_id,
            requeue_failed=False,
        ), None, None
    except Exception:
        db.rollback()
        message = "Source processing could not be queued. Retry the same upload action."
        ticket_id: str | None = None
        try:
            ticket = create_failure_ticket(
                db,
                {
                    "apiPath": f"{PRODUCT_API_PREFIX}/decks/upload",
                    "statusCode": 503,
                    "errorName": "SourceWorkflowQueueFailure",
                    "errorMessage": message,
                    "errorStack": None,
                    "severity": "high",
                    "source": "backend",
                    "deckId": deck.id,
                    "context": {
                        "deckId": deck.id,
                        "failureStage": "upload_queue_failed",
                        "nextAction": "retry_same_upload",
                        "retryable": True,
                    },
                },
                request=request,
                current_user=current_user,
                commit=True,
            )
            ticket_id = ticket.id
        except Exception:
            db.rollback()
        logger.warning(
            "upload_source_workflow_queue_failed",
            extra={"deck_id": deck.id, "failure_category": "deck_upload_source_queue"},
        )
        return None, message, ticket_id


@router.post("/products/deck-aistack-codes/decks/upload", response_model=FirstDeckUploadResponse)
async def upload_deck_rescue(
    request: Request,
    deck: UploadFile = File(...),
    workspace_id: str | None = Form(default=None),
    company_name: str | None = Form(default=None),
    website_url: str | None = Form(default=None),
    audience: str | None = Form(default=None),
    purpose: str | None = Form(default=None),
    founder_name: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    team_notes: str | None = Form(default=None),
    linkedin_urls: str | None = Form(default=None),
    supporting_urls: str | None = Form(default=None),
    preferred_workspace: str | None = Form(default=None),
    brand_guide: UploadFile | None = File(default=None),
    logo_file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FirstDeckUploadResponse:
    from app.services.storage.upload_readiness import get_upload_persistence_readiness
    client_request_hash = _require_upload_client_request_hash(request)
    readiness = get_upload_persistence_readiness()
    if not readiness["ok"]:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Deck upload is temporarily unavailable.",
                "failureCategory": "deck_upload_save",
                "requestId": getattr(request.state, "request_id", None),
                "recoverable": True,
            },
        )
    
    file_name = deck.filename or "uploaded-deck.pdf"
    content_type = deck.content_type or "application/octet-stream"
    deck_upload = None
    auxiliary_uploads = []
    preferred_workspace_value = "instant_deck" if preferred_workspace == "instant_deck" else "smart_deck"

    try:
        require_supported_deck_upload(file_name, content_type)
        deck_upload = await stream_limited_upload(deck)
        brand_guide_upload = None
        logo_upload = None
        if brand_guide is not None and brand_guide.filename:
            brand_guide_upload = await stream_limited_upload(brand_guide, max_size=AUXILIARY_UPLOAD_MAX_BYTES)
            auxiliary_uploads.append(brand_guide_upload)
        if logo_file is not None and logo_file.filename:
            logo_upload = await stream_limited_upload(logo_file, max_size=AUXILIARY_UPLOAD_MAX_BYTES)
            auxiliary_uploads.append(logo_upload)

        app_user = _ensure_app_db_user(db, current_user)
        workspace = _workspace_for_user(db, app_user, workspace_id)
        canonical_intent = _canonical_upload_intent(
            deck_checksum=deck_upload.checksum_sha256,
            source_filename=file_name,
            source_content_type=content_type,
            workspace_id=workspace.id,
            preferred_workspace=preferred_workspace_value,
            company_name=company_name,
            website_url=website_url,
            audience=audience,
            purpose=purpose,
            founder_name=founder_name,
            notes=notes,
            team_notes=team_notes,
            linkedin_urls=linkedin_urls,
            supporting_urls=supporting_urls,
            brand_guide_checksum=brand_guide_upload.checksum_sha256 if brand_guide_upload else None,
            brand_guide_filename=brand_guide.filename if brand_guide_upload and brand_guide else None,
            logo_checksum=logo_upload.checksum_sha256 if logo_upload else None,
            logo_filename=logo_file.filename if logo_upload and logo_file else None,
        )
        intent_hash = _hash_upload_intent(canonical_intent)
        file_name = canonical_intent["sourceFilename"]
        content_type = canonical_intent["sourceContentType"]
        replay = _upload_request_replay(
            db,
            user_id=app_user.id,
            workspace_id=workspace.id,
            client_request_hash=client_request_hash,
        )
        if replay is not None:
            replay_deck, replay_file = _require_matching_upload_replay(
                replay,
                intent_hash=intent_hash,
            )
            _, queue_message, queue_ticket_id = _ensure_source_workflow(db, deck=replay_deck, current_user=current_user, request=request)
            return FirstDeckUploadResponse(
                **_apply_source_workflow_repair_result(
                    build_existing_upload_response(
                        db,
                        workspace=workspace,
                        deck=replay_deck,
                        deck_file=replay_file,
                        preferred_workspace=preferred_workspace_value,
                    ),
                    message=queue_message,
                    ticket_id=queue_ticket_id,
                )
            )
        # A checksum identifies bytes, not a new upload intent. A fresh request
        # identity must own a fresh deck and therefore a fresh workflow/deadline.
        deck_id = generate_id("deck")
        upload_id = generate_id("upload")
        stored_filename = f"users/{app_user.id}/decks/{deck_id}/source/{upload_id}/{safe_filename(file_name)}"

        storage, storage_warning = _upload_storage_with_fallback()
        stored = storage.move_file(deck_upload.path, stored_filename)
        try:
            security_scan = scan_upload_path(stored.path)
        except (UploadScanInfectedError, UploadScannerUnavailableError):
            storage.delete(stored.storage_path)
            raise
        if storage_warning is None:
            try:
                stored = promote_upload(stored)
            except Exception as promote_exc:
                stored.path.unlink(missing_ok=True)
                logger.warning(
                    "upload_remote_storage_promotion_failed",
                    extra={"failure_category": "deck_upload_storage"},
                )
                raise HTTPException(
                    status_code=503,
                    detail={
                        "message": "Deck upload could not be persisted to shared storage. Please retry.",
                        "failureCategory": "deck_upload_storage",
                        "requestId": getattr(request.state, "request_id", None),
                        "recoverable": True,
                    },
                ) from promote_exc

        # Persist the storage provider/path from the final stored object so
        # downstream workers resolve the source file through the same backend.
        persisted_storage_provider = stored.provider
        persisted_storage_path = stored.storage_path

        upload_metadata = {
            "securityScan": security_scan,
            "smartDeckProcessing": "queued_automatically",
            "preferredWorkspace": canonical_intent["preferredWorkspace"],
            "uploadIntentHash": intent_hash,
        }
        if storage_warning is not None:
            upload_metadata["storageWarning"] = storage_warning

        deck_record = Deck(
            id=deck_id,
            workspace_id=workspace.id,
            user_id=app_user.id,
            title=_title_from_filename(canonical_intent["sourceFilename"], canonical_intent["companyName"]),
            audience=canonical_intent["audience"],
            purpose=canonical_intent["purpose"],
            status="uploaded",
            source_type="uploaded_deck",
            summary=f"Saved original source deck {canonical_intent['sourceFilename']}. Processing will continue in the background.",
            metadata_json={"uploadIntent": canonical_intent},
        )
        db.add(deck_record)
        db.flush()
        _persist_upload_brand_intent(
            db,
            workspace=workspace,
            deck=deck_record,
            canonical_intent=canonical_intent,
        )

        deck_file = DeckFile(
            id=generate_id("file"),
            deck_id=deck_record.id,
            filename=stored_filename,
            original_filename=canonical_intent["sourceFilename"],
            file_extension=Path(canonical_intent["sourceFilename"]).suffix.lower().removeprefix("."),
            mime_type=canonical_intent["sourceContentType"],
            size=deck_upload.size,
            storage_provider=persisted_storage_provider,
            storage_path=persisted_storage_path,
            checksum_sha256=deck_upload.checksum_sha256,
            metadata_json=upload_metadata,
        )
        db.add(deck_file)
        db.flush()
        db.add(
            DeckUploadRequest(
                id=generate_id("uploadreq"),
                user_id=app_user.id,
                workspace_id=workspace.id,
                client_request_hash=client_request_hash,
                intent_hash=intent_hash,
                deck_id=deck_record.id,
                deck_file_id=deck_file.id,
            )
        )
        try:
            # Flush the scoped identity before creating the source outbox, but
            # commit neither independently. queue_source_extraction commits the
            # upload, coordination row, and canonical source jobs atomically.
            db.flush()
        except IntegrityError:
            # A concurrent transport replay may pass the first lookup before
            # its winner commits. Keep the winner and remove the losing object.
            db.rollback()
            storage.delete(stored.storage_path)
            replay = _upload_request_replay(
                db,
                user_id=app_user.id,
                workspace_id=workspace.id,
                client_request_hash=client_request_hash,
            )
            if replay is None:
                raise
            replay_deck, replay_file = _require_matching_upload_replay(
                replay,
                intent_hash=intent_hash,
            )
            _, queue_message, queue_ticket_id = _ensure_source_workflow(db, deck=replay_deck, current_user=current_user, request=request)
            return FirstDeckUploadResponse(
                **_apply_source_workflow_repair_result(
                    build_existing_upload_response(
                        db,
                        workspace=workspace,
                        deck=replay_deck,
                        deck_file=replay_file,
                        preferred_workspace=preferred_workspace_value,
                    ),
                    message=queue_message,
                    ticket_id=queue_ticket_id,
                )
            )
        source_commit_confirmation_unknown = False
        try:
            processing = queue_source_extraction(
                db,
                deck_record.id,
                requested_by_user_id=app_user.id,
                requeue_failed=False,
            )
        except Exception as queue_exc:
            db.rollback()
            committed_replay = _upload_request_replay(
                db,
                user_id=app_user.id,
                workspace_id=workspace.id,
                client_request_hash=client_request_hash,
            )
            if committed_replay is not None:
                # queue_source_extraction may have committed before an outer
                # adapter raised. Preserve the durable source and report an
                # explicit unknown confirmation; replay safely repairs it.
                deck_record, deck_file = _require_matching_upload_replay(
                    committed_replay,
                    intent_hash=intent_hash,
                )
                source_commit_confirmation_unknown = True
                processing = {
                    "accepted": True,
                    "status": "committed",
                    "phase": "source_queue_confirmation_unknown",
                    "commitState": "committed",
                    "queueConfirmation": "unknown",
                }
                logger.warning(
                    "upload_source_workflow_commit_confirmation_unknown",
                    extra={"deck_id": deck_record.id, "failure_category": "deck_upload_source_queue_confirmation"},
                )
            else:
                storage.delete(stored.storage_path)
                logger.warning(
                    "upload_source_workflow_atomic_queue_failed",
                    extra={"failure_category": "deck_upload_source_queue"},
                )
                raise HTTPException(
                    status_code=503,
                    detail={
                        "message": "Deck upload could not start source processing. Please retry.",
                        "failureCategory": "deck_upload_source_queue",
                        "requestId": getattr(request.state, "request_id", None),
                        "recoverable": True,
                    },
                ) from queue_exc
        db.refresh(deck_record)
        db.refresh(deck_file)

        queue_failure_message = (
            "Your upload was saved. Source processing confirmation is pending."
            if source_commit_confirmation_unknown
            else None
        )
        queue_failure_ticket_id = None

        uploaded_at = deck_file.uploaded_at.isoformat() if deck_file.uploaded_at else None
        payload = {
            "ok": True,
            "deck_id": deck_record.id,
            "filename": file_name,
            "upload_success": True,
            "upload_status": "saved",
            "source_file_status": "saved",
            "original_file_url": None,
            "source_file_name": deck_file.original_filename,
            "source_file_size_bytes": deck_file.size,
            "source_file_mime_type": deck_file.mime_type,
            "source_file_extension": deck_file.file_extension,
            "source_file_display_name": deck_file.original_filename,
            "source_file_uploaded_at": uploaded_at,
            "deck_extraction_status": "queued" if processing else "failed",
            "status": "queued" if processing else "failed",
            "state": "queued" if processing else "failed",
            "deckStatus": "queued" if processing else "failed",
            "ui_state": "uploaded" if processing else "failed",
            "upload_message": "Uploaded" if storage_warning is None else "Uploaded with storage warning",
            "next_step_message": queue_failure_message or "Your deck is saved and processing has started.",
            "next_action": "view_processing" if processing else "manual_review",
            "create_smart_deck_url": f"{PRODUCT_API_PREFIX}/decks/{deck_record.id}/workflows/source-extraction",
            "processing_status_url": f"{PRODUCT_API_PREFIX}/decks/{deck_record.id}/workflow-state",
            "smart_deck_url": f"/decks/{deck_record.id}/smart-deck",
            "preferred_workspace": preferred_workspace_value,
            "preferred_workspace_url": (
                f"/decks/{deck_record.id}/instant-deck"
                if preferred_workspace_value == "instant_deck"
                else f"/decks/{deck_record.id}/smart-deck"
            ),
            "storage_warning": storage_warning,
            "processing": processing
            if processing
            else {
                "status": "failed",
                "nextAction": "manual_review",
                "canRetry": True,
                "message": queue_failure_message,
                "errorMessage": queue_failure_message,
                "ticketId": queue_failure_ticket_id,
                "failureTicketId": queue_failure_ticket_id,
            },
            "queue_error": queue_failure_message,
            "queue_failure_ticket_id": queue_failure_ticket_id,
            "confirmation": None,
            "workspace": _workspace_response(workspace, deck_record, deck_file),
        }
        return FirstDeckUploadResponse(**payload)
    except HTTPException:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        raise
    except UploadScanInfectedError as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "message": "The uploaded file did not pass the security scan.",
                "failureCategory": "deck_upload_malware_detected",
                "recoverable": False,
            },
        ) from exc
    except UploadScannerUnavailableError as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "File security scanning is temporarily unavailable. Please retry.",
                "failureCategory": "deck_upload_scanner_unavailable",
                "recoverable": True,
            },
        ) from exc
    except ValueError as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Deck upload request could not be validated.",
                "failureCategory": "deck_upload_validation",
                "recoverable": True,
            },
        ) from exc
    except Exception as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        db.rollback()
        ticket_id = _record_failure_ticket(db, request, current_user, exc, content_type=content_type)
        logger.exception(
            "upload_rescue_save_failed",
            extra={
                "ticket_id": ticket_id,
                "failure_category": "deck_upload_save",
            },
        )
        raise HTTPException(
            status_code=503,
            detail=_upload_save_failure_detail(request, exc, ticket_id),
        ) from exc
    finally:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        for auxiliary_upload in auxiliary_uploads:
            auxiliary_upload.path.unlink(missing_ok=True)
