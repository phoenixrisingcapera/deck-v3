from __future__ import annotations

from app.schemas.brand_profile import DeckBrandProfilePayload
from app.services.brand.deterministic_swatches import with_deterministic_swatch_contract

# LEGACY API: Retained for existing enrichment/scripts and frontend-compatible
# dictionary shape. Canonical deterministic evidence is owned by
# deterministic_swatches.py; this adapter must not publish card-v1 evidence.
CARD_CONTRACT_VERSION = "brand-profile-card-v1"


def attach_card_swatches(profile_payload: dict) -> dict:
    # DISABLED: The former implementation emitted role/field metadata and
    # `brand-profile-card-v1`, overwriting canonical persisted extraction
    # evidence during enrichment. The callable remains, but delegates to the
    # one current role-first {label,value} contract.
    # payload = dict(profile_payload)
    # slots = [
    #     ("primary", "Primary", "primaryColor"),
    #     ("secondary", "Secondary", "secondaryColor"),
    #     ("accent", "Accent", "accentColor"),
    #     ("background", "Background", "backgroundColor"),
    #     ("text", "Text", "textColor"),
    # ]
    # values = []
    # seen = set()
    # for role, label, key in slots:
    #     value = payload.get(key)
    #     if isinstance(value, str) and value.strip():
    #         clean = value.strip()
    #         values.append({"role": role, "label": label, "value": clean, "field": key})
    #         seen.add(clean)
    # for value in payload.get("palette") or []:
    #     if len(values) >= 5:
    #         break
    #     if isinstance(value, str) and value.strip() and value.strip() not in seen:
    #         index = len(values) + 1
    #         clean = value.strip()
    #         values.append({"role": f"color_{index}", "label": f"Color {index}", "value": clean, "field": "palette"})
    #         seen.add(clean)
    # payload["deterministicMappingVersion"] = CARD_CONTRACT_VERSION
    # payload["deterministicSwatches"] = values
    # return payload
    payload = dict(profile_payload)
    canonical_input = dict(payload)
    # Legacy callers historically supplied palette fields only; synthetic IDs
    # satisfy the typed helper without leaking into the returned dictionary.
    canonical_input.setdefault("id", "legacy-brand-profile-card")
    canonical_input.setdefault("deckId", "legacy-brand-profile-card")
    canonical = with_deterministic_swatch_contract(DeckBrandProfilePayload(**canonical_input))
    payload["deterministicMappingVersion"] = canonical.deterministicMappingVersion
    payload["deterministicSwatches"] = [swatch.model_dump() for swatch in canonical.deterministicSwatches]
    return payload
