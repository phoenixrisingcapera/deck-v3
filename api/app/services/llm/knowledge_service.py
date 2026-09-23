from __future__ import annotations

from app.ai.slide_archetypes_context import load_deck_archetype_knowledge
from app.ai.diligence_knowledge_context import load_diligence_knowledge
from app.ai.architecture_runtime_context import load_architecture_runtime_knowledge
from app.ai.instant_deck_knowledge_context import (
    instant_deck_knowledge_health,
    load_instant_deck_knowledge,
)
from app.ai.market_research_knowledge_context import (
    load_market_research_knowledge,
    market_research_knowledge_health,
)
from app.ai.vc_finance_knowledge_context import (
    load_vc_finance_knowledge,
    vc_finance_knowledge_health,
)
from app.ai.vc_methodology_knowledge_context import vc_methodology_knowledge_health


REQUIRED_ARCHETYPE_FIELDS = (
    "slug",
    "description",
    "deck_types",
    "llm_contract",
    "render_contract",
    "quality_rubric",
    "narrative_role",
    "required_inputs",
    "evidence_hierarchy",
    "generation_rules",
    "critique_rules",
    "rewrite_modes",
    "visual_guidance",
    "output_contract",
    "validation_rules",
    "frontend_render_hints",
)

REQUIRED_KNOWLEDGE_MODULES = (
    "deck_types",
    "narrative_flows",
    "render_schema_rules",
    "writing_rules",
    "quality_rubrics",
    "hallucination_constraints",
    "retrieval_routing",
    "deck_recipes",
    "diagnostics",
    "generation_contracts",
    "examples",
    "eval_cases",
)

DILIGENCE_REQUIRED_MODULES = (
    "audience_profiles",
    "vc_due_diligence",
    "lp_intelligence",
    "investment_committee",
    "scoring_models",
    "examples",
)

ARCHITECTURE_RUNTIME_REQUIRED_MODULES = (
    "docs",
    "json",
    "schemas",
    "llm_knowledge",
    "prompts",
)

INSTANT_DECK_REQUIRED_MODULES = (
    "reference_registry",
    "prompt_recipe",
    "vc_aistack_modules",
    "context_vigilance_patterns",
    "embedding_seed_sources",
)


def _package_summary(knowledge: dict) -> dict:
    modules = knowledge.get("knowledge_modules") or {}
    return {
        "name": knowledge.get("name"),
        "version": knowledge.get("version"),
        "source": knowledge.get("source"),
        "indexPath": knowledge.get("index_path"),
        "moduleCount": len(modules),
        "modules": sorted(modules.keys()),
        "manifest": knowledge.get("manifest") or {},
    }


def build_llm_knowledge_metadata() -> dict:
    archetype_knowledge = load_deck_archetype_knowledge()
    diligence_knowledge = load_diligence_knowledge()
    runtime_knowledge = load_architecture_runtime_knowledge()
    market_knowledge = load_market_research_knowledge()
    vc_finance_knowledge = load_vc_finance_knowledge()
    instant_deck_knowledge = load_instant_deck_knowledge()
    vc_methodology = vc_methodology_knowledge_health()
    return {
        "name": archetype_knowledge.get("name"),
        "version": archetype_knowledge.get("version"),
        "source": archetype_knowledge.get("source"),
        "archetypeCount": len(archetype_knowledge.get("archetypes") or []),
        "moduleCount": len(archetype_knowledge.get("knowledge_modules") or {}),
        "modules": sorted((archetype_knowledge.get("knowledge_modules") or {}).keys()),
        "runtimeContract": archetype_knowledge.get("runtime_contract") or {},
        "packages": {
            "deck_archetypes": {
                **_package_summary(archetype_knowledge),
                "archetypeCount": len(archetype_knowledge.get("archetypes") or []),
                "runtimeContract": archetype_knowledge.get("runtime_contract") or {},
            },
            "due_diligence": _package_summary(diligence_knowledge),
            "vc_finance": _package_summary(vc_finance_knowledge),
            "architecture_runtime": {
                "name": runtime_knowledge.get("name"),
                "version": runtime_knowledge.get("version"),
                "source": runtime_knowledge.get("source"),
                "indexPath": runtime_knowledge.get("index_path"),
                "moduleCount": sum(
                    len(bundle)
                    for bundle in [
                        runtime_knowledge.get("docs") or {},
                        runtime_knowledge.get("json") or {},
                        runtime_knowledge.get("schemas") or {},
                        runtime_knowledge.get("llm_knowledge") or {},
                        runtime_knowledge.get("prompts") or {},
                        runtime_knowledge.get("examples") or {},
                    ]
                ),
                "manifest": runtime_knowledge.get("manifest") or {},
            },
            "market_research": _package_summary(market_knowledge),
            "instant_deck": _package_summary(instant_deck_knowledge),
            "vc_methodology": vc_methodology,
        },
    }


def _validate_archetype_knowledge(archetype_knowledge: dict) -> dict:
    archetypes = archetype_knowledge.get("archetypes") or []
    modules = archetype_knowledge.get("knowledge_modules") or {}
    missing_modules = [module_id for module_id in REQUIRED_KNOWLEDGE_MODULES if module_id not in modules]
    archetype_field_errors = []

    for archetype in archetypes:
        slug = archetype.get("slug") or "unknown"
        missing_fields = [
            field
            for field in REQUIRED_ARCHETYPE_FIELDS
            if field not in archetype or archetype.get(field) in (None, "", [], {})
        ]
        render_contract = archetype.get("render_contract") if isinstance(archetype.get("render_contract"), dict) else {}
        if render_contract.get("schema_version") != "smart-deck-render-schema.v1":
            missing_fields.append("render_contract.schema_version")
        if missing_fields:
            archetype_field_errors.append({"slug": slug, "missingFields": missing_fields})

    return {
        "ready": archetype_knowledge.get("source") == "compiled_json" and not missing_modules and not archetype_field_errors,
        "missingModules": missing_modules,
        "archetypeFieldErrors": archetype_field_errors,
    }


def _build_task_contracts(*, deck_ready: bool, market_ready: bool, vc_finance_ready: bool = False, instant_deck_ready: bool = False) -> dict:
    return {
        "slide_classification": {
            "ready": deck_ready,
            "knowledgePack": "deck_archetypes",
            "requiredOutputs": ["archetype", "confidence", "evidence", "alternatives", "missingInputs"],
            "artifactMetadata": ["knowledge_pack_id", "knowledge_pack_version", "classification_confidence"],
        },
        "block_classification": {
            "ready": deck_ready,
            "knowledgePack": "deck_archetypes",
            "requiredOutputs": ["blockRole", "confidence", "evidence", "alternatives", "missingInputs"],
            "artifactMetadata": ["knowledge_pack_id", "knowledge_pack_version", "classification_confidence"],
        },
        "market_verification": {
            "ready": market_ready,
            "knowledgePack": "market_research",
            "requiredOutputs": ["claim", "verificationStatus", "evidence", "confidence", "missingInputs"],
            "artifactMetadata": ["knowledge_pack_id", "knowledge_pack_version", "verification_confidence"],
        },
        "vc_finance_verification": {
            "ready": vc_finance_ready,
            "knowledgePack": "vc_finance",
            "requiredOutputs": [
                "financialClaim",
                "verificationStatus",
                "assumptions",
                "consistencyIssues",
                "evidenceNeeded",
                "saferWording",
                "slideImplementationInstruction",
            ],
            "artifactMetadata": ["knowledge_pack_id", "knowledge_pack_version", "financial_verification_confidence"],
        },
        "audience_diligence_conversion": {
            "ready": deck_ready and vc_finance_ready,
            "knowledgePack": "audience_diligence + vc_finance",
            "requiredOutputs": [
                "audiencePriorities",
                "audienceObjections",
                "deckImplementationPlan",
                "slideLevelInstructions",
                "financialInsights",
                "smartDeckInstruction",
                "smartEditInstructions",
            ],
            "artifactMetadata": ["prompt_package_id", "prompt_package_version", "vc_finance_knowledge_version"],
        },
        "instant_deck_generation": {
            "ready": deck_ready and instant_deck_ready,
            "knowledgePack": "deck_archetypes + instant_deck",
            "requiredOutputs": ["designVersionName", "slides", "renderSchema", "missingInputs", "confidence"],
            "artifactMetadata": ["prompt_package_id", "prompt_package_version", "instant_deck_knowledge_version"],
        },
    }


def get_llm_knowledge_task_contracts() -> dict:
    archetype_validation = _validate_archetype_knowledge(load_deck_archetype_knowledge())
    market_health = market_research_knowledge_health()
    vc_finance_health = vc_finance_knowledge_health()
    instant_deck_health = instant_deck_knowledge_health()
    return {
        "schemaVersion": "llm-knowledge-task-contracts.v1",
        "tasks": _build_task_contracts(
            deck_ready=archetype_validation["ready"],
            market_ready=market_health.get("ready") is True,
            vc_finance_ready=vc_finance_health.get("ready") is True,
            instant_deck_ready=instant_deck_health.get("ready") is True,
        ),
        "api": {
            "health": "GET /api/admin/llm-knowledge/health",
            "tasks": "GET /api/admin/llm-knowledge/tasks",
            "reload": "POST /api/admin/llm-knowledge/reload",
        },
    }


def reload_llm_knowledge() -> dict:
    load_deck_archetype_knowledge.cache_clear()
    load_diligence_knowledge.cache_clear()
    load_architecture_runtime_knowledge.cache_clear()
    load_market_research_knowledge.cache_clear()
    load_vc_finance_knowledge.cache_clear()
    load_instant_deck_knowledge.cache_clear()
    return get_llm_knowledge_health()


def get_llm_knowledge_health() -> dict:
    archetype_knowledge = load_deck_archetype_knowledge()
    diligence_knowledge = load_diligence_knowledge()
    runtime_knowledge = load_architecture_runtime_knowledge()
    archetype_validation = _validate_archetype_knowledge(archetype_knowledge)

    diligence_missing = [module for module in DILIGENCE_REQUIRED_MODULES if not (diligence_knowledge.get(module) or {})]
    diligence_ready = diligence_knowledge.get("source") == "compiled_json" and bool(diligence_knowledge.get("manifest")) and not diligence_missing

    runtime_missing = [module for module in ARCHITECTURE_RUNTIME_REQUIRED_MODULES if not (runtime_knowledge.get(module) or {})]
    runtime_ready = runtime_knowledge.get("source") == "compiled_json" and bool(runtime_knowledge.get("manifest")) and not runtime_missing

    market_health = market_research_knowledge_health()
    vc_finance_health = vc_finance_knowledge_health()
    instant_deck_health = instant_deck_knowledge_health()
    is_ready = (
        archetype_validation["ready"]
        and diligence_ready
        and runtime_ready
        and market_health.get("ready") is True
        and vc_finance_health.get("ready") is True
        and instant_deck_health.get("ready") is True
    )

    return {
        "status": "ready" if is_ready else "degraded",
        "knowledge": build_llm_knowledge_metadata(),
        "packages": {
            "deck_archetypes": {
                "ready": archetype_validation["ready"],
                "indexPath": archetype_knowledge.get("index_path"),
                "requiredModules": {
                    "expected": list(REQUIRED_KNOWLEDGE_MODULES),
                    "missing": archetype_validation["missingModules"],
                },
                "archetypeValidation": {
                    "requiredFields": list(REQUIRED_ARCHETYPE_FIELDS),
                    "errorCount": len(archetype_validation["archetypeFieldErrors"]),
                    "errors": archetype_validation["archetypeFieldErrors"][:25],
                },
            },
            "due_diligence": {
                "ready": diligence_ready,
                "indexPath": diligence_knowledge.get("index_path"),
                "requiredModules": {
                    "expected": list(DILIGENCE_REQUIRED_MODULES),
                    "missing": diligence_missing,
                },
            },
            "vc_finance": vc_finance_health,
            "architecture_runtime": {
                "ready": runtime_ready,
                "indexPath": runtime_knowledge.get("index_path"),
                "requiredModules": {
                    "expected": list(ARCHITECTURE_RUNTIME_REQUIRED_MODULES),
                    "missing": runtime_missing,
                },
            },
            "market_research": market_health,
            "instant_deck": instant_deck_health,
        },
        "tasks": _build_task_contracts(
            deck_ready=archetype_validation["ready"],
            market_ready=market_health.get("ready") is True,
            vc_finance_ready=vc_finance_health.get("ready") is True,
            instant_deck_ready=instant_deck_health.get("ready") is True,
        ),
    }
