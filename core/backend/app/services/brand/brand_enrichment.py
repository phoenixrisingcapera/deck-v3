from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import Deck, DeckBrandAsset, DeckInputSource
from app.services.brand.brand_extraction import build_brand_asset_public_url, _field_evidence, _protected_field, _safe_request
from app.services.brand.brand_profile_card_contract import attach_card_swatches
from app.services.brand.brand_source_labels import build_brand_source_labels
from app.services.storage.upload_scan import scan_upload_path
from app.services.storage.artifact_storage import get_upload_storage, promote_upload

_FONT_FAMILY_PATTERN = re.compile(r"font-family\s*:\s*([^;}{]+)", flags=re.IGNORECASE)
_STYLESHEET_LINK_PATTERN = re.compile(r"<link[^>]+rel\s*=\s*['\"]?stylesheet['\"]?[^>]*>", flags=re.IGNORECASE)
_HREF_PATTERN = re.compile(r"href\s*=\s*(['\"])(.*?)\1", flags=re.IGNORECASE)
_FETCH_TIMEOUT_SECONDS = 4
_FETCH_TEXT_BYTES = 180_000
_FETCH_ASSET_BYTES = 512_000
_ALLOWED_REMOTE_ASSET_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}
_FALLBACK_FONTS = ["Manrope", "General Sans"]


def _safe_fetch(url: str, *, max_bytes: int, accept: str) -> tuple[bytes | None, str | None]:
    payload, content_type = _safe_request(
        url,
        timeout_seconds=_FETCH_TIMEOUT_SECONDS,
        max_bytes=max_bytes,
    )
    return payload, content_type.split(";", 1)[0].strip().lower() if content_type else None


def _read_json(value: dict | str | None) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _font_candidates_from_css(css_text: str) -> list[str]:
    fonts: dict[str, str] = {}
    for match in _FONT_FAMILY_PATTERN.finditer(css_text):
        raw_stack = match.group(1)
        for candidate in raw_stack.split(","):
            normalized = candidate.strip().strip("'\"")
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in {"serif", "sans-serif", "monospace", "system-ui", "inherit", "initial"}:
                continue
            key = normalized.casefold()
            current = fonts.get(key)
            if current is None or normalized < current:
                fonts[key] = normalized
            if len(fonts) >= 6:
                return list(fonts.values())
    return list(fonts.values())


def _stylesheet_urls(html_text: str, website_url: str) -> list[str]:
    urls: list[str] = []
    for link_tag in _STYLESHEET_LINK_PATTERN.finditer(html_text):
        href_match = _HREF_PATTERN.search(link_tag.group(0))
        if href_match is None:
            continue
        href = href_match.group(2).strip()
        if href:
            urls.append(urljoin(website_url, href))
        if len(urls) >= 8:
            break
    return urls


def _extract_typography_evidence(website_url: str | None) -> tuple[list[str], dict]:
    if not website_url:
        return [], {"typographySource": "no_website"}
    page_payload, _ = _safe_fetch(website_url, max_bytes=_FETCH_TEXT_BYTES, accept="text/html, text/css, */*;q=0.8")
    if not page_payload:
        return [], {"typographySource": "website_unreachable", "sourceUrl": website_url}
    html_text = page_payload.decode("utf-8", errors="ignore")
    fonts = _font_candidates_from_css(html_text)
    stylesheet_count = 0
    for stylesheet_url in _stylesheet_urls(html_text, website_url):
        css_payload, content_type = _safe_fetch(stylesheet_url, max_bytes=_FETCH_TEXT_BYTES, accept="text/css, text/plain, */*;q=0.8")
        if not css_payload:
            continue
        if content_type and not content_type.startswith(("text/css", "text/plain", "application/octet-stream")):
            continue
        stylesheet_count += 1
        for font in _font_candidates_from_css(css_payload.decode("utf-8", errors="ignore")):
            if font.casefold() not in {candidate.casefold() for candidate in fonts}:
                fonts.append(font)
            if len(fonts) >= 6:
                break
        if len(fonts) >= 6:
            break
    return fonts, {
        "typographySource": "website_css" if fonts else "website_no_fonts_found",
        "sourceUrl": website_url,
        "stylesheetCount": stylesheet_count,
        "fontCandidates": fonts,
    }


def _remote_asset_suffix(asset_url: str, content_type: str | None) -> str:
    if content_type in _ALLOWED_REMOTE_ASSET_TYPES:
        return _ALLOWED_REMOTE_ASSET_TYPES[content_type]
    suffix = Path(urlparse(asset_url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}:
        return suffix
    return ".bin"


def _persist_remote_logo_asset(db: Session, deck: Deck, asset_url: str) -> DeckBrandAsset | None:
    existing = next(
        (
            asset
            for asset in deck.brand_assets
            if asset.asset_type == "logo" and asset.source == "website" and asset.public_url
        ),
        None,
    )
    storage = get_upload_storage()
    if existing is not None and existing.storage_path:
        existing_path = storage.resolve_path(existing.storage_path)
        if existing_path is not None and existing_path.exists():
            return None
        existing_metadata = _read_json(existing.metadata_json)
        persisted_source_url = existing_metadata.get("sourceUrl")
        if isinstance(persisted_source_url, str) and persisted_source_url.strip():
            asset_url = persisted_source_url.strip()
    payload, content_type = _safe_fetch(asset_url, max_bytes=_FETCH_ASSET_BYTES, accept="image/*, */*;q=0.8")
    if not payload:
        return None
    if content_type not in _ALLOWED_REMOTE_ASSET_TYPES and not Path(urlparse(asset_url).path).suffix.lower() in {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"
    }:
        return None

    suffix = _remote_asset_suffix(asset_url, content_type)
    stored_name = storage.generated_name("brand_remote_logo", suffix)
    stored = storage.write_bytes(stored_name, payload)
    try:
        security_scan = scan_upload_path(stored.path)
        stored = promote_upload(stored)
    except Exception:
        storage.delete(stored.storage_path)
        raise

    if existing is not None:
        existing.label = Path(urlparse(asset_url).path).name or "website-logo"
        existing.mime_type = content_type or "application/octet-stream"
        existing.storage_path = stored.storage_path
        existing.metadata_json = json.dumps({"sourceUrl": asset_url, "securityScan": security_scan})
        source_input = getattr(existing, "source_input", None)
        if source_input is not None:
            source_input.external_url = asset_url
            source_input.mime_type = existing.mime_type
            source_input.storage_path = stored.storage_path
            source_input.status = "ready"
        db.flush()
        return existing

    source_input = DeckInputSource(
        id=generate_id("source"),
        deck_id=deck.id,
        source_type="website_logo_asset",
        label="Website-derived logo asset",
        external_url=asset_url,
        mime_type=content_type or "application/octet-stream",
        storage_path=stored.storage_path,
        status="ready",
    )
    db.add(source_input)
    db.flush()

    asset = DeckBrandAsset(
        id=generate_id("asset"),
        deck_id=deck.id,
        source_input_id=source_input.id,
        asset_type="logo",
        source="website",
        label=Path(urlparse(asset_url).path).name or "website-logo",
        mime_type=content_type or "application/octet-stream",
        storage_path=stored.storage_path,
        public_url=None,
        metadata_json=json.dumps({"sourceUrl": asset_url, "securityScan": security_scan}),
    )
    db.add(asset)
    db.flush()
    asset.public_url = build_brand_asset_public_url(deck.id, asset.id)
    db.flush()
    return asset


def enrich_brand_profile_after_extract(db: Session, deck_id: str) -> None:
    deck = (
        db.query(Deck)
        .options(selectinload(Deck.brand_profile), selectinload(Deck.brand_assets))
        .filter(Deck.id == deck_id)
        .first()
    )
    if deck is None or deck.brand_profile is None:
        return

    profile = deck.brand_profile
    evidence = _read_json(profile.raw_evidence_json)
    website_url = profile.company_website_url

    fonts, typography_evidence = _extract_typography_evidence(website_url)
    field_evidence = _field_evidence(evidence)
    font_evidence = field_evidence.get("fontCandidates") if isinstance(field_evidence.get("fontCandidates"), dict) else {}
    existing_source = str(font_evidence.get("source") or "")
    protected_fonts = _protected_field(field_evidence, "fontCandidates")
    confirmed_url = evidence.get("confirmedWebsiteUrl") == website_url and bool(website_url)
    # Enrichment fills gaps in the canonical extraction. It must not replace
    # typography already observed in the uploaded deck with website UI fonts.
    missing_observed_fonts = not profile.font_candidates_json or existing_source in {'', 'fallback_safe_fonts'}
    if fonts and confirmed_url and not protected_fonts and missing_observed_fonts:
        profile.font_candidates_json = fonts[:8]
        field_evidence["fontCandidates"] = {"source": "url_live_css", "confidence": 0.82, "status": "extracted"}
        evidence["fieldEvidence"] = field_evidence
        evidence["typographyEvidence"] = typography_evidence
    elif not profile.font_candidates_json and not protected_fonts:
        profile.font_candidates_json = _FALLBACK_FONTS
        field_evidence["fontCandidates"] = {"source": "fallback_safe_fonts", "confidence": 0.3, "status": "fallback"}
        evidence["fieldEvidence"] = field_evidence
    evidence["websiteTypographyEvidence"] = typography_evidence

    sampled_asset_url = None
    palette_evidence = evidence.get("paletteEvidence")
    if isinstance(palette_evidence, dict):
        value = palette_evidence.get("sampledAssetUrl")
        if isinstance(value, str):
            sampled_asset_url = value
    if sampled_asset_url and not _protected_field(field_evidence, "logoUrl"):
        remote_asset = _persist_remote_logo_asset(db, deck, sampled_asset_url)
        if remote_asset is not None:
            profile.logo_url = remote_asset.public_url
            field_evidence["logoUrl"] = {"source": "url_live_asset", "confidence": 0.82, "status": "extracted"}
            evidence["fieldEvidence"] = field_evidence
            evidence["websiteLogoAssetId"] = remote_asset.id
            evidence["websiteLogoSourceUrl"] = sampled_asset_url

    effective_logo_asset_id = evidence.get("logoAssetId") or evidence.get("websiteLogoAssetId")
    sampled_urls = palette_evidence.get("sampledUrls") if isinstance(palette_evidence, dict) else []
    evidence["sourceLabels"] = build_brand_source_labels(
        website_url=website_url,
        logo_asset_id=str(effective_logo_asset_id) if effective_logo_asset_id else None,
        deck_source_ready=bool(evidence.get("deckSourceReady")),
        brand_guidelines_asset_id=(
            str(evidence["brandGuideAssetId"])
            if evidence.get("brandGuideAssetId")
            else None
        ),
        palette_source=str(evidence.get("paletteSource") or ""),
        sampled_urls=sampled_urls if isinstance(sampled_urls, list) else [],
    )

    card_payload = attach_card_swatches(
        {
            "primaryColor": profile.primary_color,
            "secondaryColor": profile.secondary_color,
            "accentColor": profile.accent_color,
            "backgroundColor": profile.background_color,
            "textColor": profile.text_color,
            "palette": profile.palette_json or [],
        }
    )
    evidence["deterministicMappingVersion"] = card_payload["deterministicMappingVersion"]
    evidence["deterministicSwatches"] = card_payload["deterministicSwatches"]

    profile.raw_evidence_json = evidence
    db.commit()
