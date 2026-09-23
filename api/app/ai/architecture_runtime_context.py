from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path

from app.ai.instant_deck_knowledge_context import build_instant_deck_generation_context
from app.services.agents.smart_deck_agent import SMART_DECK_AGENT
from app.services.agents.instant_deck_agent import INSTANT_DECK_AGENT
from app.services.llm.prompt_package_loader import load_prompt_package
from app.workers.dispatch.worker_runtime_service import SERVICE_NAME_TO_WORKER_KIND


def _package_root() -> Path:
    return Path(__file__).resolve().parents[2] / "llm_knowledge" / "dididecks_architecture_runtime_knowledge_pack"


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


def _load_text_files(base: Path, relative_dir: str, suffixes: tuple[str, ...]) -> dict[str, str]:
    root = base / relative_dir
    if not root.is_dir():
        return {}
    files: dict[str, str] = {}
    for item in sorted(root.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in suffixes:
            continue
        rel_key = str(item.relative_to(base)).replace("\\", "/")
        try:
            files[rel_key] = item.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return files


def _worker_services_for_job_chain(job_chain: tuple[str, ...]) -> list[str]:
    services_by_kind: dict[str, list[str]] = {}
    for service_name, worker_kind in SERVICE_NAME_TO_WORKER_KIND.items():
        services_by_kind.setdefault(worker_kind, []).append(service_name)
    ordered_services: list[str] = []
    for worker_kind in job_chain:
        ordered_services.extend(sorted(services_by_kind.get(worker_kind, [])))
    return ordered_services


@lru_cache(maxsize=1)
def load_architecture_runtime_knowledge() -> dict:
    configured = os.getenv("ARCHITECTURE_RUNTIME_KNOWLEDGE_PATH", "").strip()
    package_root = Path(configured).expanduser().resolve() if configured else _package_root()
    manifest = _load_json(package_root / "PACK_MANIFEST.json")
    if not manifest:
        manifest = {
            "package_name": "dididecks_architecture_runtime_knowledge_pack",
            "version": "unknown",
            "purpose": "Architecture runtime knowledge pack",
        }
    return {
        "name": manifest.get("package_name") or "dididecks_architecture_runtime_knowledge_pack",
        "version": manifest.get("version") or "unknown",
        "source": "compiled_json" if package_root.exists() else "missing",
        "index_path": str(package_root),
        "manifest": manifest,
        "docs": _load_text_files(package_root, "docs", (".md", ".txt")),
        "json": _load_json_files(package_root, "json"),
        "schemas": _load_json_files(package_root, "schemas"),
        "llm_knowledge": _load_json_files(package_root, "llm_knowledge"),
        "prompts": _load_text_files(package_root, "prompts", (".md", ".txt")),
        "examples": _load_json_files(package_root, "examples"),
        "status": _load_json_files(package_root, "status"),
        "typescript": _load_json_files(package_root, "typescript"),
        "sql": _load_json_files(package_root, "sql"),
    }


def build_architecture_runtime_context() -> dict:
    knowledge = load_architecture_runtime_knowledge()
    manifest = knowledge.get("manifest") or {}
    product_boundary = manifest.get("product_boundary") or {}
    core_concepts = (knowledge.get("json") or {}).get("json/product_domain_concepts.json") or {}
    workflow_state_machine = (knowledge.get("json") or {}).get("json/workflow_state_machine.json") or {}
    route_registry = (knowledge.get("json") or {}).get("json/route_registry.json") or {}
    api_contracts = (knowledge.get("json") or {}).get("json/api_contracts.json") or {}
    guardrail_rules = (knowledge.get("json") or {}).get("json/guardrail_rules.json") or {}
    component_registry = (knowledge.get("json") or {}).get("json/component_registry.json") or {}
    llm_extensions = knowledge.get("llm_knowledge") or {}
    return {
        "schemaVersion": "architecture-runtime-context.v1",
        "knowledgeMetadata": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
            "source": knowledge.get("source"),
            "moduleCount": sum(len(bundle) for bundle in [knowledge.get("docs") or {}, knowledge.get("json") or {}, knowledge.get("schemas") or {}, knowledge.get("llm_knowledge") or {}, knowledge.get("prompts") or {}, knowledge.get("examples") or {}]),
        },
        "productBoundary": product_boundary,
        "productObjects": core_concepts.get("core_concepts", []),
        "workflowStateMachine": workflow_state_machine,
        "routeRegistry": route_registry,
        "apiContracts": api_contracts,
        "guardrailRules": guardrail_rules,
        "componentRegistry": component_registry,
        "llmExtensions": llm_extensions,
        "reviewSurfaceRules": [
            "The editor, map, smart-edit, rebuild, review matrix, and exports must consume the same deck model.",
            "AI proposals must stay reviewable before apply.",
            "No frontend component should store backend secrets or directly mutate persistent fields.",
        ],
        "allowedCommands": [
            "draft_change_request",
            "preview_field_change",
            "apply_rebuild_job",
            "refresh_export",
        ],
    }


def build_smart_deck_runtime_capabilities() -> dict:
    knowledge = load_architecture_runtime_knowledge()
    manifest = knowledge.get("manifest") or {}
    json_modules = knowledge.get("json") or {}
    llm_modules = knowledge.get("llm_knowledge") or {}
    schemas = knowledge.get("schemas") or {}
    prompts = knowledge.get("prompts") or {}
    instant_deck = build_instant_deck_generation_context()
    instant_prompt_package = load_prompt_package("instant_deck")

    task_router = json_modules.get("json/llm_task_router_taxonomy.json") or {}
    guardrail_rules = json_modules.get("json/guardrail_rules.json") or {}
    workflow_state_machine = json_modules.get("json/workflow_state_machine.json") or {}
    api_contracts = json_modules.get("json/api_contracts.json") or {}
    component_registry = json_modules.get("json/component_registry.json") or {}

    tasks = [
        {
            "key": str(task.get("key") or "unknown"),
            "inputs": [str(item) for item in task.get("inputs") or []],
            "outputs": [str(item) for item in task.get("outputs") or []],
        }
        for task in task_router.get("tasks", [])
        if isinstance(task, dict)
    ]
    guardrail_groups = [
        {
            "group": str(group.get("group") or "Guardrail"),
            "rules": [str(rule) for rule in group.get("rules") or []],
        }
        for group in guardrail_rules.get("guardrail_groups", [])
        if isinstance(group, dict)
    ]

    return {
        "schemaVersion": "smart-deck-runtime-capabilities.v1",
        "knowledgeMetadata": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
            "source": knowledge.get("source"),
            "purpose": manifest.get("purpose"),
            "moduleCount": sum(
                len(bundle)
                for bundle in [
                    knowledge.get("docs") or {},
                    json_modules,
                    schemas,
                    llm_modules,
                    prompts,
                    knowledge.get("examples") or {},
                ]
            ),
        },
        "productBoundary": manifest.get("product_boundary") or {},
        "llmTasks": tasks,
        "guardrailGroups": guardrail_groups,
        "llmExtensions": sorted(llm_modules.keys()),
        "schemas": sorted(schemas.keys()),
        "prompts": sorted(prompts.keys()),
        "workflowStates": workflow_state_machine,
        "apiContracts": api_contracts,
        "componentRegistry": component_registry,
        "enabledSmartDeckCapabilities": [
            "slide_classification",
            "block_role_classification",
            "market_research_vigilance",
            "due_diligence_gap_detection",
            "architecture_drift_detection",
            "review_surface_guardrails",
            "ai_change_safety",
        ],
        "instructions": [
            "Use runtime capabilities to route Smart Deck assistant tasks to the right knowledge module.",
            "Use guardrail groups before proposing slide edits, rebuilds, or export-ready claims.",
            "Keep AI output tied to deck objects, source slide blocks, persistent fields, and review surfaces.",
            "Prefer missing-evidence flags over invented market, traction, financial, or diligence claims.",
        ],
        "instantDeck": {
            "generationMode": "instant_deck",
            "defaultPrompt": ((instant_deck.get("promptRecipe") or {}).get("defaultPrompt")),
            "knowledgePack": instant_deck.get("knowledgeSource") or {},
            "launchVariants": instant_deck.get("launchVariants") or [],
            "promptPackage": {
                "name": instant_prompt_package.package_id,
                "version": instant_prompt_package.version,
                "sections": sorted(instant_prompt_package.sections.keys()),
            },
            "agentOrchestration": {
                "agentKey": INSTANT_DECK_AGENT.agent_key,
                "execution": INSTANT_DECK_AGENT.execution,
                "commandRoute": INSTANT_DECK_AGENT.command_route,
                "workflowJobType": INSTANT_DECK_AGENT.workflow_job_type,
                "jobChain": list(INSTANT_DECK_AGENT.job_chain),
                "workerServices": _worker_services_for_job_chain(INSTANT_DECK_AGENT.job_chain),
                "providerUseCase": INSTANT_DECK_AGENT.provider_use_case,
                "requiredInputFields": list(INSTANT_DECK_AGENT.required_input_fields),
            },
            "referenceRegistry": instant_deck.get("referenceRegistry") or {},
            "embeddingSeedSources": instant_deck.get("embeddingSeedSources") or {},
        },
    }
