"""Optional VC-style evaluation synthesis agent.

Scores team, market, product, traction, moat, and funding fit from extracted
context. Treat scores as advisory until source facts are canonical.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.llm_agent_utils import complete_json_with_ai_provider

VC_EVALUATION_AGENT_SYSTEM_PROMPT = """You are a seasoned VC analyst evaluating a company based on its pitch deck. Score each dimension and provide a compelling thesis.

Evaluate across:
1. TEAM (1-10) — Founder-market fit, relevant experience, track record, completeness
2. MARKET (1-10) — Market size, growth rate, timing, tailwinds
3. PRODUCT (1-10) — Solution quality, differentiation, technical innovation, UX
4. TRACTION (1-10) — Revenue, users, growth metrics, partnerships, milestones
5. COMPETITIVE_MOAT (1-10) — Defensibility, IP, network effects, barriers
6. BUSINESS_MODEL (1-10) — Unit economics, margins, scalability, revenue model
7. FUNDING_FIT (1-10) — Ask alignment with stage, milestone clarity, use of funds
8. OVERALL (1-10) — Overall investment potential

Return JSON:
{
  "scores": {
    "team": 0-10,
    "market": 0-10,
    "product": 0-10,
    "traction": 0-10,
    "competitiveMoat": 0-10,
    "businessModel": 0-10,
    "fundingFit": 0-10,
    "overall": 0-10
  },
  "strengths": ["string"],
  "risks": ["string"],
  "questions": ["string (questions a VC would ask)"],
  "investmentThesis": "string (2-3 sentence thesis)",
  "verdict": "strong_yes|yes|maybe|no|pass",
  "recommendedCheckSize": "string | null",
  "confidence": 0.0-1.0
}"""


def run_vc_evaluation_agent(
    slides_data: list[dict[str, Any]],
    *,
    provider_config: dict[str, str] | None = None,
    extraction_results: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not slides_data:
        return {"status": "skipped", "reason": "no slides"}

    context = _build_vc_context(slides_data, extraction_results)

    if provider_config and context.get("hasExtractionData"):
        user_prompt = f"""Evaluate this company as a VC investor based on the following deck analysis.

Deck information:
{json.dumps(context, indent=2, ensure_ascii=False)[:4000]}

Score each dimension and provide an investment thesis. Return JSON."""

        result = complete_json_with_ai_provider(
            provider_config=provider_config,
            system=VC_EVALUATION_AGENT_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=3000,
        )
        if result is not None:
            return {"status": "completed", "vcEvaluation": result}

    return {
        "status": "completed",
        "vcEvaluation": _default_vc_evaluation(context.get("extractionSummary", "")),
    }


def _build_vc_context(
    slides_data: list[dict[str, Any]],
    extraction_results: dict[str, Any] | None,
) -> dict[str, Any]:
    deck_title = (slides_data[0].get("title", "") if slides_data else "Unknown")
    slide_count = len(slides_data)
    all_text = " ".join(s.get("rawText", "") for s in slides_data)[:2000]

    summary = {}
    has_data = False

    if extraction_results:
        market = extraction_results.get("market", {})
        if market.get("status") == "completed":
            has_data = True
            mr = market.get("marketResearch", {})
            summary["market"] = mr.get("marketOverview", {})
            summary["marketSize"] = mr.get("marketSize", {})
            summary["competitors"] = mr.get("competitors", [])

        ca = extraction_results.get("competitive_advantage", {})
        if ca.get("status") == "completed":
            has_data = True
            adv = ca.get("competitiveAdvantage", {})
            summary["defensibilityScore"] = adv.get("defensibilityScore")
            summary["moats"] = adv.get("competitiveMoats", [])

        people = extraction_results.get("people", {})
        if people.get("status") == "completed":
            has_data = True
            ppl = people.get("people", {})
            summary["teamSize"] = ppl.get("teamSize")
            summary["teamMembers"] = [p.get("name") for p in ppl.get("people", [])[:5]]

    return {
        "deckTitle": deck_title,
        "slideCount": slide_count,
        "hasExtractionData": has_data,
        "extractionSummary": summary,
        "textPreview": all_text[:500],
    }


def _default_vc_evaluation(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "scores": {
            "team": 5,
            "market": 5,
            "product": 5,
            "traction": 5,
            "competitiveMoat": 5,
            "businessModel": 5,
            "fundingFit": 5,
            "overall": 5,
        },
        "strengths": ["Awaiting full agent extraction"],
        "risks": ["Limited data available for evaluation"],
        "questions": ["What is the core value proposition?"],
        "investmentThesis": "Evaluation requires complete agent extraction. Currently showing neutral baseline scores.",
        "verdict": "maybe",
        "recommendedCheckSize": None,
        "confidence": 0.1,
    }
