from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import unicodedata

from app.core.utils import read_json_payload


REQUIRED_INSTANT_DECK_MODULES = (
    "manifest",
    "reference_registry",
    "prompt_recipe",
    "vc_aistack_modules",
    "context_vigilance_patterns",
    "embedding_seed_sources",
    "design_quality_rules",
)

# Legacy import compatibility. The active investor beta intentionally has no
# named launch/style variants; callers that still build the historical lookup
# receive an empty immutable collection.
INSTANT_DECK_LAUNCH_VARIANTS: tuple[dict, ...] = ()

def _knowledge_root() -> Path:
    return Path(__file__).resolve().parents[2] / "llm_knowledge"


def _default_instant_directory() -> Path:
    return _knowledge_root() / "instant_deck_knowledge_pack"


def _configured_instant_path() -> Path | None:
    configured = os.getenv("INSTANT_DECK_KNOWLEDGE_PATH", "").strip()
    return Path(configured).expanduser().resolve() if configured else None


def _is_local_only_work_log(path: Path, *, root: Path) -> bool:
    """Keep operator Bitácora files outside every product knowledge lane."""
    for part in path.relative_to(root).parts:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", part)
            if not unicodedata.combining(character)
        ).casefold()
        if normalized.startswith("bitacora"):
            return True
    return False


def _load_json_files_from_directory(root: Path) -> dict[str, list[dict]]:
    modules: dict[str, list[dict]] = {}
    if not root.is_dir():
        return modules
    for item in sorted(root.rglob("*.json")):
        if _is_local_only_work_log(item, root=root):
            continue
        payload = read_json_payload(item.read_text(encoding="utf-8"))
        if payload is None:
            continue
        key = item.stem.lower().replace("-", "_").replace(" ", "_")
        modules.setdefault(key, []).append({"path": item.relative_to(root).as_posix(), "payload": payload})
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
def load_instant_deck_knowledge() -> dict:
    source_path = _configured_instant_path() or _default_instant_directory()
    if not source_path.exists():
        return {
            "name": "instant_deck_knowledge_pack",
            "version": "missing",
            "source": "missing",
            "index_path": str(source_path),
            "manifest": {},
            "knowledge_modules": {},
        }

    raw_modules = _load_json_files_from_directory(source_path)
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
        or os.getenv("INSTANT_DECK_KNOWLEDGE_VERSION", "").strip()
        or "unknown"
    )
    return {
        "name": manifest.get("name") or manifest.get("package") or "instant_deck_knowledge_pack",
        "version": version,
        "source": "source_json",
        "index_path": str(source_path),
        "manifest": manifest,
        "knowledge_modules": modules,
    }


def instant_deck_knowledge_health() -> dict:
    knowledge = load_instant_deck_knowledge()
    modules = knowledge.get("knowledge_modules") or {}
    missing = [module for module in REQUIRED_INSTANT_DECK_MODULES if module not in modules]
    return {
        "ready": knowledge.get("source") == "source_json" and not missing,
        "name": knowledge.get("name"),
        "version": knowledge.get("version"),
        "source": knowledge.get("source"),
        "indexPath": knowledge.get("index_path"),
        "moduleCount": len(modules),
        "modules": sorted(modules.keys()),
        "requiredModules": {
            "expected": list(REQUIRED_INSTANT_DECK_MODULES),
            "missing": missing,
        },
    }


def build_instant_deck_generation_context() -> dict:
    knowledge = load_instant_deck_knowledge()
    modules = knowledge.get("knowledge_modules") or {}

    def first_payload(key: str) -> dict:
        payloads = (modules.get(key) or {}).get("payloads") or []
        first = payloads[0] if payloads else {}
        return first if isinstance(first, dict) else {}

    return {
        "schemaVersion": "instant-deck-generation-context.v1",
        "knowledgeSource": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
            "source": knowledge.get("source"),
            "moduleCount": len(modules),
        },
        "manifest": knowledge.get("manifest") or {},
        "referenceRegistry": first_payload("reference_registry"),
        "promptRecipe": first_payload("prompt_recipe"),
        "vcAiStackModules": first_payload("vc_aistack_modules"),
        "contextVigilancePatterns": first_payload("context_vigilance_patterns"),
        "embeddingSeedSources": first_payload("embedding_seed_sources"),
        "designQualityRules": first_payload("design_quality_rules"),
        "instructions": [
            "Use the Instant Deck knowledge pack as additive venture-context guidance, not as a source of founder facts.",
            "Keep every claim tied to uploaded deck evidence; use the knowledge pack to improve structure, narrative sequence, diligence readiness, and operator framing.",
            "Treat the embedding seed registry as the default external corpus for Instant Deck retrieval/indexing evolution.",
            "Redesign the complete uploaded deck as a VC for a VC/investor audience. This is the application-owned default and requires no user-written prompt. Develop a coherent visual direction from the company's brand and source content. Choose narrative, slide order, copy, and composition freely; no predefined style family or named variant is required.",
            "Retrieve product-owned design rules to guide composition, then require rendered geometry proof before persistence.",
        ],
    }
