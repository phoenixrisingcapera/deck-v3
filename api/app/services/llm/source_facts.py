from __future__ import annotations

import re
from typing import Any


METRIC_PATTERN = re.compile(r"(\$|%|\b\d+(?:\.\d+)?\s?(?:x|m|k|b|million|billion|users|customers|arr|mrr|revenue)\b)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def classify_source_fact(
    *,
    text: str,
    source_type: str,
    field: str | None = None,
    confidence: str | None = None,
) -> dict[str, Any]:
    lower_text = text.lower()
    lower_field = (field or "").lower()
    fact_type = _fact_type(lower_text, lower_field, source_type)
    evidence_strength = _evidence_strength(fact_type=fact_type, source_type=source_type, confidence=confidence)
    safety_flags = _safety_flags(fact_type=fact_type, text=lower_text, evidence_strength=evidence_strength)
    return {
        "factType": fact_type,
        "evidenceStrength": evidence_strength,
        "safetyFlags": safety_flags,
    }


def summarize_fact_types(facts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fact in facts:
        fact_type = str(fact.get("factType") or "unknown")
        counts[fact_type] = counts.get(fact_type, 0) + 1
    return counts


def summarize_safety_flags(facts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for fact in facts:
        for flag in fact.get("safetyFlags") or []:
            flag_text = str(flag)
            counts[flag_text] = counts.get(flag_text, 0) + 1
    return counts


def _fact_type(text: str, field: str, source_type: str) -> str:
    if source_type in {"user_instruction", "smart_edit_instruction"}:
        return "instruction"
    if source_type == "brand_profile":
        return "brand"
    if field in {"audience", "purpose", "role", "block_type"}:
        return "context"
    if field == "title":
        return "positioning"
    if METRIC_PATTERN.search(text):
        if any(term in text for term in ("arr", "mrr", "revenue", "margin", "burn", "cash", "$")):
            return "financial"
        return "metric"
    if any(term in text for term in ("customer", "client", "logo", "design partner", "pilot", "contract")):
        return "customer"
    if any(term in text for term in ("founder", "team", "ceo", "cto", "operator", "advisor", "board")):
        return "team"
    if any(term in text for term in ("market", "tam", "sam", "som", "category", "segment")):
        return "market"
    if any(term in text for term in ("regulation", "regulatory", "policy", "compliance", "fda", "sec", "law")):
        return "regulatory"
    if any(term in text for term in ("product", "platform", "workflow", "feature", "integration", "api")):
        return "product"
    if YEAR_PATTERN.search(text) or any(term in text for term in ("roadmap", "milestone", "launch", "quarter", "month")):
        return "timeline"
    if any(term in text for term in ("raise", "ask", "use of proceeds", "runway", "round")):
        return "ask"
    if any(term in text for term in ("assume", "estimate", "project", "forecast", "expected")):
        return "assumption"
    return "general"


def _evidence_strength(*, fact_type: str, source_type: str, confidence: str | None) -> str:
    if confidence == "high" and source_type in {"source_slide", "source_block", "deck_metadata"}:
        return "high"
    if fact_type in {"financial", "regulatory", "customer", "metric"} and source_type not in {"source_slide", "source_block"}:
        return "medium"
    if source_type in {"user_instruction", "smart_edit_instruction"}:
        return "medium"
    if confidence == "low":
        return "low"
    return "medium"


def _safety_flags(*, fact_type: str, text: str, evidence_strength: str) -> list[str]:
    flags: list[str] = []
    if fact_type in {"financial", "regulatory", "customer", "metric"}:
        flags.append("requires_source")
    if fact_type in {"financial", "regulatory"}:
        flags.append("requires_user_confirmation")
    if evidence_strength != "high":
        flags.append("do_not_strengthen")
    if any(term in text for term in ("best", "leading", "only", "guaranteed", "risk-free")):
        flags.append("avoid_superlative")
    return flags
