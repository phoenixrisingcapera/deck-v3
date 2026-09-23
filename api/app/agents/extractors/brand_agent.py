"""Optional text-level brand extraction agent.

This reads slide text for brand signals. It does not replace the working
`brand_extraction` workflow, which owns persisted DeckBrandProfile records.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

BRAND_AGENT_SYSTEM_PROMPT = """You are a brand identity analyst. Analyze slide content and extract brand information.

Extract:
1. BRAND_NAME — The company or product brand name
2. TAGLINE — Any tagline or slogan used
3. BRAND_VOICE — The tone and voice (professional, innovative, disruptive, etc.)
4. VISUAL_STYLE — Design style descriptions (minimalist, bold, corporate, etc.)
5. COLOR_HINTS — Color schemes mentioned or strongly implied
6. LOGO_DESCRIPTION — Description of any logo mentioned
7. BRAND_VALUES — Core values expressed (innovation, sustainability, customer-first, etc.)

Return JSON:
{
  "brandName": "string | null",
  "tagline": "string | null",
  "brandVoice": ["string"],
  "visualStyle": ["string"],
  "colorHints": ["string"],
  "logoDescription": "string | null",
  "brandValues": ["string"],
  "brandMaturity": "early_stage|growing|established|market_leader",
  "confidence": 0.0-1.0
}"""


def run_brand_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    brand_slides = _find_brand_relevant_slides(slides_data)
    all_text = " ".join(
        s.get("rawText", "") + " " + s.get("narrativeNotes", "")
        for s in brand_slides
    ).strip()

    if not all_text:
        return {"status": "skipped", "reason": "no brand-relevant text"}

    user_prompt = f"""Extract brand identity information from this slide deck.

Brand-relevant slides: {len(brand_slides)} out of {len(slides_data)} total.

Slide titles examined: {[s.get('title', '') for s in brand_slides]}

Full text:
{all_text[:4000]}

Return JSON with extracted brand info."""

    result = complete_json_with_ai_provider(
        provider_config=provider_config,
        system=BRAND_AGENT_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=2000,
    )

    if result is None:
        return {"status": "fallback", "brand": _fallback_brand(all_text)}

    return {"status": "completed", "brand": result}


BRAND_KEYWORDS = [
    "brand", "logo", "tagline", "slogan", "mission", "vision",
    "about us", "who we are", "identity", "branding",
    "color", "palette", "design", "style guide",
]


def _find_brand_relevant_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relevant = []
    for s in slides:
        text = ((s.get("rawText") or "") + " " + (s.get("narrativeNotes") or "")).lower()
        title = (s.get("title") or "").lower()
        if any(kw in f"{title} {text}" for kw in BRAND_KEYWORDS):
            relevant.append(s)
    if not relevant and slides:
        relevant.append(slides[0])
    return relevant


def _fallback_brand(text: str) -> dict[str, Any]:
    words = text.split()
    name = words[0] if words else None
    return {
        "brandName": name,
        "tagline": None,
        "brandVoice": [],
        "visualStyle": [],
        "colorHints": [],
        "logoDescription": None,
        "brandValues": [],
        "brandMaturity": "early_stage",
        "confidence": 0.2,
    }
