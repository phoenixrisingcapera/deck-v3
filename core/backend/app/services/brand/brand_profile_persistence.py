from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import CompanyProfile, Deck, DeckBrandAsset, DeckBrandProfile, DeckInputSource
from app.schemas.brand_profile import normalize_branding_json_payload
from app.services.brand.website_context import build_website_context
from app.services.brand.brand_extraction import _evidence, _field_evidence, _protected_field


def _serialize_brand_assets(assets: list[DeckBrandAsset]) -> str | None:
    if not assets:
        return None

    labels = [asset.label for asset in assets if asset.label]
    if not labels:
        return None

    return ", ".join(labels)


def _stable_hex(seed: str, salt: str) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).hexdigest()
    return f"#{digest[:6].upper()}"


def _mix_hex(base: str, target: str, ratio: float) -> str:
    def channel(value: str) -> tuple[int, int, int]:
        raw = value.removeprefix("#")[:6].ljust(6, "0")
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)

    base_rgb = channel(base)
    target_rgb = channel(target)
    return "#{:02X}{:02X}{:02X}".format(
        int(base_rgb[0] + (target_rgb[0] - base_rgb[0]) * ratio),
        int(base_rgb[1] + (target_rgb[1] - base_rgb[1]) * ratio),
        int(base_rgb[2] + (target_rgb[2] - base_rgb[2]) * ratio),
    )


def _fallback_palette(seed_text: str) -> dict[str, str | list[str]]:
    primary = _stable_hex(seed_text, "primary")
    secondary = _mix_hex(primary, "#0F172A", 0.72)
    accent = _mix_hex(primary, "#8B5CF6", 0.42)
    background = "#081225"
    text = "#E6EEF8"
    surface = "#111C32"
    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "background": background,
        "surface": surface,
        "text": text,
        "mutedText": "#8FA1C2",
        "palette": [primary, secondary, accent, surface, text],
    }


def _infer_palette_source(input_sources: list[DeckInputSource], brand_assets: list[DeckBrandAsset]) -> str:
    if any(asset.asset_type == "logo" for asset in brand_assets):
        return "logo_pending_extraction"
    if any(source.source_type == "company_website" for source in input_sources):
        return "url_pending_extraction"
    return "deck_context_seed"


def _branding_json(profile: DeckBrandProfile, palette: dict[str, str | list[str]], palette_source: str) -> dict:
    palette_values = palette.get("palette") if isinstance(palette.get("palette"), list) else []
    return {
        "brandProfileId": profile.id,
        "company": {
            "name": profile.company_name,
            "websiteUrl": profile.company_website_url,
        },
        "logo": {
            "assetId": None,
            "url": profile.logo_url,
            "mimeType": None,
            "fileName": None,
        },
        "colors": {
            "primary": palette.get("primary"),
            "secondary": palette.get("secondary"),
            "accent": palette.get("accent"),
            "background": palette.get("background"),
            "surface": palette.get("surface"),
            "text": palette.get("text"),
            "mutedText": palette.get("mutedText"),
            "palette": palette_values,
        },
        "usageRules": {
            "preferredBackground": "dark",
            "useLogoColorsFirst": True,
            "avoidLowContrast": True,
            "keepInvestorGrade": True,
            "preserveSourceDeckStructure": True,
        },
        "designHints": {
            "mood": ["calm", "investor-grade"],
            "visualStyle": profile.visual_style,
            "deckUseCase": profile.primary_goal,
        },
        "llmInstructions": [
            "Use these swatches as fallback art direction until full brand extraction completes."
        ],
        "provenance": {
            "paletteSource": palette_source,
            "fallback": True,
            "reason": "Intake-created default swatches before full brand extraction.",
        },
    }


def upsert_brand_profile(
    db: Session,
    deck: Deck,
    company_profile: CompanyProfile,
    input_sources: list[DeckInputSource],
    brand_assets: list[DeckBrandAsset],
    audience: str,
    purpose: str,
) -> DeckBrandProfile:
    profile = deck.brand_profile
    if profile is None:
        profile = DeckBrandProfile(
            id=generate_id("brand"),
            deck_id=deck.id,
        )
        deck.brand_profile = profile
        db.add(profile)

    website_context = build_website_context(company_profile.website_url)
    source_labels = [source.label for source in input_sources if source.label]
    brand_asset_summary = _serialize_brand_assets(brand_assets)

    raw_evidence = dict(profile.raw_evidence_json or {})
    field_evidence = _field_evidence(raw_evidence)
    def assign(field: str, attribute: str, value: object) -> None:
        if value is not None and not _protected_field(field_evidence, field):
            setattr(profile, attribute, value)
            field_evidence[field] = _evidence("context_seed", 0.48)

    assign("companyName", "company_name", company_profile.canonical_name)
    assign("companyWebsiteUrl", "company_website_url", company_profile.website_url)
    profile.founder_name = company_profile.founder_name
    profile.team_summary = company_profile.team_summary
    brand_summary = (
        website_context["brand_summary"]
        if website_context is not None
        else "Brand profile derived from uploaded source material and ready for review."
    )
    if brand_asset_summary:
        brand_summary = f"{brand_summary} Source assets: {brand_asset_summary}."
    assign("brandSummary", "brand_summary", brand_summary)

    source_copy = ", ".join(source_labels) if source_labels else "uploaded deck"
    visual_direction = (
        f"Use a calm investor-grade layout guided by {source_copy}"
        + (f" and website context from {website_context['host']}" if website_context is not None else "")
        + "."
    )
    assign("visualDirection", "visual_direction", visual_direction)
    assign("audienceLabel", "audience_label", audience)
    assign("primaryGoal", "primary_goal", purpose)
    raw_evidence["fieldEvidence"] = field_evidence
    profile.raw_evidence_json = raw_evidence

    if not (profile.logo_url or profile.primary_color or (profile.palette_json and len(profile.palette_json) > 0)):
        seed_text = company_profile.website_url or company_profile.canonical_name or deck.title or deck.id
        palette = _fallback_palette(seed_text)
        palette_source = _infer_palette_source(input_sources, brand_assets)
        profile.primary_color = str(palette["primary"])
        profile.secondary_color = str(palette["secondary"])
        profile.accent_color = str(palette["accent"])
        profile.background_color = str(palette["background"])
        profile.text_color = str(palette["text"])
        profile.palette_json = list(palette["palette"]) if isinstance(palette["palette"], list) else []
        profile.font_candidates_json = ["Manrope", "General Sans"]
        profile.confidence_score = 0.48
        profile.source_mode = "context_seed"
        profile.processing_status = "ready"
        profile.warnings_json = [
            "Default swatches were created from intake context. Run brand extraction to replace them with live URL, logo, or deck-derived colours."
        ]
        profile.raw_evidence_json = {
            **(profile.raw_evidence_json or {}),
            "paletteSource": palette_source,
            "fallbackReason": "intake_default_before_extraction",
            "sourceLabels": source_labels,
            "brandAssetLabels": [asset.label for asset in brand_assets if asset.label],
        }
        profile.branding_json = _branding_json(profile, palette, palette_source)
    elif not profile.processing_status:
        profile.processing_status = "ready"

    if normalize_branding_json_payload(profile.branding_json) is None:
        palette = {
            "primary": profile.primary_color or "#3B82F6",
            "secondary": profile.secondary_color,
            "accent": profile.accent_color,
            "background": profile.background_color,
            "surface": "#111C32",
            "text": profile.text_color,
            "mutedText": "#8FA1C2",
            "palette": list(profile.palette_json or []),
        }
        palette_source = str((profile.raw_evidence_json or {}).get("paletteSource") or "deck_context_seed")
        profile.branding_json = _branding_json(profile, palette, palette_source)

    db.flush()
    return profile
