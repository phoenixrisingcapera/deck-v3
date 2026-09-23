from __future__ import annotations

import logging
import re
import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session, load_only

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import (
    Deck,
    DeckBrandProfile,
    DeckExport,
    DeckFile,
    DeckInputSource,
    DeckSaveConfirmation,
    DeckSlide,
    DeckWorkspacePreference,
    DeckGenerationWorkspace,
    DeckSlideVersion,
    User,
    Workspace,
)
from app.schemas.workspace_summary import WelcomeStateResponse, WorkspaceSummaryResponse
from app.services.deck_processing.workflow_state_read_model import get_deck_workflow_state
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state, transition_deck_state
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.platform.shell.workspace_ai_provider_service import get_workspace_ai_provider_summary
from app.services.deck_processing.deck_intake_service import build_source_file_summary, build_upload_widget_state, persist_deck_intake
from app.services.deck_processing.save_confirmation import map_save_confirmation, record_save_confirmation
from app.services.storage.upload_scan import scan_upload_path
from app.services.storage.upload_security import (
    LimitedUpload,
    MAX_DECK_UPLOAD_SIZE_BYTES,
    SUPPORTED_DECK_UPLOADS,
    detect_supported_deck_extension,
)
from app.services.storage.artifact_storage import get_upload_storage, promote_upload

logger = logging.getLogger(__name__)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
WORKFLOW_FAILED_STATUSES = {"failed_retryable", "failed_final", "blocked", "timed_out"}
WORKFLOW_READY_PHASES = {"source_ready", "smart_deck_ready", "preview_ready", "applied", "export_ready"}
AUTO_SOFT_DELETE_INTAKE_STATES = {DeckState.UPLOADED.value, DeckState.PROCESSING.value, DeckState.FAILED.value}

FIRST_TIME_TEMPLATES = [
    {
        "id": "template_vc_diligence",
        "title": "VC diligence rewrite",
        "audience_label": "Investment Committee",
        "description": "Restructure an uploaded founder deck into a cleaner diligence narrative with proof gaps called out.",
        "tags": ["VC", "Diligence", "Investment committee"],
        "cta_label": "Browse template",
    },
    {
        "id": "template_lp_update",
        "title": "LP or board update",
        "audience_label": "LP / Board",
        "description": "Turn source material into an update format that keeps the signal high and the narrative compact.",
        "tags": ["Board", "LP", "Status update"],
        "cta_label": "View sample",
    },
    {
        "id": "template_advisory_version",
        "title": "Advisory review version",
        "audience_label": "Advisor",
        "description": "Frame the same deck for operating partners, advisers, or strategic reviewers before export.",
        "tags": ["Advisory", "Strategy", "Review"],
        "cta_label": "Open preview",
    },
]

# The backend is the source of truth for uploaded deck artifacts.
# These are the file types the product currently accepts as intake material.
def _is_soft_deleted(deck: Deck) -> bool:
    metadata = deck.metadata_json or {}
    return bool(metadata.get("soft_deleted_at"))


def _silent_delete_after_seconds() -> int:
    raw_value = os.getenv("DECK_OLD_INTAKE_DECK_SOFT_DELETE_AFTER_SECONDS", "43200")
    try:
        seconds = int(raw_value)
    except ValueError:
        return 43200
    return max(seconds, 0)


def _deck_soft_delete_reason(deck: Deck) -> str:
    state = canonical_deck_state(deck.status).value
    return f"auto_silent_cleanup_{state}"


def _should_soft_delete_old_intake_deck(deck: Deck) -> bool:
    if _is_soft_deleted(deck):
        return False
    if canonical_deck_state(deck.status).value not in AUTO_SOFT_DELETE_INTAKE_STATES:
        return False

    anchor = deck.updated_at or deck.created_at
    if anchor is None:
        return False

    cutoff = datetime.utcnow() - timedelta(seconds=_silent_delete_after_seconds())
    return anchor <= cutoff


def _soft_delete_old_intake_decks(db: Session, workspace: Workspace | None) -> list[str]:
    if workspace is None:
        return []

    decks = (
        db.query(Deck)
        .filter(Deck.workspace_id == workspace.id)
        .order_by(Deck.updated_at.desc())
        .all()
    )

    soft_deleted_deck_ids: list[str] = []
    soft_deleted_at = datetime.utcnow().isoformat()
    for deck in decks:
        if not _should_soft_delete_old_intake_deck(deck):
            continue
        metadata = dict(deck.metadata_json or {})
        metadata.update(
            {
                "soft_deleted_at": soft_deleted_at,
                "soft_deleted_reason": _deck_soft_delete_reason(deck),
                "soft_deleted_source_surface": "workspace_summary_auto_cleanup",
            }
        )
        deck.metadata_json = metadata
        soft_deleted_deck_ids.append(deck.id)

    if soft_deleted_deck_ids:
        db.commit()

    return soft_deleted_deck_ids


def soft_delete_old_intake_decks(db: Session, workspace: Workspace | None) -> list[str]:
    """Public wrapper for the workspace auto-cleanup helper.

    Keep the implementation in one place, but expose a non-private symbol so
    callers do not depend on an underscored import during worker startup.
    """
    return _soft_delete_old_intake_decks(db, workspace)


def _resolve_deck_for_workspace(db: Session, deck_id: str, workspace_id: str | None = None) -> Deck | None:
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if deck is None:
        return None

    if workspace_id and deck.workspace_id != workspace_id:
        return None

    return deck


def _detect_supported_extension(file_name: str, content_type: str) -> str | None:
    return detect_supported_deck_extension(file_name, content_type)


def _safe_storage_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "deck.bin"
    cleaned = SAFE_FILENAME_RE.sub("-", name).strip(".-")
    return cleaned[:180] or "deck.bin"


def _normalize_deck_title(file_name: str) -> str:
    lowered_name = file_name.lower()

    for extension in SUPPORTED_DECK_UPLOADS:
        if lowered_name.endswith(extension):
            return file_name[: -len(extension)].replace("_", " ").replace("-", " ").strip() or "Uploaded deck"

    return file_name.replace("_", " ").replace("-", " ").strip() or "Uploaded deck"


def find_existing_upload_by_checksum(
    db: Session,
    *,
    user_id: str,
    workspace_id: str,
    checksum_sha256: str | None,
) -> tuple[Deck, DeckFile] | None:
    checksum = str(checksum_sha256 or "").strip()
    if not checksum:
        return None

    matches = (
        db.query(Deck, DeckFile)
        .join(DeckFile, DeckFile.deck_id == Deck.id)
        .filter(
            Deck.user_id == user_id,
            Deck.workspace_id == workspace_id,
            DeckFile.checksum_sha256 == checksum,
        )
        .order_by(DeckFile.uploaded_at.desc())
        .all()
    )
    for deck, deck_file in matches:
        if _is_soft_deleted(deck):
            continue
        return deck, deck_file
    return None


def build_existing_upload_response(
    db: Session,
    *,
    workspace: Workspace,
    deck: Deck,
    deck_file: DeckFile,
    preferred_workspace: str = "smart_deck",
) -> dict:
    workflow = get_deck_workflow_state(db, deck.id) or {}
    deck_state = _workflow_backed_deck_state(db, deck)
    file_summary = build_source_file_summary(deck_file)
    widget_state = build_upload_widget_state(deck_state, deck_file)
    can_open_smart_deck = bool(workflow.get("canOpenSmartDeck")) or deck_state == DeckState.READY.value
    next_action = str(workflow.get("nextAction") or "").strip()
    if not next_action:
        if can_open_smart_deck:
            next_action = "open_smart_deck"
        elif deck_state == DeckState.UPLOADED.value:
            next_action = "create_smart_deck"
        else:
            next_action = "view_processing"
    next_step_message = {
        "create_smart_deck": "This source deck was already uploaded. Press Create your Smart Deck to continue.",
        "open_smart_deck": "This deck is already ready. Open Smart Deck to continue.",
        "view_processing": "This deck is already in progress. Open processing to continue.",
    }.get(next_action, "This source deck was already uploaded. Continue from the current deck state.")
    preferred_workspace_value = "instant_deck" if preferred_workspace == "instant_deck" else "smart_deck"
    preferred_workspace_url = (
        f"/decks/{deck.id}/instant-deck"
        if preferred_workspace_value == "instant_deck"
        else f"/decks/{deck.id}/smart-deck"
    )

    return {
        "ok": True,
        "deck_id": deck.id,
        "duplicate_of_deck_id": deck.id,
        "idempotent_replay": True,
        "filename": deck_file.original_filename or deck.title or "Uploaded deck",
        "upload_success": True,
        "upload_status": DeckState.UPLOADED.value,
        "source_file_status": DeckState.UPLOADED.value,
        **file_summary,
        "deck_extraction_status": deck_state,
        "status": deck_state,
        "state": deck_state,
        "deckStatus": deck_state,
        "processing": workflow or None,
        **widget_state,
        "upload_message": "Already uploaded",
        "next_step_message": next_step_message,
        "next_action": next_action,
        "create_smart_deck_url": f"/api/products/deck-aistack-codes/decks/{deck.id}/workflows/source-extraction",
        "processing_status_url": f"/api/products/deck-aistack-codes/decks/{deck.id}/workflow-state",
        "smart_deck_url": f"/decks/{deck.id}/smart-deck",
        "preferred_workspace": preferred_workspace_value,
        "preferred_workspace_url": preferred_workspace_url,
        "workspace": get_workspace_summary(db, workspace.id),
    }


def _first_slide(deck: Deck) -> DeckSlide | None:
    return next(iter(sorted(deck.slides, key=lambda slide: slide.slide_index)), None)


def _slide_preview_url(slide: DeckSlide | None) -> str | None:
    if slide is None:
        return None
    if not (slide.rendered_image_path or slide.thumbnail_path):
        return None
    return f"/api/decks/{slide.deck_id}/slides/{slide.id}/preview"


def _deck_state(deck: Deck) -> str:
    return canonical_deck_state(deck.status).value


def _workflow_backed_deck_state(db: Session, deck: Deck) -> str:
    persisted_state = _deck_state(deck)
    if persisted_state == DeckState.READY.value:
        return DeckState.READY.value

    workflow = get_deck_workflow_state(db, deck.id)
    if workflow is None:
        return persisted_state

    workflow_status = str(workflow.get("status") or "")
    workflow_phase = str(workflow.get("phase") or "")

    if workflow.get("canOpenSmartDeck") or workflow_phase in WORKFLOW_READY_PHASES:
        return DeckState.READY.value
    if workflow_status in {"completed", "ready"} and persisted_state == DeckState.READY.value:
        return DeckState.READY.value
    if workflow_status in WORKFLOW_FAILED_STATUSES:
        return DeckState.FAILED.value
    if workflow_phase in {"upload_accepted", "source_file_saved"}:
        return DeckState.UPLOADED.value
    if workflow.get("activeJob") or workflow.get("latestJobs"):
        return DeckState.PROCESSING.value
    return persisted_state


def _deck_summary(db: Session, deck: Deck) -> dict:
    file_name = deck.file.original_filename if deck.file is not None and deck.file.original_filename else deck.original_filename
    file_name = file_name or deck.title
    detected_extension = _detect_supported_extension(file_name, deck.file.mime_type if deck.file is not None else "") or ""
    first_slide = _first_slide(deck)
    preview_url = _slide_preview_url(first_slide)
    # Workspace lists and welcome-entry surfaces must stay fast and resilient.
    # Do not block them on deeper workflow-state reconstruction for every deck.
    deck_state = _deck_state(deck)

    return {
        "id": deck.id,
        "workspace_id": deck.workspace_id,
        "display_name": deck.title,
        "title": deck.title,
        "original_filename": file_name,
        "filename": deck.file.filename if deck.file is not None else None,
        "file_type": detected_extension.replace(".", "") or "other",
        "mime_type": deck.file.mime_type if deck.file is not None else None,
        "file_size_bytes": deck.file.size if deck.file is not None else None,
        "slide_count": deck.slide_count or len(deck.slides),
        "thumbnail_url": preview_url,
        "preview_url": preview_url,
        "first_slide_id": first_slide.id if first_slide is not None else None,
        "uploaded_at": deck.file.uploaded_at if deck.file is not None else None,
        "audience": deck.audience,
        "purpose": deck.purpose,
        "status": deck_state,
        "state": deck_state,
        "deckStatus": deck_state,
        "summary": deck.summary,
        "created_at": deck.created_at,
        "updated_at": deck.updated_at,
    }


def _map_brand_card(profile: DeckBrandProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "primary": profile.primary_color,
        "secondary": profile.secondary_color,
        "accent": profile.accent_color,
        "background": profile.background_color,
        "text": profile.text_color,
        "palette": profile.palette_json or [],
    }


def list_workspace_decks(db: Session, workspace_id: str | None = None) -> list[dict]:
    workspace = resolve_workspace(db, workspace_id)
    if workspace is None:
        return []
    _soft_delete_old_intake_decks(db, workspace)

    decks = (
        db.query(Deck)
        .filter(Deck.workspace_id == workspace.id)
        .order_by(Deck.updated_at.desc())
        .all()
    )

    return [_deck_summary(db, deck) for deck in decks if not _is_soft_deleted(deck)]


def resolve_workspace(db: Session, workspace_id: str | None = None) -> Workspace | None:
    if workspace_id:
        workspace = (
            db.query(Workspace)
            .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
            .filter(Workspace.id == workspace_id)
            .first()
        )
        if workspace is not None:
            return workspace

    return (
        db.query(Workspace)
        .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
        .order_by(Workspace.created_at.asc())
        .first()
    )


def resolve_workspace_for_user(db: Session, user_id: str) -> Workspace | None:
    return (
        db.query(Workspace)
        .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
        .filter(Workspace.user_id == user_id)
        .order_by(Workspace.created_at.asc())
        .first()
    )


def get_workspace_summary(db: Session, workspace_id: str | None = None) -> WorkspaceSummaryResponse:
    workspace = resolve_workspace(db, workspace_id)
    if workspace is None:
        return WorkspaceSummaryResponse(
            workspace={"id": workspace_id or "ws_default", "name": "Deck AI Stack Workspace"},
            deck_count=0,
            active_deck_id=None,
            latest_decks=[],
            processing_deck_count=0,
            ready_deck_count=0,
            export_count=0,
            first_time_templates=FIRST_TIME_TEMPLATES,
        )
    _soft_delete_old_intake_decks(db, workspace)

    decks = (
        db.query(Deck)
        .filter(Deck.workspace_id == workspace.id)
        .order_by(Deck.updated_at.desc())
        .all()
    )

    export_count = (
        db.query(DeckExport)
        .join(Deck, Deck.id == DeckExport.deck_id)
        .filter(Deck.workspace_id == workspace.id)
        .count()
    )

    visible_decks = [deck for deck in decks if not _is_soft_deleted(deck)]
    latest_decks = [_deck_summary(db, deck) for deck in visible_decks[:3]]
    deck_states = {deck.id: _deck_state(deck) for deck in visible_decks}

    return WorkspaceSummaryResponse(
        workspace={"id": workspace.id, "name": workspace.name},
        deck_count=len(visible_decks),
        active_deck_id=visible_decks[0].id if visible_decks else None,
        latest_decks=latest_decks,
        processing_deck_count=sum(1 for deck in visible_decks if deck_states.get(deck.id) == DeckState.PROCESSING.value),
        ready_deck_count=sum(1 for deck in visible_decks if deck_states.get(deck.id) == DeckState.READY.value),
        export_count=export_count,
        first_time_templates=FIRST_TIME_TEMPLATES,
    )


def get_workspace_summary_for_user(db: Session, user: User, workspace_id: str | None = None) -> WorkspaceSummaryResponse:
    workspace = resolve_workspace_for_user(db, user.id) if workspace_id is None else (
        db.query(Workspace)
        .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
        .filter(
            Workspace.id == workspace_id,
            Workspace.user_id == user.id,
        )
        .first()
    )
    if user.role == "super_admin" and workspace_id is not None:
        workspace = (
            db.query(Workspace)
            .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
            .filter(Workspace.id == workspace_id)
            .first()
        )
    if workspace is None:
        return WorkspaceSummaryResponse(
            workspace={"id": workspace_id or "ws_default", "name": "Deck AI Stack Workspace"},
            deck_count=0,
            active_deck_id=None,
            latest_decks=[],
            processing_deck_count=0,
            ready_deck_count=0,
            export_count=0,
            first_time_templates=FIRST_TIME_TEMPLATES,
        )
    return get_workspace_summary(db, workspace.id)


def list_workspace_decks_for_user(db: Session, user: User, workspace_id: str | None = None) -> list[dict]:
    workspace = resolve_workspace_for_user(db, user.id) if workspace_id is None else (
        db.query(Workspace)
        .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
        .filter(
            Workspace.id == workspace_id,
            Workspace.user_id == user.id,
        )
        .first()
    )
    if user.role == "super_admin" and workspace_id is not None:
        workspace = (
            db.query(Workspace)
            .options(load_only(Workspace.id, Workspace.name, Workspace.user_id, Workspace.created_at, Workspace.updated_at))
            .filter(Workspace.id == workspace_id)
            .first()
        )
    if workspace is None:
        return []
    return [
        deck
        for deck in list_workspace_decks(db, workspace.id)
        if deck.get("status") != DeckState.FAILED.value
    ]


def get_welcome_state(db: Session, user: User) -> WelcomeStateResponse:
    workspace = resolve_workspace_for_user(db, user.id)
    if workspace is None:
        workspace = Workspace(id="ws_default", name=f"{user.name.split()[0]}'s Workspace", user_id=user.id)
    _soft_delete_old_intake_decks(db, workspace)

    decks = (
        db.query(Deck)
        .filter(Deck.workspace_id == workspace.id)
        .order_by(Deck.updated_at.desc())
        .all()
    )

    visible_decks = [deck for deck in decks if not _is_soft_deleted(deck)]
    has_deck = len(visible_decks) > 0
    active_deck = visible_decks[0] if visible_decks else None
    active_deck_state = _deck_state(active_deck) if active_deck is not None else None
    deck_ownership_status = "none" if len(visible_decks) == 0 else "single" if len(visible_decks) == 1 else "many"
    entry_view = "dashboard" if has_deck else "welcome"
    latest_accepted_slide_id = None
    latest_accepted_slide_version_id = None
    latest_accepted_slide_title = None
    last_viewed_slide_id = None
    last_viewed_batch_id = None
    last_viewed_slide_version_id = None
    last_visited_deck_id = None
    resume_card = None

    latest_preference = (
        db.query(DeckWorkspacePreference)
        .join(Deck, Deck.id == DeckWorkspacePreference.deck_id)
        .filter(Deck.workspace_id == workspace.id, DeckWorkspacePreference.user_id == user.id)
        .order_by(DeckWorkspacePreference.updated_at.desc(), DeckWorkspacePreference.created_at.desc())
        .first()
    )

    if latest_preference is not None:
        last_visited_deck_id = latest_preference.deck_id
        last_viewed_slide_id = latest_preference.selected_slide_id
        last_viewed_batch_id = latest_preference.last_batch_id
        last_viewed_slide_version_id = latest_preference.last_slide_version_id

    resume_deck = None
    if last_visited_deck_id is not None:
        resume_deck = next((deck for deck in visible_decks if deck.id == last_visited_deck_id), None)
    if resume_deck is None:
        resume_deck = active_deck

    if resume_deck is not None:
        preference = latest_preference if latest_preference is not None and latest_preference.deck_id == resume_deck.id else (
            db.query(DeckWorkspacePreference)
            .filter(
                DeckWorkspacePreference.deck_id == resume_deck.id,
                DeckWorkspacePreference.user_id == user.id,
            )
            .order_by(DeckWorkspacePreference.updated_at.desc())
            .first()
        )
        if preference is not None:
            last_viewed_slide_id = preference.selected_slide_id
            last_viewed_batch_id = preference.last_batch_id
            last_viewed_slide_version_id = preference.last_slide_version_id

        latest_applied_version = (
            db.query(DeckSlideVersion)
            .join(DeckGenerationWorkspace, DeckGenerationWorkspace.id == DeckSlideVersion.deck_generation_workspace_id)
            .filter(
                DeckGenerationWorkspace.deck_id == resume_deck.id,
                DeckSlideVersion.status.in_(("applied", "accepted")),
            )
            .order_by(DeckSlideVersion.updated_at.desc(), DeckSlideVersion.created_at.desc())
            .first()
        )

        if latest_applied_version is not None:
            latest_accepted_slide_version_id = latest_applied_version.id
            latest_accepted_slide_id = latest_applied_version.source_slide_id
            latest_accepted_slide_title = latest_applied_version.title
        elif last_viewed_slide_id is not None:
            selected_slide = (
                db.query(DeckSlide)
                .filter(DeckSlide.id == last_viewed_slide_id, DeckSlide.deck_id == resume_deck.id)
                .first()
            )
            if selected_slide is not None:
                latest_accepted_slide_id = selected_slide.id
                latest_accepted_slide_title = selected_slide.title

        resume_deck_state = _deck_state(resume_deck)
        resume_card = {
            "deckId": resume_deck.id,
            "title": resume_deck.title,
            "status": resume_deck_state,
            "state": resume_deck_state,
            "deckStatus": resume_deck_state,
            "slideId": latest_accepted_slide_id or last_viewed_slide_id,
            "slideTitle": latest_accepted_slide_title,
            "batchId": last_viewed_batch_id,
            "slideVersionId": latest_accepted_slide_version_id or last_viewed_slide_version_id,
            "brand": _map_brand_card(resume_deck.brand_profile),
        }

    deck_miniatures = []
    for deck in decks[:12]:
        deck_state = _deck_state(deck)
        deck_miniatures.append(
            {
                "deckId": deck.id,
                "title": deck.title,
                "status": deck_state,
                "state": deck_state,
                "deckStatus": deck_state,
                "updatedAt": deck.updated_at.isoformat() if deck.updated_at is not None else None,
                "brand": _map_brand_card(deck.brand_profile),
            }
        )

    try:
        provider_summary = get_workspace_ai_provider_summary(db, user.id)
    except ValueError:
        provider_summary = None
    provider_card = {
        "provider": provider_summary.provider if provider_summary is not None else None,
        "providerLabel": (
            "OpenAI"
            if provider_summary is not None and provider_summary.provider == "openai"
            else "OpenRouter"
            if provider_summary is not None and provider_summary.provider == "openrouter"
            else "Claude"
            if provider_summary is not None and provider_summary.provider == "claude"
            else None
        ),
        "providerLogo": provider_summary.provider if provider_summary is not None else None,
        "preferredModel": provider_summary.preferred_model if provider_summary is not None else None,
        "isConfigured": provider_summary.is_configured if provider_summary is not None else False,
    }

    return WelcomeStateResponse(
        workspace={"id": workspace.id, "name": workspace.name},
        hasDeck=has_deck,
        deckOwnershipStatus=deck_ownership_status,
        deckCount=len(visible_decks),
        activeDeckId=active_deck.id if active_deck is not None else None,
        latestDeckTitle=active_deck.title if active_deck is not None else None,
        latestDeckStatus=active_deck_state,
        latestDeckState=active_deck_state,
        lastVisitedDeckId=last_visited_deck_id,
        latestAcceptedSlideId=latest_accepted_slide_id,
        latestAcceptedSlideVersionId=latest_accepted_slide_version_id,
        latestAcceptedSlideTitle=latest_accepted_slide_title,
        lastViewedSlideId=last_viewed_slide_id,
        lastViewedBatchId=last_viewed_batch_id,
        lastViewedSlideVersionId=last_viewed_slide_version_id,
        resumeCard=resume_card,
        deckMiniatures=deck_miniatures,
        providerCard=provider_card,
        entryView=entry_view,
        entryRoute=f"/{entry_view}",
    )


def create_deck_upload_session() -> dict:
    return {
        "ok": True,
        "accepted_file_types": ["pdf", "ppt", "pptx"],
        "max_file_size_bytes": MAX_DECK_UPLOAD_SIZE_BYTES,
    }


def complete_deck_upload(db: Session, deck_id: str, workspace_id: str | None = None) -> dict:
    workspace = resolve_workspace(db, workspace_id)
    deck = _resolve_deck_for_workspace(db, deck_id, workspace.id if workspace is not None else workspace_id)
    if deck is None or _is_soft_deleted(deck):
        raise ValueError("Deck not found")

    latest_confirmation = (
        db.query(DeckSaveConfirmation)
        .filter(DeckSaveConfirmation.deck_id == deck.id)
        .order_by(DeckSaveConfirmation.created_at.desc())
        .first()
    )
    deck_state = _deck_state(deck)
    return {
        "ok": True,
        "deck_id": deck.id,
        "status": deck_state,
        "state": deck_state,
        "deckStatus": deck_state,
        "confirmation": map_save_confirmation(latest_confirmation) if latest_confirmation is not None else None,
    }

def soft_delete_workspace_deck(
    db: Session,
    deck_id: str,
    workspace_id: str | None = None,
    *,
    reason: str | None = None,
    source_surface: str | None = None,
) -> dict:
    workspace = resolve_workspace(db, workspace_id)
    deck = _resolve_deck_for_workspace(db, deck_id, workspace.id if workspace is not None else workspace_id)
    if deck is None:
        raise ValueError("Deck not found")

    metadata = dict(deck.metadata_json or {})
    if _is_soft_deleted(deck):
        return {
            "ok": True,
            "deck_id": deck.id,
            "soft_deleted": True,
            "noop": True,
            "reason": metadata.get("soft_deleted_reason"),
            "sourceSurface": metadata.get("soft_deleted_source_surface"),
        }

    metadata["soft_deleted_at"] = datetime.utcnow().isoformat()
    metadata["soft_deleted_reason"] = (reason or "user_requested").strip() or "user_requested"
    metadata["soft_deleted_source_surface"] = (source_surface or "products_soft_delete").strip() or "products_soft_delete"
    deck.metadata_json = metadata
    db.commit()
    return {
        "ok": True,
        "deck_id": deck.id,
        "soft_deleted": True,
        "noop": False,
        "reason": metadata["soft_deleted_reason"],
        "sourceSurface": metadata["soft_deleted_source_surface"],
    }


async def create_first_deck_upload(
    db: Session,
    user_id: str,
    file_name: str,
    content_type: str,
    deck_upload: LimitedUpload,
    workspace_id: str | None = None,
    company_name: str | None = None,
    website_url: str | None = None,
    audience: str | None = None,
    purpose: str | None = None,
    founder_name: str | None = None,
    notes: str | None = None,
    team_notes: str | None = None,
    linkedin_urls: list[str] | None = None,
    supporting_urls: list[str] | None = None,
    brand_guide: UploadFile | None = None,
    logo_file: UploadFile | None = None,
) -> dict:
    workspace = resolve_workspace_for_user(db, user_id) if workspace_id is None else db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.user_id == user_id,
    ).first()
    if workspace is None:
        deck_upload.path.unlink(missing_ok=True)
        raise ValueError("Workspace not found")

    detected_extension = _detect_supported_extension(file_name, content_type)
    if detected_extension is None:
        deck_upload.path.unlink(missing_ok=True)
        raise ValueError("Only PDF, PPT, and PPTX uploads are supported")
    if deck_upload.size > MAX_DECK_UPLOAD_SIZE_BYTES:
        deck_upload.path.unlink(missing_ok=True)
        raise ValueError("Deck uploads must be 200MB or smaller")

    existing_upload = find_existing_upload_by_checksum(
        db,
        user_id=user_id,
        workspace_id=workspace.id,
        checksum_sha256=deck_upload.checksum_sha256,
    )
    if existing_upload is not None:
        deck_upload.path.unlink(missing_ok=True)
        deck, deck_file = existing_upload
        return build_existing_upload_response(db, workspace=workspace, deck=deck, deck_file=deck_file)

    deck_id = generate_id("deck")
    upload_id = generate_id("upload")
    stored_filename = f"users/{user_id}/decks/{deck_id}/source/{upload_id}/{_safe_storage_filename(file_name)}"
    storage = get_upload_storage()
    stored = storage.move_file(deck_upload.path, stored_filename)
    try:
        security_scan = scan_upload_path(stored.path)
        stored = promote_upload(stored)
    except Exception:
        storage.delete(stored.storage_path)
        raise

    uploaded_summary = f"Saved original source deck {file_name}. Extraction can continue in the background."
    deck = Deck(
        id=deck_id,
        workspace_id=workspace.id,
        user_id=user_id,
        title=f"{company_name.strip()} deck" if company_name and company_name.strip() else _normalize_deck_title(file_name),
        audience=audience or "Investment Committee",
        purpose=purpose or "Initial diligence review",
        status=DeckState.UPLOADED.value,
        summary=uploaded_summary,
    )
    db.add(deck)
    db.flush()
    transition_deck_state(
        db,
        deck,
        DeckState.UPLOADED,
        actor_user_id=user_id,
        reason="first_deck_upload_saved",
        summary=uploaded_summary,
        source_surface="upload_widget",
        source_route="/decks/new",
        metadata={"filename": file_name, "storedFilename": stored_filename},
    )

    deck_file = DeckFile(
        id=generate_id("file"),
        deck_id=deck.id,
        filename=stored_filename,
        original_filename=file_name,
        file_extension=detected_extension.removeprefix("."),
        mime_type=content_type,
        size=deck_upload.size,
        storage_provider=stored.provider,
        storage_path=stored.storage_path,
        checksum_sha256=deck_upload.checksum_sha256,
        metadata_json={"securityScan": security_scan},
    )
    db.add(deck_file)
    db.add(
        DeckInputSource(
            id=generate_id("source"),
            deck_id=deck.id,
            source_type="uploaded_deck",
            label="Uploaded deck",
            original_filename=file_name,
            mime_type=content_type,
            storage_path=stored_filename,
            status="ready",
        )
    )

    await persist_deck_intake(
        db=db,
        workspace=workspace,
        deck=deck,
        website_url=website_url,
        company_name=company_name,
        founder_name=founder_name,
        notes=notes,
        team_notes=team_notes,
        linkedin_urls=linkedin_urls or [],
        supporting_urls=supporting_urls or [],
        audience=deck.audience,
        purpose=deck.purpose,
        brand_guide=brand_guide,
        logo_file=logo_file,
    )
    confirmation = record_save_confirmation(
        db,
        deck_id=deck.id,
        workspace_id=workspace.id,
        user_id=user_id,
        event_type="deck_upload_saved",
        entity_type="deck",
        entity_id=deck.id,
        title="Deck saved successfully",
        message="Your deck is secure and ready for the next step.",
        source_surface="upload_widget",
        source_route="/decks/new",
        dedupe_key=f"deck_upload_saved:{deck.id}:{stored_filename}",
        metadata={"filename": file_name, "storedFilename": stored_filename},
    )
    db.commit()
    db.refresh(deck_file)
    extraction = {"status": DeckState.PROCESSING.value, "slideCount": 0}
    queue_failure_ticket_id: str | None = None
    queue_failure_message: str | None = None
    try:
        from app.services.deck_processing.workflow_orchestration import queue_source_extraction

        processing = queue_source_extraction(db, deck.id, requested_by_user_id=user_id)
        extraction = processing if isinstance(processing, dict) else extraction
    except Exception:
        queue_failure_message = "Source processing could not be queued. Please retry."
        logger.warning(
            "first_deck_upload_source_queue_failed",
            extra={"deck_id": deck.id, "failure_category": "deck_upload_source_queue"},
        )
        try:
            ticket = create_failure_ticket(
                db,
                {
                    "apiPath": "/api/products/deck-aistack-codes/decks/upload",
                    "statusCode": 503,
                    "errorName": "SourceWorkflowQueueFailure",
                    "errorMessage": queue_failure_message,
                    "errorStack": None,
                    "severity": "high",
                    "source": "backend",
                    "deckId": deck.id,
                    "context": {
                        "deckId": deck.id,
                        "workspaceId": workspace.id,
                        "failureStage": "first_deck_upload_queue_failed",
                        "stage": "first_deck_upload_queue_failed",
                        "nextAction": "manual_review",
                        "retryable": True,
                    },
                },
                commit=True,
            )
            queue_failure_ticket_id = ticket.id
        except Exception:
            db.rollback()
        extraction = {
            "status": DeckState.FAILED.value,
            "slideCount": 0,
            "message": queue_failure_message,
            "errorMessage": queue_failure_message,
            "failureTicketId": queue_failure_ticket_id,
            "nextAction": "manual_review",
            "canRetry": True,
        }
    file_summary = build_source_file_summary(deck_file)
    extraction_state = canonical_deck_state(str(extraction.get("status") or DeckState.PROCESSING.value)).value
    widget_state = build_upload_widget_state(extraction_state, deck_file)

    return {
        "ok": True,
        "deck_id": deck.id,
        "filename": file_name,
        "upload_success": True,
        "upload_status": DeckState.UPLOADED.value,
        "source_file_status": DeckState.UPLOADED.value,
        "original_file_url": None,
        **file_summary,
        "deck_extraction_status": extraction_state,
        "status": extraction_state,
        "state": extraction_state,
        "deckStatus": extraction_state,
        "processing": extraction,
        "queueError": queue_failure_message,
        "queueFailureTicketId": queue_failure_ticket_id,
        **widget_state,
        "confirmation": map_save_confirmation(confirmation),
        "workspace": get_workspace_summary(db, workspace.id),
    }


async def create_source_true_first_batch(
    db: Session,
    user_id: str,
    source_type: str,
    workspace_id: str | None = None,
    company_name: str | None = None,
    website_url: str | None = None,
    audience: str | None = None,
    purpose: str | None = None,
    founder_name: str | None = None,
    notes: str | None = None,
    team_notes: str | None = None,
    linkedin_urls: list[str] | None = None,
    supporting_urls: list[str] | None = None,
    brand_guide: UploadFile | None = None,
    logo_file: UploadFile | None = None,
) -> dict:
    if source_type not in {"url_branding", "logo_branding"}:
        raise ValueError("First batch source must be url_branding or logo_branding")
    if source_type == "url_branding" and not (website_url and website_url.strip()):
        raise ValueError("A company URL is required for URL branding")
    if source_type == "logo_branding" and (logo_file is None or not logo_file.filename):
        raise ValueError("A logo file is required for logo branding")

    workspace = resolve_workspace_for_user(db, user_id) if workspace_id is None else db.query(Workspace).filter(
        Workspace.id == workspace_id,
        Workspace.user_id == user_id,
    ).first()
    if workspace is None:
        raise ValueError("Workspace not found")

    clean_company_name = company_name.strip() if company_name and company_name.strip() else None
    batch_id = generate_id("batch")
    deck = Deck(
        id=generate_id("deck"),
        workspace_id=workspace.id,
        user_id=user_id,
        title=f"{clean_company_name} brand deck" if clean_company_name else "Brand-first Smart Deck",
        audience=audience or "Investment Committee",
        purpose=purpose or "Initial diligence review",
        status=DeckState.UPLOADED.value,
        source_type=source_type,
        summary=(
            "Brand-first deck context created from company URL."
            if source_type == "url_branding"
            else "Brand-first deck context created from uploaded logo."
        ),
        metadata_json={
            "firstBatch": {
                "id": batch_id,
                "sourceType": source_type,
                "status": "ready",
            }
        },
    )
    db.add(deck)
    db.flush()

    await persist_deck_intake(
        db=db,
        workspace=workspace,
        deck=deck,
        website_url=website_url,
        company_name=clean_company_name,
        founder_name=founder_name,
        notes=notes,
        team_notes=team_notes,
        linkedin_urls=linkedin_urls or [],
        supporting_urls=supporting_urls or [],
        audience=deck.audience,
        purpose=deck.purpose,
        brand_guide=brand_guide,
        logo_file=logo_file,
    )

    confirmation = record_save_confirmation(
        db,
        deck_id=deck.id,
        workspace_id=workspace.id,
        user_id=user_id,
        event_type="deck_properties_saved",
        entity_type="first_batch",
        entity_id=batch_id,
        title="First batch saved",
        message=(
            "URL branding is ready for Smart Deck review."
            if source_type == "url_branding"
            else "Logo branding is ready for Smart Deck review."
        ),
        source_surface="welcome_first_batch",
        source_route="/welcome",
        dedupe_key=f"first_batch:{deck.id}:{batch_id}",
        metadata={"sourceType": source_type},
    )
    db.commit()
    db.refresh(deck)

    return {
        "ok": True,
        "workspace_id": workspace.id,
        "workspaceId": workspace.id,
        "deck_id": deck.id,
        "deckId": deck.id,
        "status": DeckState.UPLOADED.value,
        "state": DeckState.UPLOADED.value,
        "deckStatus": DeckState.UPLOADED.value,
        "batch_id": batch_id,
        "batchId": batch_id,
        "source_type": source_type,
        "sourceType": source_type,
        "generation_status": "ready",
        "generationStatus": "ready",
        "next_url": f"/decks/{deck.id}/smart-deck",
        "nextUrl": f"/decks/{deck.id}/smart-deck",
        "confirmation": map_save_confirmation(confirmation),
        "workspace": get_workspace_summary(db, workspace.id),
    }
