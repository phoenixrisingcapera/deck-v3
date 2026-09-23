from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2] / "llm_knowledge" / "deckaistack_duediligence_llm_knowledge_pack" / "deckaistack_extended_llm_knowledge_pack"


def _default_manifest_path() -> Path:
    return _package_root() / "pipeline" / "llm_knowledge_manifest.json"


def _default_schema_path() -> Path:
    return _package_root() / "schemas" / "deck_diligence_output_schema.json"


def _default_prompt_path() -> Path:
    return _package_root() / "prompts" / "master_diligence_classifier_prompt.json"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_files(base: Path, relative_dir: str) -> dict[str, dict]:
    root = base / relative_dir
    if not root.is_dir():
        return {}
    files: dict[str, dict] = {}
    for item in sorted(root.rglob("*.json")):
        rel_key = str(item.relative_to(base)).replace("\\", "/")
        try:
            files[rel_key] = json.loads(item.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return files


@lru_cache(maxsize=1)
def load_diligence_knowledge() -> dict:
    configured = os.getenv("DILIGENCE_KNOWLEDGE_PATH", "").strip()
    package_root = Path(configured).expanduser().resolve() if configured else _package_root()
    manifest = _load_json(Path(configured).expanduser().resolve() if configured and Path(configured).expanduser().resolve().is_file() else _default_manifest_path())
    if not manifest:
        manifest = {
            "package": "deckaistack_extended_llm_knowledge_pack",
            "version": "unknown",
            "modules": [],
            "recommended_pipeline": [],
            "ui_panels": [],
        }

    audience_profiles = _load_json_files(package_root, "audience_profiles")
    vc_due_diligence = _load_json_files(package_root, "vc_due_diligence")
    lp_intelligence = _load_json_files(package_root, "lp_intelligence")
    investment_committee = _load_json_files(package_root, "investment_committee")
    scoring_models = _load_json_files(package_root, "scoring_models")
    examples = _load_json_files(package_root, "examples")

    return {
        "name": manifest.get("package") or "deckaistack_extended_llm_knowledge_pack",
        "version": manifest.get("version") or "unknown",
        "source": "compiled_json" if configured or package_root.exists() else "missing",
        "index_path": str(package_root),
        "manifest": manifest,
        "audience_profiles": audience_profiles,
        "vc_due_diligence": vc_due_diligence,
        "lp_intelligence": lp_intelligence,
        "investment_committee": investment_committee,
        "scoring_models": scoring_models,
        "examples": examples,
        "output_schema": _load_json(_default_schema_path()),
        "prompt": _load_json(_default_prompt_path()),
        "knowledge_modules": {
            "audience_profiles": audience_profiles,
            "vc_due_diligence": vc_due_diligence,
            "lp_intelligence": lp_intelligence,
            "investment_committee": investment_committee,
            "scoring_models": scoring_models,
            "examples": examples,
            "schemas": {"deck_diligence_output_schema": _load_json(_default_schema_path())},
            "prompts": {"master_diligence_classifier_prompt": _load_json(_default_prompt_path())},
        },
    }


def build_diligence_workspace_context(
    *,
    deck: dict,
    findings: list[dict],
    suggestions: list[dict],
    smart_edit_suggestions: list[dict],
    slides: list[dict],
    audience_profile: dict | None = None,
) -> dict:
    knowledge = load_diligence_knowledge()
    pack_manifest = knowledge.get("manifest") or {}
    due_diligence_modules = knowledge.get("vc_due_diligence") or {}
    audience_profiles = knowledge.get("audience_profiles") or {}
    matched_profile = audience_profile or next(
        (profile for profile in audience_profiles.values() if isinstance(profile, dict) and profile.get("label") == deck.get("audience")),
        None,
    )
    slide_classification = []
    domain_keys = list((knowledge.get("output_schema") or {}).get("required") or [])
    for slide in slides:
        role = str(slide.get("role") or "").lower()
        title = str(slide.get("title") or "").lower()
        archetype = "general"
        if "problem" in role or "problem" in title:
            archetype = "problem"
        elif "solution" in role or "solution" in title:
            archetype = "solution"
        elif "market" in role or "market" in title:
            archetype = "market"
        elif "traction" in role or "traction" in title:
            archetype = "traction"
        elif "team" in role or "team" in title:
            archetype = "team"
        slide_classification.append(
            {
                "slide_id": slide.get("id"),
                "archetype": archetype,
                "confidence": 0.55 if archetype != "general" else 0.35,
                "reasoning_summary": slide.get("summary") or slide.get("rawText") or slide.get("title"),
                "block_roles": [block.get("block_type") for block in slide.get("blocks", []) if isinstance(block, dict)],
            }
        )

    evidence_gaps = [
        {
            "slideId": finding.get("slide_id"),
            "blockId": finding.get("block_id"),
            "title": finding.get("title"),
            "detail": finding.get("detail"),
            "severity": finding.get("severity"),
            "category": finding.get("category"),
        }
        for finding in findings
    ]
    recommended_actions = [
        {
            "title": suggestion.get("title"),
            "reason": suggestion.get("reason"),
            "slideId": suggestion.get("slide_id"),
            "blockId": suggestion.get("block_id"),
            "status": suggestion.get("status"),
        }
        for suggestion in suggestions[:12]
    ]
    market_research_flags = []
    for key in ("market", "traction", "competition", "financials", "legal", "governance", "risks"):
        if key in due_diligence_modules:
            market_research_flags.append({"domain": key, "present": True})

    ic_readiness = pack_manifest.get("modules", [])
    lp_view = knowledge.get("lp_intelligence") or {}

    return {
        "schemaVersion": "diligence-workspace.v1",
        "deckId": deck.get("id"),
        "knowledgeMetadata": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
            "source": knowledge.get("source"),
            "moduleCount": len(knowledge.get("knowledge_modules") or {}),
        },
        "audienceProfile": matched_profile or {},
        "slideClassification": slide_classification,
        "audienceFit": {
            "score": 0.7 if matched_profile else 0.45,
            "strengths": [deck.get("audience"), deck.get("purpose")],
            "gaps": [finding.get("title") for finding in findings[:5]],
        },
        "dueDiligence": {
            "domains": domain_keys,
            "findings": evidence_gaps,
            "modules": due_diligence_modules,
        },
        "lpView": lp_view,
        "icReadiness": {
            "modules": ic_readiness,
            "issues": evidence_gaps[:8],
        },
        "marketResearchFlags": market_research_flags,
        "missingEvidence": [
            {
                "slideId": item.get("slideId"),
                "blockId": item.get("blockId"),
                "title": item.get("title"),
                "detail": item.get("detail"),
            }
            for item in evidence_gaps
            if item.get("severity") in {"high", "critical"} or item.get("category") in {"evidence", "missing_evidence"}
        ],
        "recommendedActions": recommended_actions,
        "smartEditSignals": smart_edit_suggestions[:8],
    }
