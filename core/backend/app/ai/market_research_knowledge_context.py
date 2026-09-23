from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from app.core.utils import read_json_payload


REQUIRED_MARKET_MODULES = (
    "market_claim_taxonomy",
    "verification_schema",
    "source_policy",
    "competitor_intelligence_taxonomy",
    "market_research_prompts",
    "pipeline_contract",
)


def _knowledge_root() -> Path:
    return Path(__file__).resolve().parents[2] / "llm_knowledge"


def _default_market_directory() -> Path:
    return _knowledge_root() / "deckaistack_vc_pitch_market_research_knowledge_pack"


def _default_market_zip() -> Path:
    return _knowledge_root() / "deckaistack_vc_pitch_market_research_knowledge_pack.zip"


def _configured_market_path() -> Path | None:
    configured = os.getenv("MARKET_RESEARCH_KNOWLEDGE_PATH", "").strip()
    return Path(configured).expanduser().resolve() if configured else None



def _module_key(relative_path: str) -> str:
    normalised = relative_path.lower().replace("-", "_").replace(" ", "_")
    filename = Path(normalised).stem
    joined = f"{normalised}/{filename}"

    if "market_claim" in joined or "claim_taxonomy" in joined:
        return "market_claim_taxonomy"
    if "verification" in joined and ("schema" in joined or "contract" in joined):
        return "verification_schema"
    if "source_policy" in joined or "source" in joined and "policy" in joined:
        return "source_policy"
    if "competitor" in joined:
        return "competitor_intelligence_taxonomy"
    if "prompt" in joined:
        return "market_research_prompts"
    if "example" in joined or "synthetic" in joined:
        return "examples"
    if "pipeline" in joined or "contract" in joined:
        return "pipeline_contract"
    return filename or "unknown"


def _append_module(modules: dict[str, list[dict]], key: str, relative_path: str, payload: dict | list) -> None:
    if isinstance(payload, dict):
        item: dict = payload
    else:
        item = {"items": payload}
    modules.setdefault(key, []).append({"path": relative_path, "payload": item})


def _load_json_files_from_directory(root: Path) -> dict[str, list[dict]]:
    modules: dict[str, list[dict]] = {}
    if not root.is_dir():
        return modules
    for item in sorted(root.rglob("*.json")):
        payload = read_json_payload(item.read_text(encoding="utf-8"))
        if payload is None:
            continue
        relative_path = item.relative_to(root).as_posix()
        _append_module(modules, _module_key(relative_path), relative_path, payload)
    return modules


def _load_json_files_from_zip(path: Path) -> dict[str, list[dict]]:
    modules: dict[str, list[dict]] = {}
    if not path.is_file():
        return modules
    try:
        with ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if not name.lower().endswith(".json"):
                    continue
                try:
                    payload = read_json_payload(archive.read(name).decode("utf-8"))
                except UnicodeDecodeError:
                    continue
                if payload is None:
                    continue
                _append_module(modules, _module_key(name), name, payload)
    except BadZipFile:
        return {}
    return modules


def _normalise_modules(modules: dict[str, list[dict]]) -> dict[str, dict]:
    normalised: dict[str, dict] = {}
    for key, entries in modules.items():
        normalised[key] = {
            "entryCount": len(entries),
            "paths": [entry["path"] for entry in entries],
            "payloads": [entry["payload"] for entry in entries],
        }
    return normalised


@lru_cache(maxsize=1)
def load_market_research_knowledge() -> dict:
    configured = _configured_market_path()
    candidates = [configured] if configured else []
    candidates.extend([_default_market_directory(), _default_market_zip()])

    source_path = next((path for path in candidates if path and path.exists()), candidates[-1])
    if source_path is None or not source_path.exists():
        return {
            "name": "deckaistack_vc_pitch_market_research_knowledge_pack",
            "version": "missing",
            "source": "missing",
            "index_path": str(source_path) if source_path else "",
            "manifest": {},
            "knowledge_modules": {},
        }

    if source_path.is_dir():
        raw_modules = _load_json_files_from_directory(source_path)
        source = "source_json"
    elif source_path.suffix.lower() == ".zip":
        raw_modules = _load_json_files_from_zip(source_path)
        source = "zip_json"
    else:
        payload = read_json_payload(source_path.read_text(encoding="utf-8"))
        raw_modules = {}
        if payload is not None:
            _append_module(raw_modules, _module_key(source_path.name), source_path.name, payload)
        source = "compiled_json" if source_path.name.endswith(".json") else "source_file"

    modules = _normalise_modules(raw_modules)
    manifest = next(
        (
            payload
            for entry in raw_modules.get("manifest", [])
            for payload in [entry.get("payload")]
            if isinstance(payload, dict)
        ),
        {},
    )
    version = (
        manifest.get("version")
        or manifest.get("pack_version")
        or os.getenv("MARKET_RESEARCH_KNOWLEDGE_VERSION", "").strip()
        or "unknown"
    )

    return {
        "name": manifest.get("name") or manifest.get("package") or "deckaistack_vc_pitch_market_research_knowledge_pack",
        "version": version,
        "source": source,
        "index_path": str(source_path),
        "manifest": manifest,
        "knowledge_modules": modules,
    }


def market_research_knowledge_health() -> dict:
    knowledge = load_market_research_knowledge()
    modules = knowledge.get("knowledge_modules") or {}
    missing = [module for module in REQUIRED_MARKET_MODULES if module not in modules]
    return {
        "ready": knowledge.get("source") in {"compiled_json", "source_json", "zip_json", "source_file"} and not missing,
        "name": knowledge.get("name"),
        "version": knowledge.get("version"),
        "source": knowledge.get("source"),
        "indexPath": knowledge.get("index_path"),
        "moduleCount": len(modules),
        "modules": sorted(modules.keys()),
        "requiredModules": {
            "expected": list(REQUIRED_MARKET_MODULES),
            "missing": missing,
        },
    }


def build_market_verification_context(*, claims: list[dict] | None = None, audience: str | None = None) -> dict:
    knowledge = load_market_research_knowledge()
    return {
        "schemaVersion": "market-verification-context.v1",
        "knowledgeSource": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
            "source": knowledge.get("source"),
            "moduleCount": len(knowledge.get("knowledge_modules") or {}),
        },
        "audience": audience,
        "claims": claims or [],
        "knowledgeModules": knowledge.get("knowledge_modules") or {},
        "verificationGuidance": [
            "Separate market verification from slide classification.",
            "Return supported facts, unsupported assertions, missing evidence, and confidence separately.",
            "Do not restate founder claims as facts without evidence.",
            "Prefer source quality, recency, and direct evidence over generic market language.",
        ],
    }
