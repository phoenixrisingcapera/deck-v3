from __future__ import annotations


CANONICAL_REGISTRY = {
    "schemaVersion": "canonical-registry.v1",
    "buildPhaseRules": [
        "Do not delete code only because it looks old.",
        "Delete code only with a concrete integration rationale and an active replacement.",
        "Absorb overlapping features into one canonical path rather than leaving parallel canonicals.",
        "User and admin surfaces should read the same backend source-of-truth objects.",
    ],
    "areas": [
        {
            "area": "processing",
            "canonical": "workflow-state",
            "compatibilityLayers": ["/processing", "/status", "upload/readiness projections"],
        },
        {
            "area": "deck_understanding",
            "canonical": "canonical_deck_intelligence",
            "compatibilityLayers": ["legacy parallel artifact reads"],
        },
        {
            "area": "due_diligence",
            "canonical": "audience_conversion",
            "compatibilityLayers": ["due-diligence product proxy", "report-shaped compatibility adapter"],
        },
        {
            "area": "smart_edit",
            "canonical": "slide-scoped classify/patch/run workflow",
            "compatibilityLayers": ["/decks/{deck_id}/smart-edit suggestion routes"],
        },
        {
            "area": "smart_deck",
            "canonical": "generation workflow + canonical_deck_intelligence",
            "compatibilityLayers": ["older assistant/redesign compatibility surfaces"],
        },
        {
            "area": "market_research",
            "canonical": "smart_deck_market_research",
            "compatibilityLayers": [],
        },
    ],
}


def get_canonical_registry() -> dict:
    return CANONICAL_REGISTRY
