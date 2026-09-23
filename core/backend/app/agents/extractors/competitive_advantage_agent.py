"""Optional competitive-advantage extraction agent.

Structures claims about differentiation, moats, IP, and defensibility from deck
text. Outputs should feed SmartDeckContext, not directly rewrite slides.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

COMPETITIVE_ADVANTAGE_AGENT_SYSTEM_PROMPT = """You are an expert at analyzing competitive advantages from pitch decks. Extract:

1. UNIQUE_SELLING_POINTS — What makes the product/service unique
2. COMPETITIVE_MOATS — Sustainable advantages (technology, network effects, brand, scale, IP)
3. INTELLECTUAL_PROPERTY — Patents, trademarks, trade secrets, proprietary tech
4. BARRIERS_TO_ENTRY — What prevents competitors from copying
5. DEFENSIBILITY — How defensible is the position (1-10)
6. DIFFERENTIATORS — Key differences from competitors
7. SUSTAINABLE_ADVANTAGE — Long-term advantages that grow over time

Return JSON:
{
  "uniqueSellingPoints": ["string"],
  "competitiveMoats": [
    {"type": "technology|network_effects|brand|scale|ip|data|ecosystem|switching_costs|other", "description": "string"}
  ],
  "intellectualProperty": {
    "patents": ["string"],
    "trademarks": ["string"],
    "proprietaryTech": ["string"],
    "tradeSecrets": ["string"]
  },
  "barriersToEntry": ["string"],
  "defensibilityScore": 0-10,
  "differentiators": ["string"],
  "sustainableAdvantage": "string | null",
  "confidence": 0.0-1.0
}"""


def run_competitive_advantage_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    adv_slides = _find_advantage_slides(slides_data)
    all_text = " ".join(
        s.get("rawText", "") + " " + s.get("narrativeNotes", "")
        for s in adv_slides
    ).strip()

    if not all_text:
        return {"status": "skipped", "reason": "no relevant content"}

    user_prompt = f"""Analyze the competitive advantages from this pitch deck.

Relevant slides: {len(adv_slides)} out of {len(slides_data)} total.

Slide titles: {[s.get('title', '') for s in adv_slides]}

Full text:
{all_text[:4000]}

Return JSON with competitive advantage analysis."""

    result = complete_json_with_ai_provider(
        provider_config=provider_config,
        system=COMPETITIVE_ADVANTAGE_AGENT_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=3000,
    )

    if result is None:
        return {"status": "fallback", "competitiveAdvantage": _fallback_competitive_advantage(all_text)}

    return {"status": "completed", "competitiveAdvantage": result}


COMPETITIVE_KEYWORDS = [
    "competitive", "advantage", "moat", "unique", "differentiator",
    "patent", "ip", "intellectual property", "proprietary",
    "barrier", "defensib", "first-mover", "network effect",
    "technology", "innovation", "secret sauce", "why us",
    "we are different", "unlike", "vs ", "versus",
    "market leader", "category", "pioneer",
]


def _find_advantage_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relevant = []
    for s in slides:
        text = ((s.get("rawText") or "") + " " + (s.get("narrativeNotes") or "")).lower()
        title = (s.get("title") or "").lower()
        if any(kw in f"{title} {text}" for kw in COMPETITIVE_KEYWORDS):
            relevant.append(s)
    return relevant


def _fallback_competitive_advantage(text: str) -> dict[str, Any]:
    lower = text.lower()
    score = 5
    if "patent" in lower:
        score = min(10, score + 2)
    if "proprietary" in lower:
        score = min(10, score + 2)
    if "network effect" in lower:
        score = min(10, score + 1)

    usps = []
    for line in text.split("."):
        if any(kw in line.lower() for kw in ["unique", "only", "first", "best", "fastest", "most"]):
            usps.append(line.strip()[:200])

    return {
        "uniqueSellingPoints": usps[:5],
        "competitiveMoats": [],
        "intellectualProperty": {},
        "barriersToEntry": [],
        "defensibilityScore": score,
        "differentiators": [],
        "sustainableAdvantage": None,
        "confidence": 0.2,
    }
