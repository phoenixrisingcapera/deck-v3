from __future__ import annotations

from typing import Any


VALID_SOURCE_LABEL_STATUSES = {"pending", "available", "fallback", "missing"}


def _label(key: str, label: str, status: str = "pending", detail: str | None = None) -> dict[str, str | None]:
    return {
        "key": key,
        "label": label,
        "status": status if status in VALID_SOURCE_LABEL_STATUSES else "pending",
        "detail": detail,
    }


def build_brand_source_labels(
    *,
    website_url: str | None = None,
    logo_asset_id: str | None = None,
    deck_source_ready: bool = False,
    brand_guidelines_asset_id: str | None = None,
    palette_source: str | None = None,
    sampled_urls: list[str] | None = None,
) -> list[dict[str, str | None]]:
    source = (palette_source or "").lower()
    is_fallback = any(marker in source for marker in ("fallback", "seed", "unreachable", "no_colors", "pending"))
    sampled_count = len(sampled_urls or [])
    labels = [
        _label(
            "website",
            "Website",
            "fallback" if website_url and is_fallback else "available" if website_url else "pending",
            f"Sampled {sampled_count} URL assets" if sampled_count else palette_source if website_url else "No website signal",
        ),
        _label("logo", "Logo", "available" if logo_asset_id else "pending", "Logo signal available" if logo_asset_id else "No logo signal"),
        _label("deck", "Deck", "available" if deck_source_ready else "pending", "Deck context available" if deck_source_ready else "No deck context"),
    ]
    if brand_guidelines_asset_id:
        labels.append(_label("brand_guidelines", "Guidelines", "available", "Brand guidelines attached"))
    if is_fallback:
        labels.append(_label("fallback", "Fallback", "fallback", palette_source))
    return labels


def normalize_brand_source_labels(raw_evidence: dict[str, Any] | None) -> list[dict[str, str | None]]:
    evidence = raw_evidence or {}
    raw_labels = evidence.get("sourceLabels") or evidence.get("source_labels") or []
    normalized: list[dict[str, str | None]] = []

    if isinstance(raw_labels, list):
        for index, item in enumerate(raw_labels):
            if isinstance(item, str) and item.strip():
                key = item.strip().lower().replace(" ", "_")[:48]
                normalized.append(_label(key or f"source_{index + 1}", item.strip(), "available"))
                continue
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            label = str(item.get("label") or key or "").strip()
            if not key or not label:
                continue
            status = str(item.get("status") or "pending").strip()
            detail = item.get("detail")
            normalized.append(_label(key, label, status, str(detail) if detail is not None else None))

    effective_logo_asset_id = (
        evidence.get("logoAssetId")
        or evidence.get("logo_asset_id")
        or evidence.get("websiteLogoAssetId")
        or evidence.get("website_logo_asset_id")
    )
    if normalized:
        if effective_logo_asset_id:
            normalized = [
                _label("logo", "Logo", "available", "Logo signal available")
                if item.get("key") == "logo"
                else item
                for item in normalized
            ]
        return normalized

    palette_evidence = evidence.get("paletteEvidence") if isinstance(evidence.get("paletteEvidence"), dict) else {}
    sampled_urls = palette_evidence.get("sampledUrls") if isinstance(palette_evidence, dict) else []
    return build_brand_source_labels(
        website_url=evidence.get("websiteUrl") or evidence.get("website_url"),
        logo_asset_id=effective_logo_asset_id,
        deck_source_ready=bool(evidence.get("deckSourceReady") or evidence.get("deck_source_ready")),
        brand_guidelines_asset_id=evidence.get("brandGuideAssetId") or evidence.get("brand_guidelines_asset_id"),
        palette_source=str(evidence.get("paletteSource") or evidence.get("palette_source") or ""),
        sampled_urls=sampled_urls if isinstance(sampled_urls, list) else [],
    )
