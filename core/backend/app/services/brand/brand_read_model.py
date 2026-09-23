from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.db.models import Deck, DeckBrandAsset
from app.schemas.brand_profile import BrandExtractionStatusResponse, BrandExtractionStagePayload
from app.services.brand.brand_extraction import (
    build_brand_asset_public_url,
    get_deck_brand_profile,
    _normalize_local_asset_url,
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _json_loads(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _asset_payload(deck_id: str, asset: DeckBrandAsset) -> dict:
    metadata = _json_loads(asset.metadata_json)
    return {
        "id": asset.id,
        "type": asset.asset_type,
        "source": asset.source,
        "label": asset.label,
        "mimeType": asset.mime_type,
        "url": _normalize_local_asset_url(asset.public_url or build_brand_asset_public_url(deck_id, asset.id)),
        "storagePath": asset.storage_path,
        "metadata": metadata,
        "createdAt": _iso(asset.created_at),
        "updatedAt": _iso(asset.updated_at),
    }


def _stage(key: str, label: str, status: str, progress: int) -> BrandExtractionStagePayload:
    return BrandExtractionStagePayload(
        key=key,
        label=label,
        status=status,
        progressPercent=progress,
    )


def get_deck_brand_status(db: Session, deck_id: str) -> BrandExtractionStatusResponse | None:
    deck = (
        db.query(Deck)
        .options(
            selectinload(Deck.brand_profile),
            selectinload(Deck.brand_assets),
            selectinload(Deck.input_sources),
        )
        .filter(Deck.id == deck_id)
        .first()
    )
    if deck is None:
        return None

    profile_payload = get_deck_brand_profile(db, deck_id)
    profile = deck.brand_profile
    assets = [_asset_payload(deck.id, asset) for asset in deck.brand_assets]
    website_sources = [source for source in deck.input_sources if source.source_type == "company_website"]
    logo_assets = [asset for asset in deck.brand_assets if asset.asset_type == "logo"]
    guide_assets = [asset for asset in deck.brand_assets if asset.asset_type == "brand_guide"]
    warnings = profile.warnings_json if profile and profile.warnings_json else []
    evidence = profile_payload.rawEvidence if profile_payload is not None else {}

    if profile is None:
        return BrandExtractionStatusResponse(
            deckId=deck.id,
            status="not_started",
            progressPercent=0,
            stages=[
                _stage("source_intake", "Source intake", "pending", 0),
                _stage("website_scrape", "Website scrape", "pending", 0),
                _stage("asset_persistence", "Asset persistence", "pending", 0),
                _stage("palette_typography", "Palette and typography", "pending", 0),
                _stage("preview_contract", "Preview contract", "pending", 0),
            ],
            assets=assets,
            warnings=[],
            evidence={},
            brandProfile=None,
        )

    has_website = bool(profile.company_website_url or website_sources)
    has_logo = bool(profile.logo_url or logo_assets)
    has_palette = bool(profile.palette_json)
    has_fonts = bool(profile.font_candidates_json)
    has_evidence = bool(profile.raw_evidence_json)
    status = profile.processing_status or "ready"
    raw_evidence = profile.raw_evidence_json if isinstance(profile.raw_evidence_json, dict) else {}
    # Confirmed website verification is independent from which source owns the
    # final composed palette (for example, a local logo may own primary).
    website_palette_evidence = raw_evidence.get("websitePaletteEvidence")
    if not isinstance(website_palette_evidence, dict):
        website_palette_evidence = raw_evidence.get("paletteEvidence")
    website_palette_evidence = website_palette_evidence if isinstance(website_palette_evidence, dict) else {}
    website_verified = bool(
        has_website
        and status == "ready"
        and str(website_palette_evidence.get("paletteSource") or "") in {"url_live_asset", "url_live_colors"}
        and website_palette_evidence.get("evidenceSha256")
    )

    stages = [
        _stage("source_intake", "Source intake", "completed" if has_website or has_logo else "warning", 20),
        _stage("website_scrape", "Website scrape", "completed" if website_verified else "warning" if has_website else "skipped", 40),
        _stage("asset_persistence", "Asset persistence", "completed" if logo_assets or guide_assets else "skipped", 60),
        _stage("palette_typography", "Palette and typography", "completed" if has_palette and has_fonts else "warning", 80),
        _stage("preview_contract", "Preview contract", "completed" if has_evidence else "warning", 100 if status == "ready" else 80),
    ]

    progress = 100 if status == "ready" else max(stage.progressPercent for stage in stages if stage.status in {"completed", "warning"})

    return BrandExtractionStatusResponse(
        deckId=deck.id,
        status="completed" if status == "ready" else status,
        progressPercent=progress,
        brandProfileId=profile.id,
        sourceMode=profile.source_mode,
        stages=stages,
        assets=assets,
        warnings=warnings,
        evidence=evidence,
        brandProfile=profile_payload,
    )
