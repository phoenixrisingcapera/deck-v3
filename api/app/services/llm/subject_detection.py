from __future__ import annotations

import re

from app.services.llm.subject_registry import SMART_DECK_SUBJECT_REGISTRY


def _tokenize(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def detect_smart_deck_subject(title: str | None, extracted_text: str | None, tags: list[str] | None = None, context: str | None = None) -> dict:
    haystack = " ".join(item for item in [title, extracted_text, " ".join(tags or []), context] if item).lower()
    tokens = _tokenize(haystack)
    best = {"subject": "unknown", "confidence": 0.0, "matchedTerms": []}

    for item in SMART_DECK_SUBJECT_REGISTRY:
        score = 0
        if item["slug"] in haystack:
            score += 6
        if item["slug"].replace("_", " ") in haystack:
            score += 4
        for variant in item["slugVariants"]:
            if variant in haystack:
                score += 5
            elif _tokenize(variant).issubset(tokens):
                score += 3
        for word in _tokenize(item["description"]):
            if word in tokens:
                score += 1
        if score > best["confidence"] * 10:
            best = {
                "subject": item["id"],
                "confidence": min(0.98, score / 10),
                "matchedTerms": [item["slug"], *item["slugVariants"][:4]],
            }

    if best["confidence"] < 0.3:
        return {"subject": "unknown", "confidence": 0.0, "matchedTerms": []}
    return best
