from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import CompanyProfile, Deck, Workspace
from app.services.brand.website_context import build_website_context


def ensure_company_profile(db: Session, deck: Deck) -> CompanyProfile:
    profiles = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.workspace_id == deck.workspace_id)
        .order_by(CompanyProfile.updated_at.desc(), CompanyProfile.created_at.desc())
        .all()
    )
    for profile in profiles:
        try:
            source_notes = json.loads(profile.source_notes_json or "{}")
        except (TypeError, ValueError):
            source_notes = {}
        if isinstance(source_notes, dict) and source_notes.get("deck_id") == deck.id:
            return profile
    for profile in profiles:
        if profile.canonical_name.strip().casefold() == (deck.title or "").strip().casefold():
            return profile

    profile = CompanyProfile(
        id=generate_id("company"),
        workspace_id=deck.workspace_id,
        canonical_name=deck.title or "Deck company",
        website_url=None,
        contact_email=None,
        inferred_stage=None,
        founder_name=None,
        team_summary=None,
        linkedin_urls_json=None,
        source_notes_json=json.dumps({"deck_id": deck.id, "source": "uploaded_deck"}),
    )
    db.add(profile)
    db.flush()
    return profile


def infer_stage_from_deck(deck: Deck) -> str | None:
    source = f"{deck.title} {deck.purpose}".lower()

    if "series b" in source:
        return "Series B"
    if "series a" in source:
        return "Series A"
    if "seed" in source:
        return "Seed"
    if "growth" in source:
        return "Growth"
    if "board" in source:
        return "Board"

    return None


def resolve_company_name(deck: Deck, provided_company_name: str | None, website_url: str | None) -> str:
    if provided_company_name and provided_company_name.strip():
        return provided_company_name.strip()

    website_context = build_website_context(website_url)
    if website_context is not None:
        return website_context["company_hint"]

    return deck.title


def upsert_company_profile(
    db: Session,
    workspace: Workspace,
    deck: Deck,
    company_name: str | None,
    website_url: str | None,
    founder_name: str | None,
    team_notes: str | None,
    linkedin_urls: list[str],
    notes: str | None,
) -> CompanyProfile:
    canonical_name = resolve_company_name(deck, company_name, website_url)
    website_context = build_website_context(website_url)

    profile = (
        db.query(CompanyProfile)
        .filter(
            CompanyProfile.workspace_id == workspace.id,
            CompanyProfile.canonical_name == canonical_name,
        )
        .first()
    )

    if profile is None and website_context is not None:
        profile = (
            db.query(CompanyProfile)
            .filter(
                CompanyProfile.workspace_id == workspace.id,
                CompanyProfile.website_url == website_context["normalized_url"],
            )
            .first()
        )

    if profile is None:
        profile = CompanyProfile(
            id=generate_id("company"),
            workspace_id=workspace.id,
            canonical_name=canonical_name,
        )
        db.add(profile)

    profile.canonical_name = canonical_name
    profile.website_url = website_context["normalized_url"] if website_context is not None else website_url
    profile.contact_email = website_context["contact_email_hint"] if website_context is not None else None
    profile.inferred_stage = infer_stage_from_deck(deck)
    profile.founder_name = founder_name.strip() if founder_name and founder_name.strip() else None
    profile.team_summary = team_notes.strip() if team_notes and team_notes.strip() else None
    profile.linkedin_urls_json = json.dumps(linkedin_urls)
    profile.source_notes_json = json.dumps(
        {
          "notes": notes.strip() if notes and notes.strip() else None,
          "deck_id": deck.id,
        }
    )

    db.flush()
    return profile
