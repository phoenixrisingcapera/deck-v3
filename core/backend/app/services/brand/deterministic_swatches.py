from __future__ import annotations

from app.schemas.brand_profile import BrandPaletteSwatchPayload, DeckBrandProfilePayload

DETERMINISTIC_MAPPING_VERSION = "deck-brand-deterministic-v1"


def deterministic_swatch_evidence(profile: DeckBrandProfilePayload) -> dict[str, object]:
    swatches = build_deterministic_swatches(profile)
    return {
        "deterministicSwatches": [swatch.model_dump() for swatch in swatches],
        "deterministicMappingVersion": DETERMINISTIC_MAPPING_VERSION,
    }


def build_deterministic_swatches(profile: DeckBrandProfilePayload) -> list[BrandPaletteSwatchPayload]:
    swatches: list[BrandPaletteSwatchPayload] = []
    seen: set[str] = set()
    role_candidates = [
        ("Primary", profile.primaryColor),
        ("Secondary", profile.secondaryColor),
        ("Accent", profile.accentColor),
        ("Background", profile.backgroundColor),
        ("Text", profile.textColor),
    ]

    for label, value in role_candidates:
        if value is None:
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        swatches.append(BrandPaletteSwatchPayload(label=label, value=normalized))
        seen.add(normalized)

    for index, value in enumerate(profile.palette or []):
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        swatches.append(BrandPaletteSwatchPayload(label=f"Palette {index + 1}", value=normalized))
        seen.add(normalized)

    return swatches[:5]


def with_deterministic_swatch_contract(profile: DeckBrandProfilePayload) -> DeckBrandProfilePayload:
    swatch_evidence = deterministic_swatch_evidence(profile)
    swatches = [BrandPaletteSwatchPayload(**value) for value in swatch_evidence["deterministicSwatches"]]
    raw_evidence = dict(profile.rawEvidence or {})
    # REPLACED: setdefault preserved stale evidence after PATCH/extraction changed
    # the canonical palette. The returned and persisted evidence must describe
    # the same current role-first swatches on every contract path.
    # raw_evidence.setdefault("deterministicSwatches", swatch_payload)
    # raw_evidence.setdefault("deterministicMappingVersion", DETERMINISTIC_MAPPING_VERSION)
    raw_evidence.update(swatch_evidence)

    profile.deterministicSwatches = swatches
    profile.deterministicMappingVersion = DETERMINISTIC_MAPPING_VERSION
    profile.rawEvidence = raw_evidence
    return profile
