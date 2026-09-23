"""Deterministic block classifier.

Classifies extracted slide blocks into diligence categories using rules only.
This intentionally avoids LLM calls so it can run before provider configuration
and can feed source-fact/package construction safely.
"""

from __future__ import annotations

import re


_TEXT_RULES = [
    (("evidence", "proof", "source", "sourced", "citation"), "unsupported_claim", "evidence"),
    (("problem", "pain", "friction", "risk", "bottleneck"), "problem_claim", "market"),
    (("solution", "product", "platform", "feature", "workflow"), "solution_claim", "product"),
    (("customer", "client", "user", "buyer", "icp", "need"), "customer_claim", "market"),
    (("competitor", "alternative", "incumbent", "substitute"), "competition_claim", "competition"),
    (("team", "founder", "experience", "operator", "engineer"), "team_context", "team"),
    (("ask", "raise", "funding", "round", "pre", "seed", "series"), "investment_ask", "positioning"),
]

_METRIC_TOKENS = (
    "$",
    "%",
    "%",
    "arr",
    "mrr",
    "arr",
    "run-rate",
    "cac",
    "ltv",
    "gross margin",
    "revenue",
    "pipeline",
    "conversion",
    "retention",
    "growth",
    "tam",
    "sam",
    "som",
    "market size",
)


def run(
    deck_id: str,
    deck_context: dict | None = None,
    *,
    provider_config: dict | None = None,
) -> list[dict[str, object]]:
    """Classify blocks from deck_context into semantic/diligence categories."""
    _ = (deck_id, provider_config)
    if not deck_context:
        return []

    slides = deck_context.get("slides") if isinstance(deck_context.get("slides"), list) else []
    results: list[dict[str, object]] = []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_id = str(slide.get("id") or "")
        role = str(slide.get("role") or "").lower()
        for block in slide.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            block_id = str(block.get("id") or "").strip()
            if not block_id or not slide_id:
                continue

            block_text = str(block.get("normalized_text") or block.get("raw_text") or "")
            block_type = str(block.get("block_type") or "").lower()
            block_index = int(block.get("block_index") or 0)
            semantic_tag, diligence_category, confidence = _classify_block(
                block_text=block_text,
                block_type=block_type,
                block_index=block_index,
                slide_role=role,
            )
            results.append(
                {
                    "deck_id": deck_id,
                    "slide_id": slide_id,
                    "block_id": block_id,
                    "semantic_tag": semantic_tag,
                    "diligence_category": diligence_category,
                    "confidence": confidence,
                }
            )
    return results


def _classify_block(
    *,
    block_text: str,
    block_type: str,
    block_index: int,
    slide_role: str,
) -> tuple[str, str, float]:
    text = _normalize(block_text)
    semantic_tag = _infer_by_position(block_type=block_type, block_index=block_index)
    diligence_category = _category_for_tag(semantic_tag)
    confidence = 0.45

    if slide_role:
        mapped = _role_mapping(slide_role)
        semantic_tag = mapped["tag"]
        diligence_category = mapped["category"]
        confidence = mapped["confidence"]

    for triggers, mapped_tag, mapped_category in _TEXT_RULES:
        if any(token in text for token in triggers):
            tag_confidence = max(confidence, 0.62)
            if _keyword_weight(triggers, text) > tag_confidence:
                confidence = min(0.96, _keyword_weight(triggers, text))
            semantic_tag = mapped_tag
            diligence_category = mapped_category
            break

    if block_type in {"metric", "table", "chart"} or _contains_metric_terms(text):
        semantic_tag = "traction_metric"
        diligence_category = "commercial_traction"
        confidence = max(confidence, 0.75)

    return semantic_tag, diligence_category, round(float(confidence), 2)


def _infer_by_position(*, block_type: str, block_index: int) -> str:
    if block_index == 0 and block_type in {"headline", "title", "header", "subheading"}:
        return "slide_title"
    return "supporting_text"


def _role_mapping(slide_role: str) -> dict[str, object]:
    role = slide_role.strip().lower()
    mapping = {
        "problem": {"tag": "problem_claim", "category": "market", "confidence": 0.72},
        "traction": {"tag": "traction_metric", "category": "commercial_traction", "confidence": 0.75},
        "team": {"tag": "team_context", "category": "team", "confidence": 0.7},
        "solution": {"tag": "solution_claim", "category": "product", "confidence": 0.7},
        "competition": {"tag": "competition_claim", "category": "competition", "confidence": 0.7},
        "financials": {"tag": "financial_claim", "category": "financials", "confidence": 0.68},
        "ask": {"tag": "investment_ask", "category": "positioning", "confidence": 0.64},
    }
    for key, value in mapping.items():
        if key in role:
            return value
    return {"tag": "supporting_text", "category": "narrative", "confidence": 0.55}


def _contains_metric_terms(block_text: str) -> bool:
    text = block_text.lower()
    return any(token in text for token in _METRIC_TOKENS)


def _category_for_tag(semantic_tag: str) -> str:
    if semantic_tag == "problem_claim":
        return "market"
    if semantic_tag in {"slide_title", "supporting_text"}:
        return "narrative"
    if semantic_tag == "solution_claim":
        return "product"
    if semantic_tag == "traction_metric":
        return "commercial_traction"
    if semantic_tag == "customer_claim":
        return "market"
    if semantic_tag == "competition_claim":
        return "competition"
    if semantic_tag in {"team_context", "unsupported_claim"}:
        return "team"
    if semantic_tag == "investment_ask":
        return "positioning"
    if semantic_tag == "financial_claim":
        return "financials"
    return "general"


def _keyword_weight(triggers: tuple[str, ...], text: str) -> float:
    score = 0.55
    hit_count = sum(1 for token in triggers if token in text)
    if hit_count:
        score += min(0.35, hit_count * 0.08)
    return min(0.96, score)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()
