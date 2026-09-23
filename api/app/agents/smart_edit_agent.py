"""Evidence-bound Smart Edit agent.

Owns one-block rewrite suggestions. This is the preferred current path for
user-facing accept/reject suggestions because it asks the LLM to cite
`source_fact_ids` and returns a reviewable payload instead of mutating slides.
"""

from __future__ import annotations


import json

from app.agents.llm_agent_utils import complete_json_with_ai_provider


def run(
    *,
    deck_id: str,
    slide_id: str,
    block_id: str,
    instruction: str,
    audience_type: str,
    original_text: str,
    deck_context: dict | None = None,
    provider_config: dict | None = None,
) -> dict[str, object]:
    """Ask the configured provider for one conservative, source-cited edit."""
    raw = complete_json_with_ai_provider(
        provider_config=provider_config,
        system=(
            "You rewrite one pitch-deck block as a reviewable suggestion. Return JSON only. "
            "Use deck_context.slideArchetypeContext knowledge modules for writing rules, "
            "diagnostics, hallucination constraints, archetype rewrite modes, and Smart Edit quality rubrics. "
            "Use deck_context.sourceFactPackage.facts as the only allowed factual source. "
            "Respect factType, evidenceStrength, and safetyFlags on each fact."
        ),
        user=(
            "Return a JSON object with original_text, suggested_text, reason, risk_level, "
            "source_fact_ids, source_facts_used, missing_inputs, and quality_warnings. "
            "risk_level must be low, medium, or high. Preserve source-backed facts, do not invent metrics, "
            "Use source_fact_ids such as fact_1 from deck_context.sourceFactPackage.facts. "
            "Do not strengthen facts marked do_not_strengthen. Treat financial, regulatory, customer, and metric facts carefully. "
            "and do not apply the edit directly. If the instruction needs missing evidence, keep the edit "
            "conservative and explain the missing input in reason.\n\n"
            f"Deck id: {deck_id}\nSlide id: {slide_id}\nBlock id: {block_id}\n"
            f"Audience: {audience_type}\nInstruction: {instruction}\nOriginal text: {original_text}\n"
            f"Deck context:\n{json.dumps(deck_context or {}, ensure_ascii=True)}"
        ),
    )
    if isinstance(raw, dict):
        risk_level = str(raw.get("risk_level") or "medium").lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = "medium"
        return {
            "original_text": str(raw.get("original_text") or original_text),
            "suggested_text": str(raw.get("suggested_text") or original_text),
            "reason": str(raw.get("reason") or "Suggested by AI provider for the selected audience."),
            "risk_level": risk_level,
            "source_fact_ids": raw.get("source_fact_ids") if isinstance(raw.get("source_fact_ids"), list) else [],
            "source_facts_used": raw.get("source_facts_used") if isinstance(raw.get("source_facts_used"), list) else [],
            "missing_inputs": raw.get("missing_inputs") if isinstance(raw.get("missing_inputs"), list) else [],
            "quality_warnings": raw.get("quality_warnings") if isinstance(raw.get("quality_warnings"), list) else [],
        }

    return {
        "original_text": original_text,
        "suggested_text": original_text,
        "reason": "Smart edit could not be generated because the AI provider did not return a structured suggestion.",
        "risk_level": "medium",
        "source_fact_ids": [],
        "source_facts_used": [],
        "missing_inputs": [],
        "quality_warnings": ["AI provider unavailable. Fallback did not rewrite content or cite source facts."],
    }
