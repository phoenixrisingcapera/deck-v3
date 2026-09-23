from __future__ import annotations

import json
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import Deck, DeckBrandAsset, DeckFile, DeckInputSource, Workspace
from app.services.brand.brand_extraction import (
    BRAND_GUIDELINES_UPLOAD_TYPES,
    LOGO_UPLOAD_TYPES,
    MAX_BRAND_GUIDELINES_UPLOAD_SIZE_BYTES,
    MAX_LOGO_UPLOAD_SIZE_BYTES,
    build_brand_asset_public_url,
    read_supported_brand_upload,
)
from app.services.brand.brand_profile_persistence import upsert_brand_profile
from app.services.brand.company_profile import upsert_company_profile
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state
from app.services.deck_processing.save_confirmation import get_latest_save_confirmation_for_deck, map_save_confirmation
from app.services.storage.upload_scan import scan_upload_path
from app.services.storage.artifact_storage import get_upload_storage, promote_upload
from app.services.brand.website_context import normalize_website_url


WORKFLOW_FAILURE_STATUSES = {"failed_retryable", "failed_final", "blocked", "timed_out"}


def _store_optional_upload(file: UploadFile, prefix: str) -> str:
    storage = get_upload_storage()
    suffix = Path(file.filename or "").suffix or ".bin"
    stored_name = f"{generate_id(prefix)}{suffix}"
    path = storage.resolve_path(stored_name)
    if path is None:
        raise ValueError("Upload storage path is invalid")
    return stored_name


def _load_deck_for_status(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.file),
            selectinload(Deck.slides),
            selectinload(Deck.brand_profile),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def _build_processing_steps(workflow: dict | None) -> list[dict[str, str]]:
    workflow = workflow or {}
    phase = str(workflow.get("phase") or "")
    source = workflow.get("source") or {}
    smart_deck = workflow.get("smartDeck") or {}
    status_value = str(workflow.get("status") or "")
    smart_deck_ready = bool(smart_deck.get("ready")) or bool(workflow.get("canOpenSmartDeck"))

    upload_status = "completed" if bool(source.get("fileSaved")) else "pending"
    processing_status = "pending"
    workspace_status = "pending"

    if status_value in WORKFLOW_FAILURE_STATUSES:
        processing_status = "failed"
    elif smart_deck_ready:
        processing_status = "completed"
    elif phase in {
        "source_ingestion_queued",
        "source_ingestion_running",
        "source_extraction_queued",
        "source_extraction_running",
        "miniatures_queued",
        "miniatures_running",
        "brand_extraction_queued",
        "brand_extraction_running",
        "smart_deck_context_queued",
        "smart_deck_context_running",
    }:
        processing_status = "running"

    if status_value in WORKFLOW_FAILURE_STATUSES:
        workspace_status = "failed"
    elif smart_deck_ready:
        workspace_status = "completed"
    elif phase in {"smart_deck_context_queued", "smart_deck_context_running"}:
        workspace_status = "running"

    return [
        {"key": "upload", "label": "Upload received", "status": upload_status},
        {"key": "processing", "label": "Preparing Smart Deck context", "status": processing_status},
        {"key": "workspace_ready", "label": "Preparing workspace", "status": workspace_status},
    ]


def build_source_file_summary(source_file: DeckFile | None) -> dict[str, str | int | None]:
    if source_file is None:
        return {
            "source_file_name": None,
            "source_file_size_bytes": None,
            "source_file_mime_type": None,
            "source_file_extension": None,
            "source_file_display_name": None,
            "source_file_uploaded_at": None,
        }

    display_name = source_file.original_filename or source_file.filename
    extension = source_file.file_extension or Path(display_name).suffix.removeprefix(".").lower() or None
    return {
        "source_file_name": source_file.filename,
        "source_file_size_bytes": source_file.size,
        "source_file_mime_type": source_file.mime_type,
        "source_file_extension": extension,
        "source_file_display_name": display_name,
        "source_file_uploaded_at": source_file.uploaded_at.isoformat() if source_file.uploaded_at else None,
    }


def build_upload_widget_state(extraction_status: str, source_file: DeckFile | None) -> dict[str, str | None]:
    if extraction_status == DeckState.FAILED.value:
        return {
            "ui_state": DeckState.FAILED.value,
            "upload_message": "Upload needs attention",
            "next_step_message": "Try the upload again or choose a different source file.",
            "next_action": "retry_job",
        }

    if extraction_status == DeckState.READY.value:
        return {
            "ui_state": DeckState.READY.value,
            "upload_message": "Deck ready",
            "next_step_message": "Your deck is ready to open in the Smart Deck workspace.",
            "next_action": "open_smart_deck",
        }

    if extraction_status == DeckState.PROCESSING.value:
        return {
            "ui_state": DeckState.PROCESSING.value,
            "upload_message": "Processing deck",
            "next_step_message": "We saved the source deck and are preparing it for the Smart Deck workspace.",
            "next_action": "view_processing",
        }

    if source_file is not None:
        return {
            "ui_state": DeckState.UPLOADED.value,
            "upload_message": "Uploaded",
            "next_step_message": "Your deck is secure and ready for the next step.",
            "next_action": "continue_upload",
        }

    return {
        "ui_state": DeckState.PENDING.value,
        "upload_message": None,
        "next_step_message": None,
        "next_action": "continue_upload",
    }


def get_deck_intake_status(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck_for_status(db, deck_id)
    if deck is None:
        return None

    source_file: DeckFile | None = deck.file
    workflow = get_deck_workflow_state(db, deck.id) or {}
    phase = str(workflow.get("phase") or "")
    workflow_status = str(workflow.get("status") or "")
    source_state = workflow.get("source") or {}
    smart_deck_state = workflow.get("smartDeck") or {}
    active_job = workflow.get("activeJob") or {}

    if workflow_status in WORKFLOW_FAILURE_STATUSES:
        extraction_status = DeckState.FAILED.value
    elif bool(smart_deck_state.get("ready")) or bool(workflow.get("canOpenSmartDeck")):
        extraction_status = DeckState.READY.value
    elif phase in {
        "source_ingestion_queued",
        "source_ingestion_running",
        "source_extraction_queued",
        "source_extraction_running",
        "miniatures_queued",
        "miniatures_running",
        "brand_extraction_queued",
        "brand_extraction_running",
        "smart_deck_context_queued",
        "smart_deck_context_running",
        "generation_queued",
        "generation_running",
        "schema_validation_queued",
        "schema_validation_running",
        "preview_render_queued",
        "preview_render_running",
        "apply_queued",
        "apply_running",
        "export_queued",
        "export_running",
    }:
        extraction_status = DeckState.PROCESSING.value
    elif bool(source_state.get("fileSaved")):
        extraction_status = DeckState.UPLOADED.value
    else:
        extraction_status = DeckState.PENDING.value

    deck_state = extraction_status

    brand_profile = deck.brand_profile
    latest_confirmation = get_latest_save_confirmation_for_deck(db, deck.id)
    brand_status = brand_profile.processing_status if brand_profile is not None else "idle"
    if brand_profile is not None and (
        brand_profile.logo_url
        or (brand_profile.palette_json and len(brand_profile.palette_json) > 0)
        or brand_profile.primary_color
    ):
        brand_status = "ready"
    elif brand_status == "ready":
        brand_status = "idle"

    file_summary = build_source_file_summary(source_file)
    widget_state = build_upload_widget_state(extraction_status, source_file)

    return {
        "deck_id": deck.id,
        "deckId": deck.id,
        "workflowId": workflow.get("workflowId"),
        "workflowPhase": workflow.get("phase"),
        "workflowStatus": workflow.get("status"),
        "workflowJobId": active_job.get("jobId"),
        "workflowJobType": active_job.get("jobType"),
        "workflowJobStatus": active_job.get("status"),
        "upload_status": DeckState.UPLOADED.value if source_file is not None else DeckState.PENDING.value,
        "source_file_status": DeckState.UPLOADED.value if source_file is not None else "missing",
        "original_file_url": source_file.storage_path if source_file is not None else None,
        **file_summary,
        "deck_extraction_status": extraction_status,
        "status": deck_state,
        "state": deck_state,
        "deckStatus": deck_state,
        **widget_state,
        "brand_status": brand_status,
        "brand_profile_id": brand_profile.id if brand_profile is not None else None,
        "slide_count": int(source_state.get("slideCount") or len(deck.slides)),
        "summary": deck.summary or workflow.get("message"),
        "steps": _build_processing_steps(workflow),
        "latest_confirmation": map_save_confirmation(latest_confirmation) if latest_confirmation is not None else None,
    }


async def persist_deck_intake(
    db: Session,
    workspace: Workspace,
    deck: Deck,
    website_url: str | None,
    company_name: str | None,
    founder_name: str | None,
    notes: str | None,
    team_notes: str | None,
    linkedin_urls: list[str],
    supporting_urls: list[str],
    audience: str,
    purpose: str,
    brand_guide: UploadFile | None = None,
    logo_file: UploadFile | None = None,
) -> None:
    input_sources: list[DeckInputSource] = []
    brand_assets: list[DeckBrandAsset] = []

    if website_url:
        normalized_url = normalize_website_url(website_url)
        if normalized_url:
            website_source = DeckInputSource(
                id=generate_id("source"),
                deck_id=deck.id,
                source_type="company_website",
                label="Company website",
                external_url=normalized_url,
                text_value=normalized_url,
                status="ready",
            )
            db.add(website_source)
            input_sources.append(website_source)

    for linkedin_url in [item for item in linkedin_urls if item]:
        source = DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type="linkedin_profile",
            label="LinkedIn profile",
            external_url=linkedin_url,
            text_value=linkedin_url,
            status="ready",
        )
        db.add(source)
        input_sources.append(source)

    if team_notes and team_notes.strip():
        source = DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type="team_notes",
            label="Team notes",
            text_value=team_notes.strip(),
            status="ready",
        )
        db.add(source)
        input_sources.append(source)

    for supporting_url in [item for item in supporting_urls if item]:
        source = DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type="supporting_url",
            label="Supporting URL",
            external_url=supporting_url,
            text_value=supporting_url,
            status="ready",
        )
        db.add(source)
        input_sources.append(source)

    for upload, source_type, label, asset_type, upload_types, max_size, type_detail, too_large_detail in [
        (
            brand_guide,
            "brand_guide",
            "Brand guide",
            "brand_guide",
            BRAND_GUIDELINES_UPLOAD_TYPES,
            MAX_BRAND_GUIDELINES_UPLOAD_SIZE_BYTES,
            "Only PDF, DOC, DOCX, TXT, and Markdown brand guidelines uploads are supported",
            "Brand guidelines uploads must be 25MB or smaller",
        ),
        (
            logo_file,
            "logo_file",
            "Logo file",
            "logo",
            LOGO_UPLOAD_TYPES,
            MAX_LOGO_UPLOAD_SIZE_BYTES,
            "Only PNG, JPEG, GIF, and WebP logo uploads are supported",
            "Logo uploads must be 10MB or smaller",
        ),
    ]:
        if upload is None or not upload.filename:
            continue

        contents = await read_supported_brand_upload(
            upload,
            upload_types=upload_types,
            max_size=max_size,
            type_detail=type_detail,
            too_large_detail=too_large_detail,
        )
        if not contents:
            continue

        stored_name = _store_optional_upload(upload, source_type)
        stored = get_upload_storage().write_bytes(stored_name, contents)
        try:
            security_scan = scan_upload_path(stored.path)
            stored = promote_upload(stored)
        except Exception:
            get_upload_storage().delete(stored.storage_path)
            raise

        source = DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type=source_type,
            label=label,
            original_filename=upload.filename,
            mime_type=upload.content_type,
            storage_path=stored_name,
            status="ready",
        )
        db.add(source)
        db.flush()
        input_sources.append(source)

        asset = DeckBrandAsset(
            id=generate_id("asset"),
            deck_id=deck.id,
            source_input_id=source.id,
            asset_type=asset_type,
            source="upload",
            label=upload.filename,
            mime_type=upload.content_type,
            storage_path=stored_name,
            metadata_json=json.dumps({"securityScan": security_scan}),
        )
        db.add(asset)
        db.flush()
        asset.public_url = build_brand_asset_public_url(deck.id, asset.id)
        brand_assets.append(asset)

    db.flush()

    company_profile = upsert_company_profile(
        db=db,
        workspace=workspace,
        deck=deck,
        company_name=company_name,
        website_url=website_url,
        founder_name=founder_name,
        team_notes=team_notes,
        linkedin_urls=linkedin_urls,
        notes=notes,
    )

    upsert_brand_profile(
        db=db,
        deck=deck,
        company_profile=company_profile,
        input_sources=input_sources,
        brand_assets=brand_assets,
        audience=audience,
        purpose=purpose,
    )
