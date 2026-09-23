"""Optional online-presence extraction agent.

Extracts URLs, social profiles, and contact hints from deck text. This is safe
to run before external website crawling because it only uses uploaded evidence.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

WEBSITE_AGENT_SYSTEM_PROMPT = """You are an expert at extracting online presence data from slide decks. Extract:

1. WEBSITE_URL — Company website URL
2. SOCIAL_LINKS — Social media profiles (LinkedIn, Twitter/X, Crunchbase, etc.)
3. CONTACT_EMAIL — Contact email addresses
4. APP_STORE — Mobile app store links if mentioned
5. PRESS — Notable press mentions or media coverage
6. SOCIAL_METRICS — Follower counts or engagement metrics if mentioned

Return JSON:
{
  "websiteUrl": "string | null",
  "socialLinks": [
    {"platform": "string", "url": "string"}
  ],
  "contactEmail": "string | null",
  "appStoreUrl": "string | null",
  "pressMentions": ["string"],
  "socialMetrics": {"platform": "string", "followers": "string"} | null,
  "confidence": 0.0-1.0
}"""


def run_website_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    all_text = " ".join(
        s.get("rawText", "") + " " + s.get("narrativeNotes", "")
        for s in slides_data
    ).strip()

    urls = _extract_urls(all_text)
    social_hints = _extract_social_hints(all_text)

    if not urls and not social_hints and provider_config:
        user_prompt = f"""Extract online presence information from this slide deck.

Total slides: {len(slides_data)}

Full text:
{all_text[:5000]}

URLs found: {json.dumps(urls) if urls else 'none'}

Return JSON with any website, social, or contact information found."""

        result = complete_json_with_ai_provider(
            provider_config=provider_config,
            system=WEBSITE_AGENT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=2000,
        )
        if result is not None:
            return {"status": "completed", "onlinePresence": result}

    return {
        "status": "completed",
        "onlinePresence": {
            "websiteUrl": urls[0] if urls else None,
            "socialLinks": social_hints,
            "contactEmail": None,
            "appStoreUrl": None,
            "pressMentions": [],
            "socialMetrics": None,
            "confidence": 0.5 if urls else 0.1,
        },
    }


URL_PATTERN = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w$.+!*\'(),;:@&=?/~#%]*)?', re.I)


def _extract_urls(text: str) -> list[str]:
    return list(set(URL_PATTERN.findall(text)))


SOCIAL_DOMAINS = {
    "linkedin.com": "LinkedIn",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "crunchbase.com": "Crunchbase",
    "angel.co": "AngelList",
    "wellfound.com": "AngelList",
    "producthunt.com": "ProductHunt",
    "github.com": "GitHub",
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "youtube.com": "YouTube",
    "tiktok.com": "TikTok",
}


def _extract_social_hints(text: str) -> list[dict[str, str]]:
    urls = _extract_urls(text)
    links = []
    for url in urls:
        for domain, platform in SOCIAL_DOMAINS.items():
            if domain in url.lower():
                links.append({"platform": platform, "url": url})
                break
    return links
