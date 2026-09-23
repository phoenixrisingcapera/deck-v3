from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[3] / "llm_knowledge" / "investor_visual_design"


@lru_cache(maxsize=1)
def load_visual_knowledge() -> dict[str, Any]:
    manifest = json.loads((KNOWLEDGE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    modules: dict[str, Any] = {}
    for module in manifest["modules"]:
        payload = json.loads((KNOWLEDGE_ROOT / f"{module}.json").read_text(encoding="utf-8"))
        if payload.get("module") != module:
            raise ValueError(f"Visual knowledge module identity mismatch: {module}")
        modules[module] = payload
    return {**manifest, "content": modules}


def selected_modules(*, has_financials: bool, has_brand: bool) -> list[str]:
    knowledge = load_visual_knowledge()
    selected = [
        "visual_decision_rules", "evidence_shape", "investor_visual_grammar",
        "composition_grammar", "deck_rhythm", "chart_selection", "diagram_selection",
        "image_policy", "typography", "visual_compliance", "designer_handoff",
    ]
    if has_financials:
        selected.extend(["financial_visualization", "forecast_semantics"])
    if has_brand:
        selected.append("brand_translation")
    return [module for module in selected if module in knowledge["modules"]]


def visual_rule_ids() -> set[str]:
    knowledge = load_visual_knowledge()
    return {
        str(rule["id"])
        for module in knowledge["content"].values()
        for rule in module.get("rules", [])
        if isinstance(rule, dict) and rule.get("id")
    }
