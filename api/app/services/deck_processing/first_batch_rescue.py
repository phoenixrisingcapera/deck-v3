from __future__ import annotations

import logging
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, Workspace
from app.services.deck_processing.deck_intake_service import persist_deck_intake
from app.services.deck_processing.save_confirmation import map_save_confirmation, record_save_confirmation
from app.services.brand.website_context import normalize_website_url
from app.services.deck_processing.workspace_summary_service import resolve_workspace_for_user

logger = logging.getLogger(__name__)


def _first_batch_metadata(batch_id: str, source_type: str, *, reused: bool = False) -> dict:
    return {
        "firstBatch": {
            "id": batch_id,
            "sourceType": source_type,
            "status": "ready",
            "mode": "minimal_recovery",
            "hasSourceFile": False,
            "reused": reused,
        }
    }


def _find_existing_brand_first_deck(
    db: Session,
    *,
    workspace_id: str,
    user_id: str,
    source_type: str,
    website_url: str | None,
) -> Deck | None:
    query = (
        db.query(Deck)
        .filter(
            Deck.workspace_id == workspace_id,
            Deck.user_id == user_id,
            Deck.source_type == source_type,
        )
        .order_by(Deck.created_at.desc())
    )
    normalized_url = normalize_website_url(website_url)

    for deck in query.limit(25).all():
        metadata = deck.metadata_json or {}
        first_batch = metadata.get("firstBatch") if isinstance(metadata, dict) else None
        if not isinstance(first_batch, dict):
            continue
        if first_batch.get("hasSourceFile") is True:
            continue
        if source_type == "url_branding":
            deck_url = normalize_website_url(
                (deck.brand_profile.company_website_url if deck.brand_profile else None)
                or metadata.get("websiteUrl")
                or metadata.get("website_url")
            )
            if normalized_url and deck_url == normalized_url:
                return deck
        else:
            return deck
    return None


async def create_source_true_first_batch_minimal(
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
    """Create or reuse a URL/logo-first deck without depending on secondary summary payloads.

    This path is source-context-first, not file-upload-first. It must therefore be
    idempotent for repeated URL/logo attempts in the same workspace; otherwise the
    UI accumulates duplicate pseudo-decks every time the user retries brand loading.
    """
    if source_type not in {"url_branding", "logo_branding"}:
        raise ValueError("First batch source must be url_branding or logo_branding")
    if source_type == "url_branding" and not (website_url and website_url.strip()):
        raise ValueError("A company URL is required for URL branding")
    if source_type == "logo_branding" and (logo_file is None or not logo_file.filename):
        raise ValueError("A logo file is required for logo branding")

    workspace = (
        resolve_workspace_for_user(db, user_id)
        if workspace_id is None
        else db.query(Workspace).filter(Workspace.id == workspace_id, Workspace.user_id == user_id).first()
    )
    if workspace is None:
        raise ValueError("Workspace not found")

    clean_company_name = company_name.strip() if company_name and company_name.strip() else None
    normalized_url = normalize_website_url(website_url)
    deck = _find_existing_brand_first_deck(
        db,
        workspace_id=workspace.id,
        user_id=user_id,
        source_type=source_type,
        website_url=normalized_url,
    )
    reused = deck is not None
    batch_id = generate_id("batch")

    if deck is None:
        deck = Deck(
            id=generate_id("deck"),
            workspace_id=workspace.id,
            user_id=user_id,
            title=f"{clean_company_name} brand deck" if clean_company_name else "Brand-first Smart Deck",
            audience=audience or "Investment Committee",
            purpose=purpose or "Initial diligence review",
            status="uploaded",
            source_type=source_type,
            summary=(
                "Brand-first deck context created from company URL."
                if source_type == "url_branding"
                else "Brand-first deck context created from uploaded logo."
            ),
            metadata_json={
                **_first_batch_metadata(batch_id, source_type),
                "websiteUrl": normalized_url,
            },
        )
        db.add(deck)
        db.flush()
    else:
        metadata = dict(deck.metadata_json or {})
        metadata.update(_first_batch_metadata(batch_id, source_type, reused=True))
        if normalized_url:
            metadata["websiteUrl"] = normalized_url
        deck.metadata_json = metadata
        deck.title = f"{clean_company_name} brand deck" if clean_company_name else deck.title
        deck.audience = audience or deck.audience or "Investment Committee"
        deck.purpose = purpose or deck.purpose or "Initial diligence review"
        db.flush()

    await persist_deck_intake(
        db=db,
        workspace=workspace,
        deck=deck,
        website_url=normalized_url,
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

    confirmation_payload = None
    try:
        confirmation = record_save_confirmation(
            db,
            deck_id=deck.id,
            workspace_id=workspace.id,
            user_id=user_id,
            event_type="deck_properties_saved",
            entity_type="first_batch",
            entity_id=batch_id,
            title="Brand context saved",
            message=(
                "URL brand context is ready for colour extraction and Smart Deck review."
                if source_type == "url_branding"
                else "Logo brand context is ready for colour extraction and Smart Deck review."
            ),
            source_surface="welcome_first_batch",
            source_route="/decks/new",
            dedupe_key=f"first_batch:{deck.id}:{source_type}:{normalized_url or 'logo'}",
            metadata={"sourceType": source_type, "mode": "minimal_recovery", "reused": reused},
        )
        confirmation_payload = map_save_confirmation(confirmation)
    except Exception as exc:
        logger.warning(
            "First-batch confirmation could not be recorded",
            extra={"deck_id": deck.id, "error_type": exc.__class__.__name__},
        )

    db.commit()
    db.refresh(deck)

    return {
        "ok": True,
        "workspace_id": workspace.id,
        "workspaceId": workspace.id,
        "deck_id": deck.id,
        "deckId": deck.id,
        "batch_id": batch_id,
        "batchId": batch_id,
        "source_type": source_type,
        "sourceType": source_type,
        "generation_status": "ready",
        "generationStatus": "ready",
        "next_url": f"/decks/{deck.id}/smart-deck",
        "nextUrl": f"/decks/{deck.id}/smart-deck",
        "has_source_file": False,
        "hasSourceFile": False,
        "reused": reused,
        "confirmation": confirmation_payload,
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
        },
    }
