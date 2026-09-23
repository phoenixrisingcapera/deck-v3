from __future__ import annotations

from app.ai.slide_archetypes_context import SLIDE_ARCHETYPES

SMART_DECK_SUBJECT_REGISTRY = [
    {
        "id": item["slug"].replace("-", "_"),
        "slug": item["slug"],
        "label": item["slug"].replace("-", " ").title(),
        "description": item["description"],
        "slugVariants": item["aliases"],
        "deckTypes": ["startup_pitch", "vc_fund_pitch"] if "VC-Pitch-Narratives" in item["tags"] and "Startup-Pitch-Narratives" in item["tags"] else ["startup_pitch"]
        if "Startup-Pitch-Narratives" in item["tags"]
        else ["vc_fund_pitch"],
        "oftenBeforeSlides": [slug.replace("-", "_") for slug in item["before"]],
        "oftenAfterSlides": [slug.replace("-", "_") for slug in item["after"]],
        "requiredChecks": [],
        "investorLogic": item["description"],
    }
    for item in SLIDE_ARCHETYPES
]

SMART_DECK_SUBJECT_BY_ID = {item["id"]: item for item in SMART_DECK_SUBJECT_REGISTRY}
