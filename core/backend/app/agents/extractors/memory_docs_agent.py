"""Optional strategic memory-document synthesis agent.

Consumes extraction outputs and creates market/company/competitive memos. This
should run after factual extraction so documents remain grounded.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

MEMORY_DOCS_AGENT_SYSTEM_PROMPT = """You are a strategic analyst that creates structured memory documents from pitch deck analysis. Based on all extracted data, generate three memory documents:

1. MARKET_MEMO — Market analysis document covering industry overview, TAM/SAM/SOM, market trends, growth drivers, risks
2. COMPETITIVE_LANDSCAPE_MEMO — Competitive analysis covering competitor landscape, positioning, moats, differentiators, threats
3. COMPANY_PROFILE_MEMO — Company summary covering business model, traction, team, product, stage, funding

Each document should be 2-4 paragraphs of strategic analysis, written for a VC audience.

Return JSON:
{
  "marketMemo": {
    "title": "string",
    "document": "string (markdown, 2-4 paragraphs)",
    "keyTags": ["string"]
  },
  "competitiveLandscapeMemo": {
    "title": "string",
    "document": "string (markdown, 2-4 paragraphs)",
    "keyTags": ["string"]
  },
  "companyProfileMemo": {
    "title": "string",
    "document": "string (markdown, 2-4 paragraphs)",
    "keyTags": ["string"]
  },
  "generatedAt": "ISO datetime string"
}"""


def run_memory_docs_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
    extraction_results: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    context = _build_memory_doc_context(slides_data, extraction_results)

    if provider_config and context.get("hasEnoughData"):
        user_prompt = f"""Based on the following deck analysis, generate three strategic memory documents.

Deck title: {context.get('deckTitle', 'Unknown')}
Total slides: {len(slides_data)}

Market data available: {context.get('hasMarketData')}
Competitive data available: {context.get('hasCompetitiveData')}
People data available: {context.get('hasPeopleData')}
Brand data available: {context.get('hasBrandData')}

Extraction summary:
{json.dumps(context.get('summary', {}), indent=2, ensure_ascii=False)[:3000]}

Return JSON with three memory documents in markdown format."""

        result = complete_json_with_ai_provider(
            provider_config=provider_config,
            system=MEMORY_DOCS_AGENT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4000,
        )
        if result is not None:
            result["generatedAt"] = datetime.utcnow().isoformat()
            return {"status": "completed", "memoryDocs": result}

    return {
        "status": "completed",
        "memoryDocs": _build_default_memory_docs(context.get("deckTitle", "Deck")),
    }


def _build_memory_doc_context(
    slides_data: list[dict[str, Any]],
    extraction_results: dict[str, Any] | None,
) -> dict[str, Any]:
    deck_title = (slides_data[0].get("title", "") if slides_data else "Deck")
    summary = {}
    has_market = False
    has_competitive = False
    has_people = False
    has_brand = False

    if extraction_results:
        market = extraction_results.get("market", {})
        if market.get("status") == "completed":
            has_market = True
            mr = market.get("marketResearch", {})
            if mr:
                summary["market"] = {
                    "industry": mr.get("marketOverview", {}).get("industry"),
                    "tam": mr.get("marketSize", {}).get("tam", {}).get("value"),
                    "competitors": len(mr.get("competitors", [])),
                }

        ca = extraction_results.get("competitive_advantage", {})
        if ca.get("status") == "completed":
            has_competitive = True
            summary["competitiveAdvantage"] = {
                "defensibility": ca.get("competitiveAdvantage", {}).get("defensibilityScore"),
                "uspCount": len(ca.get("competitiveAdvantage", {}).get("uniqueSellingPoints", [])),
            }

        people = extraction_results.get("people", {})
        if people.get("status") == "completed":
            has_people = True
            summary["people"] = {
                "count": len(people.get("people", {}).get("people", [])),
                "teamSize": people.get("people", {}).get("teamSize"),
            }

        brand = extraction_results.get("brand", {})
        if brand.get("status") == "completed":
            has_brand = True
            summary["brand"] = {
                "name": brand.get("brand", {}).get("brandName"),
                "maturity": brand.get("brand", {}).get("brandMaturity"),
            }

    all_text = " ".join(s.get("rawText", "") for s in slides_data)[:1000]

    return {
        "deckTitle": deck_title,
        "hasEnoughData": bool(all_text.strip()),
        "hasMarketData": has_market,
        "hasCompetitiveData": has_competitive,
        "hasPeopleData": has_people,
        "hasBrandData": has_brand,
        "summary": summary,
        "textPreview": all_text[:500],
    }


def _build_default_memory_docs(deck_title: str) -> dict[str, Any]:
    return {
        "marketMemo": {
            "title": f"Market Analysis: {deck_title}",
            "document": f"# Market Analysis: {deck_title}\n\nMarket data was not fully extracted. Review the deck for market size, growth rates, and industry trends.",
            "keyTags": ["market", "pending-analysis"],
        },
        "competitiveLandscapeMemo": {
            "title": f"Competitive Landscape: {deck_title}",
            "document": f"# Competitive Landscape: {deck_title}\n\nCompetitive analysis was not fully extracted. Review the deck for competitor mentions, positioning, and competitive advantages.",
            "keyTags": ["competitive", "pending-analysis"],
        },
        "companyProfileMemo": {
            "title": f"Company Profile: {deck_title}",
            "document": f"# Company Profile: {deck_title}\n\nCompany profile was compiled from available data. Full enrichment requires agent extraction.",
            "keyTags": ["company", "pending-analysis"],
        },
        "generatedAt": datetime.utcnow().isoformat(),
    }
