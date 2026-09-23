"""Optional founder/team extraction agent.

Extracts people/team signals from deck text. It must remain evidence-based and
should not infer founder claims that are not present in source material.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

PEOPLE_AGENT_SYSTEM_PROMPT = """You are an expert at extracting people information from pitch decks. For each person mentioned, extract:

1. NAME — Full name
2. ROLE — Title or role (CEO, CTO, Founder, Board Member, Advisor, etc.)
3. CATEGORY — founder|executive|board|advisor|investor|team
4. BIO — Short background or description
5. LINKEDIN_URL — LinkedIn URL if mentioned
6. PREVIOUS_COMPANY — Notable previous company
7. EDUCATION — Education background if mentioned

Also extract:
- TEAM_SIZE — Total team size mentioned
- TEAM_STRENGTHS — Key team advantages (domain expertise, serial founders, etc.)
- NOTABLE_BOARD — Board members or advisors

Return JSON:
{
  "people": [
    {
      "name": "string",
      "role": "string",
      "category": "founder|executive|board|advisor|investor|team",
      "bio": "string",
      "linkedinUrl": "string | null",
      "previousCompany": "string | null",
      "education": "string | null"
    }
  ],
  "teamSize": "string | null",
  "teamStrengths": ["string"],
  "notableBoard": ["string"],
  "confidence": 0.0-1.0
}"""


def run_people_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    people_slides = _find_people_slides(slides_data)
    all_text = " ".join(
        s.get("rawText", "") + " " + s.get("narrativeNotes", "")
        for s in people_slides
    ).strip()

    if not all_text:
        return {"status": "skipped", "reason": "no people-related content"}

    user_prompt = f"""Extract people information from this pitch deck.

People-related slides: {len(people_slides)} out of {len(slides_data)} total.

Slide titles: {[s.get('title', '') for s in people_slides]}

Full text:
{all_text[:4000]}

Return JSON with extracted people data."""

    result = complete_json_with_ai_provider(
        provider_config=provider_config,
        system=PEOPLE_AGENT_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=3000,
    )

    if result is None:
        return {"status": "fallback", "people": _fallback_people(people_slides, all_text)}

    return {"status": "completed", "people": result}


PEOPLE_KEYWORDS = [
    "founder", "co-founder", "ceo", "cto", "cfo", "chief", "executive",
    "board", "advisor", "advisory", "management", "team",
    "leadership", "president", "director", "head of",
    "linkedin", "previous", "background", "experience",
    "our team", "meet the team", "about us",
]


def _find_people_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    relevant = []
    for s in slides:
        text = ((s.get("rawText") or "") + " " + (s.get("narrativeNotes") or "")).lower()
        title = (s.get("title") or "").lower()
        if any(kw in f"{title} {text}" for kw in PEOPLE_KEYWORDS):
            relevant.append(s)
    return relevant


def _fallback_people(slides: list[dict[str, Any]], text: str) -> dict[str, Any]:
    names = re.findall(r'([A-Z][a-z]+ [A-Z][a-z]+)', text)
    team_size = None
    for match in re.finditer(r'(\d+)\+?\s*(?:team|people|employees)', text, re.I):
        team_size = match.group(1)
        break
    return {
        "people": [{"name": n, "role": "mentioned", "category": "team"} for n in names[:10]],
        "teamSize": team_size,
        "teamStrengths": [],
        "notableBoard": [],
        "confidence": 0.2,
    }
