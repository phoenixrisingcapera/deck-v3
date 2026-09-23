from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import User
from app.schemas.workspace_summary import FirstDeckUploadResponse
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state, transition_deck_state
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event
from app.services.storage.upload_security import require_supported_deck_upload, stream_limited_upload
from app.services.deck_processing.workspace_summary_service import create_first_deck_upload, get_workspace_summary_for_user

router = APIRouter(tags=["product-upload-compat"])

PRODUCT_API_PREFIX = "/api/products/deck-aistack-codes"


def _manual_smart_deck_fields(deck_id: str) -> dict[str, str | None]:
    state = DeckState.UPLOADED.value
    return {
        "workflowId": f"deckwf_{deck_id}",
        "workflowPhase": "source_file_saved",
        "workflowStatus": "completed",
        "workflowJobId": None,
        "workflowJobType": None,
        "workflowJobStatus": None,
        "status": state,
        "state": state,
        "deckStatus": state,
        "ui_state": state,
        "upload_message": "Deck saved",
        "next_step_message": "Click Create Smart Deck to start processing.",
        "next_action": "create_smart_deck",
        "create_smart_deck_url": f"{PRODUCT_API_PREFIX}/decks/{deck_id}/workflows/source-extraction",
        "processing_status_url": f"{PRODUCT_API_PREFIX}/decks/{deck_id}/workflow-state",
        "smart_deck_url": f"/decks/{deck_id}/smart-deck",
        "preferred_workspace": "smart_deck",
        "preferred_workspace_url": f"/decks/{deck_id}/smart-deck",
    }


def _hold_uploaded_deck_for_manual_smart_deck_start(
    db: Session,
    *,
    current_user: User,
    deck_id: str,
) -> None:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    current_state = canonical_deck_state(deck.status)
    if current_state in {DeckState.PENDING, DeckState.FAILED}:
        transition_deck_state(
            db,
            deck,
            DeckState.UPLOADED,
            actor_user_id=current_user.id,
            reason="manual_smart_deck_start_hold",
            summary="Source deck saved. Click Create Smart Deck to start processing.",
            source_surface="upload_compat",
            source_route="/decks/new",
            metadata={"compatRoute": True},
            commit=True,
        )


def _coalesce(*values: str | None) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _split_form_lines(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").splitlines() if item.strip()]


@router.post("/products/deck-aistack-codes/decks", response_model=FirstDeckUploadResponse)
async def first_deck_upload_collection_compat(
    request: Request,
    file: UploadFile = File(...),
    workspace_id: str | None = Form(default=None),
    workspaceId: str | None = Form(default=None),
    company_name: str | None = Form(default=None),
    companyName: str | None = Form(default=None),
    website_url: str | None = Form(default=None),
    websiteUrl: str | None = Form(default=None),
    audience: str | None = Form(default=None),
    purpose: str | None = Form(default=None),
    founder_name: str | None = Form(default=None),
    founderName: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    team_notes: str | None = Form(default=None),
    teamNotes: str | None = Form(default=None),
    linkedin_urls: str | None = Form(default=None),
    linkedinUrls: str | None = Form(default=None),
    supporting_urls: str | None = Form(default=None),
    supportingUrls: str | None = Form(default=None),
    preferred_workspace: str | None = Form(default=None),
    preferredWorkspace: str | None = Form(default=None),
    brand_guide: UploadFile | None = File(default=None),
    brandGuide: UploadFile | None = File(default=None),
    logo_file: UploadFile | None = File(default=None),
    logoFile: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FirstDeckUploadResponse:
    """Backward-compatible upload wrapper for older clients.

    Canonical uploads should use:
    POST /api/products/deck-aistack-codes/decks/upload
    multipart field: deck

    This wrapper keeps the previous collection route alive for clients that still
    submit multipart field `file` and camelCase metadata fields.
    """

    enforce_rate_limit(f"upload:user:{current_user.id}", db=db, limit=20, window_seconds=3600)
    
    from app.services.storage.upload_readiness import get_upload_persistence_readiness
    readiness = get_upload_persistence_readiness()
    if not readiness["ok"]:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Deck upload is temporarily unavailable.",
                "failureCategory": "deck_upload_collection_compat_save",
                "requestId": getattr(request.state, "request_id", None),
                "recoverable": True,
            },
        )
    
    file_name = file.filename or "uploaded-deck.pdf"
    content_type = file.content_type or "application/octet-stream"
    deck_upload = None
    resolved_workspace_id = _coalesce(workspace_id, workspaceId)

    try:
        require_supported_deck_upload(file_name, content_type)
        deck_upload = await stream_limited_upload(file)
        payload = await create_first_deck_upload(
            db=db,
            user_id=current_user.id,
            file_name=file_name,
            content_type=content_type,
            deck_upload=deck_upload,
            workspace_id=resolved_workspace_id,
            company_name=_coalesce(company_name, companyName),
            website_url=_coalesce(website_url, websiteUrl),
            audience=audience,
            purpose=purpose,
            founder_name=_coalesce(founder_name, founderName),
            notes=notes,
            team_notes=_coalesce(team_notes, teamNotes),
            linkedin_urls=_split_form_lines(_coalesce(linkedin_urls, linkedinUrls)),
            supporting_urls=_split_form_lines(_coalesce(supporting_urls, supportingUrls)),
            brand_guide=brand_guide or brandGuide,
            logo_file=logo_file or logoFile,
        )
        deck_id = str(payload.get("deck_id") or "")
        if deck_id:
            if not payload.get("processing"):
                _hold_uploaded_deck_for_manual_smart_deck_start(db, current_user=current_user, deck_id=deck_id)
                payload.update(_manual_smart_deck_fields(deck_id))
                payload["deck_extraction_status"] = DeckState.UPLOADED.value
            payload["workspace"] = get_workspace_summary_for_user(db, current_user, resolved_workspace_id)
    except HTTPException as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        record_security_event(
            db,
            action="deck.upload.compat",
            result="failure",
            actor=current_user,
            resource_type="deck",
            request=request,
            details={
                "contentType": content_type,
                "fileExtension": Path(file_name).suffix.lower(),
                "statusCode": exc.status_code,
                "compatRoute": True,
            },
            commit=True,
        )
        raise
    except ValueError as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        record_security_event(
            db,
            action="deck.upload.compat",
            result="failure",
            actor=current_user,
            resource_type="deck",
            request=request,
            details={
                "contentType": content_type,
                "fileExtension": Path(file_name).suffix.lower(),
                "reason": exc.__class__.__name__,
                "compatRoute": True,
            },
            commit=True,
        )
        raise HTTPException(
            status_code=400,
            detail={"message": "Deck upload request could not be validated.", "failureCategory": "deck_upload_validation", "recoverable": True},
        ) from exc
    except Exception as exc:
        if deck_upload is not None:
            deck_upload.path.unlink(missing_ok=True)
        db.rollback()
        ticket_id = None
        try:
            ticket = create_failure_ticket(
                db,
                {
                    "apiPath": request.url.path,
                    "statusCode": 503,
                    "errorName": "DeckUploadFailure",
                    "errorMessage": "Compatibility upload failed before persistence completed.",
                    "errorStack": None,
                    "severity": "critical",
                    "source": "backend",
                    "context": {
                        "phase": "deck_upload_collection_compat_save",
                        "compatRoute": True,
                        "contentType": content_type,
                        "fileExtension": Path(file_name).suffix.lower(),
                    },
                },
                request=request,
                current_user=current_user,
                commit=True,
            )
            ticket_id = ticket.id
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Deck upload could not be saved. Please retry.",
                "failureCategory": "deck_upload_collection_compat_save",
                "requestId": getattr(request.state, "request_id", None),
                "ticketId": ticket_id,
                "recoverable": True,
            },
        ) from exc

    record_security_event(
        db,
        action="deck.upload.compat",
        result="success",
        actor=current_user,
        resource_type="deck",
        resource_id=str(payload.get("deck_id") or ""),
        request=request,
        details={
            "contentType": content_type,
            "fileExtension": Path(file_name).suffix.lower(),
            "size": payload.get("source_file_size_bytes"),
            "workspaceId": payload.get("workspace", {}).get("id") if isinstance(payload.get("workspace"), dict) else None,
            "nextAction": payload.get("next_action"),
            "deckState": payload.get("state") or payload.get("status"),
            "compatRoute": True,
        },
        commit=True,
    )

    return FirstDeckUploadResponse(**payload)
