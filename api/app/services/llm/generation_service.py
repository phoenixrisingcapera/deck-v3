from __future__ import annotations

"""Smart Deck LLM orchestration and persistence.

CRITICAL PATH: User clicks "Generate" → LLM call → Slide generation → Rendered deck

This file owns:
1. Provider resolution (Qwen/OpenAI/Anthropic/OpenRouter)
2. Knowledge-backed prompt assembly
3. LLM generation orchestration
4. Design-version persistence
5. Smart Deck workspace read model

USER JOURNEY:
1. User clicks "Generate Smart Deck" in frontend
2. Frontend sends POST /api/products/deck-aistack-codes/decks/{id}/smart-deck/generate
3. Server validates request:
   - Check user is authenticated
   - Check deck exists
   - Check brand profile exists
   - Check source extraction complete
4. Server resolves LLM provider:
   - Check workspace settings (encrypted API keys)
   - Fall back to environment variables
   - Select provider (Qwen/OpenAI/Anthropic/OpenRouter)
5. Server builds prompt:
   - Load deck structure (slides, text, images)
   - Load brand profile (colors, fonts, style)
   - Load source slides
   - Build system prompt with brand context
   - Build user prompt with slide generation instructions
   - Add slide archetypes (title, problem, solution, etc.)
   - Add VC prompt context (investor-focused language)
6. Server calls LLM API:
   - Send prompt to provider
   - Parse response (JSON or text)
   - Validate output schema
   - Extract slide structure
7. Server creates generated slides:
   - Parse LLM response into slide structure
   - Create generated_slide records
   - Create slide elements (text, images, charts)
   - Apply brand colors and fonts
8. Server renders slides:
   - Generate slide preview images
   - Apply design version
   - Create final deck
9. Server returns response:
   - smart_deck_id
   - slide_count
   - status: "ready"
   - slides: [...]

LLM PROVIDERS:
- DashScope (Qwen): Primary provider, best for technical content
- OpenAI: GPT-4, GPT-4o, good for general content
- Anthropic: Claude, good for creative content
- OpenRouter: Multi-provider routing

PROMPT ASSEMBLY:
- System prompt: Brand context, visual style, tone
- User prompt: Slide generation instructions
- Slide archetypes: Title, problem, solution, market, team, etc.
- VC context: Investor-focused language, diligence criteria
- Knowledge context: Architecture runtime context

TOKEN ACCOUNTING:
- Track input/output tokens per request
- Track latency per request
- Track errors per request
- Aggregate by workspace, provider, model

ERROR HANDLING:
- Provider errors are masked (never expose raw errors to frontend)
- Retry logic with exponential backoff
- Fallback to secondary provider if primary fails
- Record all errors in agent telemetry

SECURITY:
- Workspace API keys are encrypted with Fernet
- Keys are decrypted only when needed
- Keys are never logged or exposed in errors
"""

import copy
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
import hashlib
import json
import logging
import math
from datetime import datetime
import re
import threading
import time
from types import SimpleNamespace
from typing import Any

from cryptography.fernet import InvalidToken
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from app.services.llm.anthropic_provider import call_anthropic_message, extract_anthropic_text
from app.services.llm.dashscope_provider import call_dashscope_chat_completion, call_dashscope_multimodal_completion, extract_dashscope_text
from app.services.llm.openai_provider import (
    OpenAIResponseFailed,
    OpenAIResponseIncomplete,
    OpenAIResponseMalformed,
    call_openai_response,
    extract_openai_text,
    extract_openai_usage,
    parse_openai_structured_response,
)


class GenerationValidationError(ValueError):
    """Blocking generation failure with a source-content-free durable summary."""

    code = "generation_validation_blocked"

    def __init__(self, summary: dict[str, Any]):
        super().__init__("Smart Deck output remains blocked by factuality or evidence validation.")
        self.summary = summary
        self.reason_codes = tuple(summary.get("reasonCodes") or [])

    def to_summary(self) -> dict[str, Any]:
        return copy.deepcopy(self.summary)


class ManualEditConflictError(ValueError):
    """A manual edit was based on stale or mismatched persisted identities."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


from app.services.llm.openrouter_provider import call_openrouter_chat_completion, extract_openrouter_text
from app.ai.architecture_runtime_context import build_architecture_runtime_context, build_smart_deck_runtime_capabilities
from app.ai.instant_deck_knowledge_context import INSTANT_DECK_LAUNCH_VARIANTS, build_instant_deck_generation_context
from app.core.config import settings
from app.core.security import generate_id
from app.core.workspace_ai_crypto import get_workspace_ai_fernet
from app.ai.slide_archetypes_context import build_slide_archetype_context, load_deck_archetype_knowledge
from app.ai.vc_prompt_context import build_vc_prompt_context
from app.services.llm.subject_detection import detect_smart_deck_subject
from app.services.admin.agent_telemetry import record_agent_event
from app.services.llm.critique_service import build_critique_decision, summarize_critique_decisions
from app.services.storage.deck_retention import apply_retention
from app.services.deck_processing.source_slide_payload import map_source_slide_payload
from app.services.brand.brand_design_tokens import (
    DEFAULT_DESIGN_TOKENS,
    build_brand_design_tokens,
    build_brand_llm_context,
    build_provider_safe_brand_context,
)
from app.services.llm.artifact_persistence import persist_canonical_llm_artifact
from app.services.llm.knowledge_service import build_llm_knowledge_metadata
from app.services.llm.canonical_deck_intelligence_service import build_canonical_deck_intelligence
from app.services.llm.prompt_package_loader import build_prompt_package_text, load_prompt_package
from app.services.llm.source_facts import classify_source_fact, summarize_fact_types, summarize_safety_flags
from app.services.llm.vision_context_service import model_image_url
from app.services.llm.operation_deadline import OperationDeadline, OperationDeadlineExceeded
from app.services.deck_processing.save_confirmation import get_latest_save_confirmation_for_deck, map_save_confirmation
from app.services.storage.signed_urls import get_bucket_artifact_service
from app.db.session import SessionLocal
from app.db.models import (
    AudienceProfile,
    Deck,
    DeckLlmArtifact,
    DeckSlide,
    DeckSlideBlock,
    DesignBatch,
    DesignToken,
    DesignVersion,
    ElementVariationJob,
    GeneratedSlide,
    GeneratedSlideCodeVersion,
    GeneratedSlideElement,
    GeneratedSlideElementVersion,
    GenerationJob,
    InstantDeckOperation,
    InstantDeckProviderAttempt,
    SmartDeckMessage,
    SmartDeckPreference,
    SmartDeckWorkspace,
    User,
    Workspace,
    WorkspaceAiCredential,
    WorkspaceAiProviderSetting,
    WorkflowJob,
)
from app.schemas.smart_deck import (
    CreateManualEditJobInput,
    CreateSmartDeckAssistantRunInput,
    CreateSmartDeckGenerationJobInput,
    CreateSmartDeckMessageInput,
    RenderSchema,
    SmartDeckAssistantInsightResponse,
    UpdateSmartDeckPreferenceInput,
)
from app.services.llm.retriever_service import (
    ContextMode,
    build_element_variation_retrieval_context,
    build_generation_context,
)
from app.ai_orchestration.provider_resolver import WORKSPACE_PROVIDER_CONFIGURATION_ERROR


DESIGN_TOKENS = DEFAULT_DESIGN_TOKENS

SMART_DECK_ARTIFACT_SCHEMA_VERSION = "smart-deck-artifacts.v1"
SMART_DECK_GENERATION_ARTIFACT_TYPES = {
    "smart_deck_generation_context",
    "smart_deck_design_version_manifest",
    "generated_slide_render_schema",
    "generated_slide_code_version",
}
SMART_DECK_ASSISTANT_ARTIFACT_TYPE = "smart_deck_assistant_run"
SMART_DECK_ASSISTANT_ARTIFACT_STORAGE_VERSION = "smart-deck-assistant-artifact.v1"
SMART_DECK_ASSISTANT_MAX_OUTPUT_TOKENS = 2500

_logger = logging.getLogger(__name__)
_openai_render_rate_lock = threading.Lock()
_openai_render_last_started_at = 0.0

ASSISTANT_INTENTS = {
    "market_size": {
        "label": "Market Size Insight",
        "template": "Assess TAM, SAM, and SOM claims through a VC lens: market definition, adoption path, pricing logic, source quality, and which assumptions need diligence before an IC memo.",
        "action": "save_insight",
    },
    "market_research": {
        "label": "Market Research",
        "template": "Summarize market claims, evidence quality, category timing, ICP clarity, buyer urgency, and the specific research needed to turn founder assertions into investor-grade proof.",
        "action": "save_insight",
    },
    "financial_projection": {
        "label": "Financial Projection Review",
        "template": "Review financial projection claims for ARR/MRR logic, gross margin, CAC, payback, burn, runway, hiring plan, and milestone credibility; separate model assumptions from deck-backed facts.",
        "action": "save_insight",
    },
    "competitor_landscape": {
        "label": "Competitor Landscape",
        "template": "Extract competitor positioning and sharpen differentiation around alternatives, incumbents, switching costs, defensibility, and why the company can win a venture-scale wedge.",
        "action": "save_insight",
    },
    "customer_persona": {
        "label": "Customer Persona",
        "template": "Infer customer segments and ICP from the deck, then identify the evidence needed to validate pain frequency, budget owner, buying trigger, sales cycle, and expansion potential.",
        "action": "save_insight",
    },
    "investor_objections": {
        "label": "Investor Objections",
        "template": "Identify likely objections from associates, partners, and IC members; provide the strongest deck-backed responses plus the missing evidence needed to answer each objection credibly.",
        "action": "save_insight",
    },
    "narrative_flow": {
        "label": "Narrative Flow",
        "template": "Critique the deck sequence as an investor decision path: problem urgency, market scale, solution wedge, traction proof, economics, team, risks, and milestone-tied ask.",
        "action": "add_to_slide",
    },
    "slide_critique": {
        "label": "Slide Critique",
        "template": "Critique the selected slide for VC usefulness: claim clarity, evidence density, metric specificity, objection handling, and one concrete update that improves decision readiness.",
        "action": "add_to_slide",
    },
    "due_diligence_risks": {
        "label": "Due Diligence Risks",
        "template": "Find diligence risks, unsupported claims, concentration issues, market/model assumptions, execution dependencies, and follow-up questions a VC team should ask before conviction.",
        "action": "save_insight",
    },
    "missing_evidence": {
        "label": "Missing Evidence",
        "template": "List the missing evidence needed to make selected claims investor-ready: source, date, owner, method, benchmark, customer proof, financial support, and where it belongs in the deck.",
        "action": "save_insight",
    },
    "rewrite_for_vc": {
        "label": "VC Rewrite",
        "template": "Rewrite the selected content for a concise VC pitch while preserving facts, increasing specificity only when supported, and making the investor takeaway explicit.",
        "action": "add_to_slide",
    },
    "create_design_version": {
        "label": "Design Version Brief",
        "template": "Create a design-version brief for Smart Deck generation that states the target VC persona, slide objective, evidence hierarchy, risk handling, and the investor takeaway each slide must land.",
        "action": "create_version",
    },
}

ASSISTANT_OUTPUT_TYPES = {
    "market_size": "insight",
    "market_research": "research",
    "financial_projection": "insight",
    "competitor_landscape": "research",
    "customer_persona": "insight",
    "investor_objections": "insight",
    "narrative_flow": "critique",
    "slide_critique": "critique",
    "due_diligence_risks": "insight",
    "missing_evidence": "insight",
    "rewrite_for_vc": "critique",
    "create_design_version": "design_version",
}

INVALID_GENERATION_PROVIDER_VALUES = {
    "deterministic",
    "fallback",
    "missing",
    "missing_provider",
    "missing_openai",
    "missing_openrouter",
    "missing_claude",
    "missing_dashscope",
}
SUPPORTED_LLM_GENERATION_PROVIDERS = {"openai", "dashscope", "anthropic", "openrouter"}

INSTANT_DECK_VARIANT_MAP = {str(variant.get("id")): variant for variant in INSTANT_DECK_LAUNCH_VARIANTS if isinstance(variant, dict) and variant.get("id")}
VALID_INSTANT_DECK_VARIANT_IDS = frozenset(INSTANT_DECK_VARIANT_MAP.keys())
_SLIDE_ARCHETYPE_KNOWLEDGE = load_deck_archetype_knowledge()
SLIDE_ARCHETYPE_LABEL_MAP: dict[str, str] = {}
for item in (_SLIDE_ARCHETYPE_KNOWLEDGE.get("archetypes") or []):
    if not isinstance(item, dict) or not item.get("slug"):
        continue
    canonical_slug = str(item.get("slug")).strip().lower()
    label = str((item.get("aliases") or [canonical_slug])[0]).replace("-", " ").title()[:120]
    SLIDE_ARCHETYPE_LABEL_MAP[canonical_slug] = label
    for alias in item.get("aliases") or []:
        normalized_alias = str(alias).strip().lower()
        if normalized_alias:
            SLIDE_ARCHETYPE_LABEL_MAP.setdefault(normalized_alias, label)
VALID_SLIDE_ARCHETYPE_IDS = frozenset(SLIDE_ARCHETYPE_LABEL_MAP.keys())


class SmartDeckProviderUnavailableError(ValueError):
    """Raised when a redesign or generation request has no usable AI provider."""

ANTHROPIC_MODEL_ALIASES = {
    "claude-sonnet": "claude-sonnet-4-5",
    "claude-opus": "claude-opus-4-1",
}
OPENAI_MODEL_PREFIXES = ("gpt-", "o1", "o3", "o4")


def _normalize_anthropic_model(model: str | None) -> str:
    if not model:
        return settings.anthropic_model
    return ANTHROPIC_MODEL_ALIASES.get(model, model)


def _is_production_mode() -> bool:
    return settings.app_env.lower() == "production" or settings.railway_environment.lower() == "production"


def _is_openai_model(model: str | None) -> bool:
    return bool(model and model.strip().lower().startswith(OPENAI_MODEL_PREFIXES))


def _is_openrouter_model(model: str | None) -> bool:
    return bool(model and "/" in model.strip())


def _is_anthropic_model(model: str | None) -> bool:
    return bool(model and model.strip().lower().startswith("claude"))


def _model_for_provider(provider: str, preferred_model: str | None, setting_model: str | None = None) -> str:
    if provider == "openai":
        if _is_openai_model(preferred_model):
            return preferred_model or settings.openai_model
        if _is_openai_model(setting_model):
            return setting_model or settings.openai_model
        return settings.openai_model
    if provider == "openrouter":
        if _is_openrouter_model(preferred_model):
            return preferred_model or settings.openrouter_model
        if _is_openrouter_model(setting_model):
            return setting_model or settings.openrouter_model
        return settings.openrouter_model
    if provider == "dashscope":
        for candidate in (preferred_model, setting_model):
            if candidate and candidate.startswith("qwen"):
                return candidate
        return settings.effective_qwen_model
    if _is_anthropic_model(preferred_model):
        return _normalize_anthropic_model(preferred_model)
    if _is_anthropic_model(setting_model):
        return _normalize_anthropic_model(setting_model)
    return settings.anthropic_model


def _provider_model_is_valid(provider: str, model: str | None) -> bool:
    if provider == "openai":
        return _is_openai_model(model)
    if provider == "openrouter":
        return _is_openrouter_model(model)
    if provider == "dashscope":
        return bool(model and model.strip().lower().startswith("qwen"))
    if provider == "anthropic":
        return _is_anthropic_model(model)
    return False


def _configured_qwen_fallback() -> dict | None:
    """Resolve the explicitly configured Qwen fallback through existing adapters."""
    provider = str(settings.qwen_fallback_provider or "").strip().lower()
    if provider == "claude":
        provider = "anthropic"
    model = str(settings.qwen_fallback_model or "").strip()
    api_keys = {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "openrouter": settings.openrouter_api_key,
    }
    api_key = api_keys.get(provider)
    if provider not in api_keys or not model or not api_key:
        return None
    return {"provider": provider, "model": model, "apiKey": api_key, "source": "qwen_fallback"}


def resolve_qwen_model_for_operation(operation: str, preferred_model: str | None = None) -> str:
    from app.services.llm.qwen_strategy import resolve_qwen_routing
    routing = resolve_qwen_routing(operation, preferred_model)
    return routing.model


def _provider_from_generation_mode() -> str | None:
    mode = (settings.deck_generation_mode or "openai").strip().lower()
    if mode == "mock":
        raise ValueError("Mock Smart Deck generation has moved to the Deck local_testing harness.")
    if _is_production_mode() and mode != "openai":
        raise SmartDeckProviderUnavailableError(
            "Production generation, repair, critique follow-up, and vision require OpenAI."
        )
    if mode == "openai":
        return "openai"
    if mode == "openrouter":
        return "openrouter"
    if mode in {"claude", "anthropic"}:
        return "anthropic"
    if mode in {"dashscope", "qwen", "alibaba"}:
        return "dashscope"
    return None


def _decrypt_workspace_api_key(credential: WorkspaceAiCredential | None) -> str | None:
    if credential is None or not credential.is_active:
        return None
    if credential.key_version != settings.workspace_ai_fernet_key_version:
        return None
    try:
        return get_workspace_ai_fernet().decrypt(credential.encrypted_api_key).decode()
    except (InvalidToken, RuntimeError, ValueError):
        return None


def _resolve_claude_config(
    db: Session,
    deck: Deck,
    preferred_model: str | None = None,
    *,
    use_case: str = "smart_deck",
) -> dict:
    setting_query = db.query(WorkspaceAiProviderSetting).filter(
        WorkspaceAiProviderSetting.workspace_id == deck.workspace_id,
        WorkspaceAiProviderSetting.configured_at.is_not(None),
    )
    if use_case == "smart_edit":
        setting_query = setting_query.filter(WorkspaceAiProviderSetting.use_for_smart_edit.is_(True))
    elif use_case == "analysis":
        setting_query = setting_query.filter(WorkspaceAiProviderSetting.use_for_analysis.is_(True))
    else:
        setting_query = setting_query.filter(WorkspaceAiProviderSetting.use_for_smart_deck.is_(True))
    setting = setting_query.first()
    if setting is None:
        env_provider = _provider_from_generation_mode()
        return _resolve_environment_provider_config(env_provider, preferred_model)
    if not setting.credential_id or setting.provider not in {"openai", "openrouter", "claude", "qwen", "dashscope"}:
        raise SmartDeckProviderUnavailableError(WORKSPACE_PROVIDER_CONFIGURATION_ERROR)
    credential = None
    if setting and setting.credential_id and setting.provider in {"openai", "openrouter", "claude", "qwen", "dashscope"}:
        credential = (
            db.query(WorkspaceAiCredential)
            .filter(
                WorkspaceAiCredential.id == setting.credential_id,
                WorkspaceAiCredential.workspace_id == deck.workspace_id,
                WorkspaceAiCredential.provider == setting.provider,
                WorkspaceAiCredential.is_active.is_(True),
            )
            .first()
        )
    workspace_api_key = _decrypt_workspace_api_key(credential)
    if workspace_api_key:
        provider = "anthropic" if setting.provider == "claude" else ("dashscope" if setting.provider == "qwen" else setting.provider)
        configured_model = setting.reasoning_model if use_case == "analysis" and setting.reasoning_model else setting.preferred_model
        return {
            "provider": provider,
            "model": _model_for_provider(provider, preferred_model, configured_model),
            "apiKey": workspace_api_key,
            "source": "workspace",
            "credentialLast4": credential.api_key_last4 if credential else None,
        }

    raise SmartDeckProviderUnavailableError(WORKSPACE_PROVIDER_CONFIGURATION_ERROR)


def _resolve_environment_provider_config(provider: str | None, preferred_model: str | None) -> dict:
    if _is_production_mode() and provider != "openai":
        raise SmartDeckProviderUnavailableError(
            "Production environment provider resolution is restricted to OpenAI."
        )
    if provider == "openai":
        if not settings.openai_api_key and not _is_production_mode():
            return {
                "provider": "deterministic",
                "model": None,
                "apiKey": None,
                "source": "fallback",
            }
        return {
            "provider": "openai" if settings.openai_api_key else "missing_openai",
            "model": _model_for_provider("openai", preferred_model),
            "apiKey": settings.openai_api_key or None,
            "source": "environment" if settings.openai_api_key else "missing",
        }
    # DISABLED FOR NOW: OpenRouter / Anthropic environment providers.
    # Keep this logic commented for later multi-provider expansion.
    # if provider == "openrouter":
    #     if not settings.openrouter_api_key and not _is_production_mode():
    #         return {
    #             "provider": "deterministic",
    #             "model": None,
    #             "apiKey": None,
    #             "source": "fallback",
    #         }
    #     return {
    #         "provider": "openrouter" if settings.openrouter_api_key else "missing_openrouter",
    #         "model": _model_for_provider("openrouter", preferred_model),
    #         "apiKey": settings.openrouter_api_key or None,
    #         "source": "environment" if settings.openrouter_api_key else "missing",
    #     }
    # if provider == "anthropic":
    #     if not settings.anthropic_api_key and not _is_production_mode():
    #         return {
    #             "provider": "deterministic",
    #             "model": None,
    #             "apiKey": None,
    #             "source": "fallback",
    #         }
    #     return {
    #         "provider": "anthropic" if settings.anthropic_api_key else "missing_claude",
    #         "model": _model_for_provider("anthropic", preferred_model),
    #         "apiKey": settings.anthropic_api_key or None,
    #         "source": "environment" if settings.anthropic_api_key else "missing",
    #     }
    if provider == "dashscope":
        api_key = settings.effective_qwen_api_key
        if not api_key and not _is_production_mode():
            return {
                "provider": "deterministic",
                "model": None,
                "apiKey": None,
                "source": "fallback",
            }
        return {
            "provider": "dashscope" if api_key else "missing_dashscope",
            "model": _model_for_provider("dashscope", preferred_model),
            "apiKey": api_key or None,
            "source": "environment" if api_key else "missing",
        }
    if settings.openai_api_key:
        return {
            "provider": "openai",
            "model": _model_for_provider("openai", preferred_model),
            "apiKey": settings.openai_api_key,
            "source": "environment",
        }
    if settings.effective_qwen_api_key:
        return {
            "provider": "dashscope",
            "model": _model_for_provider("dashscope", preferred_model),
            "apiKey": settings.effective_qwen_api_key,
            "source": "environment",
        }
    if settings.openrouter_api_key:
        return {
            "provider": "openrouter",
            "model": _model_for_provider("openrouter", preferred_model),
            "apiKey": settings.openrouter_api_key,
            "source": "environment",
        }
    if not _is_production_mode():
        return {
            "provider": "deterministic",
            "model": None,
            "apiKey": None,
            "source": "fallback",
        }
    return {
        "provider": "anthropic" if settings.anthropic_api_key else "missing_provider",
        "model": _model_for_provider("anthropic", preferred_model),
        "apiKey": settings.anthropic_api_key or None,
        "source": "environment" if settings.anthropic_api_key else "missing",
    }


def get_generation_provider_config(
    db: Session,
    deck: Deck,
    preferred_model: str | None,
    *,
    strict: bool = False,
    use_case: str = "smart_deck",
) -> dict:
    config = _resolve_claude_config(db, deck, preferred_model, use_case=use_case)
    if strict and config.get("provider") in INVALID_GENERATION_PROVIDER_VALUES:
        raise SmartDeckProviderUnavailableError("AI generation provider is unavailable.")
    if strict and not config.get("apiKey"):
        raise SmartDeckProviderUnavailableError("AI generation provider credentials are missing.")
    return config


def _require_instant_deck_llm_provider(config: dict) -> None:
    if config.get("provider") in INVALID_GENERATION_PROVIDER_VALUES or not config.get("apiKey"):
        raise SmartDeckProviderUnavailableError("Instant Deck requires an available LLM provider.")


def _safe_generation_failure_message(exc: Exception) -> str:
    if isinstance(exc, GenerationValidationError):
        return "Generated slide output failed validation."
    if isinstance(exc, OperationDeadlineExceeded):
        return "Smart Deck generation exceeded its operation deadline."
    if isinstance(exc, SmartDeckProviderUnavailableError):
        return str(exc)
    code = str(getattr(exc, "code", "") or "").strip()
    if code and re.fullmatch(r"[a-z0-9_\-]+", code):
        return f"AI provider request failed ({code})."
    return "Smart Deck generation failed."


def _require_instant_deck_grounding(
    *,
    requested_slide_ids: list[str],
    generated_by_source_id: dict[str, dict],
    source_fact_package: dict,
) -> None:
    expected_ids = set(requested_slide_ids)
    if set(generated_by_source_id) != expected_ids:
        raise GenerationValidationError(
            {
                "schemaVersion": "generation-validation-failure.v1",
                "reasonCodes": ["instant_deck_complete_slide_coverage_required"],
            }
        )
    allowed_by_slide: dict[str, set[str]] = {slide_id: set() for slide_id in expected_ids}
    shared_allowed_ids: set[str] = set()
    legacy_untyped_facts = not source_fact_package.get("schemaVersion")
    for fact in source_fact_package.get("facts") or []:
        if not isinstance(fact, dict) or not fact.get("id"):
            continue
        source_id = str(fact.get("sourceId") or fact.get("sourceSlideId") or fact.get("slideId") or "")
        source_type = fact.get("sourceType")
        is_slide_fact = source_type == "source_slide" or (source_type is None and legacy_untyped_facts)
        if is_slide_fact and source_id in allowed_by_slide:
            allowed_by_slide[source_id].add(str(fact["id"]))
        elif not is_slide_fact:
            shared_allowed_ids.add(str(fact["id"]))
    for slide_id in expected_ids:
        render_schema = generated_by_source_id.get(slide_id, {}).get("renderSchema") or {}
        analytics = render_schema.get("analytics") if isinstance(render_schema, dict) else {}
        cited_ids = {str(fact_id) for fact_id in (analytics.get("sourceFactIds") or [])} if isinstance(analytics, dict) else set()
        slide_allowed_ids = allowed_by_slide[slide_id]
        allowed_ids = slide_allowed_ids | shared_allowed_ids
        if (
            not slide_allowed_ids
            or not cited_ids
            or not cited_ids.issubset(allowed_ids)
            or cited_ids.isdisjoint(slide_allowed_ids)
        ):
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_source_grounding_required"],
                    "blockedSlideCount": 1,
                }
            )


def _require_llm_only_completed_instant_version(job: GenerationJob, version: DesignVersion) -> None:
    if job.provider not in SUPPORTED_LLM_GENERATION_PROVIDERS or not _provider_model_is_valid(job.provider, job.model):
        raise GenerationValidationError(
            {
                "schemaVersion": "generation-validation-failure.v1",
                "reasonCodes": ["instant_deck_llm_provider_required"],
            }
        )
    result_json = job.result_json if isinstance(job.result_json, dict) else {}
    if (
        result_json.get("generationMode") != "instant_deck"
        or result_json.get("coverageComplete") is not True
        or result_json.get("wholeDeckCoverageComplete") is not True
    ):
        raise GenerationValidationError(
            {
                "schemaVersion": "generation-validation-failure.v1",
                "reasonCodes": ["instant_deck_llm_provenance_required"],
            }
        )
    generated_by_source_id: dict[str, dict] = {}
    for slide in version.generated_slides:
        current_version_id = getattr(slide, "current_version_id", None)
        current_code = _current_code_version(slide)
        if current_version_id and current_code is None:
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_current_code_version_required"],
                }
            )
        effective_code = current_code or _latest_code_version(slide)
        if effective_code is None:
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_llm_provenance_required"],
                }
            )
        try:
            effective_schema = RenderSchema.model_validate(effective_code.render_schema_json).model_dump()
        except (ValidationError, ValueError) as exc:
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_render_schema_invalid"],
                }
            ) from exc
        code_json = effective_code.code_json if isinstance(effective_code.code_json, dict) else {}
        code_provider = str(code_json.get("provider") or "")
        code_model = str(code_json.get("model") or "")
        if (
            code_provider != job.provider
            or code_model != job.model
            or not _provider_model_is_valid(code_provider, code_model)
        ):
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_llm_provenance_required"],
                }
            )
        if slide.render_schema_json != effective_code.render_schema_json:
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_render_schema_identity_required"],
                }
            )
        analytics = effective_schema.get("analytics") if isinstance(effective_schema, dict) else {}
        warnings = analytics.get("qualityWarnings") if isinstance(analytics, dict) else []
        if any("deterministic fallback" in str(warning).lower() for warning in (warnings or [])):
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_non_llm_slide_rejected"],
                    "blockedSlideCount": 1,
                }
            )
        if not slide.source_slide_id:
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_complete_slide_coverage_required"],
                }
            )
        if slide.source_slide_id in generated_by_source_id:
            raise GenerationValidationError(
                {
                    "schemaVersion": "generation-validation-failure.v1",
                    "reasonCodes": ["instant_deck_complete_slide_coverage_required"],
                }
            )
        generated_by_source_id[slide.source_slide_id] = {"renderSchema": effective_schema}
    llm_context = job.llm_context_json if isinstance(job.llm_context_json, dict) else {}
    source_fact_package = llm_context.get("sourceFactPackage") if isinstance(llm_context.get("sourceFactPackage"), dict) else {}
    deck_slide_ids = {slide.id for slide in version.deck.slides}
    selected_slide_ids = list(job.selected_source_slide_ids_json or [])
    if len(selected_slide_ids) != len(set(selected_slide_ids)) or set(selected_slide_ids) != deck_slide_ids:
        raise GenerationValidationError(
            {
                "schemaVersion": "generation-validation-failure.v1",
                "reasonCodes": ["instant_deck_authoritative_deck_coverage_required"],
            }
        )
    _require_instant_deck_grounding(
        requested_slide_ids=selected_slide_ids,
        generated_by_source_id=generated_by_source_id,
        source_fact_package=source_fact_package,
    )


def _instant_deck_version_requires_smart_edit_review(version: DesignVersion) -> bool:
    """A completed Instant Deck version stays provisional for Smart Edit review
    when any generated slide carries a reviewable validation status. Only fully
    valid versions may auto-apply as the accepted baseline."""
    generated_slides = list(getattr(version, "generated_slides", []) or [])
    return not generated_slides or any(
        getattr(slide, "validation_status", None) != "valid"
        for slide in generated_slides
    )


def _auto_apply_completed_instant_deck_version(db: Session, deck: Deck, version: DesignVersion) -> bool:
    """Apply a complete Instant Deck version only when every slide is valid."""
    if _instant_deck_version_requires_smart_edit_review(version):
        return False

    from app.services.platform.shell.shell_service import record_accepted_deck_version

    for prior_version in deck.design_versions:
        if prior_version.id != version.id:
            prior_version.is_active = False
    version.is_active = True
    version.status = "applied"
    version.applied_at = datetime.utcnow()
    deck.current_design_version_id = version.id
    record_accepted_deck_version(
        db,
        deck.id,
        source_surface="instant_deck",
        source_artifact_id=version.id,
        design_version_id=version.id,
        change_summary="Initial Instant Deck generated from the uploaded source deck.",
    )
    return True


def generation_job_is_instant_deck(job: GenerationJob | None) -> bool:
    if job is None:
        return False
    result_value = getattr(job, "result_json", None)
    context_value = getattr(job, "llm_context_json", None)
    result_json = result_value if isinstance(result_value, dict) else {}
    llm_context = context_value if isinstance(context_value, dict) else {}
    if result_json.get("generationMode") == "instant_deck" or llm_context.get("generationMode") == "instant_deck":
        return True
    try:
        workflow_jobs = list(job.deck.workflow_jobs)
    except (AttributeError, TypeError):
        workflow_jobs = []
    return any(
        workflow_job.id == job.id and workflow_job.job_type == "instant_deck_generation"
        for workflow_job in workflow_jobs
    )


def require_publishable_instant_design_version(version: DesignVersion) -> None:
    if version.generation_job is None:
        raise GenerationValidationError(
            {
                "schemaVersion": "generation-validation-failure.v1",
                "reasonCodes": ["instant_deck_llm_provenance_required"],
            }
        )
    if version.render_mode == "html_compiled.v1":
        result_json = version.generation_job.result_json if isinstance(version.generation_job.result_json, dict) else {}
        if (
            version.artifact_type != "full_html_deck.v1"
            or result_json.get("outputContract") != "full_html_deck.v1"
            or result_json.get("coverageComplete") is not True
            or result_json.get("wholeDeckCoverageComplete") is not True
        ):
            raise GenerationValidationError({"schemaVersion": "generation-validation-failure.v1", "reasonCodes": ["instant_html_compilation_required"]})
        from app.services.rendering.render_proof_service import RenderProofRequired, require_complete_render_proofs
        try:
            require_complete_render_proofs(version)
        except RenderProofRequired as exc:
            raise GenerationValidationError({"schemaVersion": "generation-validation-failure.v1", "reasonCodes": ["instant_html_render_proof_required"]}) from exc
        return
    _require_llm_only_completed_instant_version(version.generation_job, version)


def design_version_is_visible(version: DesignVersion) -> bool:
    if not generation_job_is_instant_deck(version.generation_job):
        return True
    try:
        require_publishable_instant_design_version(version)
        return True
    except GenerationValidationError:
        return False


def _build_deterministic_render_payload(selected_slides: list[DeckSlide], prompt: str) -> dict:
    return {
        "designVersionName": "Deterministic Smart Deck Preview",
        "slides": [
            {
                "sourceSlideId": slide.id,
                "slideNumber": idx + 1,
                "title": slide.title or f"Slide {idx + 1}",
                "renderSchema": _build_render_schema(slide, prompt),
            }
            for idx, slide in enumerate(selected_slides)
        ],
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _public_asset_url(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/api/", "/uploads/", "/static/", "data:")):
        return path
    if path.startswith("/home/") or path.startswith("/tmp/"):
        return None
    return f"/{path.lstrip('/')}"


def _load_deck(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.slides).selectinload(DeckSlide.assets),
            selectinload(Deck.workspace).selectinload(Workspace.user).selectinload(User.profile),
            selectinload(Deck.workspace).selectinload(Workspace.company_profiles),
            selectinload(Deck.generation_jobs),
            selectinload(Deck.design_versions).selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(Deck.design_versions).selectinload(DesignVersion.html_compilation),
            selectinload(Deck.design_versions).selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.source_lineage),
            selectinload(Deck.design_versions)
            .selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
            selectinload(Deck.llm_artifacts),
            selectinload(Deck.brand_profile),
            selectinload(Deck.smart_deck_workspace).selectinload(SmartDeckWorkspace.preference),
            selectinload(Deck.smart_deck_workspace).selectinload(SmartDeckWorkspace.messages),
            selectinload(Deck.design_tokens),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def _load_instant_deck(db: Session, deck_id: str) -> Deck | None:
    """Load only relationships used by the Instant Deck read model."""
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.slides).selectinload(DeckSlide.assets),
            selectinload(Deck.generation_jobs),
            selectinload(Deck.design_versions).selectinload(DesignVersion.generation_job),
            selectinload(Deck.design_versions)
            .selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.code_versions),
            selectinload(Deck.design_versions).selectinload(DesignVersion.html_compilation),
            selectinload(Deck.design_versions)
            .selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.source_lineage),
            selectinload(Deck.design_versions)
            .selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
            selectinload(Deck.smart_deck_workspace).selectinload(SmartDeckWorkspace.preference),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def _load_audience_profile(db: Session, audience: str | None) -> dict | None:
    if not audience:
        return None
    profile = db.query(AudienceProfile).filter(AudienceProfile.label == audience).first()
    if profile is None:
        profile = db.query(AudienceProfile).filter(AudienceProfile.label.ilike(f"%{audience}%")).first()
    if profile is None:
        return None
    return {
        "label": profile.label,
        "focus": profile.focus,
        "tone": profile.tone,
    }


def _source_slide_number(slide: DeckSlide) -> int:
    return slide.slide_number or slide.source_page_number or slide.slide_index + 1


def _map_source_slide(slide: DeckSlide) -> dict:
    return map_source_slide_payload(slide)


def _map_job(job: GenerationJob) -> dict:
    result_json = job.result_json if isinstance(job.result_json, dict) else {}
    context = job.llm_context_json if isinstance(job.llm_context_json, dict) else {}
    return {
        "id": job.id,
        "deckId": job.deck_id,
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "prompt": job.prompt,
        "selectedSourceSlideIds": job.selected_source_slide_ids_json or [],
        "styleId": job.style_id,
        "brandProductId": job.brand_product_id,
        "errorMessage": job.error_message,
        "createdAt": _iso(job.created_at) or "",
        "updatedAt": _iso(job.updated_at) or "",
        "completedAt": _iso(job.completed_at),
        "timings": result_json.get("timings") or {},
        "progress": result_json.get("progress") or {},
        "requestedSlideIds": result_json.get("requestedSlideIds") or [],
        "completedSlideIds": result_json.get("completedSlideIds") or [],
        "failedSlideIds": result_json.get("failedSlideIds") or [],
        "coverageComplete": result_json.get("coverageComplete"),
        "wholeDeckCoverageComplete": result_json.get("wholeDeckCoverageComplete"),
        "generationMode": result_json.get("generationMode") or context.get("generationMode") or (
            "instant_deck" if context.get("fullHtmlRequestContextArtifactId") else "standard"
        ),
        "visionExecution": result_json.get("visionExecution"),
    }


def _generated_slide_preview_status(slide: GeneratedSlide, render_proof_status: str) -> str:
    if slide.render_mode == "html_compiled.v1":
        return render_proof_status
    return "ready" if slide.preview_image_url else "pending"


def _map_generated_slide(slide: GeneratedSlide) -> dict:
    latest_code = _latest_code_version(slide)
    current_code = _current_code_version(slide) or latest_code
    source_slide = getattr(slide, "source_slide", None)
    bucket_artifacts = _map_bucket_artifacts(current_code)
    render_schema = RenderSchema.model_validate(slide.render_schema_json).model_dump() if slide.render_schema_json else None
    analytics = render_schema.get("analytics") if isinstance(render_schema, dict) and isinstance(render_schema.get("analytics"), dict) else {}
    quality_warnings = [str(item) for item in analytics.get("qualityWarnings") or []]
    missing_inputs = [str(item) for item in analytics.get("missingInputs") or []]
    quality_flags = ["needs_human_review"] if quality_warnings or missing_inputs or slide.validation_status != "valid" else ["ok"]
    compilation = slide.design_version.html_compilation if slide.render_mode == "html_compiled.v1" else None
    render_proof_status = compilation.render_proof_status if compilation is not None else "pending"
    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "designVersionId": slide.design_version_id,
        "generationJobId": slide.generation_job_id,
        "sourceSlideId": slide.source_slide_id,
        "slideNumber": slide.slide_number,
        "title": slide.title,
        "status": slide.status,
        "renderSchema": render_schema,
        "renderMode": slide.render_mode,
        "sectionId": slide.section_id,
        "sectionSha256": slide.section_sha256,
        "compilationHash": slide.compilation_hash,
        "sourceSlideIds": (
            [entry.source_slide_id for entry in slide.source_lineage]
            if slide.render_mode == "html_compiled.v1"
            else ([slide.source_slide_id] if slide.source_slide_id else [])
        ),
        "renderProofStatus": render_proof_status,
        "designRationale": analytics.get("designRationale") or analytics.get("slidePurpose"),
        "speakerNotes": analytics.get("speakerNotes"),
        "sourceFactIds": analytics.get("sourceFactIds") or [],
        "sourceFactsUsed": analytics.get("sourceFactsUsed") or [],
        "assumptions": analytics.get("assumptions") or [],
        "missingInputs": missing_inputs,
        "qualityWarnings": quality_warnings,
        "confidence": analytics.get("confidence"),
        "qualityFlags": quality_flags,
        "designTokens": None if slide.render_mode == "html_compiled.v1" else slide.design_tokens_json,
        "previewImageUrl": _public_asset_url(slide.preview_image_url),
        # Compiled HTML is itself the canonical generated preview artifact; it
        # intentionally has no raster preview_image_url. Report its browser
        # proof state instead of leaving a proven artifact permanently pending.
        "previewStatus": _generated_slide_preview_status(slide, render_proof_status),
        "schemaStatus": "ready" if slide.render_schema_json else "unavailable",
        "validationStatus": slide.validation_status,
        "elements": [_map_generated_slide_element(element) for element in sorted(slide.elements, key=lambda item: item.z_index)],
        "createdAt": _iso(slide.created_at) or "",
        "updatedAt": _iso(slide.updated_at) or "",
        "generated_slide_id": slide.id,
        "slide_index": slide.slide_number,
        "archetype_id": getattr(source_slide, "role", None),
        "current_version_id": slide.current_version_id or (current_code.id if current_code else None),
        "current_design_version_id": slide.design_version_id,
        "version_number": current_code.version_number if current_code else None,
        "render_schema_json": render_schema,
        "bucket_render_schema_key": _render_schema_bucket_key(slide, current_code),
        "bucket_code_key": bucket_artifacts.get("code_key"),
        "bucket_artifacts": bucket_artifacts,
        "variantId": analytics.get("deckVariantId"),
        "variantLabel": analytics.get("deckVariantLabel"),
        "variantRationale": analytics.get("deckVariantRationale"),
        "archetypeId": analytics.get("slideArchetypeId") or getattr(source_slide, "role", None),
        "archetypeLabel": analytics.get("slideArchetypeLabel"),
        "narrativeRole": analytics.get("narrativeRole"),
    }


def _normalize_label_text(value: object, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return None
    return normalized[:max_length]


def _resolved_variant_metadata(variant_id: object, variant_rationale: object) -> dict[str, str] | None:
    if not isinstance(variant_id, str):
        return None
    normalized_id = variant_id.strip().lower()
    variant = INSTANT_DECK_VARIANT_MAP.get(normalized_id)
    if variant is None:
        return None
    rationale = _normalize_label_text(variant_rationale, max_length=600)
    return {
        "id": normalized_id,
        "label": str(variant.get("label") or normalized_id.replace("-", " ").title())[:120],
        "rationale": rationale or str(variant.get("description") or "")[:600],
    }


def _resolved_archetype_metadata(archetype_id: object, narrative_role: object) -> dict[str, str | None] | None:
    if not isinstance(archetype_id, str):
        return None
    normalized_id = archetype_id.strip().lower()
    if normalized_id not in VALID_SLIDE_ARCHETYPE_IDS:
        return None
    return {
        "id": normalized_id,
        "label": SLIDE_ARCHETYPE_LABEL_MAP.get(normalized_id, normalized_id.replace("-", " ").title())[:120],
        "narrativeRole": _normalize_label_text(narrative_role, max_length=160),
    }


def _normalized_variant_candidate(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in VALID_INSTANT_DECK_VARIANT_IDS:
        return normalized
    for variant_id, variant in INSTANT_DECK_VARIANT_MAP.items():
        label = str(variant.get("label") or "").strip().lower()
        if normalized == label:
            return variant_id
    return None


def _normalized_archetype_candidate(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in VALID_SLIDE_ARCHETYPE_IDS:
        return normalized
    dashed = normalized.replace("_", "-").replace(" ", "-")
    if dashed in VALID_SLIDE_ARCHETYPE_IDS:
        return dashed
    underscored = normalized.replace("-", "_").replace(" ", "_")
    if underscored in VALID_SLIDE_ARCHETYPE_IDS:
        return underscored
    return None


def _normalize_instant_deck_payload_metadata(render_payload: dict) -> dict:
    normalized = copy.deepcopy(render_payload)
    slides_payload = normalized.get("slides") if isinstance(normalized.get("slides"), list) else []
    first_slide = slides_payload[0] if slides_payload and isinstance(slides_payload[0], dict) else {}
    first_render_schema = first_slide.get("renderSchema") if isinstance(first_slide.get("renderSchema"), dict) else {}
    first_analytics = first_render_schema.get("analytics") if isinstance(first_render_schema.get("analytics"), dict) else {}

    root_variant_id = _normalized_variant_candidate(normalized.get("variantId"))
    if root_variant_id is None:
        root_variant_id = _normalized_variant_candidate(first_analytics.get("deckVariantId"))
    if root_variant_id is None:
        root_variant_id = _normalized_variant_candidate(first_analytics.get("deckVariantLabel"))
    if root_variant_id is not None:
        normalized["variantId"] = root_variant_id

    if not _normalize_label_text(normalized.get("variantRationale"), max_length=600):
        analytics_rationale = _normalize_label_text(first_analytics.get("deckVariantRationale"), max_length=600)
        if analytics_rationale:
            normalized["variantRationale"] = analytics_rationale

    for slide_payload in slides_payload:
        if not isinstance(slide_payload, dict):
            continue
        render_schema = slide_payload.get("renderSchema") if isinstance(slide_payload.get("renderSchema"), dict) else {}
        analytics = render_schema.get("analytics") if isinstance(render_schema.get("analytics"), dict) else {}
        archetype_id = _normalized_archetype_candidate(slide_payload.get("archetypeId"))
        if archetype_id is None:
            archetype_id = _normalized_archetype_candidate(analytics.get("slideArchetypeId"))
        if archetype_id is None:
            archetype_id = _normalized_archetype_candidate(analytics.get("slideArchetypeLabel"))
        if archetype_id is not None:
            slide_payload["archetypeId"] = archetype_id
        if not _normalize_label_text(slide_payload.get("narrativeRole"), max_length=160):
            analytics_role = _normalize_label_text(analytics.get("narrativeRole"), max_length=160)
            if analytics_role:
                slide_payload["narrativeRole"] = analytics_role
    return normalized


def _map_generated_slide_element_version(version: GeneratedSlideElementVersion) -> dict:
    return {
        "id": version.id,
        "elementId": version.element_id,
        "generatedSlideId": version.generated_slide_id,
        "designVersionId": version.design_version_id,
        "versionNumber": version.version_number,
        "source": version.source,
        "status": version.status,
        "style": version.style_json,
        "content": version.content_json,
        "changeSummary": version.change_summary,
        "createdAt": _iso(version.created_at) or "",
    }


def _map_generated_slide_element(element: GeneratedSlideElement) -> dict:
    versions = sorted(element.versions, key=lambda item: item.version_number, reverse=True)
    return {
        "id": element.id,
        "generatedSlideId": element.generated_slide_id,
        "deckId": element.deck_id,
        "designVersionId": element.design_version_id,
        "sourceSlideId": element.source_slide_id,
        "elementKey": element.element_key,
        "elementType": element.element_type,
        "parentElementId": element.parent_element_id,
        "zIndex": element.z_index,
        "x": element.x,
        "y": element.y,
        "width": element.width,
        "height": element.height,
        "rotation": element.rotation,
        "locked": element.locked,
        "visible": element.visible,
        "style": element.style_json,
        "content": element.content_json,
        "versions": [_map_generated_slide_element_version(version) for version in versions],
        "createdAt": _iso(element.created_at) or "",
        "updatedAt": _iso(element.updated_at) or "",
    }


def _map_design_version(version: DesignVersion) -> dict:
    slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
    changed_slide_ids = [slide.source_slide_id or slide.id for slide in slides]
    generation_job = getattr(version, "generation_job", None)
    llm_context = generation_job.llm_context_json if generation_job and isinstance(generation_job.llm_context_json, dict) else {}
    subject_context = llm_context.get("subjectContext") if isinstance(llm_context.get("subjectContext"), dict) else {}
    selected_element_id = subject_context.get("selectedElementId") or llm_context.get("selectedElementId")
    validation_statuses = {str(slide.validation_status or "unknown") for slide in slides}
    if "invalid" in validation_statuses:
        validation_status = "invalid"
    elif "warning" in validation_statuses:
        validation_status = "warning"
    elif validation_statuses == {"valid"}:
        validation_status = "valid"
    else:
        validation_status = "unknown"
    preview_asset_url = next((_public_asset_url(slide.preview_image_url) for slide in slides if slide.preview_image_url), None)
    source_slide_ids = [slide.source_slide_id for slide in slides if slide.source_slide_id]
    selected_element_ids = [selected_element_id] if isinstance(selected_element_id, str) and selected_element_id else []
    prompt_task = subject_context.get("actionId") or subject_context.get("selectedSubject") or (generation_job.prompt if generation_job else None)
    compilation = version.html_compilation if version.render_mode == "html_compiled.v1" else None
    manifest = compilation.manifest_json if compilation is not None and isinstance(compilation.manifest_json, dict) else {}
    return {
        "id": version.id,
        "version_id": version.id,
        "deckId": version.deck_id,
        "deck_id": version.deck_id,
        "generationJobId": version.generation_job_id,
        "name": version.name,
        "status": version.status,
        "isActive": version.is_active,
        "summary": version.summary,
        "artifactType": version.artifact_type,
        "renderMode": version.render_mode,
        "htmlArtifact": ({
            "id": compilation.sanitized_html_artifact_id,
            "sha256": manifest.get("contentHash"),
            "slideCount": len(manifest.get("slides") or []),
            "parserVersion": manifest.get("parserVersion"),
            "compilerVersion": compilation.compiler_version,
            "sanitizerPolicyVersion": compilation.sanitizer_policy_version,
            "rendererVersion": compilation.renderer_version,
        } if compilation is not None else None),
        "renderProofStatus": compilation.render_proof_status if compilation is not None else None,
        "generatedSlides": [_map_generated_slide(slide) for slide in slides],
        "createdAt": _iso(version.created_at) or "",
        "updatedAt": _iso(version.updated_at) or "",
        "appliedAt": _iso(version.applied_at),
        "discardedAt": _iso(version.discarded_at),
        "state": _design_version_state(version),
        "source": _design_version_source(version),
        "changed_slide_ids": changed_slide_ids,
        "sourceSlideIds": source_slide_ids,
        "source_slide_ids": source_slide_ids,
        "selectedElementIds": selected_element_ids,
        "selected_element_ids": selected_element_ids,
        "promptTask": prompt_task,
        "prompt_task": prompt_task,
        "audience": subject_context.get("audience") or (llm_context.get("deck") or {}).get("audience"),
        "deckType": subject_context.get("deckType"),
        "deck_type": subject_context.get("deckType"),
        "model": generation_job.model if generation_job else None,
        "renderSchemaJson": slides[0].render_schema_json if len(slides) == 1 else None,
        "render_schema_json": slides[0].render_schema_json if len(slides) == 1 else None,
        "validationStatus": validation_status,
        "validation_status": validation_status,
        "previewAssetUrl": preview_asset_url,
        "preview_asset_url": preview_asset_url,
        "previewAssetKey": version.bucket_manifest_key,
        "preview_asset_key": version.bucket_manifest_key,
        "errorMessage": generation_job.error_message if generation_job else None,
        "error_message": generation_job.error_message if generation_job else None,
        "created_at": _iso(version.created_at) or "",
    }


def _map_code_version(code_version: GeneratedSlideCodeVersion, *, render_schema_override: dict | None = None) -> dict:
    return {
        "id": code_version.id,
        "generatedSlideId": code_version.generated_slide_id,
        "versionNumber": code_version.version_number,
        "codeKind": code_version.code_kind,
        "schemaVersion": code_version.schema_version,
        "renderSchema": RenderSchema.model_validate(render_schema_override or code_version.render_schema_json).model_dump(),
        "codeJson": code_version.code_json,
        "bucketRenderSchemaKey": code_version.bucket_render_schema_key,
        "bucketCodeKey": code_version.bucket_code_key,
        "bucketThumbnailKey": code_version.bucket_thumbnail_key,
        "status": code_version.status,
        "validationErrors": code_version.validation_errors_json,
        "createdAt": _iso(code_version.created_at) or "",
    }


def _latest_code_version(slide: GeneratedSlide) -> GeneratedSlideCodeVersion | None:
    code_versions = list(getattr(slide, "code_versions", []) or [])
    if not code_versions:
        return None
    return sorted(code_versions, key=lambda item: item.version_number, reverse=True)[0]


def _current_code_version(slide: GeneratedSlide) -> GeneratedSlideCodeVersion | None:
    current_version_id = getattr(slide, "current_version_id", None)
    if not current_version_id:
        return None
    return next((version for version in list(getattr(slide, "code_versions", []) or []) if version.id == current_version_id), None)


def _render_schema_bucket_key(slide: GeneratedSlide, code_version: GeneratedSlideCodeVersion | None) -> str | None:
    if code_version is None:
        return None
    if code_version.bucket_render_schema_key:
        return code_version.bucket_render_schema_key
    code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
    storage_path = code_json.get("bucketRenderSchemaKey") or code_json.get("renderSchemaStoragePath")
    if isinstance(storage_path, str):
        return storage_path
    return (
        f"decks/{slide.deck_id}/design-versions/{slide.design_version_id}/slides/"
        f"{slide.id}/code-versions/{code_version.id}/render_schema.json"
    )


def _map_bucket_artifacts(code_version: GeneratedSlideCodeVersion | None) -> dict:
    if code_version is None:
        return {}
    code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
    return {
        "render_schema_key": code_version.bucket_render_schema_key or code_json.get("bucketRenderSchemaKey") or code_json.get("renderSchemaStoragePath"),
        "code_key": code_version.bucket_code_key or code_json.get("bucketCodeJsonKey") or code_json.get("codeJsonStoragePath"),
        "thumbnail_key": code_version.bucket_thumbnail_key or code_json.get("bucketThumbnailKey"),
        "render_schema_url": None,
        "thumbnail_url": None,
    }


def _design_version_state(version: DesignVersion) -> str:
    if version.status == "archived":
        return "archived"
    if version.status == "discarded":
        return "discarded"
    if version.is_active or version.status in {"applied", "saved"}:
        return "saved"
    return "preview"


def _design_version_source(version: DesignVersion) -> str:
    if version.status == "restored":
        return "restore"
    if version.generation_job_id:
        return "smart_edit"
    return "manual"


def _instant_deck_version_is_complete(
    payload: CreateSmartDeckGenerationJobInput,
    created_slide_ids: list[str],
    slide_failures: list[dict],
    *,
    all_source_slide_ids: list[str] | None = None,
) -> bool:
    required_source_slide_ids = all_source_slide_ids or payload.selectedSourceSlideIds
    return (
        payload.generationMode == "instant_deck"
        and set(payload.selectedSourceSlideIds) == set(required_source_slide_ids)
        and not slide_failures
        and len(created_slide_ids) == len(required_source_slide_ids)
    )


def _partial_generation_must_fail(
    payload: CreateSmartDeckGenerationJobInput,
    slide_results: list[dict],
    slide_failures: list[dict],
) -> bool:
    return bool(
        slide_failures
        and (
            payload.generationMode == "instant_deck"
            or not settings.allow_partial_batch_success
            or not slide_results
        )
    )


def _workspace_generation_contract(
    *,
    source_slides: list[DeckSlide],
    jobs: list[GenerationJob],
    saved_version: DesignVersion | None,
    candidate_version: DesignVersion | None,
    resolved_version: DesignVersion | None,
    saved_deck_version: DesignBatch | None = None,
) -> dict:
    requested_ids: list[str] = []
    if resolved_version is not None and resolved_version.generation_job_id:
        generation_job = next((job for job in jobs if job.id == resolved_version.generation_job_id), None)
        if generation_job is not None:
            requested_ids = list(generation_job.selected_source_slide_ids_json or [])
    if not requested_ids:
        requested_ids = [slide.id for slide in source_slides]

    generated_ids = [
        slide.source_slide_id
        for slide in (resolved_version.generated_slides if resolved_version is not None else [])
        if slide.source_slide_id
    ]
    generated_id_set = set(generated_ids)
    missing_ids = [slide_id for slide_id in requested_ids if slide_id not in generated_id_set]
    coverage_complete = bool(requested_ids) and not missing_ids and len(generated_id_set) == len(requested_ids)

    latest_job = jobs[0] if jobs else None
    if resolved_version is None:
        latest_status = str(latest_job.status or "").lower() if latest_job is not None else ""
        status = "queued" if latest_status == "queued" else "running" if latest_status in {"running", "processing"} else "no_version"
    elif not coverage_complete:
        status = "incomplete"
    elif any(not slide.preview_image_url for slide in resolved_version.generated_slides):
        status = "preview_pending"
    elif saved_version is not None and resolved_version.id == saved_version.id:
        status = "saved_ready"
    else:
        status = "candidate_ready"

    return {
        "savedDeckVersionId": saved_deck_version.id if saved_deck_version else None,
        "savedDeckVersionNumber": saved_deck_version.version_number if saved_deck_version else None,
        "savedDesignVersionId": saved_version.id if saved_version else None,
        "candidateDesignVersionId": candidate_version.id if candidate_version else None,
        "resolvedDesignVersionId": resolved_version.id if resolved_version else None,
        "generatedWorkspaceStatus": status,
        "requestedSourceSlideIds": requested_ids,
        "generatedSourceSlideIds": generated_ids,
        "missingSourceSlideIds": missing_ids,
        "coverageComplete": coverage_complete,
    }


def _map_product_spine_slide(slide: GeneratedSlide) -> dict:
    mapped = _map_generated_slide(slide)
    return {
        "generated_slide_id": mapped["generated_slide_id"],
        "slide_index": mapped["slide_index"],
        "title": mapped["title"],
        "archetype_id": mapped["archetype_id"],
        "current_version_id": mapped["current_version_id"],
        "current_design_version_id": mapped["current_design_version_id"],
        "version_number": mapped["version_number"],
        "render_schema_json": mapped["render_schema_json"],
    }


def _map_product_spine_design_version(version: DesignVersion) -> dict:
    mapped = _map_design_version(version)
    return {
        "id": mapped["id"],
        "state": mapped["state"],
        "source": mapped["source"],
        "changed_slide_ids": mapped["changed_slide_ids"],
        "created_at": mapped["created_at"],
    }


def _set_code_version_lifecycle(code_version: GeneratedSlideCodeVersion, lifecycle: str) -> None:
    code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
    code_version.code_json = {**code_json, "lifecycle": lifecycle}


def _code_version_lifecycle(code_version: GeneratedSlideCodeVersion) -> str | None:
    code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
    lifecycle = code_json.get("lifecycle") or code_json.get("state")
    return lifecycle if isinstance(lifecycle, str) else None


def _record_design_version_snapshot_artifact(db: Session, deck_id: str, version: DesignVersion, reason: str) -> None:
    slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
    _record_llm_artifact(
        db,
        deck_id=deck_id,
        artifact_type="design_version_slide_versions_snapshot",
        artifact_key=f"{version.id}:{reason}",
        summary=f"Design version slide snapshot for {version.id} ({reason}).",
        payload_json={
            "designVersionId": version.id,
            "reason": reason,
            "slides": [_map_product_spine_slide(slide) for slide in slides],
        },
        metrics_json={"slideCount": len(slides)},
    )


def _design_version_manifest_payload(version: DesignVersion, state: str, reason: str | None = None) -> dict:
    slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
    first_render_schema = slides[0].render_schema_json if slides and isinstance(slides[0].render_schema_json, dict) else {}
    first_analytics = first_render_schema.get("analytics") if isinstance(first_render_schema.get("analytics"), dict) else {}
    return {
        "deck_id": version.deck_id,
        "design_version_id": version.id,
        "designVersionId": version.id,
        "deckVariantId": first_analytics.get("deckVariantId"),
        "deckVariantLabel": first_analytics.get("deckVariantLabel"),
        "deckVariantRationale": first_analytics.get("deckVariantRationale"),
        "state": state,
        "status": version.status,
        "isActive": version.is_active,
        "reason": reason,
        "generationJobId": version.generation_job_id,
        "generatedSlideIds": [slide.id for slide in slides],
        "slides": [
            {
                "generated_slide_id": slide.id,
                "source_slide_id": slide.source_slide_id,
                "slideArchetypeId": ((slide.render_schema_json or {}).get("analytics") or {}).get("slideArchetypeId"),
                "slideArchetypeLabel": ((slide.render_schema_json or {}).get("analytics") or {}).get("slideArchetypeLabel"),
                "narrativeRole": ((slide.render_schema_json or {}).get("analytics") or {}).get("narrativeRole"),
                "current_version_id": slide.current_version_id,
                "render_schema_json_cached": bool(slide.render_schema_json),
                "code_versions": [
                    {
                        "code_version_id": code_version.id,
                        "lifecycle": _code_version_lifecycle(code_version),
                        "render_schema_key": code_version.bucket_render_schema_key,
                        "code_key": code_version.bucket_code_key,
                        "thumbnail_key": code_version.bucket_thumbnail_key,
                    }
                    for code_version in sorted(slide.code_versions, key=lambda item: item.version_number)
                ],
            }
            for slide in slides
        ],
        "updatedAt": datetime.utcnow().isoformat() + "Z",
    }


def _rewrite_design_version_manifest(db: Session, version: DesignVersion, state: str, reason: str) -> None:
    payload = _design_version_manifest_payload(version, state, reason)
    manifest_artifact = _write_design_version_manifest_json_artifact(
        user_id=version.deck.user_id if version.deck else None,
        deck_id=version.deck_id,
        design_version_id=version.id,
        manifest_json=payload,
    )
    version.bucket_manifest_key = manifest_artifact["storagePath"]
    _record_llm_artifact(
        db,
        deck_id=version.deck_id,
        artifact_type="smart_deck_design_version_manifest",
        artifact_key=f"{version.id}:{reason}",
        summary=f"Manifest for Smart Deck design version {version.id} updated to {state}.",
        payload_json={
            **payload,
            "bucketManifestKey": manifest_artifact["storagePath"],
            "manifestHash": manifest_artifact["manifestHash"],
        },
        metrics_json={"generatedSlideCount": len(version.generated_slides)},
    )


def _map_workspace_state(workspace: SmartDeckWorkspace) -> dict:
    return {
        "id": workspace.id,
        "deckId": workspace.deck_id,
        "userId": workspace.user_id,
        "activeDesignVersionId": workspace.active_design_version_id,
        "activeSourceSlideId": workspace.active_source_slide_id,
        "activeGeneratedSlideId": workspace.active_generated_slide_id,
        "selectedElementId": workspace.selected_element_id,
        "status": workspace.status,
        "createdAt": _iso(workspace.created_at) or "",
        "updatedAt": _iso(workspace.updated_at) or "",
    }


def _map_preference(preference: SmartDeckPreference) -> dict:
    return {
        "id": preference.id,
        "workspaceId": preference.workspace_id,
        "deckId": preference.deck_id,
        "userId": preference.user_id,
        "selectedSourceSlideIds": preference.selected_source_slide_ids_json or [],
        "activeSourceSlideId": preference.active_source_slide_id,
        "activeDesignVersionId": preference.active_design_version_id,
        "activeGeneratedSlideId": preference.active_generated_slide_id,
        "selectedElementId": preference.selected_element_id,
        "audience": preference.audience,
        "deckType": preference.deck_type,
        "preferredModel": preference.preferred_model,
        "selectedSubject": preference.selected_subject,
        "selectedActionId": preference.selected_action_id,
        "zoomLevel": preference.zoom_level,
        "canvasFitMode": preference.canvas_fit_mode,
        "rightPanelOpen": preference.right_panel_open,
        "slideRailOpen": preference.slide_rail_open,
        "updatedAt": _iso(preference.updated_at) or "",
    }


def _map_message(message: SmartDeckMessage) -> dict:
    return {
        "id": message.id,
        "workspaceId": message.workspace_id,
        "deckId": message.deck_id,
        "generationJobId": message.generation_job_id,
        "role": message.role,
        "content": message.content,
        "selectedSourceSlideIds": message.selected_source_slide_ids_json or [],
        "metadata": message.metadata_json,
        "createdAt": _iso(message.created_at) or "",
    }


def _map_design_token(token: DesignToken) -> dict:
    return {
        "id": token.id,
        "deckId": token.deck_id,
        "designVersionId": token.design_version_id,
        "generatedSlideId": token.generated_slide_id,
        "tokenName": token.token_name,
        "tokenValue": token.token_value,
        "tokenType": token.token_type,
        "source": token.source,
        "createdAt": _iso(token.created_at) or "",
        "updatedAt": _iso(token.updated_at) or "",
    }


def _ensure_workspace_state(db: Session, deck: Deck) -> tuple[SmartDeckWorkspace, SmartDeckPreference]:
    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck.id).first()
    if workspace is None:
        workspace = SmartDeckWorkspace(
            id=generate_id("sdws"),
            deck_id=deck.id,
            user_id=deck.user_id,
            status="ready",
        )
        db.add(workspace)
        db.flush()

    preference = db.query(SmartDeckPreference).filter(SmartDeckPreference.workspace_id == workspace.id).first()
    if preference is None:
        first_slide = sorted(deck.slides, key=lambda item: (item.slide_index, item.id))[0] if deck.slides else None
        active_version = next((version for version in deck.design_versions if version.is_active), None)
        active_slides = sorted(active_version.generated_slides, key=lambda item: item.slide_number) if active_version else []
        preference = SmartDeckPreference(
            id=generate_id("sdpref"),
            workspace_id=workspace.id,
            deck_id=deck.id,
            user_id=deck.user_id,
            selected_source_slide_ids_json=[first_slide.id] if first_slide else [],
            active_source_slide_id=workspace.active_source_slide_id or (first_slide.id if first_slide else None),
            active_design_version_id=workspace.active_design_version_id or (active_version.id if active_version else None),
            active_generated_slide_id=workspace.active_generated_slide_id or (active_slides[0].id if active_slides else None),
            audience=deck.audience,
            deck_type="vc_fund_pitch" if deck.audience and any(marker in deck.audience.lower() for marker in ("lp", "fund", "partner")) else "startup_pitch",
            preferred_model=settings.anthropic_model,
            selected_subject=first_slide.role if first_slide else None,
        )
        db.add(preference)
        db.flush()

    return workspace, preference


def _ensure_instant_deck_workspace_state(
    db: Session,
    deck: Deck,
) -> tuple[SmartDeckWorkspace, SmartDeckPreference]:
    """Create only persisted selection state; never infer provider preferences."""
    workspace = deck.smart_deck_workspace
    if workspace is None:
        workspace = SmartDeckWorkspace(
            id=generate_id("sdws"),
            deck_id=deck.id,
            user_id=deck.user_id,
            status="ready",
        )
        db.add(workspace)
        db.flush()

    preference = workspace.preference
    if preference is None:
        first_slide = sorted(deck.slides, key=lambda item: (item.slide_index, item.id))[0] if deck.slides else None
        active_version = next(
            (
                version
                for version in deck.design_versions
                if version.is_active and version.render_mode == "html_compiled.v1"
            ),
            None,
        )
        active_slides = sorted(active_version.generated_slides, key=lambda item: item.slide_number) if active_version else []
        preference = SmartDeckPreference(
            id=generate_id("sdpref"),
            workspace_id=workspace.id,
            deck_id=deck.id,
            user_id=deck.user_id,
            selected_source_slide_ids_json=[slide.id for slide in sorted(deck.slides, key=lambda item: (item.slide_index, item.id))],
            active_source_slide_id=first_slide.id if first_slide else None,
            active_design_version_id=active_version.id if active_version else None,
            active_generated_slide_id=active_slides[0].id if active_slides else None,
            audience=deck.audience,
            deck_type="startup_pitch",
            preferred_model=None,
            selected_subject=first_slide.role if first_slide else None,
        )
        db.add(preference)
        db.flush()

    return workspace, preference


def _record_smart_deck_message(
    db: Session,
    *,
    workspace_id: str,
    deck_id: str,
    role: str,
    content: str,
    generation_job_id: str | None = None,
    selected_source_slide_ids: list[str] | None = None,
    metadata_json: dict | None = None,
) -> SmartDeckMessage:
    if generation_job_id and db.get(GenerationJob, generation_job_id) is None:
        # Failure telemetry must not hide the original provider error behind a
        # secondary FK failure when a durable workflow id has no GenerationJob row.
        generation_job_id = None
    message = SmartDeckMessage(
        id=generate_id("sdmsg"),
        workspace_id=workspace_id,
        deck_id=deck_id,
        generation_job_id=generation_job_id,
        role=role,
        content=content,
        selected_source_slide_ids_json=selected_source_slide_ids or [],
        metadata_json=metadata_json,
    )
    db.add(message)
    return message


def _record_design_tokens(
    db: Session,
    *,
    deck_id: str,
    design_version_id: str,
    generated_slide_id: str | None = None,
    design_tokens: dict[str, str] | None = None,
) -> None:
    for token_name, token_value in (design_tokens or DESIGN_TOKENS).items():
        db.add(
            DesignToken(
                id=generate_id("dstok"),
                deck_id=deck_id,
                design_version_id=design_version_id,
                generated_slide_id=generated_slide_id,
                token_name=token_name,
                token_value=token_value,
                token_type="font" if token_name.endswith("Font") else "color",
                source="brand_profile" if design_tokens else "smart_deck_llm",
            )
        )


def _render_element_type(schema_type: str) -> str:
    if schema_type == "chart_placeholder":
        return "chart"
    return schema_type


def _persist_generated_slide_elements(
    db: Session,
    *,
    deck_id: str,
    design_version_id: str,
    generated_slide: GeneratedSlide,
    source_slide_id: str | None,
    render_schema: dict,
) -> list[GeneratedSlideElement]:
    persisted: list[GeneratedSlideElement] = []
    for z_index, render_element in enumerate(render_schema.get("elements", []), start=1):
        element_id = generate_id("gselem")
        style_json = {
            key: render_element.get(key)
            for key in ["fontSize", "fontWeight", "colorToken", "fillToken", "assetUrl"]
            if render_element.get(key) is not None
        }
        content_json = {
            "text": render_element.get("text"),
            "renderElementId": render_element.get("id"),
            "renderType": render_element.get("type"),
            "analyticsKey": render_element.get("analyticsKey"),
        }
        element = GeneratedSlideElement(
            id=element_id,
            generated_slide_id=generated_slide.id,
            deck_id=deck_id,
            design_version_id=design_version_id,
            source_slide_id=source_slide_id,
            element_key=str(render_element.get("id") or element_id),
            element_type=_render_element_type(str(render_element.get("type") or "shape")),
            z_index=int(render_element.get("zIndex") or z_index),
            x=int(render_element.get("x") or 0),
            y=int(render_element.get("y") or 0),
            width=int(render_element.get("width") or 1),
            height=int(render_element.get("height") or 1),
            rotation=0,
            locked=False,
            visible=True,
            style_json=style_json,
            content_json=content_json,
        )
        db.add(element)
        db.flush()
        db.add(
            GeneratedSlideElementVersion(
                id=generate_id("gsever"),
                element_id=element.id,
                generated_slide_id=generated_slide.id,
                design_version_id=design_version_id,
                version_number=1,
                source="initial_generation",
                status="active",
                style_json=style_json,
                content_json=content_json,
                change_summary="Initial element version from validated render_schema_json.",
            )
        )
        persisted.append(element)
    return persisted


SOURCE_FACT_MAX_TEXT_LENGTH = 320
SOURCE_FACT_MAX_PER_SLIDE = 8
SOURCE_FACT_MAX_TOTAL = 80


def _normalise_fact_text(value: object, *, limit: int = SOURCE_FACT_MAX_TEXT_LENGTH) -> str:
    text = str(value if value is not None else "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit].strip()


def _fact_candidates_from_text(text: str | None) -> list[str]:
    normalised = _normalise_fact_text(text, limit=5000)
    if not normalised:
        return []
    parts = [
        part.strip(" -:\t")
        for part in re.split(r"(?<=[.!?])\s+|\n+|[•·]\s*", normalised)
        if part.strip(" -:\t")
    ]
    if len(parts) <= 1:
        parts = [
            part.strip(" -:\t")
            for part in re.split(r"\s{2,}|;\s+", normalised)
            if part.strip(" -:\t")
        ]
    return [_normalise_fact_text(part) for part in parts if len(part) >= 8]


def _append_source_fact(
    facts: list[dict],
    seen: set[str],
    *,
    source_type: str,
    source_id: str,
    text: object,
    confidence: str,
    scope: str,
    field: str | None = None,
) -> None:
    fact_text = _normalise_fact_text(text)
    if not fact_text:
        return
    key = f"{source_type}:{source_id}:{field or ''}:{fact_text.lower()}"
    if key in seen:
        return
    seen.add(key)
    classification = classify_source_fact(
        text=fact_text,
        source_type=source_type,
        field=field,
        confidence=confidence,
    )
    facts.append(
        {
            "id": f"fact_{len(facts) + 1}",
            "sourceType": source_type,
            "sourceId": source_id,
            "field": field,
            "text": fact_text,
            "confidence": confidence,
            "scope": scope,
            **classification,
        }
    )


def _bound_source_facts(facts: list[dict], selected_slides: list[DeckSlide]) -> list[dict]:
    if len(facts) <= SOURCE_FACT_MAX_TOTAL:
        return facts

    slide_fact_indexes = {slide.id: [] for slide in selected_slides}
    shared_fact_indexes: list[int] = []
    for index, fact in enumerate(facts):
        source_id = str(fact.get("sourceId") or "")
        if fact.get("sourceType") == "source_slide":
            if source_id in slide_fact_indexes:
                slide_fact_indexes[source_id].append(index)
        else:
            shared_fact_indexes.append(index)

    selected_indexes: set[int] = set()
    for indexes in slide_fact_indexes.values():
        if indexes:
            selected_indexes.add(indexes[0])
        substantive_index = next(
            (index for index in indexes if facts[index].get("field") not in {"title", "role"}),
            None,
        )
        if substantive_index is not None:
            selected_indexes.add(substantive_index)
        elif len(indexes) > 1:
            selected_indexes.add(indexes[1])

    fact_limit = max(
        SOURCE_FACT_MAX_TOTAL,
        len(selected_indexes) + len(shared_fact_indexes),
    )

    for index in shared_fact_indexes:
        if len(selected_indexes) >= fact_limit:
            break
        selected_indexes.add(index)

    remaining_by_slide = deque(
        deque(index for index in indexes if index not in selected_indexes)
        for indexes in slide_fact_indexes.values()
        if any(index not in selected_indexes for index in indexes)
    )
    while remaining_by_slide and len(selected_indexes) < fact_limit:
        indexes = remaining_by_slide.popleft()
        selected_indexes.add(indexes.popleft())
        if indexes:
            remaining_by_slide.append(indexes)

    return [fact for index, fact in enumerate(facts) if index in selected_indexes]


def _source_slide_fact_counts(facts: list[dict], selected_slides: list[DeckSlide]) -> dict[str, int]:
    counts = {slide.id: 0 for slide in selected_slides}
    for fact in facts:
        source_id = str(fact.get("sourceId") or "")
        if fact.get("sourceType") == "source_slide" and source_id in counts:
            counts[source_id] += 1
    return counts


_SOURCE_FACT_GROUNDING_RULES = (
    "Use only these sourceFacts for factual claims.",
    "If a needed fact is missing, put the gap in renderSchema.analytics.missingInputs.",
    "Do not upgrade weak facts into metrics, customer names, commitments, returns, legal claims, or regulatory claims.",
    "Every generated slide should list relevant fact IDs in renderSchema.analytics.sourceFactIds.",
    "Every generated slide should list readable fact labels or excerpts in renderSchema.analytics.sourceFactsUsed.",
    "Facts include factType, evidenceStrength, and safetyFlags; do not strengthen facts marked do_not_strengthen.",
)


def _canonical_source_fact_package(
    facts: list[dict[str, Any]],
    selected_slides: list[DeckSlide],
    *,
    has_user_instruction: bool,
    has_additional_context: bool,
    has_prompt_context_artifact: bool,
    candidate_facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the one source-fact consumer contract used by fresh and recovered generation."""
    slide_fact_counts = _source_slide_fact_counts(facts, selected_slides)
    package: dict[str, Any] = {
        "schemaVersion": "smart-deck-source-facts.v1",
        "rules": list(_SOURCE_FACT_GROUNDING_RULES),
        "factCount": len(facts),
        "facts": facts,
        "factTypeCounts": summarize_fact_types(facts),
        "safetyFlagCounts": summarize_safety_flags(facts),
        "coverage": {
            "selectedSlideCount": len(selected_slides),
            "sourceSlideFactCounts": slide_fact_counts,
            "missingSlideFactIds": [
                slide.id
                for slide in selected_slides
                if slide_fact_counts.get(slide.id, 0) <= 1
            ],
            "hasUserInstruction": has_user_instruction,
            "hasAdditionalContext": has_additional_context,
            "hasPromptContextArtifact": has_prompt_context_artifact,
        },
    }
    if candidate_facts is not None and len(candidate_facts) > len(facts):
        package["candidateMetrics"] = {
            "factCount": len(candidate_facts),
            "factTypeCounts": summarize_fact_types(candidate_facts),
            "safetyFlagCounts": summarize_safety_flags(candidate_facts),
            "sourceSlideFactCounts": _source_slide_fact_counts(candidate_facts, selected_slides),
            "truncatedFactCount": len(candidate_facts) - len(facts),
        }
    return package


def _extract_artifact_fact_texts(artifact_context: object, *, limit: int = 12) -> list[str]:
    if not isinstance(artifact_context, dict):
        return []
    candidates: list[str] = []

    def walk(value: object) -> None:
        if len(candidates) >= limit:
            return
        if isinstance(value, str):
            text = _normalise_fact_text(value)
            if text and len(text) >= 12:
                candidates.append(text)
            return
        if isinstance(value, list):
            for item in value[:limit]:
                walk(item)
                if len(candidates) >= limit:
                    break
            return
        if isinstance(value, dict):
            for key in ("summary", "headline", "title", "description", "text", "claim", "finding", "value"):
                if key in value:
                    walk(value.get(key))
                    if len(candidates) >= limit:
                        return
            for item in list(value.values())[:limit]:
                walk(item)
                if len(candidates) >= limit:
                    return

    walk(artifact_context)
    return candidates[:limit]


def _validate_generation_slide_coverage(
    requested_slide_ids: list[str],
    slide_results: list[dict],
    slide_failures: list[dict],
) -> dict:
    completed_slide_ids = [str(result.get("sourceSlideId") or "").strip() for result in slide_results]
    failed_slide_ids = [str(failure.get("sourceSlideId") or "").strip() for failure in slide_failures]
    if not all(requested_slide_ids) or not all(completed_slide_ids + failed_slide_ids):
        raise ValueError("Smart Deck generation coverage contains an empty source slide ID.")
    if len(set(requested_slide_ids)) != len(requested_slide_ids):
        raise ValueError("Smart Deck generation requested slide IDs must be unique.")
    if len(set(completed_slide_ids)) != len(completed_slide_ids):
        raise ValueError("Smart Deck generation completed slide IDs must be unique.")
    if len(set(failed_slide_ids)) != len(failed_slide_ids):
        raise ValueError("Smart Deck generation failed slide IDs must be unique.")

    requested = set(requested_slide_ids)
    completed = set(completed_slide_ids)
    failed = set(failed_slide_ids)
    if completed & failed:
        raise ValueError("Smart Deck generation slide coverage cannot be both completed and failed.")
    if completed | failed != requested:
        raise ValueError("Smart Deck generation slide coverage does not match the requested slides.")
    return {
        "requestedSlideIds": requested_slide_ids,
        "completedSlideIds": completed_slide_ids,
        "failedSlideIds": failed_slide_ids,
        "coverageComplete": not failed_slide_ids,
        "partialSuccess": bool(completed_slide_ids and failed_slide_ids),
    }


def _build_source_fact_package(
    *,
    deck: Deck,
    selected_slides: list[DeckSlide],
    payload: CreateSmartDeckGenerationJobInput,
    brand_profile,
    prompt_context_artifact: object,
) -> dict:
    facts: list[dict] = []
    seen: set[str] = set()

    _append_source_fact(
        facts,
        seen,
        source_type="deck_metadata",
        source_id=deck.id,
        field="title",
        text=deck.title,
        confidence="high",
        scope="deck",
    )
    _append_source_fact(
        facts,
        seen,
        source_type="deck_metadata",
        source_id=deck.id,
        field="audience",
        text=deck.audience,
        confidence="high",
        scope="deck",
    )
    _append_source_fact(
        facts,
        seen,
        source_type="deck_metadata",
        source_id=deck.id,
        field="purpose",
        text=deck.purpose,
        confidence="high",
        scope="deck",
    )
    _append_source_fact(
        facts,
        seen,
        source_type="deck_metadata",
        source_id=deck.id,
        field="summary",
        text=deck.summary,
        confidence="medium",
        scope="deck",
    )
    _append_source_fact(
        facts,
        seen,
        source_type="user_instruction",
        source_id=deck.id,
        field="prompt",
        text=payload.prompt,
        confidence="high",
        scope="job",
    )
    _append_source_fact(
        facts,
        seen,
        source_type="user_instruction",
        source_id=deck.id,
        field="additionalContext",
        text=payload.additionalContext,
        confidence="medium",
        scope="job",
    )

    if brand_profile is not None:
        _append_source_fact(
            facts,
            seen,
            source_type="brand_profile",
            source_id=getattr(brand_profile, "id", deck.id),
            field="company_name",
            text=getattr(brand_profile, "company_name", None),
            confidence="medium",
            scope="brand",
        )
        _append_source_fact(
            facts,
            seen,
            source_type="brand_profile",
            source_id=getattr(brand_profile, "id", deck.id),
            field="visual_direction",
            text=getattr(brand_profile, "visual_direction", None),
            confidence="medium",
            scope="brand",
        )

    for slide in selected_slides:
        _append_source_fact(
            facts,
            seen,
            source_type="source_slide",
            source_id=slide.id,
            field="title",
            text=slide.title,
            confidence="high",
            scope="slide",
        )
        _append_source_fact(
            facts,
            seen,
            source_type="source_slide",
            source_id=slide.id,
            field="role",
            text=slide.role or slide.semantic_slide_type,
            confidence="medium",
            scope="slide",
        )
        for candidate in _fact_candidates_from_text(slide.raw_text)[:SOURCE_FACT_MAX_PER_SLIDE]:
            _append_source_fact(
                facts,
                seen,
                source_type="source_slide",
                source_id=slide.id,
                field="raw_text",
                text=candidate,
                confidence="high",
                scope="slide",
            )

    for text in _extract_artifact_fact_texts(prompt_context_artifact):
        _append_source_fact(
            facts,
            seen,
            source_type="llm_artifact",
            source_id=deck.id,
            field="prompt_context",
            text=text,
            confidence="medium",
            scope="deck",
        )

    # Whole-deck HTML generation is one bounded request and must retain the
    # complete deterministic fact set for every selected source. Its serialized
    # context is rejected by full_html_generation_service before an attempt is
    # started if it exceeds model token or byte limits. Legacy per-slide
    # render-schema generation keeps its established fact cap.
    emitted_facts = (
        facts
        if payload.outputContract == "full_html_deck.v1"
        else _bound_source_facts(facts, selected_slides)
    )
    return _canonical_source_fact_package(
        emitted_facts,
        selected_slides,
        has_user_instruction=bool(_normalise_fact_text(payload.prompt)),
        has_additional_context=bool(_normalise_fact_text(payload.additionalContext)),
        has_prompt_context_artifact=isinstance(prompt_context_artifact, dict),
        candidate_facts=facts,
    )


def _build_media_context(deck: Deck) -> dict:
    """Build bounded media context for LLM consumption."""
    from app.services.media.media_context import build_deck_media_context

    session = deck._sa_instance_state.session
    if session is None:
        return {"schemaVersion": "deck-media-context.v1", "deckId": deck.id, "assetCount": 0, "totalBytes": 0, "assets": []}

    try:
        return build_deck_media_context(session, deck_id=deck.id)
    except Exception as error:
        # Media context is non-blocking; log and return empty
        import logging
        logging.getLogger(__name__).warning("Failed to build media context for deck %s: %s", deck.id, error)
        return {"schemaVersion": "deck-media-context.v1", "deckId": deck.id, "assetCount": 0, "totalBytes": 0, "assets": []}


# Build the full LLM context package that the generation prompt uses. This is
# the main bridge from product state and the knowledge base into model input.
def _generation_context_mode(payload: CreateSmartDeckGenerationJobInput) -> ContextMode:
    if payload.generationMode == "instant_deck" and payload.outputContract == "full_html_deck.v1":
        return ContextMode.full_deck
    return ContextMode.slide_generation


def _build_llm_context(
    deck: Deck,
    selected_slides: list[DeckSlide],
    payload: CreateSmartDeckGenerationJobInput,
    audience_profile: dict | None = None,
    vision_design_analysis: dict | None = None,
) -> dict:
    context_started = time.perf_counter()
    brand_profile = deck.brand_profile
    brand_context = build_provider_safe_brand_context(
        brand_profile,
        neutral_when_absent=(payload.outputContract == "full_html_deck.v1"),
    )
    brand_design_tokens = build_brand_design_tokens(brand_profile)
    prompt_context_artifact = next(
        (
            artifact.payload_json
            for artifact in deck.llm_artifacts
            if artifact.artifact_type == "prompt_context" and artifact.status == "ready"
        ),
        None,
    )
    active_design_version = next((version for version in deck.design_versions if version.is_active), None)
    archetype_context = build_slide_archetype_context(
        audience=deck.audience,
        purpose=deck.purpose,
        slide_texts=[slide.raw_text or "" for slide in selected_slides],
        slide_titles=[slide.title or "" for slide in selected_slides],
        slide_roles=[slide.role or "" for slide in selected_slides],
    )
    knowledge_metadata = build_llm_knowledge_metadata()
    detected_subjects = [
        {
            **detect_smart_deck_subject(slide.title, slide.raw_text, [slide.role, slide.semantic_slide_type] if slide.semantic_slide_type else [slide.role]),
            "slideId": slide.id,
            "slideTitle": slide.title,
        }
        for slide in selected_slides
    ]
    selected_subject = payload.selectedSubject or (detected_subjects[0]["subject"] if detected_subjects else None)
    retrieval_started = time.perf_counter()
    retrieval_context = build_generation_context(
        mode=_generation_context_mode(payload),
        deck=deck,
        selected_slides=selected_slides,
        active_design_version=active_design_version,
        prompt=payload.prompt,
        additional_context=payload.additionalContext,
        design_tokens=brand_design_tokens,
        artifact_context=prompt_context_artifact,
        audience_context=build_vc_prompt_context(
            audience=deck.audience,
            purpose=deck.purpose,
            user_role=deck.workspace.user.role if deck.workspace and deck.workspace.user else None,
            audience_profile=audience_profile,
            deck_metadata=deck.metadata_json,
            brand_evidence=brand_profile.raw_evidence_json if brand_profile else None,
            slide_texts=[slide.raw_text or "" for slide in selected_slides],
        ),
        archetype_context=archetype_context,
    )
    retrieval_seconds = time.perf_counter() - retrieval_started
    audience_context = retrieval_context["audienceContext"]
    source_facts_started = time.perf_counter()
    source_fact_package = _build_source_fact_package(
        deck=deck,
        selected_slides=selected_slides,
        payload=payload,
        brand_profile=brand_profile,
        prompt_context_artifact=prompt_context_artifact,
    )
    source_fact_seconds = time.perf_counter() - source_facts_started
    runtime_context = build_architecture_runtime_context()
    runtime_capabilities = build_smart_deck_runtime_capabilities()
    design_context = payload.designContext if isinstance(payload.designContext, dict) else None
    generation_mode = payload.generationMode if payload.generationMode == "instant_deck" else "standard"
    instant_deck_context = build_instant_deck_generation_context() if generation_mode == "instant_deck" else None
    # Diligence, conversion, and deck-map artifacts remain available to their
    # analysis surfaces. They are deliberately excluded from render generation
    # so their advice and evidence checklists cannot become visible slide copy.
    return {
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
        },
        "brand": {
            **brand_context,
            "name": (
                brand_context.get("companyName")
                if payload.outputContract == "full_html_deck.v1"
                else brand_context.get("companyName") or "Deck AI Stack"
            ),
            "visualDirection": (
                brand_context.get("visualDirection")
                if payload.outputContract == "full_html_deck.v1"
                else brand_context.get("visualDirection") or "modern, premium, clear"
            ),
        },
        "designContext": design_context,
        "generationMode": generation_mode,
        "instantDeckContext": instant_deck_context,
        "visionDesignAnalysis": vision_design_analysis,
        "selectedSlides": [_map_source_slide(slide) for slide in selected_slides],
        "subjectContext": {
            "deckType": payload.deckType or "unknown",
            "audience": payload.audience or deck.audience,
            "selectedSubject": selected_subject,
            "selectedElementId": payload.selectedElementId,
            "detectedSubjects": detected_subjects,
            "actionId": payload.actionId,
            "actionPrompt": payload.actionPrompt,
            "userPrompt": payload.userPrompt or payload.prompt,
            "latestBatchId": payload.latestBatchId,
            "generationMode": generation_mode,
        },
        "audienceContext": audience_context,
        "slideArchetypeContext": archetype_context,
        "knowledgeMetadata": knowledge_metadata,
        "runtimeContext": runtime_context,
        "runtimeCapabilities": runtime_capabilities,
        "outputContract": {
            "rootShape": {
                "designVersionName": "string",
                "variantId": f"one of {', '.join(sorted(VALID_INSTANT_DECK_VARIANT_IDS))}",
                "variantRationale": "string",
                "slides": [
                    {
                        "sourceSlideId": "must match one selectedSlides id",
                        "title": "string",
                        "archetypeId": "must be a known slide archetype slug",
                        "narrativeRole": "string",
                        "renderSchema": "must validate against renderSchemaJsonSchema",
                    }
                ],
            },
            "renderSchemaJsonSchema": RenderSchema.model_json_schema(),
            "additionalPropertiesAllowed": False,
        },
        "sourceFactPackage": source_fact_package,
        "artifactContext": prompt_context_artifact,
        "retrievalContext": retrieval_context,
        "mediaContext": _build_media_context(deck),
        "userInstruction": payload.prompt,
        "styleId": payload.styleId,
        "brandProductId": payload.brandProductId,
        "additionalContext": payload.additionalContext,
        "orchestrationTimings": {
            "contextLoading": time.perf_counter() - context_started,
            "vectorRetrieval": retrieval_seconds,
            "sourceFactAssembly": source_fact_seconds,
        },
        "rules": [
            "Return one generated slide for each selected source slide.",
            "Do not edit the uploaded PDF directly.",
            "Use render_schema_json only; do not return HTML, Svelte, or executable JavaScript.",
            "Follow outputContract exactly. Do not add canvas, content, style, fontFamily, color, textAlign, border, or other fields absent from renderSchemaJsonSchema.",
            "Keep all element bounds inside a 1920x1080 canvas.",
            "Use subjectContext to classify the slide topic before rewriting it.",
            "Use audienceContext to tune language, evidence density, and decision criteria for the VC persona.",
            "Use slideArchetypeContext to preserve the expected pitch-deck narrative arc and slide job.",
            "Keep analysis artifacts out of visible slide copy. Deck-map, audience-diligence, audience-conversion, recommended-version, evidence-gap, risk-register, and implementation-plan text belongs to the report surface, not to renderSchema elements.",
            "Never render advice or placeholder commands such as 'Add:', 'Replace:', 'Missing:', 'Proof:', 'provide', or 'evidence needed' as a slide headline, label, body, or callout. Record a genuine evidence gap only in the output analytics/missing-input fields and preserve source-grounded slide content.",
            "Use runtimeContext to keep deck objects, field usage, rebuild jobs, and review surfaces aligned with the repository model.",
            "Use runtimeCapabilities to select the right LLM task, guardrail group, and missing-evidence behavior before responding.",
            "Use sourceFactPackage as the only factual claim source and flag missing evidence instead of inventing stronger claims.",
            "Use designContext for visual direction when present. Treat it as non-blocking fallback guidance, not factual evidence.",
            "Use visionDesignAnalysis to choose the background, composition, text-safe zones, and contrast. The vision model defines visual direction; the text model writes source-grounded content.",
            "Use brand.colors, brand.palette, and brand.tokens as the approved deck color system whenever a persisted brand profile exists.",
            "Do not invent external image URLs. Use approved brand tokens, six-digit hex colors, gradients, or layered shape backgrounds unless an internal asset URL is provided.",
            "A flat background with text only is invalid. Every slide needs meaningful visual composition through an approved internal image, gradient, chart, foreground shape, or decorative layered background.",
            "When selectedSlides.assets contains an appropriate internal image assetUrl, incorporate it as an image element or layered background instead of discarding the source visual.",
            "Keep text readable against its actual background. Use high-contrast brand tokens or colors and add a contrasting overlay or card when text sits over imagery.",
            "Resolve visual guidance in this order: brand_profile, logo, company_url, presentation, default_presentation.",
            "Use presentation-scale typography on the 1920x1080 canvas: headlines 44-72px, normal slide copy 28-36px, and supporting labels or notes 20-24px. Shorten copy instead of shrinking text.",
            *(
                [
                    "Instant Deck mode is active. Use instantDeckContext to sharpen the whole-deck story, connect the deck to diligence and memo expectations, and keep proof gaps explicit.",
                    "Use instantDeckContext.embeddingSeedSources only as additive venture-context registry guidance, never as founder evidence.",
                    "First infer the product gist, customer/problem gist, and brand gist from the uploaded deck itself before rewriting slides.",
                    "Use subjectContext.userPrompt as the redesign direction for the whole deck: it should shape narrative emphasis, sequencing, and visual tone across the finished investor deck.",
                    "The output should feel like a full investor-facing redesign of this company, not a template fill or a set of isolated slide edits.",
                    "Choose one launch variant from instantDeckContext.launchVariants for the whole deck and keep it coherent across slides.",
                    "Return root variantId and variantRationale, then assign every slide an archetypeId and narrativeRole that reflect the redesigned investor story.",
                    "The redesign must be real: do not keep the source sequence and copy unchanged unless the source already fits the best investor narrative.",
                    "Choose one launch variant from instantDeckContext.launchVariants for the whole deck and keep it coherent across slides.",
                    "Return root variantId and variantRationale, then assign every slide an archetypeId and narrativeRole that reflect the redesigned investor story.",
                    "The redesign must be real: do not keep the source sequence and copy unchanged unless the source already fits the best investor narrative.",
                ]
                if generation_mode == "instant_deck"
                else []
            ),
        ],
    }


def _selected_slide_visual_inputs(selected_slides: list[DeckSlide], *, limit: int = 4) -> list[dict]:
    visual_inputs: list[dict] = []
    for slide in selected_slides:
        image_url = None
        for path in (getattr(slide, "preview_image_url", None), getattr(slide, "thumbnail_path", None)):
            image_url = model_image_url(path)
            if image_url:
                break
        if not image_url:
            continue
        visual_inputs.append(
            {
                "sourceSlideId": slide.id,
                "slideTitle": slide.title,
                "slideRole": slide.role,
                "imageUrl": image_url,
            }
        )
        if len(visual_inputs) >= limit:
            break
    return visual_inputs


def _normalise_vision_design_analysis(payload: dict, source_slide_ids: set[str]) -> dict:
    raw_slides = payload.get("slides") if isinstance(payload.get("slides"), list) else []
    slides: list[dict] = []
    allowed_background_types = {"token", "color", "gradient", "layered"}
    for raw_slide in raw_slides:
        if not isinstance(raw_slide, dict):
            continue
        source_slide_id = str(raw_slide.get("sourceSlideId") or "")
        if source_slide_id not in source_slide_ids:
            continue
        background_type = str(raw_slide.get("backgroundType") or "layered").lower()
        if background_type not in allowed_background_types:
            background_type = "layered"
        colors = [
            str(color)
            for color in (raw_slide.get("dominantColors") or [])
            if isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color)
        ][:6]
        slides.append(
            {
                "sourceSlideId": source_slide_id,
                "backgroundType": background_type,
                "backgroundDescription": _fit_text(str(raw_slide.get("backgroundDescription") or ""), 500),
                "composition": _fit_text(str(raw_slide.get("composition") or ""), 500),
                "textSafeZones": _fit_text(str(raw_slide.get("textSafeZones") or ""), 500),
                "contrastGuidance": _fit_text(str(raw_slide.get("contrastGuidance") or ""), 500),
                "reusableVisualCues": _fit_text(str(raw_slide.get("reusableVisualCues") or ""), 500),
                "dominantColors": colors,
            }
        )
    return {
        "schemaVersion": "smart-deck-vision-design-analysis.v1",
        "status": "ready",
        "overallStyle": _fit_text(str(payload.get("overallStyle") or ""), 600),
        "backgroundStrategy": _fit_text(str(payload.get("backgroundStrategy") or ""), 600),
        "layoutStrategy": _fit_text(str(payload.get("layoutStrategy") or ""), 600),
        "slides": slides,
    }


VISION_ANALYSIS_PROMPT_VERSION = "smart-deck-vision.v2"


def _vision_analysis_cache_key(selected_slides: list[DeckSlide], *, provider: str, model: str | None) -> str:
    inputs = []
    for slide in selected_slides:
        inputs.append(
            {
                "slideId": slide.id,
                "preview": getattr(slide, "preview_image_url", None),
                "thumbnail": getattr(slide, "thumbnail_path", None),
                "rendered": getattr(slide, "rendered_image_path", None),
                "metadata": getattr(slide, "metadata_json", None),
            }
        )
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"{VISION_ANALYSIS_PROMPT_VERSION}:{provider}:{model or 'unconfigured'}:{digest}"


def _analyze_selected_slide_visuals(
    selected_slides: list[DeckSlide],
    *,
    provider: str,
    model: str | None,
    api_key: str | None,
    deadline: OperationDeadline | None = None,
) -> dict:
    visual_inputs = _selected_slide_visual_inputs(selected_slides)
    if not api_key:
        return {"schemaVersion": "smart-deck-vision-design-analysis.v1", "status": "unavailable", "slides": [], "telemetry": {"providerCallExecuted": False}}
    if not visual_inputs:
        return {"schemaVersion": "smart-deck-vision-design-analysis.v1", "status": "no_images", "slides": [], "telemetry": {"providerCallExecuted": False}}
    image_map = [
        {
            "imageIndex": index + 1,
            "sourceSlideId": item["sourceSlideId"],
            "slideTitle": item["slideTitle"],
            "slideRole": item["slideRole"],
        }
        for index, item in enumerate(visual_inputs)
    ]
    try:
        system_prompt = "You are a presentation art director. Analyze slide visuals and return valid JSON only."
        user_prompt = (
                "Analyze the ordered source-slide images. Define a coherent visual system for a redesigned deck. "
                "Focus on backgrounds, composition, text-safe zones, contrast, and reusable visual cues. "
                "Do not write slide copy and do not return external asset URLs. Return overallStyle, "
                "backgroundStrategy, layoutStrategy, and slides[]. Each slide must contain sourceSlideId, "
                "backgroundType, backgroundDescription, composition, textSafeZones, contrastGuidance, "
                "reusableVisualCues, and dominantColors as six-digit hex values. Image mapping: "
                + json.dumps(image_map, ensure_ascii=True)
            )
        if provider == "openai":
            response = call_openai_response(
                api_key=api_key,
                model=settings.openai_vision_model,
                system=system_prompt,
                user=user_prompt,
                image_urls=[item["imageUrl"] for item in visual_inputs],
                timeout=deadline.provider_timeout(90.0) if deadline is not None else 90,
                max_output_tokens=2500,
                response_format={"type": "json_object"},
            )
            payload = _extract_json_payload(extract_openai_text(response))
        elif provider == "dashscope":
            # Vision tasks require OpenAI; Qwen vision model does not support PDF input
            response = call_openai_response(
                api_key=settings.openai_api_key,
                model=settings.openai_vision_model,
                system=system_prompt,
                user=user_prompt,
                image_urls=[item["imageUrl"] for item in visual_inputs],
                timeout=deadline.provider_timeout(90.0) if deadline is not None else 90,
                max_output_tokens=2500,
                response_format={"type": "json_object"},
            )
            payload = _extract_json_payload(extract_openai_text(response))
        else:
            return {"schemaVersion": "smart-deck-vision-design-analysis.v1", "status": "unsupported_provider", "slides": [], "telemetry": {"providerCallExecuted": False}}
        return {**_normalise_vision_design_analysis(payload, {item["sourceSlideId"] for item in visual_inputs}), "telemetry": {"providerCallExecuted": True}}
    except OperationDeadlineExceeded:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        _logger.warning("smart_deck_vision_analysis_degraded", extra={"errorType": exc.__class__.__name__})
        return {
            "schemaVersion": "smart-deck-vision-design-analysis.v1",
            "status": "degraded",
            "slides": [],
            "message": "Vision design analysis was unavailable; generation used brand and design context.",
            "telemetry": {"providerCallExecuted": True},
        }
    except Exception as exc:
        from app.services.llm.provider_errors import is_provider_capacity_error

        if not is_provider_capacity_error(exc):
            raise
        _logger.warning("smart_deck_vision_analysis_capacity_degraded", extra={"errorType": exc.__class__.__name__})
        return {
            "schemaVersion": "smart-deck-vision-design-analysis.v1",
            "status": "degraded",
            "slides": [],
            "message": "Vision design analysis was capacity-limited; generation used brand and design context.",
            "telemetry": {"providerCallExecuted": True, "capacityLimited": True},
        }


def _slide_generation_context(llm_context: dict, slide: DeckSlide) -> dict:
    """Build an immutable, slide-sized prompt package for concurrent workers."""
    context = copy.deepcopy(llm_context)
    source_slide_id = slide.id
    selected_slide_context: list[dict] = []
    for item in context.get("selectedSlides", []):
        if not isinstance(item, dict) or item.get("id") != source_slide_id:
            continue
        compact = {
            key: item.get(key)
            for key in (
                "id",
                "slideIndex",
                "slideNumber",
                "sourcePageNumber",
                "title",
                "role",
                "semanticSlideType",
                "summary",
                "rawText",
                "layoutHints",
                "previewImageUrl",
            )
            if item.get(key) is not None
        }
        source_assets = [
            asset
            for asset in item.get("assets", [])
            if isinstance(asset, dict)
            and isinstance(asset.get("assetUrl"), str)
            and asset["assetUrl"].startswith(("/api/", "/uploads/", "/static/"))
            and (
                str(asset.get("mimeType") or "").startswith("image/")
                or str(asset.get("assetType") or "") in {"embedded_image", "image", "logo", "source_preview"}
            )
        ]
        source_assets.sort(key=lambda asset: (str(asset.get("assetType") or ""), str(asset.get("id") or "")))
        assets = [
            {
                key: asset.get(key)
                for key in ("id", "assetType", "label", "mimeType", "assetUrl", "width", "height")
                if asset.get(key) is not None
            }
            for asset in source_assets[:6]
        ]
        if assets:
            compact["assets"] = assets
        selected_slide_context.append(compact)
    context["selectedSlides"] = selected_slide_context
    source_package = context.get("sourceFactPackage")
    if isinstance(source_package, dict):
        facts = source_package.get("facts") if isinstance(source_package.get("facts"), list) else []
        matching_facts: list[dict] = []
        matching_slide_fact_count = 0
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            fact_source_id = str(
                fact.get("sourceId")
                or fact.get("sourceSlideId")
                or fact.get("slideId")
                or fact.get("source_slide_id")
                or ""
            )
            is_slide_fact = fact.get("sourceType") == "source_slide" or (
                fact.get("sourceType") is None and bool(fact_source_id)
            )
            if is_slide_fact:
                if fact_source_id != source_slide_id:
                    continue
                matching_slide_fact_count += 1
            matching_facts.append(fact)
        source_coverage = source_package.get("coverage") if isinstance(source_package.get("coverage"), dict) else {}
        filtered_package = {
            **source_package,
            "facts": matching_facts,
            "factCount": len(matching_facts),
            "factTypeCounts": summarize_fact_types(matching_facts),
            "safetyFlagCounts": summarize_safety_flags(matching_facts),
            "coverage": {
                **source_coverage,
                "selectedSlideCount": 1,
                "sourceSlideFactCounts": {source_slide_id: matching_slide_fact_count},
                "missingSlideFactIds": [source_slide_id] if matching_slide_fact_count <= 1 else [],
            },
        }
        filtered_package.pop("candidateMetrics", None)
        context["sourceFactPackage"] = filtered_package
    vision = context.get("visionDesignAnalysis")
    if isinstance(vision, dict):
        context["visionDesignAnalysis"] = {
            **vision,
            "slides": [
                item for item in vision.get("slides", [])
                if isinstance(item, dict) and item.get("sourceSlideId") == source_slide_id
            ],
        }
    retrieval = context.get("retrievalContext")
    if isinstance(retrieval, dict):
        retrieval = copy.deepcopy(retrieval)
        # selectedSlides, deck, audience, and brand already exist canonically at
        # the top level. Keep retrieval limited to evidence and retrieval rules.
        for duplicate_key in ("selectedSourceSlides", "audienceContext", "brand", "deck", "userPrompt"):
            retrieval.pop(duplicate_key, None)
        vector_retrieval = retrieval.get("vectorRetrieval")
        if isinstance(vector_retrieval, dict) and isinstance(vector_retrieval.get("chunks"), list):
            chunks = vector_retrieval["chunks"]
            matching_chunks = [
                chunk for chunk in chunks
                if isinstance(chunk, dict)
                and str(chunk.get("sourceSlideId") or chunk.get("slideId") or chunk.get("source_slide_id") or "") == source_slide_id
            ]
            vector_retrieval["chunks"] = matching_chunks or chunks[:3]
            retrieval["vectorRetrieval"] = vector_retrieval
        # The canonical archetype context is rebuilt for this slide below.
        retrieval.pop("slideArchetypeContext", None)
        context["retrievalContext"] = retrieval
    archetype_context = build_slide_archetype_context(
        audience=(context.get("deck") or {}).get("audience"),
        purpose=(context.get("deck") or {}).get("purpose"),
        slide_texts=[str(getattr(slide, "raw_text", "") or "")],
        slide_titles=[str(getattr(slide, "title", "") or "")],
        slide_roles=[
            str(
                getattr(slide, "semantic_slide_type", None)
                or getattr(slide, "role", None)
                or ""
            )
        ],
    )
    inferred_archetypes = (
        archetype_context.get("inferredArchetypes")
        if isinstance(archetype_context.get("inferredArchetypes"), list)
        else []
    )
    archetype_context["inferredArchetypes"] = inferred_archetypes[:1]
    archetype_context.pop("knowledgeModules", None)
    context["slideArchetypeContext"] = {
        key: archetype_context.get(key)
        for key in (
            "schemaVersion",
            "knowledgeSource",
            "audience",
            "purpose",
            "recommendedSequence",
            "runtimeContract",
            "narrativeGuidance",
        )
        if archetype_context.get(key) is not None
    }
    subject_context = context.get("subjectContext")
    if isinstance(subject_context, dict) and isinstance(subject_context.get("detectedSubjects"), list):
        subject_context["detectedSubjects"] = [
            item
            for item in subject_context["detectedSubjects"]
            if isinstance(item, dict) and item.get("slideId") == source_slide_id
        ]
    context.pop("runtimeContext", None)
    context.pop("runtimeCapabilities", None)
    instant_deck_context = context.get("instantDeckContext")
    if isinstance(instant_deck_context, dict):
        context["instantDeckContext"] = {
            key: instant_deck_context.get(key)
            for key in (
                "schemaVersion",
                "knowledgeSource",
                "promptRecipe",
                "launchVariants",
                "vcAiStackModules",
                "contextVigilancePatterns",
                "instructions",
            )
            if instant_deck_context.get(key) is not None
        }
    knowledge_metadata = context.get("knowledgeMetadata")
    if isinstance(knowledge_metadata, dict):
        context["knowledgeMetadata"] = {
            key: knowledge_metadata.get(key)
            for key in ("name", "version", "source")
            if knowledge_metadata.get(key) is not None
        }
    context["generationPlan"] = {
        **{
            key: value
            for key, value in (
                context.get("generationPlan")
                if isinstance(context.get("generationPlan"), dict)
                else {}
            ).items()
            if key not in {"runtimeContext", "knowledgeMetadata"}
        },
        "selectedSlideCount": 1,
    }
    if inferred_archetypes:
        primary_archetype = inferred_archetypes[0]
        context["generationPlan"]["primaryArchetype"] = {
            "slug": primary_archetype.get("slug"),
            "description": primary_archetype.get("description"),
            "requiredInputs": primary_archetype.get("requiredInputs") or [],
            "renderContract": primary_archetype.get("renderContract") or {},
            "outputContract": primary_archetype.get("outputContract") or {},
        }
    return context


_NON_ACTIONABLE_REPAIR_ACTIONS = {"surface_missing_evidence"}


def _critique_is_blocking(critique: dict) -> bool:
    if critique.get("status") == "blocking":
        return True
    decision = critique.get("decision") if isinstance(critique.get("decision"), dict) else {}
    try:
        return int(decision.get("blockingCount") or 0) > 0
    except (TypeError, ValueError):
        return True


def _can_degrade_critique_repair_to_follow_up(llm_context: dict, critique: dict) -> bool:
    return llm_context.get("generationMode") == "instant_deck" and not _critique_is_blocking(critique)


def _append_review_follow_up_warning(critique: dict, *, reason: str) -> dict:
    updated = copy.deepcopy(critique)
    decision = dict(updated.get("decision") or {}) if isinstance(updated.get("decision"), dict) else {}

    def _safe_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    reason_codes = {
        str(reason_code)
        for reason_code in (decision.get("reasonCodes") or updated.get("reasonCodes") or [])
        if str(reason_code).strip()
    }
    reason_codes.add("critique_repair_follow_up")
    follow_up_dimension = {
        "name": "follow_up",
        "severity": "warning",
        "message": "Instant Deck kept the original validated slide because critique follow-up repair did not complete cleanly.",
    }
    dimensions = list(updated.get("dimensions") or [])
    if follow_up_dimension not in dimensions:
        dimensions.append(follow_up_dimension)
    repair_actions = list(updated.get("repairActions") or [])
    follow_up_action = {
        "type": "manual_follow_up",
        "dimension": "follow_up",
        "instruction": "Review the critique warnings later; the original validated slide was kept to preserve a complete usable Instant Deck.",
    }
    if follow_up_action not in repair_actions:
        repair_actions.append(follow_up_action)
    warning_count = max(
        _safe_int(updated.get("warningCount")),
        _safe_int(decision.get("warningCount")),
        1,
    )
    updated.update(
        {
            "status": "review",
            "warningCount": warning_count,
            "dimensions": dimensions[:50],
            "repairActions": repair_actions[:25],
            "reasonCodes": sorted(reason_codes),
            "repairFallback": {
                "mode": "preserve_validated_slide",
                "reason": reason[:300],
            },
        }
    )
    updated["decision"] = {
        **decision,
        "schemaVersion": decision.get("schemaVersion") or "critique-summary.v1",
        "status": "review",
        "blockingCount": 0,
        "warningCount": warning_count,
        "repairActions": repair_actions[:25],
        "reasonCodes": sorted(reason_codes),
    }
    return updated


def _critique_requires_llm_repair(critique: dict) -> bool:
    if critique.get("status") == "blocking":
        return True
    if critique.get("status") != "review":
        return False
    if _critique_is_blocking(critique):
        return True
    try:
        has_missing_inputs = int(critique.get("missingInputCount") or 0) > 0
    except (TypeError, ValueError):
        has_missing_inputs = False
    if not has_missing_inputs:
        has_missing_inputs = any(
            isinstance(slide, dict) and bool(slide.get("missingInputs"))
            for slide in (critique.get("slides") or [])
        )
    if not has_missing_inputs:
        return True
    action_types = {
        str(action.get("type"))
        for action in (critique.get("repairActions") or [])
        if isinstance(action, dict) and action.get("type")
    }
    return not action_types or bool(action_types - _NON_ACTIONABLE_REPAIR_ACTIONS)


def _generate_one_slide(
    provider: str,
    llm_context: dict,
    slide: DeckSlide,
    prompt: str,
    model: str | None,
    api_key: str | None,
    deadline: OperationDeadline | None = None,
) -> dict:
    """Generate, validate, critique, and repair one slide without touching SQLAlchemy."""
    started = time.perf_counter()
    if provider == "dashscope":
        from app.services.llm.dashscope_provider import begin_usage_tracking

        begin_usage_tracking()
    slide_context = _slide_generation_context(llm_context, slide)
    try:
        render_payload = _generate_render_payload(
            provider,
            slide_context,
            [SimpleNamespace(id=slide.id)],
            prompt,
            model,
            api_key,
            deadline=deadline,
        )
    except (json.JSONDecodeError, OpenAIResponseFailed, OpenAIResponseIncomplete, OpenAIResponseMalformed) as exc:
        retry_locally = (
            isinstance(exc, (json.JSONDecodeError, OpenAIResponseMalformed))
            or isinstance(exc, OpenAIResponseIncomplete) and exc.reason == "max_output_tokens"
            or isinstance(exc, OpenAIResponseFailed) and exc.reason == "server_error"
        )
        if not retry_locally:
            raise
        # Structured-output providers can still return a truncated JSON object or
        # fail transiently. Retry this slide once in place so one recoverable
        # response does not force the durable whole-deck job to regenerate every
        # completed slide. Content filters, unknown incomplete reasons, refusals,
        # and terminal failed reasons are not retried with the identical prompt.
        _logger.warning(
            "smart_deck_slide_generation_malformed_json_retry",
            extra={"sourceSlideId": slide.id, "provider": provider, "errorType": exc.__class__.__name__},
        )
        try:
            render_payload = _generate_render_payload(
                provider,
                slide_context,
                [SimpleNamespace(id=slide.id)],
                prompt,
                model,
                api_key,
                deadline=deadline,
            )
        except json.JSONDecodeError as retry_exc:
            raise OpenAIResponseMalformed(reason="invalid_json") from retry_exc
    schema_repair_seconds = 0.0
    try:
        generated = _validate_generated_render_payload(
            render_payload,
            [SimpleNamespace(id=slide.id)],
            design_tokens=(slide_context.get("brand") or {}).get("tokens"),
            generation_mode=str(slide_context.get("generationMode") or "standard"),
        )
    except (ValidationError, ValueError) as validation_error:
        repair_started = time.perf_counter()
        # The schema repair receives only this slide, never the full deck payload.
        render_payload = _repair_invalid_render_schema_payload(
            provider, slide_context, render_payload, validation_error, [SimpleNamespace(id=slide.id)], prompt, model, api_key, deadline=deadline
        )
        schema_repair_seconds = time.perf_counter() - repair_started
        generated = _validate_generated_render_payload(
            render_payload,
            [SimpleNamespace(id=slide.id)],
            design_tokens=(slide_context.get("brand") or {}).get("tokens"),
            generation_mode=str(slide_context.get("generationMode") or "standard"),
        )

    critique_started = time.perf_counter()
    critique = _critique_generated_render_payload(
        generated,
        slide_context.get("generationPlan") or {},
        slide_context.get("sourceFactPackage") if isinstance(slide_context.get("sourceFactPackage"), dict) else {},
    )
    critique_seconds = time.perf_counter() - critique_started
    critique_repair_seconds = 0.0
    repair_payload = None
    if _critique_requires_llm_repair(critique):
        repair_started = time.perf_counter()
        original_render_payload = render_payload
        original_generated = generated
        original_critique = critique
        try:
            render_payload, generated, critique, repair_payload = _repair_render_payload(
                provider, slide_context, render_payload, critique, [SimpleNamespace(id=slide.id)], prompt, model, api_key, deadline=deadline
            )
            if _can_degrade_critique_repair_to_follow_up(slide_context, original_critique) and _critique_is_blocking(critique):
                repaired_critique = critique
                render_payload = original_render_payload
                generated = original_generated
                critique = _append_review_follow_up_warning(
                    original_critique,
                    reason="Critique repair produced a stricter blocking result than the original validated slide.",
                )
                repair_payload = {
                    "schemaVersion": "smart-deck-generation-repair.v1",
                    "status": "follow_up",
                    "fallbackMode": "preserve_validated_slide",
                    "originalCritique": original_critique,
                    "repairedCritique": repaired_critique,
                    "message": "Instant Deck kept the original validated slide because critique repair made the result worse.",
                }
        except Exception as exc:
            if not _can_degrade_critique_repair_to_follow_up(slide_context, original_critique):
                raise
            safe_repair_error = _safe_generation_failure_message(exc)
            render_payload = original_render_payload
            generated = original_generated
            critique = _append_review_follow_up_warning(original_critique, reason=safe_repair_error)
            repair_payload = {
                "schemaVersion": "smart-deck-generation-repair.v1",
                "status": "follow_up",
                "fallbackMode": "preserve_validated_slide",
                "originalCritique": original_critique,
                "error": safe_repair_error,
                "message": "Instant Deck kept the original validated slide because critique repair failed.",
            }
        critique_repair_seconds = time.perf_counter() - repair_started
    _require_nonblocking_generation(critique)
    tracked_usage = None
    if provider == "dashscope":
        from app.services.llm.dashscope_provider import get_tracked_usage

        tracked_usage = get_tracked_usage()
    elif provider == "openai" and isinstance(render_payload, dict):
        tracked_usage = render_payload.get("_tracked_usage") if isinstance(render_payload.get("_tracked_usage"), dict) else None
    return {
        "sourceSlideId": slide.id,
        "title": next(iter(generated.values())).get("title") if generated else "Generated slide",
        "renderPayload": render_payload,
        "generated": generated[slide.id],
        "critique": critique,
        "repairArtifact": repair_payload,
        "trackedUsage": tracked_usage,
        "timings": {
            "generation": max(0.0, time.perf_counter() - started - schema_repair_seconds - critique_seconds - critique_repair_seconds),
            "schemaRepair": schema_repair_seconds,
            "critique": critique_seconds,
            "critiqueRepair": critique_repair_seconds,
            "total": time.perf_counter() - started,
        },
    }


def _require_nonblocking_generation(critique: dict) -> None:
    decision = critique.get("decision") if isinstance(critique.get("decision"), dict) else {}
    if critique.get("status") == "blocking" or int(decision.get("blockingCount") or 0) > 0:
        # DISABLED: raising a plain ValueError discarded the safe reason and
        # action metadata needed after the generation transaction rolled back.
        # raise ValueError("Smart Deck output remains blocked by factuality or evidence validation.")
        slides = critique.get("slides") if isinstance(critique.get("slides"), list) else []
        raise GenerationValidationError(
            {
                "schemaVersion": "generation-validation-failure.v1",
                "blockedSlideCount": sum(1 for slide in slides if isinstance(slide, dict) and slide.get("status") == "blocking"),
                "reasonCodes": sorted(
                    {
                        str(reason_code)
                        for reason_code in (decision.get("reasonCodes") or [])
                        if str(reason_code).strip()
                    }
                ),
                "blockingDimensions": sorted(
                    {
                        str(dimension.get("name"))
                        for dimension in (critique.get("dimensions") or [])
                        if isinstance(dimension, dict) and dimension.get("severity") == "blocking" and dimension.get("name")
                    }
                ),
                "repairActionTypes": sorted(
                    {
                        str(action.get("type"))
                        for action in (critique.get("repairActions") or [])
                        if isinstance(action, dict) and action.get("type")
                    }
                ),
            }
        )


def _publish_generation_progress(run_id: str | None, *, phase: str, completed: int, total: int, slide_id: str | None = None) -> None:
    if not run_id:
        return
    progress_db = SessionLocal()
    try:
        workflow_job = progress_db.query(WorkflowJob).filter(WorkflowJob.id == run_id).one_or_none()
        if workflow_job is None:
            return
        output = dict(workflow_job.output_json or {})
        output.update(
            {
                # DISABLED: "phase": phase exposed the internal stage as an invalid public WorkflowPhase.
                "phase": "generation_running",
                "generationStage": phase,
                "progress": {
                    "completedSlideCount": completed,
                    "selectedSlideCount": total,
                    "activeSourceSlideId": slide_id,
                },
            }
        )
        workflow_job.output_json = output
        # DISABLED: workflow_job.published_phase = phase incorrectly published a non-terminal internal stage.
        workflow_job.heartbeat_at = datetime.utcnow()
        progress_db.commit()
    except Exception:
        progress_db.rollback()
        _logger.warning("smart_deck_progress_publish_failed", exc_info=True)
    finally:
        progress_db.close()


def _run_slide_generation_tasks(
    *,
    provider: str,
    llm_context: dict,
    slide_inputs: list[SimpleNamespace],
    prompt: str,
    model: str | None,
    api_key: str | None,
    run_id: str | None = None,
    deadline: OperationDeadline | None = None,
) -> tuple[list[dict], list[dict]]:
    """Run network-bound slide generation with a configured concurrency ceiling."""
    results: list[dict] = []
    failures: list[dict] = []
    first_failure: Exception | None = None
    retryable_slide_ids: set[str] = set()
    unresolved_exceptions: dict[str, Exception] = {}

    def append_failure(slide_id: str, exc: Exception) -> None:
        unresolved_exceptions[slide_id] = exc
        retryable = False
        try:
            from app.services.llm.provider_errors import is_provider_capacity_error

            retryable = is_provider_capacity_error(exc)
        except Exception:
            retryable = False
        failures.append(
            {
                "sourceSlideId": slide_id,
                "error": _safe_generation_failure_message(exc),
                "errorType": exc.__class__.__name__,
                "validationFailure": exc.to_summary() if isinstance(exc, GenerationValidationError) else None,
                "retryable": retryable,
            }
        )
        if retryable:
            retryable_slide_ids.add(slide_id)

    concurrency_limit = settings.max_concurrent_slide_generations
    if provider.strip().lower() == "openai" and llm_context.get("generationMode") == "instant_deck":
        concurrency_limit = settings.instant_deck_max_concurrent_slide_generations
    max_workers = max(1, min(concurrency_limit, len(slide_inputs)))
    _publish_generation_progress(run_id, phase="generating_slides", completed=0, total=len(slide_inputs))
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="smart-deck-slide")
    wait_for_shutdown = True
    try:
        future_to_slide = {
            executor.submit(
                _generate_one_slide,
                provider,
                llm_context,
                slide,
                prompt,
                model,
                api_key,
                **({"deadline": deadline} if deadline is not None else {}),
            ): slide
            for slide in slide_inputs
        }
        completed_count = 0
        future_iterator = (
            as_completed(future_to_slide, timeout=deadline.remaining())
            if deadline is not None
            else as_completed(future_to_slide)
        )
        for future in future_iterator:
            slide = future_to_slide[future]
            try:
                results.append(future.result())
            except Exception as exc:
                _logger.warning(
                    "smart_deck_slide_generation_failed",
                    extra={"sourceSlideId": slide.id, "errorType": exc.__class__.__name__},
                )
                append_failure(slide.id, exc)
                if first_failure is None:
                    first_failure = exc
            completed_count += 1
            _publish_generation_progress(
                run_id,
                phase="generating_slides",
                completed=completed_count,
                total=len(slide_inputs),
                slide_id=slide.id,
            )
    except FuturesTimeoutError as exc:
        wait_for_shutdown = False
        executor.shutdown(wait=False, cancel_futures=True)
        raise OperationDeadlineExceeded("Smart Deck slide generation exceeded its operation deadline.") from exc
    finally:
        if wait_for_shutdown:
            executor.shutdown(wait=True)

    if retryable_slide_ids:
        retry_inputs = [slide for slide in slide_inputs if slide.id in retryable_slide_ids]
        failures = [failure for failure in failures if failure.get("sourceSlideId") not in retryable_slide_ids]
        for slide in retry_inputs:
            try:
                results.append(
                    _generate_one_slide(
                        provider,
                        llm_context,
                        slide,
                        prompt,
                        model,
                        api_key,
                        **({"deadline": deadline} if deadline is not None else {}),
                    )
                )
                unresolved_exceptions.pop(slide.id, None)
            except Exception as exc:
                _logger.warning(
                    "smart_deck_slide_generation_retry_failed",
                    extra={"sourceSlideId": slide.id, "errorType": exc.__class__.__name__},
                )
                append_failure(slide.id, exc)
                if first_failure is None:
                    first_failure = exc

    slide_order = {slide.id: index for index, slide in enumerate(slide_inputs)}
    results.sort(key=lambda result: slide_order[result["sourceSlideId"]])
    # Preserve the typed provider/validation exception for Instant Deck when
    # any slide remains unrecovered. The whole-deck worker fails closed on even
    # one missing slide, so converting the first slide exception into a generic
    # ValueError would hide the real retryability/validation cause.
    if failures and llm_context.get("generationMode") == "instant_deck":
        final_failure = min(
            failures,
            key=lambda item: (
                0 if item.get("validationFailure") else 1 if not item.get("retryable") else 2,
                slide_order.get(str(item.get("sourceSlideId")), len(slide_order)),
            ),
        )
        unresolved = unresolved_exceptions.get(str(final_failure.get("sourceSlideId")))
        if unresolved is not None:
            raise unresolved
        raise ValueError("Instant Deck slide generation failed.")
    # NEW: Preserve the typed provider exception when the whole concurrent
    # batch failed. Previously it was converted into ValueError below, losing
    # the OpenAI quota/rate-limit classification before durable job handling.
    if first_failure is not None and not results:
        raise first_failure
    return results, failures


def _map_variation_job(job: ElementVariationJob) -> dict:
    return {
        "id": job.id,
        "deckId": job.deck_id,
        "workspaceId": job.workspace_id,
        "generatedSlideId": job.generated_slide_id,
        "elementId": job.element_id,
        "baseElementVersionId": job.base_element_version_id,
        "instruction": job.instruction,
        "variationCount": job.variation_count,
        "status": job.status,
        "outputElementVersionId": job.output_element_version_id,
        "errorMessage": job.error_message,
        "createdAt": _iso(job.created_at) or "",
        "startedAt": _iso(job.started_at),
        "completedAt": _iso(job.completed_at),
    }


def _latest_element_version(element: GeneratedSlideElement) -> GeneratedSlideElementVersion | None:
    if not element.versions:
        return None
    return sorted(element.versions, key=lambda item: item.version_number, reverse=True)[0]


def _next_element_version_number(element: GeneratedSlideElement) -> int:
    latest = _latest_element_version(element)
    return (latest.version_number + 1) if latest else 1


def _normalise_element_variation_position(
    element: GeneratedSlideElement,
    *,
    raw_position: object,
    render_schema: RenderSchema,
) -> dict[str, int]:
    position = raw_position if isinstance(raw_position, dict) else {}

    def bounded_int(key: str, fallback: int, minimum: int, maximum: int) -> int:
        value = position.get(key, fallback)
        if isinstance(value, bool):
            return fallback
        try:
            normalized = int(round(float(value)))
        except (TypeError, ValueError, OverflowError):
            return fallback
        return max(minimum, min(normalized, maximum))

    width = bounded_int("width", element.width, 1, render_schema.width)
    height = bounded_int("height", element.height, 1, render_schema.height)
    return {
        "x": bounded_int("x", element.x, 0, render_schema.width - width),
        "y": bounded_int("y", element.y, 0, render_schema.height - height),
        "width": width,
        "height": height,
    }


def _normalise_element_variation_output(
    element: GeneratedSlideElement,
    *,
    raw_output: object,
    render_schema_json: dict,
) -> tuple[dict, dict, dict]:
    if not isinstance(raw_output, dict):
        raise ValueError("AI element variation output must be a JSON object.")
    content = raw_output.get("content")
    style = raw_output.get("style")
    if content is not None and not isinstance(content, dict):
        raise ValueError("AI element variation content must be a JSON object.")
    if style is not None and not isinstance(style, dict):
        raise ValueError("AI element variation style must be a JSON object.")
    allowed_content_keys = set(element.content_json or {}) | {"text", "analyticsKey"}
    allowed_style_keys = set(element.style_json or {}) | {"fontSize", "fontWeight", "colorToken", "fillToken", "assetUrl"}

    normalized_content = {
        **dict(element.content_json or {}),
        **{key: value for key, value in dict(content or {}).items() if key in allowed_content_keys},
    }
    normalized_style = {
        **dict(element.style_json or {}),
        **{key: value for key, value in dict(style or {}).items() if key in allowed_style_keys},
    }
    if element.element_type == "text":
        text = str(normalized_content.get("text") or "").strip()
        if not text:
            raise ValueError("AI element variation must return non-empty text for a text element.")
        normalized_content["text"] = _fit_text(text, 4000)
    render_schema = RenderSchema.model_validate(render_schema_json)
    normalized_position = _normalise_element_variation_position(
        element,
        raw_position=raw_output.get("position"),
        render_schema=render_schema,
    )
    candidate_schema = _render_schema_with_element_variation(
        render_schema.model_dump(),
        element,
        normalized_content,
        normalized_style,
        normalized_position,
    )
    candidate_render_element = next(
        item for item in candidate_schema["elements"] if item.get("id") == element.element_key
    )
    if "fontSize" in normalized_style:
        normalized_style["fontSize"] = candidate_render_element.get("fontSize", normalized_style["fontSize"])
    if "fontWeight" in normalized_style:
        normalized_style["fontWeight"] = candidate_render_element.get("fontWeight", normalized_style["fontWeight"])
    for key in ("colorToken", "fillToken", "assetUrl"):
        if key in normalized_style:
            normalized_style[key] = candidate_render_element.get(key, normalized_style[key])
    if "analyticsKey" in normalized_content:
        normalized_content["analyticsKey"] = candidate_render_element.get("analyticsKey", normalized_content["analyticsKey"])
    return normalized_content, normalized_style, normalized_position


def _generate_element_variation(
    db: Session,
    deck: Deck,
    element: GeneratedSlideElement,
    *,
    instruction: str,
    retrieval_context: dict,
    render_schema_json: dict,
) -> tuple[dict, dict, dict]:
    from app.services.llm.structured_json_service import call_structured_json

    config = get_generation_provider_config(db, deck, preferred_model=None, strict=True, use_case="smart_edit")
    raw_output = call_structured_json(
        provider=config["provider"],
        model=config["model"],
        api_key=config.get("apiKey"),
        credential_source=config.get("source", "environment"),
        system_prompt=(
            "Return only JSON for one selected slide element variation. Preserve factual meaning and element identity. "
            "Use exactly these optional top-level keys: content, style, position. Do not return HTML or commentary."
        ),
        user_prompt=json.dumps(
            {
                "instruction": instruction,
                "elementType": element.element_type,
                "current": {
                    "content": element.content_json or {},
                    "style": element.style_json or {},
                    "position": {
                        "x": element.x,
                        "y": element.y,
                        "width": element.width,
                        "height": element.height,
                    },
                },
                "retrievalContext": retrieval_context,
                "outputContract": {
                    "content": "object",
                    "style": "object",
                    "position": {"x": "integer", "y": "integer", "width": "integer", "height": "integer"},
                },
            },
            default=str,
        ),
        timeout=90,
        max_tokens=2500,
    )
    return _normalise_element_variation_output(
        element,
        raw_output=raw_output,
        render_schema_json=render_schema_json,
    )


def _apply_element_to_render_schema(slide: GeneratedSlide, element: GeneratedSlideElement) -> None:
    render_schema = RenderSchema.model_validate(slide.render_schema_json).model_dump()
    for render_element in render_schema["elements"]:
        if render_element.get("id") != element.element_key:
            continue
        render_element["x"] = element.x
        render_element["y"] = element.y
        render_element["width"] = element.width
        render_element["height"] = element.height
        content = element.content_json or {}
        style = element.style_json or {}
        if "text" in content:
            render_element["text"] = content.get("text")
        if "analyticsKey" in content:
            render_element["analyticsKey"] = content.get("analyticsKey")
        for key in ["fontSize", "fontWeight", "colorToken", "fillToken", "assetUrl"]:
            if key in style:
                render_element[key] = style[key]
        break
    slide.render_schema_json = RenderSchema.model_validate(render_schema).model_dump()


def _render_schema_with_element_variation(
    render_schema_json: dict,
    element: GeneratedSlideElement,
    content: dict,
    style: dict,
    position: dict,
) -> dict:
    render_schema = RenderSchema.model_validate(render_schema_json).model_dump()
    for render_element in render_schema["elements"]:
        if render_element.get("id") != element.element_key:
            continue
        render_element["x"] = int(position.get("x", element.x))
        render_element["y"] = int(position.get("y", element.y))
        render_element["width"] = int(position.get("width", element.width))
        render_element["height"] = int(position.get("height", element.height))
        if "text" in content:
            render_element["text"] = content.get("text")
        if "analyticsKey" in content:
            render_element["analyticsKey"] = content.get("analyticsKey")
        for key in ["fontSize", "fontWeight", "colorToken", "fillToken", "assetUrl"]:
            if key in style:
                render_element[key] = style[key]
        break
    return RenderSchema.model_validate(render_schema).model_dump()


def _load_completed_element_variation_replay(
    db: Session,
    *,
    deck_id: str,
    workspace_id: str,
    base_element_version_id: str | None,
    instruction: str,
    variation_count: int,
) -> tuple[dict, dict, dict, dict, dict, dict] | None:
    replay_job = (
        db.query(ElementVariationJob)
        .filter(
            ElementVariationJob.deck_id == deck_id,
            ElementVariationJob.workspace_id == workspace_id,
            ElementVariationJob.base_element_version_id == base_element_version_id,
            ElementVariationJob.instruction == instruction,
            ElementVariationJob.variation_count == variation_count,
            ElementVariationJob.status == "completed",
            ElementVariationJob.output_element_version_id.is_not(None),
        )
        .order_by(ElementVariationJob.created_at.desc())
        .first()
    )
    if replay_job is None:
        return None
    replay_version = (
        db.query(GeneratedSlideElementVersion)
        .filter(GeneratedSlideElementVersion.id == replay_job.output_element_version_id)
        .first()
    )
    replay_element = (
        db.query(GeneratedSlideElement)
        .options(selectinload(GeneratedSlideElement.versions))
        .filter(GeneratedSlideElement.id == replay_job.element_id)
        .first()
    )
    replay_slide = (
        db.query(GeneratedSlide)
        .options(selectinload(GeneratedSlide.code_versions), selectinload(GeneratedSlide.elements).selectinload(GeneratedSlideElement.versions))
        .filter(GeneratedSlide.id == replay_job.generated_slide_id)
        .first()
    )
    replay_design_version = (
        db.query(DesignVersion)
        .options(selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions))
        .filter(DesignVersion.id == replay_slide.design_version_id)
        .first()
        if replay_slide is not None
        else None
    )
    if replay_version is None or replay_element is None or replay_slide is None or replay_design_version is None:
        return None
    return (
        _map_variation_job(replay_job),
        _map_generated_slide_element(replay_element),
        _map_generated_slide_element_version(replay_version),
        _map_generated_slide(replay_slide),
        _map_design_version(replay_design_version),
        get_smart_deck_workspace(db, deck_id),
    )


def _record_llm_artifact(
    db: Session,
    *,
    deck_id: str,
    artifact_type: str,
    artifact_key: str,
    summary: str,
    payload_json: dict,
    metrics_json: dict | None = None,
    store_payload: bool = True,
    persist_canonical: bool = True,
) -> DeckLlmArtifact:
    artifact_id = generate_id("artifact")
    stored_payload = _write_json_artifact_to_storage(db, deck_id, artifact_id, payload_json) if store_payload else payload_json
    stored_metrics = dict(metrics_json or {})
    if store_payload:
        stored_metrics.update(
            {
                "artifactStorageProvider": stored_payload.get("storageProvider"),
                "artifactStoragePath": stored_payload.get("storagePath"),
            }
        )
    canonical_payload = (
        persist_canonical_llm_artifact(
            db,
            deck_id=deck_id,
            artifact_type=artifact_type,
            payload=payload_json,
        )
        if persist_canonical
        else None
    )
    if canonical_payload:
        stored_metrics.update(
            {
                "canonicalArtifactFilename": canonical_payload["filename"],
                "canonicalArtifactStoragePath": canonical_payload["storagePath"],
            }
        )
        if isinstance(stored_payload, dict):
            stored_payload = {
                **stored_payload,
                "canonicalFilename": canonical_payload["filename"],
                "canonicalStoragePath": canonical_payload["storagePath"],
            }
    artifact = DeckLlmArtifact(
        id=artifact_id,
        deck_id=deck_id,
        extraction_run_id=None,
        artifact_type=artifact_type,
        artifact_key=artifact_key,
        schema_version=SMART_DECK_ARTIFACT_SCHEMA_VERSION,
        status="ready",
        summary=summary,
        payload_json=stored_payload,
        bucket_payload_key=stored_payload.get("storagePath") if isinstance(stored_payload, dict) else None,
        metrics_json=stored_metrics,
    )
    db.add(artifact)
    return artifact


def _storage_user_id_for_deck(db: Session, deck_id: str) -> str:
    user_id = db.query(Deck.user_id).filter(Deck.id == deck_id).scalar()
    return user_id or "unknown-user"


def _write_json_artifact_to_storage(db: Session, deck_id: str, artifact_key: str, payload: dict) -> dict:
    bucket_service = get_bucket_artifact_service()
    user_id = _storage_user_id_for_deck(db, deck_id)
    storage_path = bucket_service.make_llm_artifact_key(user_id=user_id, deck_id=deck_id, artifact_id=artifact_key)
    bucket_service.put_json_sync(key=storage_path, data=payload)
    return {
        "artifactStorageVersion": SMART_DECK_ASSISTANT_ARTIFACT_STORAGE_VERSION,
        "storageProvider": settings.upload_storage_backend,
        "storagePath": storage_path,
        "contentType": "application/json",
    }


def _json_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def _write_render_schema_json_artifact(
    *,
    user_id: str | None,
    deck_id: str,
    design_version_id: str,
    generated_slide_id: str,
    code_version_id: str,
    render_schema: dict,
) -> dict:
    bucket_service = get_bucket_artifact_service()
    storage_user_id = user_id or "unknown-user"
    storage_path = bucket_service.make_render_schema_key(
        user_id=storage_user_id,
        deck_id=deck_id,
        design_version_id=design_version_id,
        generated_slide_id=generated_slide_id,
        code_version_id=code_version_id,
    )
    bucket_service.put_json_sync(key=storage_path, data=render_schema)
    return {
        "storageProvider": settings.upload_storage_backend,
        "storagePath": storage_path,
        "contentType": "application/json",
        "renderSchemaHash": _json_hash(render_schema),
    }


def _write_code_metadata_json_artifact(
    *,
    user_id: str | None,
    deck_id: str,
    design_version_id: str,
    generated_slide_id: str,
    code_version_id: str,
    code_json: dict,
) -> dict:
    bucket_service = get_bucket_artifact_service()
    storage_user_id = user_id or "unknown-user"
    storage_path = bucket_service.make_code_key(
        user_id=storage_user_id,
        deck_id=deck_id,
        design_version_id=design_version_id,
        generated_slide_id=generated_slide_id,
        code_version_id=code_version_id,
    )
    bucket_service.put_json_sync(key=storage_path, data=code_json)
    return {
        "storageProvider": settings.upload_storage_backend,
        "storagePath": storage_path,
        "contentType": "application/json",
        "codeJsonHash": _json_hash(code_json),
    }


def _write_design_version_manifest_json_artifact(
    *,
    user_id: str | None,
    deck_id: str,
    design_version_id: str,
    manifest_json: dict,
) -> dict:
    bucket_service = get_bucket_artifact_service()
    storage_user_id = user_id or "unknown-user"
    storage_path = bucket_service.make_manifest_key(
        user_id=storage_user_id,
        deck_id=deck_id,
        design_version_id=design_version_id,
    )
    bucket_service.put_json_sync(key=storage_path, data=manifest_json)
    return {
        "storageProvider": settings.upload_storage_backend,
        "storagePath": storage_path,
        "contentType": "application/json",
        "manifestHash": _json_hash(manifest_json),
    }


def load_deck_llm_artifact_payload(artifact: DeckLlmArtifact) -> dict:
    from app.services.visualizer.slide_read_model import load_deck_llm_artifact_payload as _impl
    return _impl(artifact)


def _fit_text(value: str, max_length: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "..."


def _build_render_schema(slide: DeckSlide, prompt: str) -> dict:
    title = _fit_text(slide.title or f"Slide {_source_slide_number(slide)}", 80)
    body_source = slide.summary or slide.narrative_notes or slide.raw_text or prompt
    body = _fit_text(body_source, 220)
    eyebrow = _fit_text(prompt, 92)
    schema = {
        "schemaVersion": "smart-deck-render-schema.v1",
        "width": 1920,
        "height": 1080,
        "background": {
            "type": "layered",
            "fill": "brand.surface",
            "layers": [
                {
                    "id": "bg_surface",
                    "type": "shape",
                    "shape": "rectangle",
                    "role": "base_surface",
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 1080,
                    "zIndex": 0,
                    "style": {"fill": "brand.surface", "opacity": 1, "radius": 0},
                },
                {
                    "id": "bg_accent_orb",
                    "type": "shape",
                    "shape": "circle",
                    "role": "brand_accent",
                    "x": 1380,
                    "y": -220,
                    "width": 680,
                    "height": 680,
                    "zIndex": 0,
                    "style": {"fill": "brand.accent", "opacity": 0.16, "radius": 999},
                },
            ],
        },
        "brandTokensUsed": ["brand.surface", "brand.accent", "brand.heading", "brand.body"],
        "analytics": {
            "slidePurpose": slide.semantic_slide_type or slide.role or "generated_slide",
            "designRationale": f"Transforms source slide {slide.title or _source_slide_number(slide)} into an investor-reviewable Smart Deck layout using the requested instruction.",
            "speakerNotes": "Review source-backed claims, missing evidence, and visual density before applying this version.",
            "audience": "smart_deck_generation",
            "trackedEvents": ["slide_view", "slide_time_spent", "element_click"],
        },
        "exportMetadata": {
            "exportReady": True,
            "renderer": "smart_deck_scene_graph",
            "supportedFormats": ["digital", "preview_image"],
        },
        "elements": [
            {
                "id": "el_eyebrow",
                "type": "text",
                "text": eyebrow,
                "x": 160,
                "y": 132,
                "width": 980,
                "height": 54,
                "zIndex": 30,
                "fontSize": 28,
                "fontWeight": "600",
                "colorToken": "brand.accent",
                "analyticsKey": "eyebrow",
            },
            {
                "id": "el_title",
                "type": "text",
                "text": title,
                "x": 160,
                "y": 230,
                "width": 1080,
                "height": 210,
                "zIndex": 31,
                "fontSize": 82,
                "fontWeight": "700",
                "colorToken": "brand.heading",
                "analyticsKey": "headline",
            },
            {
                "id": "el_body",
                "type": "text",
                "text": body,
                "x": 166,
                "y": 505,
                "width": 960,
                "height": 210,
                "zIndex": 32,
                "fontSize": 34,
                "fontWeight": "400",
                "colorToken": "brand.body",
                "analyticsKey": "body",
            },
            {
                "id": "el_rule",
                "type": "shape",
                "x": 160,
                "y": 804,
                "width": 520,
                "height": 8,
                "zIndex": 21,
                "fillToken": "brand.accent",
                "analyticsKey": "accent_rule",
            },
        ],
    }
    return RenderSchema.model_validate(schema).model_dump()


def _extract_json_payload(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return json.loads(text[start : end + 1])


def _build_openai_render_payload_json_schema() -> dict:
    """Return the root-envelope JSON Schema for OpenAI json_schema output.

    The root envelope (slides array and per-slide identity fields) is fully
    constrained. ``renderSchema`` keeps the full Pydantic schema as its
    structural target so the model emits the same shape the validation and
    repair passes already expect. The request is sent with ``strict: false`` so
    the provider never rejects the nested optional/nullable Pydantic fields;
    Pydantic validation remains the final enforcement boundary.
    """
    render_schema = RenderSchema.model_json_schema()
    render_schema_definitions = render_schema.pop("$defs", {})
    slide_object = {
        "type": "object",
        "properties": {
            "sourceSlideId": {"type": "string"},
            "slideNumber": {"type": "integer"},
            "title": {"type": "string"},
            "designRationale": {"type": "string"},
            "speakerNotes": {"type": "string"},
            "archetypeId": {"type": "string"},
            "narrativeRole": {"type": "string"},
            "renderSchema": render_schema,
        },
        "required": ["sourceSlideId", "renderSchema"],
        "additionalProperties": False,
    }
    return {
        "$defs": render_schema_definitions,
        "type": "object",
        "properties": {
            "designVersionName": {"type": "string"},
            "variantId": {"type": "string"},
            "variantRationale": {"type": "string"},
            "slides": {"type": "array", "items": slide_object},
        },
        "required": ["slides"],
        "additionalProperties": False,
    }


def _build_anthropic_prompt(llm_context: dict) -> str:
    prompt_package_name = "instant_deck" if llm_context.get("generationMode") == "instant_deck" else "smart_deck"
    llm_context = {
        **llm_context,
        "promptPackage": {
            "name": prompt_package_name,
            "version": load_prompt_package(prompt_package_name)["version"],
            "section": "generator",
        },
    }
    return build_prompt_package_text(prompt_package_name, "generator", context_label="Smart Deck context", context=llm_context)


def _call_anthropic_render_payload(llm_context: dict, model: str, api_key: str, *, deadline: OperationDeadline | None = None) -> dict:
    response_payload = call_anthropic_message(
        api_key=api_key,
        model=model,
        max_tokens=settings.anthropic_max_tokens,
        system="You output only valid JSON for a backend-validated slide render schema.",
        user=_build_anthropic_prompt(llm_context),
        timeout=deadline.provider_timeout(90.0) if deadline is not None else 90,
    )
    return _extract_json_payload(extract_anthropic_text(response_payload))


def _call_openai_render_payload(llm_context: dict, model: str, api_key: str, *, deadline: OperationDeadline | None = None) -> dict:
    _wait_for_openai_render_rate_slot(deadline)
    response_payload = call_openai_response(
        api_key=api_key,
        model=model,
        system="You output only valid JSON for a backend-validated slide render schema.",
        user=_build_anthropic_prompt(llm_context),
        timeout=deadline.provider_timeout(float(settings.openai_timeout_seconds)) if deadline is not None else settings.openai_timeout_seconds,
        max_output_tokens=settings.openai_render_max_output_tokens,
        response_format={
            "type": "json_schema",
            "name": "smart_deck_render_payload",
            "schema": _build_openai_render_payload_json_schema(),
            "strict": False,
        },
    )
    payload = _extract_json_payload(parse_openai_structured_response(response_payload))
    tracked_usage = extract_openai_usage(response_payload, model=model)
    if tracked_usage:
        payload["_tracked_usage"] = tracked_usage
    return payload


def _wait_for_openai_render_rate_slot(deadline: OperationDeadline | None = None) -> None:
    """Serialize large render requests for provider projects with low TPM limits."""
    global _openai_render_last_started_at

    minimum_interval = float(settings.openai_render_min_interval_seconds)
    if minimum_interval <= 0:
        return
    with _openai_render_rate_lock:
        now = time.monotonic()
        wait_seconds = max(0.0, minimum_interval - (now - _openai_render_last_started_at))
        if wait_seconds > 0:
            if deadline is not None and deadline.remaining() <= wait_seconds:
                raise OperationDeadlineExceeded("OpenAI render pacing exceeded the operation deadline.")
            time.sleep(wait_seconds)
            now += wait_seconds
        _openai_render_last_started_at = now


def _call_openrouter_render_payload(llm_context: dict, model: str, api_key: str, *, deadline: OperationDeadline | None = None) -> dict:
    response_payload = call_openrouter_chat_completion(
        api_key=api_key,
        model=model,
        system="You output only valid JSON for a backend-validated slide render schema.",
        user=_build_anthropic_prompt(llm_context),
        timeout=deadline.provider_timeout(90.0) if deadline is not None else 90,
        response_format={"type": "json_object"},
    )
    return _extract_json_payload(extract_openrouter_text(response_payload))


def _call_dashscope_render_payload(llm_context: dict, model: str, api_key: str, *, deadline: OperationDeadline | None = None) -> dict:
    response_payload = call_dashscope_chat_completion(
        api_key=api_key,
        model=model,
        system="You output only valid JSON for a backend-validated slide render schema.",
        user=_build_anthropic_prompt(llm_context),
        timeout=deadline.provider_timeout(float(settings.effective_qwen_timeout)) if deadline is not None else settings.effective_qwen_timeout,
        response_format={"type": "json_object"},
    )
    return _extract_json_payload(extract_dashscope_text(response_payload))


def _validate_generated_render_payload(
    render_payload: dict,
    selected_slides: list[DeckSlide],
    *,
    design_tokens: dict[str, str] | None = None,
    generation_mode: str = "standard",
) -> dict[str, dict]:
    if generation_mode == "instant_deck":
        render_payload = _normalize_instant_deck_payload_metadata(render_payload)
    expected_ids = [slide.id for slide in selected_slides]
    slides_payload = render_payload.get("slides")
    variant_metadata = _resolved_variant_metadata(render_payload.get("variantId"), render_payload.get("variantRationale"))
    explicit_variant_rationale = _normalize_label_text(render_payload.get("variantRationale"), max_length=600)
    if not isinstance(slides_payload, list):
        raise ValueError("LLM response must include a slides array.")
    if generation_mode == "instant_deck" and (variant_metadata is None or not explicit_variant_rationale):
        raise ValueError(
            "Instant Deck response must include a valid variantId and non-empty variantRationale from instantDeckContext.launchVariants."
        )
    if len(slides_payload) != len(expected_ids):
        raise ValueError("LLM response slide count must match selectedSourceSlideIds.")

    by_source_id: dict[str, dict] = {}
    for slide_payload in slides_payload:
        if not isinstance(slide_payload, dict):
            raise ValueError("Each generated slide payload must be an object.")
        source_slide_id = slide_payload.get("sourceSlideId")
        if source_slide_id not in expected_ids:
            raise ValueError(f"LLM response included an unselected source slide: {source_slide_id}")
        if source_slide_id in by_source_id:
            raise ValueError(f"LLM response duplicated source slide: {source_slide_id}")
        archetype_metadata = _resolved_archetype_metadata(slide_payload.get("archetypeId"), slide_payload.get("narrativeRole"))
        if generation_mode == "instant_deck" and (archetype_metadata is None or not archetype_metadata.get("narrativeRole")):
            raise ValueError(
                f"Instant Deck slide {source_slide_id} must include a valid archetypeId and narrativeRole."
            )
        # DISABLED: Raw provider JSON was passed directly into the strict schema.
        # Common Qwen nesting drift then discarded the entire generated deck.
        # render_schema = RenderSchema.model_validate(slide_payload.get("renderSchema")).model_dump()
        normalized_render_schema = _normalize_generated_render_schema(slide_payload.get("renderSchema"))
        if generation_mode == "instant_deck":
            _apply_instant_deck_variant_shell(
                normalized_render_schema,
                variant_metadata=variant_metadata,
                archetype_metadata=archetype_metadata,
            )
        render_schema = RenderSchema.model_validate(normalized_render_schema).model_dump()
        _validate_render_schema_legibility(render_schema, allow_reviewable_layout_issues=generation_mode == "instant_deck")
        if generation_mode == "instant_deck":
            analytics = render_schema.setdefault("analytics", {})
            provider_warnings = [str(item).strip() for item in analytics.get("qualityWarnings") or [] if str(item).strip()]
            detected_warnings = _collect_render_schema_reviewable_layout_warnings(render_schema)
            analytics["qualityWarnings"] = _cap_render_schema_quality_warnings(provider_warnings, detected_warnings)
            _apply_instant_deck_text_surface_fallback(render_schema, design_tokens=design_tokens)
        _repair_render_schema_text_contrast(render_schema, design_tokens=design_tokens)
        _validate_render_schema_visual_quality(render_schema, design_tokens=design_tokens)
        analytics = render_schema.setdefault("analytics", {})
        if variant_metadata is not None:
            if not analytics.get("deckVariantId"):
                analytics["deckVariantId"] = variant_metadata["id"]
            if not analytics.get("deckVariantLabel"):
                analytics["deckVariantLabel"] = variant_metadata["label"]
            if not analytics.get("deckVariantRationale"):
                analytics["deckVariantRationale"] = variant_metadata["rationale"]
        if archetype_metadata is not None:
            if not analytics.get("slideArchetypeId"):
                analytics["slideArchetypeId"] = archetype_metadata["id"]
            if not analytics.get("slideArchetypeLabel"):
                analytics["slideArchetypeLabel"] = archetype_metadata["label"]
            if archetype_metadata.get("narrativeRole"):
                if not analytics.get("narrativeRole"):
                    analytics["narrativeRole"] = archetype_metadata["narrativeRole"]
        if isinstance(slide_payload.get("designRationale"), str) and not analytics.get("designRationale"):
            analytics["designRationale"] = slide_payload["designRationale"].strip()[:1200]
        if isinstance(slide_payload.get("speakerNotes"), str) and not analytics.get("speakerNotes"):
            analytics["speakerNotes"] = slide_payload["speakerNotes"].strip()[:2000]
        render_schema = RenderSchema.model_validate(render_schema).model_dump()
        by_source_id[source_slide_id] = {
            "sourceSlideId": source_slide_id,
            "slideNumber": int(slide_payload.get("slideNumber") or 0),
            "title": str(slide_payload.get("title") or "Generated slide"),
            "renderSchema": render_schema,
            "variantId": analytics.get("deckVariantId"),
            "variantLabel": analytics.get("deckVariantLabel"),
            "variantRationale": analytics.get("deckVariantRationale"),
            "archetypeId": analytics.get("slideArchetypeId"),
            "archetypeLabel": analytics.get("slideArchetypeLabel"),
            "narrativeRole": analytics.get("narrativeRole"),
        }

    missing_ids = [slide_id for slide_id in expected_ids if slide_id not in by_source_id]
    if missing_ids:
        raise ValueError(f"LLM response omitted selected source slides: {', '.join(missing_ids)}")
    return by_source_id


def _validate_render_schema_legibility(render_schema: dict, *, allow_reviewable_layout_issues: bool = False) -> None:
    """Reject document-scale text so the existing repair pass can reflow it."""
    supporting_markers = (
        "eyebrow",
        "kicker",
        "caption",
        "footnote",
        "source",
        "evidence",
        "note",
        "disclaimer",
        "footer",
        "audit",
        "date_tag",
        "synthetic",
        "slide_number",
        "page_number",
    )
    headline_ids = {"headline", "title", "el_title", "main_title", "hero_title"}
    failures: list[str] = []
    for element in render_schema.get("elements", []):
        if not isinstance(element, dict) or element.get("type") != "text":
            continue
        element_id = str(element.get("id") or "text")
        normalized_id = element_id.lower()
        font_size = element.get("fontSize")
        analytics_key = str(element.get("analyticsKey") or "").lower()
        if normalized_id in headline_ids or ("headline" in normalized_id and "subheadline" not in normalized_id) or analytics_key == "headline":
            minimum = 44
        elif any(marker in normalized_id for marker in supporting_markers):
            minimum = 20
        else:
            minimum = 28
        if not isinstance(font_size, (int, float)) or font_size < minimum:
            failures.append(f"{element_id} requires fontSize >= {minimum}px (received {font_size!r})")

    if not allow_reviewable_layout_issues:
        failures.extend(_collect_render_schema_reviewable_layout_warnings(render_schema))

    if failures:
        raise ValueError(
            "Smart Deck typography is not presentation-legible on the 1920x1080 canvas: "
            + "; ".join(failures)
            + ". Shorten copy and resize or reflow text boxes instead of shrinking text."
        )


def _collect_render_schema_reviewable_layout_warnings(render_schema: dict) -> list[str]:
    warnings: list[str] = []
    text_elements = [
        element
        for element in render_schema.get("elements", [])
        if isinstance(element, dict) and element.get("type") == "text"
    ]

    def estimated_line_capacity(element: dict, font_size: float) -> tuple[int, float]:
        width = float(element.get("width") or 0)
        height = float(element.get("height") or 0)
        chars_per_line = max(1, int(width / max(font_size * 0.52, 1)))
        text = str(element.get("text") or "")
        wrapped_lines = 0
        for raw_line in text.splitlines() or [text]:
            compact_line = raw_line.strip()
            wrapped_lines += max(1, math.ceil(len(compact_line) / chars_per_line)) if compact_line else 1
        required_height = wrapped_lines * font_size * 1.08
        return wrapped_lines, required_height - height

    def text_overlap_area(first: dict, second: dict) -> float:
        left = max(float(first.get("x") or 0), float(second.get("x") or 0))
        top = max(float(first.get("y") or 0), float(second.get("y") or 0))
        right = min(
            float(first.get("x") or 0) + float(first.get("width") or 0),
            float(second.get("x") or 0) + float(second.get("width") or 0),
        )
        bottom = min(
            float(first.get("y") or 0) + float(first.get("height") or 0),
            float(second.get("y") or 0) + float(second.get("height") or 0),
        )
        return max(0.0, right - left) * max(0.0, bottom - top)

    for element in text_elements:
        font_size = element.get("fontSize")
        if not isinstance(font_size, (int, float)):
            continue
        if isinstance(element.get("text"), str) and element.get("text").strip():
            estimated_lines, extra_height = estimated_line_capacity(element, float(font_size))
            if extra_height > max(float(font_size) * 0.6, 12.0):
                warnings.append(
                    f"{str(element.get('id') or 'text')} text box is too small for approximately {estimated_lines} wrapped lines at {font_size}px; adjust in Smart Edit"
                )

    for index, first in enumerate(text_elements):
        first_area = max(1.0, float(first.get("width") or 0) * float(first.get("height") or 0))
        first_id = str(first.get("id") or f"text_{index}")
        for second in text_elements[index + 1 :]:
            second_area = max(1.0, float(second.get("width") or 0) * float(second.get("height") or 0))
            overlap_area = text_overlap_area(first, second)
            if overlap_area <= 1200:
                continue
            if overlap_area / min(first_area, second_area) < 0.08:
                continue
            warnings.append(f"{first_id} overlaps {str(second.get('id') or 'text')}; adjust in Smart Edit")
    return warnings


def _cap_render_schema_quality_warnings(
    provider_warnings: list[str],
    detected_warnings: list[str],
    *,
    cap: int = 12,
) -> list[str]:
    """Return distinct warnings, prioritizing detected layout defects within cap."""
    if cap <= 0:
        return []
    unique_provider = list(dict.fromkeys(provider_warnings))
    unique_detected = list(dict.fromkeys(detected_warnings))[:cap]
    detected_set = set(unique_detected)
    provider_only = [warning for warning in unique_provider if warning not in detected_set]
    provider_slots = max(0, cap - len(unique_detected))
    return provider_only[:provider_slots] + unique_detected


def _persisted_generated_slide_validation_warnings(render_schema: dict) -> list[str]:
    analytics = render_schema.get("analytics") if isinstance(render_schema.get("analytics"), dict) else {}
    warnings = [str(item).strip() for item in analytics.get("qualityWarnings") or [] if str(item).strip()]
    for item in analytics.get("missingInputs") or []:
        missing_input = str(item).strip()
        warning = f"Missing input: {missing_input}" if missing_input else ""
        if warning and warning not in warnings:
            warnings.append(warning)
    return warnings


def _persisted_generated_slide_validation_status(render_schema: dict) -> str:
    return "warning" if _persisted_generated_slide_validation_warnings(render_schema) else "valid"


def _resolve_render_color(value: object, design_tokens: dict[str, str]) -> str | None:
    resolved = design_tokens.get(str(value), value)
    if not isinstance(resolved, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", resolved):
        return None
    return resolved


def _relative_luminance(value: str) -> float:
    channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _render_item_z_index(item: dict, default: int) -> int:
    value = item.get("zIndex")
    return int(value) if value is not None else default


def _render_item_covers_text(item: dict, text: dict) -> bool:
    return (
        float(item.get("x") or 0) <= float(text.get("x") or 0)
        and float(item.get("y") or 0) <= float(text.get("y") or 0)
        and float(item.get("x") or 0) + float(item.get("width") or 0) >= float(text.get("x") or 0) + float(text.get("width") or 0)
        and float(item.get("y") or 0) + float(item.get("height") or 0) >= float(text.get("y") or 0) + float(text.get("height") or 0)
    )


def _render_item_intersects_text(item: dict, text: dict) -> bool:
    return (
        float(item.get("x") or 0) < float(text.get("x") or 0) + float(text.get("width") or 0)
        and float(item.get("x") or 0) + float(item.get("width") or 0) > float(text.get("x") or 0)
        and float(item.get("y") or 0) < float(text.get("y") or 0) + float(text.get("height") or 0)
        and float(item.get("y") or 0) + float(item.get("height") or 0) > float(text.get("y") or 0)
    )


def _text_contrast_minimum(text: dict) -> float:
    font_size = float(text.get("fontSize") or 0)
    raw_font_weight = str(text.get("fontWeight") or "").lower()
    font_weight = int(raw_font_weight) if raw_font_weight.isdigit() else 700 if raw_font_weight in {"bold", "bolder"} else 400
    return 3.0 if font_size >= 24 or (font_size >= 19 and font_weight >= 700) else 4.5


def _resolve_text_surface_color(
    text: dict,
    *,
    elements: list[dict],
    layers: list[dict],
    base_color: str | None,
    design_tokens: dict[str, str],
) -> str | None:
    text_z = _render_item_z_index(text, 20)
    surface_candidates: list[tuple[int, int, str | None]] = [(-100, -1, base_color)]
    for visual_order, visual in enumerate(elements, start=len(layers)):
        if visual is text or visual.get("type") == "text" or not _render_item_intersects_text(visual, text):
            continue
        visual_z = _render_item_z_index(visual, 20)
        visual_color = (
            _resolve_render_color(visual.get("fillToken"), design_tokens)
            if visual.get("type") == "shape" and visual_z < text_z and _render_item_covers_text(visual, text)
            else None
        )
        surface_candidates.append((visual_z, visual_order, visual_color))
    for layer_order, layer in enumerate(layers):
        if not _render_item_intersects_text(layer, text):
            continue
        style = layer.get("style") if isinstance(layer.get("style"), dict) else {}
        layer_z = _render_item_z_index(layer, 0)
        layer_color = (
            _resolve_render_color(style.get("fill"), design_tokens)
            if layer.get("type") == "shape"
            and layer.get("shape") == "rectangle"
            and layer_z < text_z
            and float(style.get("opacity") if style.get("opacity") is not None else 1) >= 1
            and _render_item_covers_text(layer, text)
            else None
        )
        surface_candidates.append((layer_z, layer_order, layer_color))
    return max(surface_candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def _append_brand_token_usage(render_schema: dict, token_name: str) -> None:
    brand_tokens_used = render_schema.setdefault("brandTokensUsed", [])
    if isinstance(brand_tokens_used, list) and len(brand_tokens_used) < 24 and token_name not in brand_tokens_used:
        brand_tokens_used.append(token_name)


def _upsert_variant_shape(
    elements: list[dict],
    *,
    shape_id: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
    fill_token: str,
) -> None:
    payload = {
        "id": shape_id,
        "type": "shape",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "zIndex": z_index,
        "fillToken": fill_token,
        "analyticsKey": shape_id,
    }
    for index, element in enumerate(elements):
        if isinstance(element, dict) and element.get("id") == shape_id:
            elements[index] = payload
            return
    elements.append(payload)


def _upsert_variant_background_layer(
    layers: list[dict],
    *,
    layer_id: str,
    layer_type: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
    fill: str | None = None,
    opacity: float = 1.0,
    radius: int = 0,
    shape: str | None = "rectangle",
    asset_url: str | None = None,
    role: str | None = None,
) -> None:
    payload = {
        "id": layer_id,
        "type": layer_type,
        "shape": shape if layer_type == "shape" else None,
        "role": role,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "zIndex": z_index,
        "style": {"fill": fill, "opacity": opacity, "radius": radius} if layer_type == "shape" else {"opacity": opacity, "radius": radius},
        "assetUrl": asset_url if layer_type == "image" else None,
    }
    for index, layer in enumerate(layers):
        if isinstance(layer, dict) and layer.get("id") == layer_id:
            layers[index] = payload
            return
    layers.append(payload)


def _text_element_kind(element: dict) -> str:
    analytics_key = str(element.get("analyticsKey") or "").lower()
    element_id = str(element.get("id") or "").lower()
    if analytics_key == "headline" or "headline" in element_id or element_id in {"title", "el_title", "main_title", "hero_title"}:
        return "headline"
    if analytics_key in {"eyebrow", "kicker"} or any(marker in element_id for marker in ("eyebrow", "kicker")):
        return "eyebrow"
    return "body"


def _largest_image_element(elements: list[dict]) -> dict | None:
    images = [element for element in elements if isinstance(element, dict) and element.get("type") == "image"]
    if not images:
        return None
    return max(images, key=lambda element: float(element.get("width") or 0) * float(element.get("height") or 0))


def _apply_instant_deck_variant_shell(
    render_schema: dict,
    *,
    variant_metadata: dict[str, str] | None,
    archetype_metadata: dict[str, str | None] | None,
) -> None:
    if variant_metadata is None:
        return
    elements = render_schema.get("elements")
    if not isinstance(elements, list) or not elements:
        return

    background = render_schema.get("background") if isinstance(render_schema.get("background"), dict) else None
    if background is None:
        return
    if background.get("type") != "layered":
        background["type"] = "layered"
        background["fill"] = background.get("value") or background.get("fill") or "brand.surfaceAlt"
        background.pop("value", None)
    elif not background.get("fill"):
        background["fill"] = "brand.surfaceAlt"
    layers = background.setdefault("layers", [])
    if not isinstance(layers, list):
        layers = []
        background["layers"] = layers

    width = int(render_schema.get("width") or 1920)
    height = int(render_schema.get("height") or 1080)
    variant_id = variant_metadata["id"]
    archetype_id = str((archetype_metadata or {}).get("id") or "")

    text_elements = [element for element in elements if isinstance(element, dict) and element.get("type") == "text"]
    image_element = _largest_image_element(elements)
    if not text_elements:
        return

    for token in ("brand.surface", "brand.surfaceAlt", "brand.accent", "brand.heading", "brand.body"):
        _append_brand_token_usage(render_schema, token)

    if variant_id == "continuum":
        _upsert_variant_background_layer(layers, layer_id="variant_continuum_panel", layer_type="shape", x=96, y=96, width=820, height=888, z_index=1, fill="brand.surface", opacity=1, radius=32, role="variant_panel")
        _upsert_variant_background_layer(layers, layer_id="variant_continuum_rail", layer_type="shape", x=96, y=96, width=18, height=888, z_index=2, fill="brand.accent", opacity=1, radius=24, role="variant_accent")
        _upsert_variant_background_layer(layers, layer_id="variant_continuum_footer", layer_type="shape", x=96, y=920, width=820, height=64, z_index=2, fill="brand.surfaceAlt", opacity=1, radius=20, role="variant_footer")
        _upsert_variant_background_layer(layers, layer_id="variant_continuum_orb", layer_type="shape", x=1320, y=-120, width=540, height=540, z_index=0, fill="brand.accent", opacity=0.18, radius=999, shape="circle", role="variant_orb")
        for element in text_elements:
            kind = _text_element_kind(element)
            if kind == "eyebrow":
                element.update({"x": 156, "y": 136, "width": 680, "height": 52, "zIndex": max(_render_item_z_index(element, 30), 30)})
            elif kind == "headline":
                element.update({"x": 156, "y": 214, "width": 690, "height": 210, "zIndex": max(_render_item_z_index(element, 31), 31)})
            else:
                element.update({"x": 156, "y": 500 if archetype_id not in {"traction", "market", "business-model"} else 458, "width": 690, "height": 250, "zIndex": max(_render_item_z_index(element, 32), 32)})
        if image_element is not None:
            asset_url = image_element.get("assetUrl")
            if isinstance(asset_url, str) and asset_url.strip():
                _upsert_variant_background_layer(layers, layer_id="variant_continuum_image", layer_type="image", x=1010, y=132, width=790, height=816, z_index=0, asset_url=asset_url, opacity=1, radius=28, role="variant_hero_image")
                elements.remove(image_element)

    elif variant_id == "hypercut":
        _upsert_variant_background_layer(layers, layer_id="variant_hypercut_topbar", layer_type="shape", x=0, y=0, width=width, height=120, z_index=2, fill="brand.accent", opacity=1, radius=0, role="variant_topbar")
        _upsert_variant_background_layer(layers, layer_id="variant_hypercut_panel", layer_type="shape", x=96, y=160, width=860, height=760, z_index=1, fill="brand.surface", opacity=1, radius=28, role="variant_panel")
        _upsert_variant_background_layer(layers, layer_id="variant_hypercut_footer", layer_type="shape", x=96, y=936, width=860, height=48, z_index=2, fill="brand.surfaceAlt", opacity=1, radius=18, role="variant_footer")
        _upsert_variant_background_layer(layers, layer_id="variant_hypercut_orb", layer_type="shape", x=1280, y=120, width=620, height=620, z_index=0, fill="brand.accent", opacity=0.24, radius=999, shape="circle", role="variant_orb")
        for element in text_elements:
            kind = _text_element_kind(element)
            if kind == "eyebrow":
                element.update({"x": 144, "y": 188, "width": 720, "height": 52, "zIndex": max(_render_item_z_index(element, 30), 30), "colorToken": "brand.accent"})
            elif kind == "headline":
                element.update({"x": 144, "y": 266, "width": 720, "height": 228, "zIndex": max(_render_item_z_index(element, 31), 31)})
            else:
                element.update({"x": 144, "y": 560, "width": 720, "height": 220, "zIndex": max(_render_item_z_index(element, 32), 32)})
        if image_element is not None:
            asset_url = image_element.get("assetUrl")
            if isinstance(asset_url, str) and asset_url.strip():
                _upsert_variant_background_layer(layers, layer_id="variant_hypercut_image", layer_type="image", x=1038, y=126, width=720, height=840, z_index=0, asset_url=asset_url, opacity=1, radius=20, role="variant_hero_image")
                elements.remove(image_element)

    elif variant_id == "zero":
        _upsert_variant_background_layer(layers, layer_id="variant_zero_panel", layer_type="shape", x=120, y=184, width=760, height=660, z_index=1, fill="brand.surface", opacity=1, radius=26, role="variant_panel")
        _upsert_variant_background_layer(layers, layer_id="variant_zero_rule", layer_type="shape", x=120, y=120, width=340, height=12, z_index=2, fill="brand.accent", opacity=1, radius=8, role="variant_rule")
        _upsert_variant_background_layer(layers, layer_id="variant_zero_footer", layer_type="shape", x=120, y=864, width=760, height=56, z_index=2, fill="brand.surfaceAlt", opacity=1, radius=18, role="variant_footer")
        _upsert_variant_background_layer(layers, layer_id="variant_zero_glow", layer_type="shape", x=1260, y=120, width=480, height=480, z_index=0, fill="brand.accent", opacity=0.14, radius=999, shape="circle", role="variant_glow")
        for element in text_elements:
            kind = _text_element_kind(element)
            if kind == "eyebrow":
                element.update({"x": 168, "y": 214, "width": 620, "height": 48, "zIndex": max(_render_item_z_index(element, 30), 30)})
            elif kind == "headline":
                element.update({"x": 168, "y": 292, "width": 620, "height": 190, "zIndex": max(_render_item_z_index(element, 31), 31)})
            else:
                element.update({"x": 168, "y": 536, "width": 620, "height": 210, "zIndex": max(_render_item_z_index(element, 32), 32)})
        if image_element is not None:
            asset_url = image_element.get("assetUrl")
            if isinstance(asset_url, str) and asset_url.strip():
                _upsert_variant_background_layer(layers, layer_id="variant_zero_image", layer_type="image", x=980, y=182, width=780, height=676, z_index=0, asset_url=asset_url, opacity=1, radius=24, role="variant_hero_image")
                elements.remove(image_element)


def _apply_instant_deck_text_surface_fallback(
    render_schema: dict,
    *,
    design_tokens: dict[str, str] | None = None,
) -> None:
    """Add a bounded solid card behind text when Instant Deck imagery/layers would otherwise fail visual validation."""
    background = render_schema.get("background") if isinstance(render_schema.get("background"), dict) else {}
    background_type = background.get("type")
    if background_type not in {"image", "layered"}:
        return

    elements = render_schema.get("elements")
    if not isinstance(elements, list):
        return
    tokens = dict(design_tokens or DEFAULT_DESIGN_TOKENS)
    layers = [layer for layer in background.get("layers", []) if isinstance(layer, dict)]
    base_color = _resolve_render_color(background.get("fill") if background_type == "layered" else background.get("value"), tokens)
    width = int(render_schema.get("width") or 1920)
    height = int(render_schema.get("height") or 1080)
    canvas_area = max(width * height, 1)
    approved_tokens = ("brand.heading", "brand.body", "brand.surface", "brand.surfaceAlt", "brand.accent", "brand.muted")
    existing_ids = {str(element.get("id") or "") for element in elements if isinstance(element, dict)}

    for text in [element for element in elements if isinstance(element, dict) and element.get("type") == "text"]:
        if _resolve_text_surface_color(text, elements=elements, layers=layers, base_color=base_color, design_tokens=tokens) is not None:
            continue
        text_z = _render_item_z_index(text, 20)
        if text_z <= 0:
            continue
        minimum = _text_contrast_minimum(text)
        text_color = _resolve_render_color(text.get("colorToken"), tokens)
        best_fill_token: str | None = None
        best_fill_score = 0.0
        for fill_token in approved_tokens:
            fill_color = _resolve_render_color(fill_token, tokens)
            if fill_color is None:
                continue
            candidate_scores = []
            if text_color is not None:
                candidate_scores.append(_contrast_ratio(text_color, fill_color))
            candidate_scores.extend(
                _contrast_ratio(candidate_text_color, fill_color)
                for candidate_text_token in approved_tokens
                if (candidate_text_color := _resolve_render_color(candidate_text_token, tokens)) is not None
            )
            achievable_contrast = max(candidate_scores, default=0.0)
            if achievable_contrast >= minimum and achievable_contrast > best_fill_score:
                best_fill_token = fill_token
                best_fill_score = achievable_contrast
        if best_fill_token is None:
            continue

        font_size = float(text.get("fontSize") or 28)
        pad_x = int(max(24, min(72, round(font_size * 1.2))))
        pad_y = int(max(16, min(48, round(font_size * 0.75))))
        left = max(0, int(float(text.get("x") or 0) - pad_x))
        top = max(0, int(float(text.get("y") or 0) - pad_y))
        right = min(width, int(float(text.get("x") or 0) + float(text.get("width") or 0) + pad_x))
        bottom = min(height, int(float(text.get("y") or 0) + float(text.get("height") or 0) + pad_y))
        card_width = right - left
        card_height = bottom - top
        if card_width <= 0 or card_height <= 0 or card_width * card_height > canvas_area * 0.6:
            continue

        base_id = f"{text.get('id') or 'text'}_contrast_card"
        card_id = base_id
        suffix = 2
        while card_id in existing_ids:
            card_id = f"{base_id}_{suffix}"
            suffix += 1
        existing_ids.add(card_id)
        elements.append(
            {
                "id": card_id,
                "type": "shape",
                "x": left,
                "y": top,
                "width": card_width,
                "height": card_height,
                "zIndex": text_z - 1,
                "fillToken": best_fill_token,
            }
        )
        _append_brand_token_usage(render_schema, best_fill_token)


def _repair_render_schema_text_contrast(
    render_schema: dict,
    *,
    design_tokens: dict[str, str] | None = None,
) -> None:
    """Use an approved brand token when provider-selected text is unreadable on a known solid surface."""
    background = render_schema.get("background") if isinstance(render_schema.get("background"), dict) else {}
    elements = [element for element in render_schema.get("elements", []) if isinstance(element, dict)]
    tokens = dict(design_tokens or DEFAULT_DESIGN_TOKENS)
    background_type = background.get("type")
    base_color = (
        _resolve_render_color(background.get("fill") if background_type == "layered" else background.get("value"), tokens)
        if background_type not in {"gradient", "image"}
        else None
    )
    layers = [layer for layer in background.get("layers", []) if isinstance(layer, dict)]

    for text in (element for element in elements if element.get("type") == "text"):
        text_color = _resolve_render_color(text.get("colorToken"), tokens)
        if text_color is None:
            continue
        surface_color = _resolve_text_surface_color(text, elements=elements, layers=layers, base_color=base_color, design_tokens=tokens)
        if surface_color is None:
            continue
        minimum = _text_contrast_minimum(text)
        if _contrast_ratio(text_color, surface_color) >= minimum:
            continue
        replacements = [
            (token_name, resolved)
            for token_name in ("brand.heading", "brand.body", "brand.surface", "brand.surfaceAlt", "brand.accent", "brand.muted")
            if (resolved := _resolve_render_color(token_name, tokens)) is not None
            and _contrast_ratio(resolved, surface_color) >= minimum
        ]
        if not replacements:
            continue
        replacement_token, _ = max(replacements, key=lambda candidate: _contrast_ratio(candidate[1], surface_color))
        text["colorToken"] = replacement_token
        _append_brand_token_usage(render_schema, replacement_token)


def _validate_render_schema_visual_quality(
    render_schema: dict,
    *,
    design_tokens: dict[str, str] | None = None,
) -> None:
    """Reject flat or unreadable slide scenes so the existing repair pass redesigns them."""
    background = render_schema.get("background") if isinstance(render_schema.get("background"), dict) else {}
    elements = [element for element in render_schema.get("elements", []) if isinstance(element, dict)]
    width = int(render_schema.get("width") or 1920)
    height = int(render_schema.get("height") or 1080)
    background_type = background.get("type")
    layers = [layer for layer in background.get("layers", []) if isinstance(layer, dict)]

    canvas_area = width * height

    def visible_area(item: dict) -> float:
        left = max(0.0, float(item.get("x") or 0))
        top = max(0.0, float(item.get("y") or 0))
        right = min(float(width), float(item.get("x") or 0) + float(item.get("width") or 0))
        bottom = min(float(height), float(item.get("y") or 0) + float(item.get("height") or 0))
        return max(0.0, right - left) * max(0.0, bottom - top)

    meaningful_layer = any(
        visible_area(layer) >= canvas_area * 0.01
        and float((layer.get("style") or {}).get("opacity") if isinstance(layer.get("style"), dict) and (layer.get("style") or {}).get("opacity") is not None else 1) > 0.15
        and (
            layer.get("type") == "image"
            or layer.get("shape") != "rectangle"
            or int(layer.get("x") or 0) != 0
            or int(layer.get("y") or 0) != 0
            or int(layer.get("width") or 0) < width
            or int(layer.get("height") or 0) < height
        )
        for layer in layers
    )
    meaningful_visual = bool(
        background_type in {"gradient", "image"}
        or meaningful_layer
        or any(
            element.get("type") in {"shape", "image", "chart_placeholder"}
            and visible_area(element) >= canvas_area * 0.01
            for element in elements
        )
    )
    if not meaningful_visual:
        raise ValueError(
            "Smart Deck visual composition is incomplete: a flat background with text only is not a presentation-ready slide. "
            "Add an approved internal image, gradient, chart, foreground shape, or decorative layered background."
        )

    tokens = dict(design_tokens or DEFAULT_DESIGN_TOKENS)
    base_color = (
        _resolve_render_color(background.get("fill") if background_type == "layered" else background.get("value"), tokens)
        if background_type not in {"gradient", "image"}
        else None
    )

    failures: list[str] = []
    for text in (element for element in elements if element.get("type") == "text"):
        text_color = _resolve_render_color(text.get("colorToken"), tokens)
        if text_color is None:
            failures.append(f"{text.get('id') or 'text'} requires an approved, resolvable text color")
            continue
        surface_color = _resolve_text_surface_color(text, elements=elements, layers=layers, base_color=base_color, design_tokens=tokens)
        if surface_color is None:
            failures.append(f"{text.get('id') or 'text'} requires a solid contrasting overlay or card over the {background_type} background")
            continue
        minimum = _text_contrast_minimum(text)
        ratio = _contrast_ratio(text_color, surface_color)
        if ratio < minimum:
            failures.append(f"{text.get('id') or 'text'} contrast is {ratio:.2f}:1; requires at least {minimum:.1f}:1")
    if failures:
        raise ValueError(
            "Smart Deck text is not readable against its rendered background: "
            + "; ".join(failures)
            + ". Use contrasting brand tokens, a readable overlay, or a contrasting card."
        )


def _normalize_generated_render_schema(payload: object) -> object:
    """Repair bounded provider formatting drift before strict schema validation."""
    if not isinstance(payload, dict):
        return payload

    normalized = copy.deepcopy(payload)
    token_aliases = {
        "brand.primary": "brand.accent",
        "brand.text": "brand.body",
    }
    background = normalized.get("background")
    if isinstance(background, dict):
        background_type = background.get("type")
        if background_type == "layered" and not background.get("fill"):
            layers = background.get("layers")
            first_layer = layers[0] if isinstance(layers, list) and layers and isinstance(layers[0], dict) else {}
            first_style = first_layer.get("style") if isinstance(first_layer.get("style"), dict) else {}
            background["fill"] = first_style.get("fill") or "brand.surface"
        elif background_type in {"color", "token", "gradient"}:
            if not background.get("value") and isinstance(background.get("fill"), str):
                background["value"] = background["fill"]
            background.pop("fill", None)

    elements = normalized.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue
            style = element.get("style")
            if isinstance(style, dict) and not element.get("fillToken") and isinstance(style.get("fill"), str):
                element["fillToken"] = style["fill"]
            provider_fill = element.pop("fill", None)
            if not element.get("fillToken") and isinstance(provider_fill, str):
                element["fillToken"] = provider_fill
            for token_key in ("colorToken", "fillToken"):
                if element.get(token_key) in token_aliases:
                    element[token_key] = token_aliases[element[token_key]]
            # Provider-only shape/style nesting is represented by the canonical
            # element type and flat token fields after normalization.
            element.pop("shape", None)
            element.pop("style", None)
            # Provider role labels are generation hints, not part of the
            # renderer contract. Preserve their useful meaning in analyticsKey
            # when possible, then remove the unsupported field before strict
            # validation so a harmless Qwen annotation cannot fail a slide.
            provider_role = element.pop("role", None)
            if not element.get("analyticsKey") and isinstance(provider_role, str):
                normalized_role = re.sub(r"[^a-z0-9_]+", "_", provider_role.strip().lower()).strip("_")
                if normalized_role:
                    element["analyticsKey"] = normalized_role[:80]

    analytics = normalized.get("analytics")
    if isinstance(analytics, dict) and isinstance(analytics.get("slidePurpose"), str):
        analytics["slidePurpose"] = analytics["slidePurpose"].strip()[:80]
    brand_tokens_used = normalized.get("brandTokensUsed")
    if isinstance(brand_tokens_used, list):
        normalized["brandTokensUsed"] = [
            token_aliases.get(token, token)
            for token in brand_tokens_used
        ]
    return normalized


def _build_generation_plan(llm_context: dict, selected_slides: list[DeckSlide]) -> dict:
    archetype_context = llm_context.get("slideArchetypeContext") if isinstance(llm_context.get("slideArchetypeContext"), dict) else {}
    inferred_archetypes = archetype_context.get("inferredArchetypes") if isinstance(archetype_context.get("inferredArchetypes"), list) else []
    primary_archetype = inferred_archetypes[0] if inferred_archetypes else {}
    knowledge_metadata = llm_context.get("knowledgeMetadata") if isinstance(llm_context.get("knowledgeMetadata"), dict) else {}
    source_fact_package = llm_context.get("sourceFactPackage") if isinstance(llm_context.get("sourceFactPackage"), dict) else {}
    return {
        "schemaVersion": "smart-deck-generation-plan.v1",
        "knowledgeMetadata": knowledge_metadata,
        "runtimeContext": llm_context.get("runtimeContext") if isinstance(llm_context.get("runtimeContext"), dict) else {},
        "sourceFactSummary": {
            "schemaVersion": source_fact_package.get("schemaVersion"),
            "factCount": source_fact_package.get("factCount") or 0,
            "coverage": source_fact_package.get("coverage") or {},
        },
        "selectedSlideCount": len(selected_slides),
        "recommendedSequence": archetype_context.get("recommendedSequence") or [],
        "primaryArchetype": {
            "slug": primary_archetype.get("slug"),
            "description": primary_archetype.get("description"),
            "requiredInputs": primary_archetype.get("requiredInputs") or [],
            "renderContract": primary_archetype.get("renderContract") or {},
            "outputContract": primary_archetype.get("outputContract") or {},
        },
        "steps": [
            {
                "id": "classify",
                "instruction": "Classify each selected slide by narrative job before generating.",
            },
            {
                "id": "retrieve",
                "instruction": "Use sourceFactPackage, audience context, deck recipe, diagnostics, writing rules, and hallucination constraints.",
            },
            {
                "id": "draft",
                "instruction": "Return render_schema_json only, with analytics for source facts, assumptions, missing inputs, quality warnings, and confidence.",
            },
            {
                "id": "critique",
                "instruction": "Check unsupported claims, missing evidence, sequence fit, visual density, and render-schema validity.",
            },
            {
                "id": "repair",
                "instruction": "If critique status is review, make one bounded repair pass and validate again before persistence.",
            },
            {
                "id": "persist",
                "instruction": "Persist final validated render schema, artifacts, telemetry, model, provider, and knowledge version.",
            },
        ],
    }


def _source_fact_package_for_generation(llm_context: dict, selected_slides: list[DeckSlide]) -> dict:
    existing = llm_context.get("sourceFactPackage")
    if isinstance(existing, dict):
        return existing
    recovered_facts: list[dict[str, Any]] = []
    for fact in llm_context.get("sourceFacts", []):
        if not isinstance(fact, dict):
            continue
        fact_id = str(fact.get("id") or fact.get("factId") or "").strip()
        text = _normalise_fact_text(fact.get("text"))
        source_type = str(fact.get("sourceType") or "").strip()
        source_id = str(fact.get("sourceId") or "").strip()
        if not fact_id or not text or not source_type or not source_id:
            continue
        classification = classify_source_fact(
            text=text,
            source_type=source_type,
            field=str(fact.get("field") or "") or None,
            confidence=str(fact.get("confidence") or "") or None,
        )
        recovered_facts.append({
            **fact,
            "id": fact_id,
            "factId": fact_id,
            "text": text,
            "sourceType": source_type,
            "sourceId": source_id,
            "sourceSlideIds": [
                source_slide_id
                for source_slide_id in (fact.get("sourceSlideIds") or [])
                if isinstance(source_slide_id, str) and source_slide_id
            ],
            "factType": str(fact.get("factType") or classification["factType"]),
            "evidenceStrength": str(fact.get("evidenceStrength") or classification["evidenceStrength"]),
            "safetyFlags": list(fact.get("safetyFlags") or classification["safetyFlags"]),
        })
    return _canonical_source_fact_package(
        recovered_facts,
        selected_slides,
        has_user_instruction=bool(_normalise_fact_text(llm_context.get("objective"))),
        has_additional_context=bool(_normalise_fact_text(llm_context.get("additionalContext"))),
        has_prompt_context_artifact=isinstance(llm_context.get("artifactContext"), dict),
    )


def _runtime_context_from_authoritative_pack(context_pack: dict[str, Any]) -> dict[str, Any]:
    """Adapt an immutable recovered pack for in-process Smart Deck consumers."""
    from app.services.llm.full_html_generation_service import (
        build_full_html_provider_runtime_context,
    )

    return build_full_html_provider_runtime_context(context_pack)


def _historical_augmented_full_html_provider_context(
    context_pack: dict[str, Any],
    selected_slides: list[Any],
) -> dict[str, Any]:
    """Reconstruct the exact pre-hardening v2-v5 provider body for replay only."""
    historical = copy.deepcopy(context_pack)
    brand = historical.get("brand")
    if not isinstance(brand, dict):
        brand = {}
    brand_tokens = brand.get("tokens")
    if (
        not isinstance(brand_tokens, dict)
        or not set(DEFAULT_DESIGN_TOKENS).issubset(brand_tokens)
    ):
        neutral_brand = build_provider_safe_brand_context(None, neutral_when_absent=True)
        brand = {
            **neutral_brand,
            **brand,
            "tokens": {
                **neutral_brand["tokens"],
                **(brand_tokens if isinstance(brand_tokens, dict) else {}),
            },
        }
    historical["brand"] = brand
    source_fact_package = _source_fact_package_for_generation(historical, selected_slides)
    historical["sourceFactPackage"] = copy.deepcopy(source_fact_package)
    historical["generationPlan"] = _build_generation_plan(historical, selected_slides)
    return historical


_FULL_HTML_BOOKKEEPING_SCHEMAS = {
    "smart-deck-source-fact-bookkeeping.v1",
    "smart-deck-generation-plan-bookkeeping.v1",
}
_FULL_HTML_BOOKKEEPING_KEYS = {
    "schemaVersion",
    "selectedSlideCount",
    "factCount",
    "sourceSlidesWithFactsCount",
    "missingSourceSlideCount",
    "sourceContentPersisted",
}
_MAX_FULL_HTML_BOOKKEEPING_COUNT = 100_000


def _validate_full_html_bookkeeping_payload(payload: dict) -> None:
    """Reject anything outside the persisted full-HTML scalar contract."""
    if set(payload) != _FULL_HTML_BOOKKEEPING_KEYS:
        raise ValueError("Invalid full HTML artifact bookkeeping keys.")
    if payload["schemaVersion"] not in _FULL_HTML_BOOKKEEPING_SCHEMAS:
        raise ValueError("Invalid full HTML artifact bookkeeping schema.")
    for key in (
        "selectedSlideCount",
        "factCount",
        "sourceSlidesWithFactsCount",
        "missingSourceSlideCount",
    ):
        value = payload[key]
        if type(value) is not int or not 0 <= value <= _MAX_FULL_HTML_BOOKKEEPING_COUNT:
            raise ValueError("Invalid full HTML artifact bookkeeping count.")
    if payload["sourceContentPersisted"] is not False:
        raise ValueError("Full HTML source content cannot be persisted in bookkeeping artifacts.")
    if payload["selectedSlideCount"] != (
        payload["sourceSlidesWithFactsCount"] + payload["missingSourceSlideCount"]
    ):
        raise ValueError("Invalid full HTML artifact slide coverage counts.")


def _content_free_source_fact_bookkeeping(
    source_fact_package: dict,
    selected_slides: list[DeckSlide] | list[SimpleNamespace],
) -> dict:
    """Build a closed, scalar-only full-HTML fact summary from runtime facts."""
    selected_ids = {
        str(slide.id) for slide in selected_slides if isinstance(getattr(slide, "id", None), str)
    }
    facts = [fact for fact in source_fact_package.get("facts", []) if isinstance(fact, dict)]
    covered_ids: set[str] = set()
    for fact in facts:
        explicit_ids = fact.get("sourceSlideIds")
        source_ids = explicit_ids if isinstance(explicit_ids, list) else []
        if "sourceSlideIds" not in fact and fact.get("sourceType") == "source_slide":
            source_ids = [fact.get("sourceId")]
        covered_ids.update(
            source_id
            for source_id in source_ids
            if isinstance(source_id, str) and source_id in selected_ids
        )
    bookkeeping = {
        "schemaVersion": "smart-deck-source-fact-bookkeeping.v1",
        "factCount": len(facts),
        "selectedSlideCount": len(selected_ids),
        "sourceSlidesWithFactsCount": len(covered_ids),
        "missingSourceSlideCount": len(selected_ids - covered_ids),
        "sourceContentPersisted": False,
    }
    _validate_full_html_bookkeeping_payload(bookkeeping)
    return bookkeeping


def _content_free_generation_plan_bookkeeping(
    source_fact_bookkeeping: dict,
    selected_slides: list[DeckSlide] | list[SimpleNamespace],
) -> dict:
    """Build the complete allowlisted full-HTML generation-plan artifact."""
    bookkeeping = {
        "schemaVersion": "smart-deck-generation-plan-bookkeeping.v1",
        "selectedSlideCount": len({
            str(slide.id) for slide in selected_slides if isinstance(getattr(slide, "id", None), str)
        }),
        "factCount": int(source_fact_bookkeeping["factCount"]),
        "sourceSlidesWithFactsCount": int(source_fact_bookkeeping["sourceSlidesWithFactsCount"]),
        "missingSourceSlideCount": int(source_fact_bookkeeping["missingSourceSlideCount"]),
        "sourceContentPersisted": False,
    }
    _validate_full_html_bookkeeping_payload(bookkeeping)
    return bookkeeping


def _full_html_artifact_metrics(bookkeeping: dict) -> dict:
    """Return only closed scalar metrics shared by full-HTML bookkeeping artifacts."""
    _validate_full_html_bookkeeping_payload(bookkeeping)
    return {
        "selectedSlideCount": int(bookkeeping["selectedSlideCount"]),
        "factCount": int(bookkeeping["factCount"]),
        "sourceSlidesWithFactsCount": int(bookkeeping["sourceSlidesWithFactsCount"]),
        "missingSourceSlideCount": int(bookkeeping["missingSourceSlideCount"]),
        "sourceContentPersisted": False,
    }


_CLAIM_TOKEN_PATTERN = re.compile(r"(?:[$\u20ac\u00a3]\s*)?\d+(?:[.,]\d+)?\s*(?:%|x|k|m|b|million|billion)?", re.IGNORECASE)
_SENSITIVE_STRENGTHENING_STEMS = {
    "approv",
    "audit",
    "authoriz",
    "certif",
    "clearance",
    "complian",
    "contract",
    "doubled",
    "guarante",
    "leading",
    "licens",
    "only",
    "profitab",
    "risk-free",
    "tripled",
    "validat",
}
_CAUTION_TERMS = {"aim", "forecast", "plan", "project", "pursu", "target", "toward", "working to"}


def _canonical_claim_token(value: str) -> str:
    return value.replace(" ", "").replace(",", "").lower().replace("million", "m").replace("billion", "b")


def _generated_claim_strengthens_source(render_schema: dict, cited_facts: list[dict]) -> bool:
    claim_elements = []
    for element in render_schema.get("elements", []):
        if not isinstance(element, dict) or element.get("type") != "text":
            continue
        element_id = str(element.get("id") or "").lower()
        analytics_key = str(element.get("analyticsKey") or "").lower()
        if any(marker in element_id or marker in analytics_key for marker in ("slide_number", "page_number")):
            continue
        claim_elements.append(str(element.get("text") or ""))
    claim_elements = [text.lower() for text in claim_elements]
    visible_text = " ".join(claim_elements)
    source_claims = [str(fact.get("text") or "").lower() for fact in cited_facts]
    source_text = " ".join(source_claims)
    visible_tokens = {_canonical_claim_token(match.group(0)) for match in _CLAIM_TOKEN_PATTERN.finditer(visible_text)}
    source_tokens = {_canonical_claim_token(match.group(0)) for match in _CLAIM_TOKEN_PATTERN.finditer(source_text)}
    if visible_tokens - source_tokens:
        return True
    for stem in _SENSITIVE_STRENGTHENING_STEMS:
        if stem in visible_text and stem not in source_text:
            return True
        relevant_sources = [claim for claim in source_claims if stem in claim]
        if relevant_sources and all(any(term in claim for term in _CAUTION_TERMS) for claim in relevant_sources):
            for output_claim in (claim for claim in claim_elements if stem in claim):
                if not any(term in output_claim for term in _CAUTION_TERMS):
                    return True
    return False


def _critique_generated_render_payload(
    generated_by_source_id: dict[str, dict],
    generation_plan: dict,
    source_fact_package: dict | None = None,
) -> dict:
    slide_critiques = []
    warning_count = 0
    missing_input_count = 0
    allowed_fact_ids: set[str] = set()
    fact_by_id: dict[str, dict] = {}
    if isinstance(source_fact_package, dict):
        fact_by_id = {
            str(fact.get("id")): fact
            for fact in source_fact_package.get("facts", [])
            if isinstance(fact, dict) and fact.get("id")
        }
        allowed_fact_ids = {
            *fact_by_id.keys()
        }
    for source_slide_id, generated_payload in generated_by_source_id.items():
        render_schema = generated_payload.get("renderSchema") if isinstance(generated_payload.get("renderSchema"), dict) else {}
        analytics = render_schema.get("analytics") if isinstance(render_schema.get("analytics"), dict) else {}
        source_fact_ids = analytics.get("sourceFactIds") if isinstance(analytics.get("sourceFactIds"), list) else []
        source_facts = analytics.get("sourceFactsUsed") if isinstance(analytics.get("sourceFactsUsed"), list) else []
        missing_inputs = analytics.get("missingInputs") if isinstance(analytics.get("missingInputs"), list) else []
        quality_warnings = analytics.get("qualityWarnings") if isinstance(analytics.get("qualityWarnings"), list) else []
        assumptions = analytics.get("assumptions") if isinstance(analytics.get("assumptions"), list) else []
        confidence = analytics.get("confidence")
        warnings = list(quality_warnings)
        unsupported_fact_ids = [
            str(fact_id)
            for fact_id in source_fact_ids
            if str(fact_id) not in allowed_fact_ids
        ]
        if allowed_fact_ids and not source_fact_ids:
            warnings.append("No fact IDs were declared in renderSchema.analytics.sourceFactIds.")
        if unsupported_fact_ids:
            warnings.append("Some analytics.sourceFactIds entries do not exist in sourceFactPackage facts.")
        valid_source_fact_ids = [str(fact_id) for fact_id in source_fact_ids if str(fact_id) in allowed_fact_ids]
        # DISABLED: sourceFactsUsed previously remained model-controlled and
        # literal substring matching below promoted display paraphrases into a
        # second blocking identity channel.
        # source_facts = analytics.get("sourceFactsUsed") if isinstance(analytics.get("sourceFactsUsed"), list) else []
        canonical_source_facts = [
            _normalise_fact_text(fact_by_id[fact_id].get("text"))
            for fact_id in valid_source_fact_ids
            if _normalise_fact_text(fact_by_id[fact_id].get("text"))
        ]
        analytics["sourceFactsUsed"] = canonical_source_facts
        source_facts = canonical_source_facts
        cited_safety_flags = sorted(
            {
                str(flag)
                for fact_id in source_fact_ids
                for flag in (fact_by_id.get(str(fact_id), {}).get("safetyFlags") or [])
            }
        )
        cited_fact_types = sorted(
            {
                str(fact_by_id.get(str(fact_id), {}).get("factType"))
                for fact_id in source_fact_ids
                if fact_by_id.get(str(fact_id), {}).get("factType")
            }
        )
        cited_facts = [fact_by_id[fact_id] for fact_id in valid_source_fact_ids]
        sensitive_claim_strengthened = (
            bool({"requires_user_confirmation", "do_not_strengthen"}.intersection(cited_safety_flags))
            and _generated_claim_strengthens_source(render_schema, cited_facts)
        )
        if "requires_source" in cited_safety_flags and not source_facts:
            warnings.append("Cited facts require source labels in analytics.sourceFactsUsed.")
        if not source_facts:
            warnings.append("No source facts were declared in renderSchema.analytics.sourceFactsUsed.")
        # DISABLED: canonical display labels are now derived from valid IDs, so
        # free-form display text cannot independently block a grounded slide.
        # unsupported_facts = []
        # for fact in source_facts:
        #     fact_text = _normalise_fact_text(fact).lower()
        #     if not fact_text:
        #         continue
        #     if allowed_fact_texts and not any(fact_text in allowed or allowed in fact_text for allowed in allowed_fact_texts):
        #         unsupported_facts.append(str(fact))
        unsupported_facts: list[str] = []
        missing_required_source_fact_id = bool(allowed_fact_ids and not source_fact_ids)
        try:
            confidence_value = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_value = None
            warnings.append("Confidence value is not numeric.")
        if assumptions and confidence_value is not None and confidence_value > 0.85:
            warnings.append("High confidence with declared assumptions should be reviewed.")
        critique_decision = build_critique_decision(
            warnings=warnings,
            missing_inputs=missing_inputs,
            unsupported_fact_ids=unsupported_fact_ids,
            unsupported_facts=unsupported_facts,
            cited_safety_flags=cited_safety_flags,
            sensitive_claim_strengthened=sensitive_claim_strengthened,
            missing_required_source_fact_id=missing_required_source_fact_id,
        )
        warning_count += len(warnings)
        missing_input_count += len(missing_inputs)
        slide_critiques.append(
            {
                "sourceSlideId": source_slide_id,
                "generatedTitle": generated_payload.get("title"),
                "status": critique_decision.get("status"),
                "sourceFactIds": [str(fact_id) for fact_id in source_fact_ids],
                "sourceFactCount": len(source_facts),
                "assumptionCount": len(assumptions),
                "missingInputs": missing_inputs,
                "warnings": warnings,
                "unsupportedSourceFactIds": unsupported_fact_ids,
                "unsupportedSourceFacts": unsupported_facts,
                "citedFactTypes": cited_fact_types,
                "citedSafetyFlags": cited_safety_flags,
                "confidence": confidence_value,
                "decision": critique_decision,
                "dimensions": critique_decision.get("dimensions") or [],
                "repairActions": critique_decision.get("repairActions") or [],
            }
        )
    critique_summary = summarize_critique_decisions(
        [slide.get("decision") or {} for slide in slide_critiques]
    )
    return {
        "schemaVersion": "smart-deck-generation-critique.v1",
        "knowledgeMetadata": generation_plan.get("knowledgeMetadata") or {},
        "status": critique_summary.get("status"),
        "warningCount": warning_count,
        "missingInputCount": missing_input_count,
        "decision": critique_summary,
        "dimensions": [
            dimension
            for slide in slide_critiques
            for dimension in (slide.get("dimensions") or [])
        ][:50],
        "repairActions": critique_summary.get("repairActions") or [],
        "allowedSourceFactIds": sorted(allowed_fact_ids),
        "sourceFactCoverage": (source_fact_package or {}).get("coverage") if isinstance(source_fact_package, dict) else {},
        "slides": slide_critiques,
    }


def _build_repair_context(llm_context: dict, render_payload: dict, generation_critique: dict) -> dict:
    return {
        **llm_context,
        "repairContext": {
            "schemaVersion": "smart-deck-generation-repair-context.v1",
            "instruction": (
                "Repair the previous Smart Deck render payload. Return the same output shape with the same "
                "sourceSlideId values. Fix only the issues listed in critique. Do not add unsupported facts. "
                "If evidence is still missing, keep the claim conservative and populate analytics.missingInputs "
                "or analytics.qualityWarnings instead of inventing data."
            ),
            "sourceFactPackage": llm_context.get("sourceFactPackage") if isinstance(llm_context.get("sourceFactPackage"), dict) else {},
            "originalRenderPayload": render_payload,
            "critique": generation_critique,
            "repairActions": generation_critique.get("repairActions") or [],
        },
    }


def _repair_render_payload(
    provider: str,
    llm_context: dict,
    render_payload: dict,
    generation_critique: dict,
    selected_slides: list[DeckSlide],
    prompt: str,
    model: str | None,
    api_key: str | None,
    deadline: OperationDeadline | None = None,
) -> tuple[dict, dict[str, dict], dict, dict]:
    repair_context = _build_repair_context(llm_context, render_payload, generation_critique)
    repaired_payload = _generate_render_payload(
        provider,
        repair_context,
        selected_slides,
        prompt,
        model,
        api_key,
        deadline=deadline,
    )
    repaired_by_source_id = _validate_generated_render_payload(
        repaired_payload,
        selected_slides,
        design_tokens=(llm_context.get("brand") or {}).get("tokens"),
        generation_mode=str(llm_context.get("generationMode") or "standard"),
    )
    repaired_critique = _critique_generated_render_payload(
        repaired_by_source_id,
        llm_context.get("generationPlan") or {},
        llm_context.get("sourceFactPackage") if isinstance(llm_context.get("sourceFactPackage"), dict) else {},
    )
    repair_artifact_payload = {
        "schemaVersion": "smart-deck-generation-repair.v1",
        "knowledgeMetadata": (llm_context.get("knowledgeMetadata") if isinstance(llm_context.get("knowledgeMetadata"), dict) else {}),
        "status": "completed",
        "originalCritique": generation_critique,
        "repairedCritique": repaired_critique,
        "originalDesignVersionName": render_payload.get("designVersionName"),
        "repairedDesignVersionName": repaired_payload.get("designVersionName"),
        "repairedSlideCount": len(repaired_payload.get("slides") or []),
    }
    return repaired_payload, repaired_by_source_id, repaired_critique, repair_artifact_payload


_RENDER_PAYLOAD_PROVIDERS: dict[str, object] = {
    "anthropic": _call_anthropic_render_payload,
    "openai": _call_openai_render_payload,
    "openrouter": _call_openrouter_render_payload,
    "dashscope": _call_dashscope_render_payload,
}


def _generate_render_payload(
    provider: str,
    llm_context: dict,
    selected_slides: list[DeckSlide],
    prompt: str,
    model: str | None,
    api_key: str | None,
    *,
    deadline: OperationDeadline | None = None,
) -> dict:
    if provider == "deterministic":
        return _build_deterministic_render_payload(selected_slides, prompt)
    fn = _RENDER_PAYLOAD_PROVIDERS.get(provider)  # type: ignore[assignment]
    if fn is None:
        raise ValueError("Smart Deck generation requires a workspace Qwen key or QWEN_API_KEY.")
    if not model or not api_key:
        raise ValueError(f"{provider} generation requires a resolved model and API key.")
    try:
        return fn(llm_context, model, api_key, deadline=deadline)  # type: ignore[no-any-return]
    except Exception as exc:
        from app.services.llm.provider_errors import is_provider_capacity_error

        fallback = (
            _configured_qwen_fallback()
            if provider == "dashscope"
            and llm_context.get("generationMode") != "instant_deck"
            and is_provider_capacity_error(exc)
            else None
        )
        if fallback is None:
            raise
        fallback_fn = _RENDER_PAYLOAD_PROVIDERS[fallback["provider"]]
        return fallback_fn(llm_context, fallback["model"], fallback["apiKey"], deadline=deadline)  # type: ignore[operator]


def _repair_invalid_render_schema_payload(
    provider: str,
    llm_context: dict,
    render_payload: dict,
    validation_error: ValidationError | ValueError,
    selected_slides: list[DeckSlide],
    prompt: str,
    model: str | None,
    api_key: str | None,
    deadline: OperationDeadline | None = None,
) -> dict:
    repair_context = {
        **llm_context,
        "schemaRepairRequest": {
            "invalidPayload": render_payload,
            "validationErrors": (
                validation_error.errors(include_url=False, include_context=False)
                if isinstance(validation_error, ValidationError)
                else [{"type": "value_error", "message": str(validation_error)}]
            ),
            "instructions": [
                "Correct every validation error without changing source-grounded claims.",
                "Return the complete root payload, not a patch or explanation.",
                "Use only fields defined by outputContract.renderSchemaJsonSchema.",
                "For typography or legibility failures, reflow, shorten, or reposition text instead of shrinking below the required minimum font size for that text role.",
                "Treat notices, captions, footnotes, disclaimers, audit labels, and synthetic-data notices as supporting text, but still keep them presentation-legible.",
                "When text appears over a layered or decorative background, place metric, label, and date/meta text inside a solid contrasting card or overlay instead of floating it directly on the layered background.",
            ],
        },
    }
    repair_model = settings.effective_qwen_repair_model if provider == "dashscope" else model
    return _generate_render_payload(provider, repair_context, selected_slides, prompt, repair_model, api_key, deadline=deadline)


def get_smart_deck_workspace(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    runtime_context = build_architecture_runtime_context()
    runtime_capabilities = build_smart_deck_runtime_capabilities()

    workspace, preference = _ensure_workspace_state(db, deck)
    db.flush()
    source_slides = sorted(deck.slides, key=lambda item: (item.slide_index, item.id))
    jobs = sorted(deck.generation_jobs, key=lambda item: item.created_at, reverse=True)
    versions = [
        version
        for version in sorted(deck.design_versions, key=lambda item: item.created_at, reverse=True)
        if design_version_is_visible(version)
    ]
    saved_version = next(
        (
            version
            for version in versions
            if version.id == deck.current_design_version_id and version.status != "discarded"
        ),
        None,
    )
    if saved_version is None:
        saved_version = next(
            (
                version
                for version in versions
                if version.id == workspace.active_design_version_id and version.status != "discarded"
            ),
            None,
        )
    if saved_version is None:
        saved_version = next((version for version in versions if version.is_active and version.status != "discarded"), None)
    candidate_version = next(
        (
            version
            for version in versions
            if version.status != "discarded" and not version.is_active and version.id != getattr(saved_version, "id", None)
        ),
        None,
    )
    active_version = saved_version or candidate_version or next((version for version in versions if version.status != "discarded"), None)
    active_generated = sorted(active_version.generated_slides, key=lambda item: item.slide_number) if active_version else []
    if active_version and workspace.active_design_version_id != active_version.id:
        workspace.active_design_version_id = active_version.id
    if active_generated and workspace.active_generated_slide_id is None:
        workspace.active_generated_slide_id = active_generated[0].id
    if source_slides and workspace.active_source_slide_id is None:
        workspace.active_source_slide_id = source_slides[0].id
    if preference.active_design_version_id is None and workspace.active_design_version_id:
        preference.active_design_version_id = workspace.active_design_version_id
    if preference.active_generated_slide_id is None and workspace.active_generated_slide_id:
        preference.active_generated_slide_id = workspace.active_generated_slide_id
    if preference.active_source_slide_id is None and workspace.active_source_slide_id:
        preference.active_source_slide_id = workspace.active_source_slide_id
    if preference.selected_element_id is None and workspace.selected_element_id:
        preference.selected_element_id = workspace.selected_element_id
    if preference.audience is None:
        preference.audience = deck.audience
    if preference.deck_type is None:
        preference.deck_type = "vc_fund_pitch" if deck.audience and any(marker in deck.audience.lower() for marker in ("lp", "fund", "partner")) else "startup_pitch"
    if preference.preferred_model is None:
        workspace_provider_setting = (
            db.query(WorkspaceAiProviderSetting)
            .filter(
                WorkspaceAiProviderSetting.workspace_id == deck.workspace_id,
                WorkspaceAiProviderSetting.configured_at.is_not(None),
                WorkspaceAiProviderSetting.use_for_smart_deck.is_(True),
            )
            .first()
        )
        persisted_model = workspace_provider_setting.preferred_model if workspace_provider_setting else None
        active_provider = _provider_from_generation_mode()
        if _is_production_mode() and persisted_model:
            if active_provider == "openai" and not _is_openai_model(persisted_model):
                persisted_model = None
            elif active_provider == "dashscope" and not persisted_model.startswith("qwen"):
                persisted_model = None
        preference.preferred_model = (
            persisted_model
            if persisted_model
            else settings.openai_model if settings.deck_generation_mode.strip().lower() == "openai"
            else settings.openrouter_model if settings.deck_generation_mode.strip().lower() == "openrouter"
            else settings.effective_qwen_model if settings.deck_generation_mode.strip().lower() in {"dashscope", "qwen", "alibaba"}
            else settings.anthropic_model
        )
    if preference.selected_subject is None and source_slides:
        preference.selected_subject = source_slides[0].role
    db.commit()
    messages = (
        db.query(SmartDeckMessage)
        .filter(SmartDeckMessage.workspace_id == workspace.id)
        .order_by(SmartDeckMessage.created_at.asc())
        .all()
    )
    design_tokens = db.query(DesignToken).filter(DesignToken.deck_id == deck.id).order_by(DesignToken.created_at.desc()).all()
    latest_confirmation = get_latest_save_confirmation_for_deck(db, deck.id)

    mapped_versions = [_map_design_version(version) for version in versions]
    mapped_generated_slides = [_map_generated_slide(slide) for slide in active_generated]
    saved_deck_version = (
        db.query(DesignBatch)
        .filter(
            DesignBatch.deck_id == deck.id,
            DesignBatch.source_design_version_id == saved_version.id,
            DesignBatch.version_number.is_not(None),
        )
        .order_by(DesignBatch.version_number.desc())
        .first()
        if saved_version is not None
        else None
    )
    workspace_generation_contract = _workspace_generation_contract(
        source_slides=source_slides,
        jobs=jobs,
        saved_version=saved_version,
        candidate_version=candidate_version,
        resolved_version=active_version,
        saved_deck_version=saved_deck_version,
    )
    return {
        "deck": {
            "id": deck.id,
            "workspaceId": deck.workspace_id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "status": deck.status,
            "summary": deck.summary,
        },
        "workspace": _map_workspace_state(workspace),
        "preferences": _map_preference(preference),
        "messages": [_map_message(message) for message in messages],
        "designTokens": [_map_design_token(token) for token in design_tokens],
        "sourceSlides": [_map_source_slide(slide) for slide in source_slides],
        "generationJobs": [_map_job(job) for job in jobs],
        "designVersions": mapped_versions,
        **workspace_generation_contract,
        "activeDesignVersionId": active_version.id if active_version else None,
        "activeSourceSlideId": workspace.active_source_slide_id,
        "activeGeneratedSlideId": workspace.active_generated_slide_id,
        "generatedSlides": mapped_generated_slides,
        "latestConfirmation": map_save_confirmation(latest_confirmation) if latest_confirmation is not None else None,
        "deck_id": deck.id,
        "current_design_version_id": active_version.id if active_version else None,
        "current_batch_id": active_version.id if active_version else None,
        "slides": [_map_product_spine_slide(slide) for slide in active_generated],
        "design_versions": [_map_product_spine_design_version(version) for version in versions],
        "knowledgeMetadata": build_llm_knowledge_metadata(),
        "runtimeContext": runtime_context,
        "runtimeCapabilities": runtime_capabilities,
    }


def get_instant_deck_workspace(db: Session, deck_id: str) -> dict | None:
    """Return only persisted source and whole-deck state used by Instant Deck."""
    deck = _load_instant_deck(db, deck_id)
    if deck is None:
        return None

    workspace, preference = _ensure_instant_deck_workspace_state(db, deck)
    source_slides = sorted(deck.slides, key=lambda item: (item.slide_index, item.id))
    jobs = [
        job
        for job in sorted(deck.generation_jobs, key=lambda item: item.created_at, reverse=True)
        if generation_job_is_instant_deck(job)
    ]
    versions = [
        version
        for version in sorted(deck.design_versions, key=lambda item: item.created_at, reverse=True)
        if design_version_is_visible(version)
        and (
            version.render_mode == "html_compiled.v1"
            or version.artifact_type == "full_html_deck.v1"
            or (version.generation_job is not None and generation_job_is_instant_deck(version.generation_job))
        )
    ]
    version_ids = {version.id for version in versions}
    preferred_version_id = next(
        (
            candidate
            for candidate in (
                deck.current_design_version_id,
                preference.active_design_version_id,
                workspace.active_design_version_id,
            )
            if candidate in version_ids
        ),
        None,
    )
    active_version = next(
        (version for version in versions if version.id == preferred_version_id),
        versions[0] if versions else None,
    )
    active_generated = (
        sorted(active_version.generated_slides, key=lambda item: item.slide_number)
        if active_version is not None
        else []
    )
    generated_ids = {slide.id for slide in active_generated}
    active_generated_id = next(
        (
            candidate
            for candidate in (
                preference.active_generated_slide_id,
                workspace.active_generated_slide_id,
            )
            if candidate in generated_ids
        ),
        active_generated[0].id if active_generated else None,
    )
    source_ids = {slide.id for slide in source_slides}
    active_source_id = next(
        (
            candidate
            for candidate in (
                preference.active_source_slide_id,
                workspace.active_source_slide_id,
            )
            if candidate in source_ids
        ),
        source_slides[0].id if source_slides else None,
    )

    workspace.active_design_version_id = active_version.id if active_version else None
    workspace.active_generated_slide_id = active_generated_id
    workspace.active_source_slide_id = active_source_id
    preference.active_design_version_id = workspace.active_design_version_id
    preference.active_generated_slide_id = active_generated_id
    preference.active_source_slide_id = active_source_id
    preference.audience = preference.audience or deck.audience
    preference.deck_type = preference.deck_type or "startup_pitch"
    db.commit()

    from app.services.ai_vc.advisory import investment_critique_status, source_summary
    from app.services.visual_intelligence.persistence import visual_intelligence_status
    from app.services.visual_intelligence.review.deck_review import vision_review_status

    return {
        "deck": {
            "id": deck.id,
            "workspaceId": deck.workspace_id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "status": deck.status,
            "summary": deck.summary,
        },
        "workspace": _map_workspace_state(workspace),
        "preferences": _map_preference(preference),
        "messages": [],
        "designTokens": [],
        "sourceSlides": [_map_source_slide(slide) for slide in source_slides],
        "generationJobs": [_map_job(job) for job in jobs],
        "designVersions": [_map_design_version(version) for version in versions],
        "activeDesignVersionId": active_version.id if active_version else None,
        "activeSourceSlideId": active_source_id,
        "activeGeneratedSlideId": active_generated_id,
        "generatedSlides": [_map_generated_slide(slide) for slide in active_generated],
        "investmentCritique": investment_critique_status(db, deck.id),
        "sourceSummary": source_summary(db, deck.id),
        "visualIntelligence": visual_intelligence_status(db, deck.id),
        "visionReview": vision_review_status(db, deck.id),
        "deck_id": deck.id,
        "current_design_version_id": active_version.id if active_version else None,
        "current_batch_id": active_version.id if active_version else None,
        "slides": [_map_product_spine_slide(slide) for slide in active_generated],
        "design_versions": [_map_product_spine_design_version(version) for version in versions],
    }


def create_generation_job(
    db: Session,
    deck_id: str,
    payload: CreateSmartDeckGenerationJobInput,
    *,
    run_id: str | None = None,
    deadline: OperationDeadline | None = None,
    usage_sink: dict | None = None,
) -> tuple[dict, dict, dict] | None:
    deadline = deadline or OperationDeadline.after(600)
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    workspace, preference = _ensure_workspace_state(db, deck)
    # Promotion outcome reconciliation may close the shared session to resolve
    # an ambiguous commit. Keep durable scalar identities so the failure path
    # never dereferences ORM instances that were detached by that boundary.
    durable_deck_id = deck.id
    durable_user_id = deck.user_id
    durable_workspace_id = workspace.id
    durable_generation_job_id = run_id

    # Replay guard: a durable workflow can crash after generation commits but
    # before its WorkflowJob completion commit. Reuse that committed result
    # before provider resolution, vision, retrieval, or any provider request.
    if run_id:
        completed_job = (
            db.query(GenerationJob)
            .options(
                selectinload(GenerationJob.design_versions)
                .selectinload(DesignVersion.generated_slides)
                .selectinload(GeneratedSlide.code_versions)
            )
            .filter(
                GenerationJob.id == run_id,
                GenerationJob.deck_id == deck.id,
                GenerationJob.status == "completed",
            )
            .one_or_none()
        )
        completed_result = completed_job.result_json if completed_job and isinstance(completed_job.result_json, dict) else {}
        design_version_id = str(completed_result.get("designVersionId") or "").strip()
        if completed_job is not None and design_version_id:
            completed_version = next(
                (version for version in completed_job.design_versions if version.id == design_version_id),
                None,
            )
            if completed_version is not None:
                if payload.generationMode == "instant_deck":
                    if payload.outputContract == "full_html_deck.v1" and getattr(completed_version, "render_mode", None) == "html_compiled.v1":
                        completed_payload = completed_job.result_json if isinstance(completed_job.result_json, dict) else {}
                        if (
                            completed_payload.get("outputContract") != "full_html_deck.v1"
                            or completed_payload.get("coverageComplete") is not True
                            or completed_payload.get("wholeDeckCoverageComplete") is not True
                            or completed_version.html_compilation is None
                        ):
                            raise ValueError("Completed Instant HTML checkpoint is incomplete.")
                    else:
                        _require_llm_only_completed_instant_version(completed_job, completed_version)
                reloaded_workspace = get_smart_deck_workspace(db, deck_id)
                if reloaded_workspace is None:
                    raise ValueError("Smart Deck workspace could not be reloaded.")
                return _map_job(completed_job), _map_design_version(completed_version), reloaded_workspace

    slide_lookup = {slide.id: slide for slide in deck.slides}
    missing_ids = [slide_id for slide_id in payload.selectedSourceSlideIds if slide_id not in slide_lookup]
    if missing_ids:
        raise ValueError(f"Selected source slides do not belong to this deck: {', '.join(missing_ids)}")
    if payload.generationMode == "instant_deck" and set(payload.selectedSourceSlideIds) != set(slide_lookup):
        raise ValueError("Instant Deck generation requires every source slide in the deck.")

    selected_slides = [slide_lookup[slide_id] for slide_id in payload.selectedSourceSlideIds]
    selected_slides.sort(key=lambda item: (item.slide_index, item.id))
    now = datetime.utcnow()
    pipeline_started = time.perf_counter()
    stage_timings: dict[str, float] = {}
    full_html_request = payload.generationMode == "instant_deck" and payload.outputContract == "full_html_deck.v1"
    try:
        if run_id:
            workflow_job = db.query(WorkflowJob).filter(WorkflowJob.id == run_id).one_or_none()
            if workflow_job and workflow_job.queued_at and workflow_job.started_at:
                stage_timings["workerQueueWait"] = max(0.0, (workflow_job.started_at - workflow_job.queued_at).total_seconds())
        provider_started = time.perf_counter()
        preferred_model = payload.preferredModel or preference.preferred_model
        if full_html_request:
            claude_config = {
                "provider": "openai",
                "model": settings.openai_model,
                "apiKey": settings.openai_api_key or None,
                "source": "environment" if settings.openai_api_key else "missing",
            }
        else:
            active_provider = _provider_from_generation_mode()
            if _is_production_mode() and preferred_model:
                if active_provider == "openai" and not _is_openai_model(preferred_model):
                    preferred_model = None
                elif active_provider == "dashscope" and not preferred_model.startswith("qwen"):
                    preferred_model = None
            claude_config = _resolve_claude_config(db, deck, preferred_model)
        if payload.generationMode == "instant_deck":
            _require_instant_deck_llm_provider(claude_config)
        stage_timings["providerResolution"] = time.perf_counter() - provider_started
        provider = claude_config["provider"]
        resolved_model = claude_config["model"]
        audience_profile = _load_audience_profile(db, deck.audience)
        vision_started = time.perf_counter()
        vision_cache_key = _vision_analysis_cache_key(
            selected_slides,
            provider=claude_config["provider"],
            model=(
                settings.openai_vision_model
                if claude_config["provider"] == "openai"
                else claude_config.get("model")
            ),
        )
        cached_vision_artifact = (
            db.query(DeckLlmArtifact)
            .filter(
                DeckLlmArtifact.deck_id == deck.id,
                DeckLlmArtifact.artifact_type == "smart_deck_vision_analysis",
                DeckLlmArtifact.artifact_key == vision_cache_key,
                DeckLlmArtifact.status == "ready",
            )
            .order_by(DeckLlmArtifact.created_at.desc())
            .first()
        )
        cached_vision_payload = cached_vision_artifact.payload_json if cached_vision_artifact else None
        if not isinstance(cached_vision_payload, dict) or cached_vision_payload.get("status") != "ready":
            cached_vision_payload = None
        vision_design_analysis = (
            cached_vision_payload
            if isinstance(cached_vision_payload, dict)
            else {"status": "not_requested", "telemetry": {"providerCallExecuted": False}}
            if payload.outputContract == "full_html_deck.v1"
            else _analyze_selected_slide_visuals(
                selected_slides,
                provider=provider,
                model=resolved_model,
                api_key=claude_config.get("apiKey"),
                deadline=deadline,
            )
        )
        stage_timings["visionAnalysis"] = time.perf_counter() - vision_started
        context_started = time.perf_counter()
        existing_generation_job = (
            db.query(GenerationJob).filter(GenerationJob.id == run_id, GenerationJob.deck_id == deck.id).one_or_none()
            if run_id and full_html_request
            else None
        )
        existing_context = (
            existing_generation_job.llm_context_json
            if existing_generation_job is not None and isinstance(existing_generation_job.llm_context_json, dict)
            else {}
        )
        if full_html_request and existing_generation_job is not None and existing_context.get("fullHtmlRequestContextArtifactId"):
            from app.services.llm.full_html_generation_service import resolve_full_html_request_bundle
            authoritative_context_pack, _llm_context_snapshot = resolve_full_html_request_bundle(
                generation_job=existing_generation_job,
                operation_id=str(payload.instantOperationId or ""),
            )
            # Tuple member one is the decrypted immutable provider input. Build
            # a separate runtime adapter for standard bookkeeping consumers;
            # never merge it or tuple member two into durable job metadata.
            llm_context = _runtime_context_from_authoritative_pack(authoritative_context_pack)
        else:
            llm_context = _build_llm_context(
                deck,
                selected_slides,
                payload,
                audience_profile,
                vision_design_analysis=vision_design_analysis,
            )
        design_tokens = llm_context["brand"]["tokens"]
        context_timings = llm_context.get("orchestrationTimings") if isinstance(llm_context.get("orchestrationTimings"), dict) else {}
        stage_timings["contextLoading"] = time.perf_counter() - context_started
        stage_timings["vectorRetrieval"] = float(context_timings.get("vectorRetrieval") or 0.0)
        stage_timings["sourceFactAssembly"] = float(context_timings.get("sourceFactAssembly") or 0.0)
        knowledge_metadata = llm_context.get("knowledgeMetadata") or {}
        source_fact_package = _source_fact_package_for_generation(llm_context, selected_slides)
        if "sourceFactPackage" not in llm_context:
            llm_context["sourceFactPackage"] = source_fact_package
        generation_plan = _build_generation_plan(llm_context, selected_slides)
        llm_context["generationPlan"] = generation_plan
        # Immutable snapshots prevent concurrent tasks from lazy-loading through
        # the worker-owned SQLAlchemy session after the rollback below.
        slide_inputs = [
            SimpleNamespace(
                id=slide.id,
                title=slide.title,
                summary=slide.summary,
                narrative_notes=slide.narrative_notes,
                raw_text=slide.raw_text,
                semantic_slide_type=slide.semantic_slide_type,
                role=slide.role,
                slide_number=slide.slide_number,
                source_page_number=slide.source_page_number,
                slide_index=slide.slide_index,
            )
            for slide in selected_slides
        ]
        # Context assembly can use optional retrieval/enrichment paths that may
        # leave the shared Core session in a failed transaction after degrading.
        # Reset that unit of work before looking up the durable generation row;
        # all generation state is written below and committed by the worker.
        db.rollback()
        # The rollback also discards workspace rows created at the start of this
        # request, so re-establish them before inserting FK-dependent messages.
        workspace, preference = _ensure_workspace_state(db, deck)
        job = None
        if run_id:
            job = db.query(GenerationJob).filter(GenerationJob.id == run_id, GenerationJob.deck_id == deck.id).first()
        if job is None:
            job = GenerationJob(
                id=run_id or generate_id("genjob"),
                deck_id=deck.id,
                status="queued",
                provider="provider_pending",
                model=None,
                prompt=payload.prompt,
                selected_source_slide_ids_json=payload.selectedSourceSlideIds,
                style_id=payload.styleId,
                brand_product_id=payload.brandProductId,
                additional_context=payload.additionalContext,
                llm_context_json=None,
            )
            db.add(job)
        durable_generation_job_id = job.id
        job.deck_id = deck.id
        job.status = "running"
        job.provider = provider
        job.model = resolved_model if provider in {"anthropic", "openai", "openrouter", "dashscope"} else None
        job.prompt = payload.prompt
        job.selected_source_slide_ids_json = payload.selectedSourceSlideIds
        job.style_id = payload.styleId
        job.brand_product_id = payload.brandProductId
        job.additional_context = payload.additionalContext
        existing_workflow_context = job.llm_context_json if isinstance(job.llm_context_json, dict) else {}
        if full_html_request:
            from app.services.llm.full_html_generation_service import sanitize_full_html_generation_metadata
            job.llm_context_json = sanitize_full_html_generation_metadata(existing_workflow_context)
        else:
            job.llm_context_json = {
                **existing_workflow_context,
                **llm_context,
                "llmProvider": {
                    "provider": provider,
                    "model": resolved_model if provider in {"anthropic", "openai", "openrouter", "dashscope"} else None,
                    "credentialSource": claude_config.get("source"),
                },
            }
        vision_status = str((vision_design_analysis or {}).get("status") or "unavailable")
        vision_execution = {
            "status": vision_status,
            "executed": bool(((vision_design_analysis or {}).get("telemetry") or {}).get("providerCallExecuted")) and cached_vision_payload is None,
            "cached": cached_vision_payload is not None,
            "provider": provider if vision_status == "ready" else None,
            "model": resolved_model if vision_status == "ready" else None,
        }
        job.result_json = None
        job.error_message = None
        job.completed_at = None
        workspace.status = "generating"
        workspace.active_source_slide_id = payload.selectedSourceSlideIds[0]
        preference.selected_source_slide_ids_json = payload.selectedSourceSlideIds
        preference.active_source_slide_id = payload.selectedSourceSlideIds[0]
        if payload.audience is not None:
            preference.audience = payload.audience
        if payload.deckType is not None:
            preference.deck_type = payload.deckType
        if payload.preferredModel is not None:
            preference.preferred_model = resolved_model if provider == "dashscope" else payload.preferredModel
        if payload.selectedSubject is not None:
            preference.selected_subject = payload.selectedSubject
        if payload.actionId is not None:
            preference.selected_action_id = payload.actionId
        # Generation messages reference GenerationJob by FK. Flush the job
        # before recording a system/user message, especially when a durable
        # workflow job supplies the generation run id.
        db.flush()
        _record_smart_deck_message(
            db,
            workspace_id=workspace.id,
            deck_id=deck.id,
            role="user",
            content=payload.prompt,
            generation_job_id=job.id,
            selected_source_slide_ids=payload.selectedSourceSlideIds,
            metadata_json={"styleId": payload.styleId, "brandProductId": payload.brandProductId},
        )
        db.flush()
        record_agent_event(
            db,
            event_name=("ai.instant_deck_generation.started" if full_html_request else "ai.smart_deck_generation.started"),
            run_type=("instant_deck_generation" if full_html_request else "smart_deck_generation"),
            workspace_id=workspace.id,
            deck_id=deck.id,
            user_id=deck.user_id,
            run_id=job.id,
            status="running",
            provider=provider,
            model=job.model,
            metadata={
                "selectedSlideCount": len(selected_slides),
                "styleId": payload.styleId,
                "brandProductId": payload.brandProductId,
                "promptLength": len(payload.prompt),
                "hasAdditionalContext": bool(payload.additionalContext),
                "credentialSource": claude_config.get("source"),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (llm_context.get("runtimeContext") or {}).get("schemaVersion"),
                "visionDesignStatus": (llm_context.get("visionDesignAnalysis") or {}).get("status"),
                "instantOperationId": payload.instantOperationId if full_html_request else None,
                "sourceFileId": getattr(getattr(deck, "file", None), "id", None),
                "sourceExtractionRunIds": sorted({
                    str(slide.extraction_run_id)
                    for slide in selected_slides
                    if getattr(slide, "extraction_run_id", None)
                }),
                "outputContract": payload.outputContract,
                "generationMode": payload.generationMode,
            },
        )
    except Exception as exc:
        if isinstance(exc, ValueError):
            safe_error_class = "ValueError"
        elif isinstance(exc, TypeError):
            safe_error_class = "TypeError"
        elif isinstance(exc, KeyError):
            safe_error_class = "KeyError"
        elif isinstance(exc, LookupError):
            safe_error_class = "LookupError"
        else:
            safe_error_class = "UnexpectedSetupError"
        _logger.error(
            "smart_deck_generation_setup_failed",
            extra={
                "errorCategory": "generation_setup_error",
                "errorClass": safe_error_class,
                "deckId": deck_id,
                "runId": run_id,
            },
        )
        db.rollback()
        raise

    try:
        source_fact_artifact_payload = (
            _content_free_source_fact_bookkeeping(source_fact_package, selected_slides)
            if full_html_request
            else source_fact_package
        )
        persisted_generation_plan = (
            _content_free_generation_plan_bookkeeping(source_fact_artifact_payload, selected_slides)
            if full_html_request
            else generation_plan
        )
        _record_llm_artifact(
            db,
            deck_id=deck.id,
            artifact_type="smart_deck_generation_plan",
            artifact_key=job.id,
            summary=f"Knowledge-aware generation plan for Smart Deck job {job.id}.",
            payload_json=persisted_generation_plan,
            metrics_json=(
                _full_html_artifact_metrics(persisted_generation_plan)
                if full_html_request
                else {
                "selectedSlideCount": len(selected_slides),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (llm_context.get("runtimeContext") or {}).get("schemaVersion"),
                }
            ),
        )
        if cached_vision_payload is None and vision_design_analysis.get("status") == "ready":
            _record_llm_artifact(
                db,
                deck_id=deck.id,
                artifact_type="smart_deck_vision_analysis",
                artifact_key=vision_cache_key,
                summary=f"Cached visual analysis for Smart Deck source slides ({vision_cache_key[-12:]}).",
                payload_json=vision_design_analysis,
                metrics_json={
                    "cacheKey": vision_cache_key,
                    "provider": provider,
                    "model": resolved_model,
                    "selectedSlideCount": len(selected_slides),
                },
                store_payload=False,
            )
        _record_llm_artifact(
            db,
            deck_id=deck.id,
            artifact_type="smart_deck_source_facts",
            artifact_key=job.id,
            summary=f"Source fact package for Smart Deck job {job.id}.",
            payload_json=source_fact_artifact_payload,
            metrics_json=(
                _full_html_artifact_metrics(source_fact_artifact_payload)
                if full_html_request
                else {
                "factCount": source_fact_package.get("factCount"),
                "factTypeCounts": source_fact_package.get("factTypeCounts"),
                "safetyFlagCounts": source_fact_package.get("safetyFlagCounts"),
                "selectedSlideCount": len(selected_slides),
                "missingSlideFactCount": len((source_fact_package.get("coverage") or {}).get("missingSlideFactIds") or []),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (llm_context.get("runtimeContext") or {}).get("schemaVersion"),
                }
            ),
            store_payload=not full_html_request,
            persist_canonical=not full_html_request,
        )
        if payload.generationMode == "instant_deck" and payload.outputContract == "full_html_deck.v1":
            from app.services.llm.full_html_generation_service import (
                build_grounded_context_pack,
                configured_provider_call,
                generate_instant_deck,
                persist_full_html_request_context,
                resolve_full_html_request_context,
            )
            if not payload.instantOperationId:
                raise ValueError("Full HTML generation requires its resolved Instant operation identity.")
            request_context_keys = {
                "fullHtmlRequestContext", "fullHtmlRequestContextHash", "fullHtmlRequestBinding",
            }
            if isinstance(job.llm_context_json, dict) and request_context_keys.intersection(job.llm_context_json):
                context_pack = resolve_full_html_request_context(
                    generation_job=job,
                    operation_id=payload.instantOperationId,
                    require_existing=True,
                    require_encrypted=True,
                )
            else:
                context_pack = build_grounded_context_pack(
                    deck=deck,
                    slides=selected_slides,
                    payload=payload,
                    llm_context=llm_context,
                    db=db,
                )
                exact_provider_context = _runtime_context_from_authoritative_pack(context_pack)
                context_pack = persist_full_html_request_context(
                    db,
                    generation_job_id=job.id,
                    operation_id=payload.instantOperationId,
                    context_pack=context_pack,
                    llm_context_snapshot={"generationMode": "instant_deck", "canonicalContext": True},
                    exact_provider_request_body=json.dumps(
                        exact_provider_context,
                        separators=(",", ":"),
                        default=str,
                    ).encode("utf-8"),
                )
            provider_context_pack = _runtime_context_from_authoritative_pack(context_pack)
            historical_provider_context_pack = _historical_augmented_full_html_provider_context(
                context_pack,
                selected_slides,
            )
            version, html_result = generate_instant_deck(
                db,
                operation_id=payload.instantOperationId,
                generation_job_id=job.id,
                # full_html_deck.v1 is pinned to the audited environment model;
                # workspace-selected aliases/variants cannot widen this boundary.
                provider="openai",
                model=settings.openai_model,
                context_pack=context_pack,
                provider_context_pack=provider_context_pack,
                historical_provider_context_pack=historical_provider_context_pack,
                provider_call=configured_provider_call(settings.openai_api_key),
                usage_sink=usage_sink,
            )
            created_slide_ids = [slide.id for slide in sorted(version.generated_slides, key=lambda item: item.slide_number)]
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            job.result_json = {
                "designVersionId": version.id,
                "state": "preview",
                "generatedSlideIds": created_slide_ids,
                "requestedSlideIds": list(payload.selectedSourceSlideIds),
                "completedSlideIds": list(payload.selectedSourceSlideIds),
                "failedSlideIds": [],
                "failedSlides": [],
                "partialSuccess": False,
                "wholeDeckCoverageComplete": True,
                "generationMode": payload.generationMode,
                **html_result,
            }
            # The provider/compilation stage may persist a provisional immutable
            # candidate, but it must not select it. The authoritative publisher
            # owns selection after schema validation and complete browser render
            # proof have both succeeded.
            instant_operation = db.query(InstantDeckOperation).filter(
                InstantDeckOperation.id == payload.instantOperationId,
            ).one()
            provider_attempt = db.query(InstantDeckProviderAttempt).filter(
                InstantDeckProviderAttempt.operation_id == instant_operation.id,
            ).order_by(InstantDeckProviderAttempt.attempt_number.desc()).first()
            retrieval = (
                context_pack.get("retrievedGuidance")
                if isinstance(context_pack.get("retrievedGuidance"), dict)
                else {}
            )
            record_agent_event(
                db,
                event_name="ai.instant_deck_generation.completed",
                run_type="instant_deck_generation",
                workspace_id=workspace.id,
                deck_id=deck.id,
                user_id=deck.user_id,
                run_id=job.id,
                status="completed",
                provider=provider,
                model=job.model,
                input_tokens=int(instant_operation.actual_input_tokens or 0),
                output_tokens=int(instant_operation.actual_output_tokens or 0),
                estimated_cost_cents=float(instant_operation.actual_provider_cost_cents or 0),
                request_id=(provider_attempt.provider_request_id if provider_attempt is not None else None),
                trace_id=str(retrieval.get("traceId") or "") or None,
                metadata={
                    "sourceFileId": getattr(getattr(deck, "file", None), "id", None),
                    "sourceExtractionRunIds": sorted({
                        str(slide.extraction_run_id)
                        for slide in selected_slides
                        if getattr(slide, "extraction_run_id", None)
                    }),
                    "generationJobId": job.id,
                    "instantOperationId": instant_operation.id,
                    "providerAttemptId": provider_attempt.id if provider_attempt is not None else None,
                    "providerResponseId": provider_attempt.provider_response_id if provider_attempt is not None else None,
                    "designVersionId": version.id,
                    "htmlArtifactId": html_result.get("htmlArtifactId"),
                    "outputContract": "full_html_deck.v1",
                    "generatedSlideCount": len(created_slide_ids),
                    "retrievalExecuted": retrieval.get("retrievalExecuted"),
                    "retrievalStatus": retrieval.get("retrievalStatus"),
                    "retrievalSkipReason": retrieval.get("skipReason"),
                    "retrievedItemIds": retrieval.get("retrievedItemIds") or [],
                    "retrievalTokenCount": retrieval.get("tokenCount"),
                    "knowledgePackage": retrieval.get("knowledgePackage") or {},
                },
            )
            db.commit()
            reloaded_workspace = get_smart_deck_workspace(db, deck_id)
            if reloaded_workspace is None:
                raise ValueError("Smart Deck workspace could not be reloaded.")
            return _map_job(job), _map_design_version(version), reloaded_workspace
        version = DesignVersion(
            id=generate_id("designver"),
            deck_id=deck.id,
            generation_job_id=job.id,
            name=f"Smart Deck redesign {now.strftime('%Y-%m-%d %H:%M')}",
            status="preview",
            is_active=False,
            summary=f"Generated {len(selected_slides)} slide design(s) from selected source slides.",
        )
        db.add(version)
        db.flush()

        _record_llm_artifact(
            db,
            deck_id=deck.id,
            artifact_type="smart_deck_generation_context",
            artifact_key=job.id,
            summary=f"LLM context for Smart Deck generation job {job.id}.",
            payload_json=llm_context,
            metrics_json={
                "selectedSlideCount": len(selected_slides),
                "hasArtifactContext": bool(llm_context.get("artifactContext")),
                "promptLength": len(payload.prompt),
                "provider": provider,
                "model": resolved_model if provider in {"anthropic", "openai", "openrouter", "dashscope"} else None,
                "credentialSource": claude_config.get("source"),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (llm_context.get("runtimeContext") or {}).get("schemaVersion"),
            },
        )

        generation_started = time.perf_counter()
        slide_results, slide_failures = _run_slide_generation_tasks(
            provider=provider,
            llm_context=llm_context,
            slide_inputs=slide_inputs,
            prompt=payload.prompt,
            model=resolved_model,
            api_key=claude_config.get("apiKey"),
            run_id=run_id,
            deadline=deadline,
        )
        stage_timings.update({
            "generation": sum((result.get("timings") or {}).get("generation", 0.0) for result in slide_results),
            "schemaValidation": 0.0,
            "schemaRepair": sum((result.get("timings") or {}).get("schemaRepair", 0.0) for result in slide_results),
            "critique": sum((result.get("timings") or {}).get("critique", 0.0) for result in slide_results),
            "critiqueRepair": sum((result.get("timings") or {}).get("critiqueRepair", 0.0) for result in slide_results),
            "slideBatchWallClock": time.perf_counter() - generation_started,
        })
        if _partial_generation_must_fail(payload, slide_results, slide_failures):
            raise ValueError(f"Smart Deck slide generation failed: {slide_failures[0]['error']}")

        slide_coverage = _validate_generation_slide_coverage(
            payload.selectedSourceSlideIds,
            slide_results,
            slide_failures,
        )
        generated_by_source_id = {result["sourceSlideId"]: result["generated"] for result in slide_results}
        if payload.generationMode == "instant_deck":
            _require_instant_deck_grounding(
                requested_slide_ids=list(payload.selectedSourceSlideIds),
                generated_by_source_id=generated_by_source_id,
                source_fact_package=source_fact_package,
            )
        final_critique = _critique_generated_render_payload(generated_by_source_id, generation_plan, source_fact_package)
        _require_nonblocking_generation(final_critique)
        repair_performed = any(bool(result.get("repairArtifact")) for result in slide_results)
        final_render_payload = {
            "designVersionName": f"Smart Deck redesign {now.strftime('%Y-%m-%d %H:%M')}",
            "slides": [result["generated"] for result in slide_results],
        }
        _record_llm_artifact(
            db,
            deck_id=deck.id,
            artifact_type="smart_deck_generation_critique",
            artifact_key=job.id,
            summary=f"Per-slide critique for Smart Deck job {job.id}.",
            payload_json={**final_critique, "slideFailures": slide_failures},
            metrics_json={
                "status": final_critique.get("status"),
                "warningCount": final_critique.get("warningCount"),
                "missingInputCount": final_critique.get("missingInputCount"),
                "blockingCount": (final_critique.get("decision") or {}).get("blockingCount"),
                "repairActionCount": len(final_critique.get("repairActions") or []),
                "selectedSlideCount": len(selected_slides),
                "successfulSlideCount": len(slide_results),
                "failedSlideCount": len(slide_failures),
            },
        )
        for result in slide_results:
            if result.get("repairArtifact"):
                _record_llm_artifact(
                    db,
                    deck_id=deck.id,
                    artifact_type="smart_deck_generation_repair",
                    artifact_key=f"{job.id}:{result['sourceSlideId']}",
                    summary=f"Bounded repair pass for Smart Deck slide {result['sourceSlideId']}.",
                    payload_json=result["repairArtifact"],
                    metrics_json={"sourceSlideId": result["sourceSlideId"]},
                )

        if isinstance(final_render_payload.get("designVersionName"), str) and final_render_payload["designVersionName"].strip():
            version.name = final_render_payload["designVersionName"].strip()[:255]

        created_slide_ids: list[str] = []
        candidate_slide_versions: list[dict] = []
        successful_source_ids = set(generated_by_source_id)
        for slide in selected_slides:
            if slide.id not in successful_source_ids:
                continue
            generated_payload = generated_by_source_id[slide.id]
            render_schema = generated_payload["renderSchema"]
            slide_validation_warnings = _persisted_generated_slide_validation_warnings(render_schema)
            persisted_validation_status = "warning" if slide_validation_warnings else "valid"
            generated_slide = GeneratedSlide(
                id=generate_id("genslide"),
                deck_id=deck.id,
                design_version_id=version.id,
                generation_job_id=job.id,
                source_slide_id=slide.id,
                slide_number=_source_slide_number(slide),
                title=generated_payload["title"],
                status="ready",
                render_schema_json=render_schema,
                design_tokens_json=design_tokens,
                preview_image_url=None,
                validation_status=persisted_validation_status,
            )
            db.add(generated_slide)
            db.flush()
            created_slide_ids.append(generated_slide.id)
            _record_design_tokens(
                db,
                deck_id=deck.id,
                design_version_id=version.id,
                generated_slide_id=generated_slide.id,
                design_tokens=design_tokens,
            )
            code_version_id = generate_id("codever")
            render_schema_artifact = _write_render_schema_json_artifact(
                user_id=deck.user_id,
                deck_id=deck.id,
                design_version_id=version.id,
                generated_slide_id=generated_slide.id,
                code_version_id=code_version_id,
                render_schema=render_schema,
            )
            code_json = {
                "renderer": "GeneratedSlideRenderer",
                "source": "render_schema_json",
                "lifecycle": "candidate",
                "state": "candidate",
                "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
                "renderSchemaStorageProvider": render_schema_artifact["storageProvider"],
                "renderSchemaStoragePath": render_schema_artifact["storagePath"],
                "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
                "provider": provider,
                "model": job.model,
                "knowledgeMetadata": knowledge_metadata,
                "sourceSlideId": slide.id,
                "designVersionId": version.id,
                "generationJobId": job.id,
                "generationMode": payload.generationMode,
            }
            code_metadata_artifact = _write_code_metadata_json_artifact(
                user_id=deck.user_id,
                deck_id=deck.id,
                design_version_id=version.id,
                generated_slide_id=generated_slide.id,
                code_version_id=code_version_id,
                code_json=code_json,
            )
            code_json = {
                **code_json,
                "codeJsonHash": code_metadata_artifact["codeJsonHash"],
                "codeJsonStorageProvider": code_metadata_artifact["storageProvider"],
                "codeJsonStoragePath": code_metadata_artifact["storagePath"],
                "bucketCodeJsonKey": code_metadata_artifact["storagePath"],
            }
            code_version = GeneratedSlideCodeVersion(
                id=code_version_id,
                generated_slide_id=generated_slide.id,
                version_number=1,
                code_kind="render_schema",
                schema_version="smart-deck-render-schema.v1",
                render_schema_json=render_schema,
                code_json=code_json,
                bucket_render_schema_key=render_schema_artifact["storagePath"],
                bucket_code_key=code_metadata_artifact["storagePath"],
                bucket_thumbnail_key=None,
                status=persisted_validation_status,
                validation_errors_json=[{"message": warning, "severity": "warning"} for warning in slide_validation_warnings],
            )
            db.add(code_version)
            generated_slide.current_version_id = code_version.id
            db.flush()
            generated_elements = _persist_generated_slide_elements(
                db,
                deck_id=deck.id,
                design_version_id=version.id,
                generated_slide=generated_slide,
                source_slide_id=slide.id,
                render_schema=render_schema,
            )
            _record_llm_artifact(
                db,
                deck_id=deck.id,
                artifact_type="generated_slide_render_schema",
                artifact_key=generated_slide.id,
                summary=f"Validated render schema for generated slide {generated_slide.id}.",
                payload_json={
                    "generatedSlideId": generated_slide.id,
                    "sourceSlideId": slide.id,
                    "designVersionId": version.id,
                    "generationJobId": job.id,
                    "codeVersionId": code_version.id,
                    "renderSchema": render_schema,
                    "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
                    "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
                    "designTokens": design_tokens,
                    "knowledgeMetadata": knowledge_metadata,
                    "generatedSlideElementIds": [element.id for element in generated_elements],
                },
                metrics_json={
                    "elementCount": len(render_schema.get("elements", [])),
                    "persistedElementCount": len(generated_elements),
                    "slideNumber": generated_slide.slide_number,
                },
            )
            _record_llm_artifact(
                db,
                deck_id=deck.id,
                artifact_type="generated_slide_code_version",
                artifact_key=code_version.id,
                summary=f"Generated slide code version {code_version.id}.",
                payload_json={
                    "generatedSlideId": generated_slide.id,
                    "codeVersionId": code_version.id,
                    "codeKind": code_version.code_kind,
                    "schemaVersion": code_version.schema_version,
                    "renderSchema": render_schema,
                    "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
                    "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
                    "codeJson": code_version.code_json,
                },
                metrics_json={
                    "validationErrorCount": len(slide_validation_warnings),
                    "versionNumber": code_version.version_number,
                },
            )
            candidate_slide_versions.append(
                {
                    "generated_slide_id": generated_slide.id,
                    "code_version_id": code_version.id,
                    "render_schema_json": render_schema,
                    "render_schema_hash": render_schema_artifact["renderSchemaHash"],
                    "bucket_render_schema_key": render_schema_artifact["storagePath"],
                    "bucket_code_key": code_metadata_artifact["storagePath"],
                    "source_slide_id": slide.id,
                    "state": "candidate",
                }
            )

        stage_timings["artifactPersistence"] = max(0.0, time.perf_counter() - generation_started - stage_timings.get("slideBatchWallClock", 0.0))
        stage_timings["totalDuration"] = time.perf_counter() - pipeline_started
        progress_payload = {
            "selectedSlideCount": len(selected_slides),
            "completedSlideCount": len(created_slide_ids),
            **slide_coverage,
            "phase": "saving_design_version",
        }
        instant_deck_complete = _instant_deck_version_is_complete(
            payload,
            created_slide_ids,
            slide_failures,
            all_source_slide_ids=[slide.id for slide in deck.slides],
        )
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.result_json = {
            "designVersionId": version.id,
            "state": "preview",
            "generatedSlideIds": created_slide_ids,
            "candidateSlideVersions": candidate_slide_versions,
            **slide_coverage,
            "failedSlides": slide_failures,
            "timings": stage_timings,
            "progress": progress_payload,
            "provenance": payload.provenance,
            "visionExecution": vision_execution,
            "generationMode": payload.generationMode,
            "wholeDeckCoverageComplete": instant_deck_complete,
        }
        workspace.status = "reviewing"
        workspace.active_design_version_id = version.id
        workspace.active_generated_slide_id = created_slide_ids[0] if created_slide_ids else None
        preference.active_design_version_id = version.id
        preference.active_generated_slide_id = workspace.active_generated_slide_id
        _record_smart_deck_message(
            db,
            workspace_id=workspace.id,
            deck_id=deck.id,
            role="assistant",
            content=f"Created design version {version.id} with {len(created_slide_ids)} generated slide(s).",
            generation_job_id=job.id,
            selected_source_slide_ids=payload.selectedSourceSlideIds,
            metadata_json={"designVersionId": version.id, "generatedSlideIds": created_slide_ids},
        )
        manifest_payload = {
            "deck_id": deck.id,
            "design_version_id": version.id,
            "designVersionId": version.id,
            "state": "preview",
            "generationJobId": job.id,
            "generatedSlideIds": created_slide_ids,
            "slides": [
                {
                    "generated_slide_id": candidate["generated_slide_id"],
                    "code_version_id": candidate["code_version_id"],
                    "render_schema_key": candidate["bucket_render_schema_key"],
                    "code_key": candidate["bucket_code_key"],
                }
                for candidate in candidate_slide_versions
            ],
            "candidateSlideVersions": candidate_slide_versions,
            "selectedSourceSlideIds": payload.selectedSourceSlideIds,
            "provider": provider,
            "model": job.model,
            "credentialSource": claude_config.get("source"),
            "knowledgeMetadata": knowledge_metadata,
            "sourceFactsArtifactType": "smart_deck_source_facts",
            "generationPlanArtifactType": "smart_deck_generation_plan",
            "generationCritiqueArtifactType": "smart_deck_generation_critique",
            "generationRepairArtifactType": "smart_deck_generation_repair" if repair_performed else None,
        }
        manifest_artifact = _write_design_version_manifest_json_artifact(
            user_id=deck.user_id,
            deck_id=deck.id,
            design_version_id=version.id,
            manifest_json=manifest_payload,
        )
        version.bucket_manifest_key = manifest_artifact["storagePath"]
        manifest_payload = {
            **manifest_payload,
            "bucketManifestKey": manifest_artifact["storagePath"],
            "manifestHash": manifest_artifact["manifestHash"],
        }
        _record_llm_artifact(
            db,
            deck_id=deck.id,
            artifact_type="smart_deck_design_version_manifest",
            artifact_key=version.id,
            summary=f"Manifest for Smart Deck design version {version.id}.",
            payload_json=manifest_payload,
            metrics_json={
                "generatedSlideCount": len(created_slide_ids),
                "selectedSlideCount": len(payload.selectedSourceSlideIds),
                "sourceFactCount": source_fact_package.get("factCount"),
                "sourceFactTypeCounts": source_fact_package.get("factTypeCounts"),
                "sourceFactSafetyFlagCounts": source_fact_package.get("safetyFlagCounts"),
                "missingSlideFactCount": len((source_fact_package.get("coverage") or {}).get("missingSlideFactIds") or []),
                "critiqueStatus": final_critique.get("status"),
                "critiqueWarningCount": final_critique.get("warningCount"),
                "critiqueMissingInputCount": final_critique.get("missingInputCount"),
                "critiqueBlockingCount": (final_critique.get("decision") or {}).get("blockingCount"),
                "repairActionCount": len(final_critique.get("repairActions") or []),
                "repairPerformed": repair_performed,
                "timings": stage_timings,
                "progress": progress_payload,
            },
        )
        if instant_deck_complete:
            db.flush()
            db.expire(deck, ["slides"])
            db.expire(version, ["generated_slides"])
            _require_llm_only_completed_instant_version(job, version)
            _auto_apply_completed_instant_deck_version(db, deck, version)
        # DISABLED: Process-global last usage could belong to another concurrent
        # generation job and therefore could misattribute user token counts.
        # from app.services.llm.dashscope_provider import get_last_usage
        # tracked_usage = get_last_usage() if provider == "dashscope" else None
        tracked_usage = None
        if provider in {"dashscope", "openai"}:
            tracked_usage = {
                "input_tokens": sum(int((result.get("trackedUsage") or {}).get("input_tokens") or 0) for result in slide_results),
                "output_tokens": sum(int((result.get("trackedUsage") or {}).get("output_tokens") or 0) for result in slide_results),
                "total_tokens": sum(int((result.get("trackedUsage") or {}).get("total_tokens") or 0) for result in slide_results),
                "input_cached_tokens": sum(int((result.get("trackedUsage") or {}).get("input_cached_tokens") or 0) for result in slide_results),
            }
            estimated_costs = [
                float((result.get("trackedUsage") or {}).get("estimated_cost_cents"))
                for result in slide_results
                if (result.get("trackedUsage") or {}).get("estimated_cost_cents") is not None
            ]
            if estimated_costs:
                tracked_usage["estimated_cost_cents"] = round(sum(estimated_costs), 4)
        if usage_sink is not None and tracked_usage is not None:
            from app.services.llm.response_models import aggregate_usage

            aggregate_usage(usage_sink, tracked_usage)
        record_agent_event(
            db,
            event_name="ai.smart_deck_generation.completed",
            run_type="smart_deck_generation",
            workspace_id=workspace.id,
            deck_id=deck.id,
            user_id=deck.user_id,
            run_id=job.id,
            status="completed",
            provider=provider,
            model=job.model,
            input_tokens=int(tracked_usage.get("input_tokens") or 0) if tracked_usage else None,
            output_tokens=int(tracked_usage.get("output_tokens") or 0) if tracked_usage else None,
            estimated_cost_cents=float(tracked_usage.get("estimated_cost_cents")) if tracked_usage and tracked_usage.get("estimated_cost_cents") is not None else None,
            metadata={
                "designVersionId": version.id,
                "generatedSlideCount": len(created_slide_ids),
                "selectedSlideCount": len(payload.selectedSourceSlideIds),
                "credentialSource": claude_config.get("source"),
                "knowledgeVersion": knowledge_metadata.get("version"),
                "knowledgeSource": knowledge_metadata.get("source"),
                "runtimeContextVersion": (llm_context.get("runtimeContext") or {}).get("schemaVersion"),
                "sourceFactCount": source_fact_package.get("factCount"),
                "sourceFactTypeCounts": source_fact_package.get("factTypeCounts"),
                "sourceFactSafetyFlagCounts": source_fact_package.get("safetyFlagCounts"),
                "missingSlideFactCount": len((source_fact_package.get("coverage") or {}).get("missingSlideFactIds") or []),
                "critiqueStatus": final_critique.get("status"),
                "critiqueWarningCount": final_critique.get("warningCount"),
                "critiqueMissingInputCount": final_critique.get("missingInputCount"),
                "critiqueBlockingCount": (final_critique.get("decision") or {}).get("blockingCount"),
                "repairActionCount": len(final_critique.get("repairActions") or []),
                "repairPerformed": repair_performed,
                "inputCachedTokens": int(tracked_usage.get("input_cached_tokens") or 0) if tracked_usage else 0,
                "trackedTotalTokens": int(tracked_usage.get("total_tokens") or 0) if tracked_usage else 0,
                "costSource": "estimated" if tracked_usage and tracked_usage.get("estimated_cost_cents") is not None else "unavailable",
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        safe_error_message = _safe_generation_failure_message(exc)

        failed_job = db.query(GenerationJob).filter(
            GenerationJob.id == durable_generation_job_id
        ).one_or_none()
        failed_workspace = db.query(SmartDeckWorkspace).filter(
            SmartDeckWorkspace.id == durable_workspace_id
        ).one_or_none()
        if failed_job is not None:
            failed_job.status = "failed"
            failed_job.error_message = safe_error_message
            failed_job.completed_at = datetime.utcnow()
        if failed_workspace is not None:
            failed_workspace.status = "failed"

        if failed_job is not None and failed_workspace is not None:
            _record_smart_deck_message(
                db,
                workspace_id=failed_workspace.id,
                deck_id=durable_deck_id,
                role="system",
                content=f"Generation failed: {safe_error_message}",
                generation_job_id=failed_job.id,
                selected_source_slide_ids=payload.selectedSourceSlideIds,
            )
            record_agent_event(
                db,
                event_name=("ai.instant_deck_generation.failed" if full_html_request else "ai.smart_deck_generation.failed"),
                run_type=("instant_deck_generation" if full_html_request else "smart_deck_generation"),
                workspace_id=failed_workspace.id,
                deck_id=durable_deck_id,
                user_id=durable_user_id,
                run_id=failed_job.id,
                event_level="error",
                status="failed",
                provider=provider,
                model=failed_job.model,
                error_category=exc.__class__.__name__,
                error_message=safe_error_message,
                metadata={
                    "selectedSlideCount": len(payload.selectedSourceSlideIds),
                    "promptLength": len(payload.prompt),
                    "hasAdditionalContext": bool(payload.additionalContext),
                    "credentialSource": claude_config.get("source"),
                    "knowledgeVersion": knowledge_metadata.get("version"),
                    "knowledgeSource": knowledge_metadata.get("source"),
                    "runtimeContextVersion": (llm_context.get("runtimeContext") or {}).get("schemaVersion"),
                    "instantOperationId": payload.instantOperationId if full_html_request else None,
                    "sourceFileId": getattr(getattr(deck, "file", None), "id", None),
                    "outputContract": payload.outputContract,
                    "generationMode": payload.generationMode,
                },
            )
        db.commit()
        raise

    workspace = get_smart_deck_workspace(db, deck_id)
    if workspace is None:
        raise ValueError("Smart Deck workspace could not be reloaded.")

    reloaded_job = db.query(GenerationJob).filter(GenerationJob.id == job.id).one()
    reloaded_version = (
        db.query(DesignVersion)
        .options(selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions))
        .filter(DesignVersion.id == version.id)
        .one()
    )
    return _map_job(reloaded_job), _map_design_version(reloaded_version), workspace


def get_generation_job(db: Session, deck_id: str, job_id: str) -> dict | None:
    job = db.query(GenerationJob).filter(GenerationJob.deck_id == deck_id, GenerationJob.id == job_id).first()
    return _map_job(job) if job else None


def get_slide_redesign_run(db: Session, run_id: str) -> dict | None:
    job = (
        db.query(GenerationJob)
        .options(
            selectinload(GenerationJob.design_versions).selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(GenerationJob.generated_slides),
        )
        .filter(GenerationJob.id == run_id)
        .first()
    )
    if job is None:
        return None

    result_json = job.result_json if isinstance(job.result_json, dict) else {}
    generated_version_ids = result_json.get("generatedSlideIds")
    if not isinstance(generated_version_ids, list):
        generated_version_ids = [slide.id for slide in job.generated_slides]

    design_version_id = result_json.get("designVersionId")
    design_version = None
    if isinstance(design_version_id, str):
        design_version = next((version for version in job.design_versions if version.id == design_version_id), None)
    if design_version is None and job.design_versions:
        design_version = sorted(job.design_versions, key=lambda item: item.created_at, reverse=True)[0]
    if design_version is not None and generation_job_is_instant_deck(job):
        require_publishable_instant_design_version(design_version)

    mapped_design_version = _map_design_version(design_version) if design_version else None
    generated_slides = [
        {
            "generated_slide_id": slide.get("generated_slide_id") or slide.get("id"),
            "code_version_id": slide.get("current_version_id"),
            "render_schema_json": slide.get("render_schema_json") or slide.get("renderSchema") or {},
            "bucket_render_schema_key": slide.get("bucket_render_schema_key"),
            "bucket_code_key": slide.get("bucket_code_key"),
            "bucket_artifacts": slide.get("bucket_artifacts") or {},
        }
        for slide in (mapped_design_version or {}).get("generatedSlides", [])
    ]
    runtime_capabilities = build_smart_deck_runtime_capabilities()
    return {
        "runId": job.id,
        "run_id": job.id,
        "deckId": job.deck_id,
        "deck_id": job.deck_id,
        "status": job.status,
        "intentType": "redesign_slides",
        "outputMode": "editable_slide_versions",
        "scope": "selected_slides",
        "selectedSlideIds": job.selected_source_slide_ids_json or [],
        "batchId": design_version.id if design_version else design_version_id,
        "design_version_id": design_version.id if design_version else design_version_id,
        "state": (mapped_design_version or {}).get("state") or ("preview" if design_version else None),
        "changed_slide_ids": (mapped_design_version or {}).get("changed_slide_ids") or [],
        "generated_slides": generated_slides,
        "generatedVersionIds": generated_version_ids,
        "generatedVersionCount": len(generated_version_ids),
        "generationJob": _map_job(job),
        "designVersion": mapped_design_version,
        "errorMessage": job.error_message,
    }


def list_design_versions(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    versions = [
        version
        for version in sorted(deck.design_versions, key=lambda item: item.created_at, reverse=True)
        if design_version_is_visible(version)
    ]
    active = next((version for version in versions if version.is_active), None)
    return {
        "designVersions": [_map_design_version(version) for version in versions],
        "activeDesignVersionId": active.id if active else None,
    }


def apply_design_version(db: Session, deck_id: str, version_id: str) -> dict | None:
    version = (
        db.query(DesignVersion)
        .options(
            selectinload(DesignVersion.generation_job),
            selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
        )
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == version_id)
        .first()
    )
    if version is None:
        return None
    if generation_job_is_instant_deck(version.generation_job):
        require_publishable_instant_design_version(version)
    now = datetime.utcnow()
    for candidate in (
        db.query(DesignVersion)
        .options(
            selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
        )
        .filter(DesignVersion.deck_id == deck_id)
        .all()
    ):
        candidate.is_active = candidate.id == version.id
        if candidate.id == version.id:
            candidate.status = "applied"
            candidate.applied_at = now
            for slide in candidate.generated_slides:
                latest_code = _latest_code_version(slide)
                if latest_code:
                    slide.current_version_id = latest_code.id
                    slide.render_schema_json = latest_code.render_schema_json
                    _set_code_version_lifecycle(latest_code, "accepted")
                for element in slide.elements:
                    for element_version in element.versions:
                        if element_version.status == "candidate":
                            element_version.status = "accepted"
        elif candidate.status in {"applied", "restored"}:
            candidate.status = "draft"
            for slide in candidate.generated_slides:
                latest_code = _latest_code_version(slide)
                if latest_code:
                    _set_code_version_lifecycle(latest_code, "superseded")
    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).first()
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if deck:
        deck.current_design_version_id = version.id
    if workspace:
        active_slides = sorted(version.generated_slides, key=lambda item: item.slide_number)
        workspace.status = "ready"
        workspace.active_design_version_id = version.id
        workspace.active_generated_slide_id = active_slides[0].id if active_slides else None
        preference = db.query(SmartDeckPreference).filter(SmartDeckPreference.workspace_id == workspace.id).first()
        if preference:
            preference.active_design_version_id = version.id
            preference.active_generated_slide_id = workspace.active_generated_slide_id
    _record_design_version_snapshot_artifact(db, deck_id, version, "apply")
    db.flush()
    _rewrite_design_version_manifest(db, version, "saved", "apply")
    from app.services.platform.shell.shell_service import record_accepted_deck_version

    result_json = version.generation_job.result_json if version.generation_job and isinstance(version.generation_job.result_json, dict) else {}
    provenance = result_json.get("provenance") if isinstance(result_json.get("provenance"), dict) else {}
    source_surface = "due_diligence" if provenance.get("mode") == "due_diligence_full_deck" else "smart_deck"
    record_accepted_deck_version(
        db,
        deck_id,
        source_surface=source_surface,
        source_artifact_id=version.id,
        design_version_id=version.id,
        changed_slide_ids=[slide.source_slide_id for slide in version.generated_slides if slide.source_slide_id],
        change_summary=version.summary or version.name,
    )
    apply_retention(db, deck_id)
    db.commit()
    return list_design_versions(db, deck_id)


def discard_design_version(db: Session, deck_id: str, version_id: str) -> dict | None:
    version = (
        db.query(DesignVersion)
        .options(
            selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
        )
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == version_id)
        .first()
    )
    if version is None:
        return None
    for slide in version.generated_slides:
        latest_code = _latest_code_version(slide)
        if latest_code:
            _set_code_version_lifecycle(latest_code, "unused")
        for element in slide.elements:
            for element_version in element.versions:
                if element_version.status == "candidate":
                    element_version.status = "unused"
    version.status = "discarded"
    version.is_active = False
    version.discarded_at = datetime.utcnow()
    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).first()
    if workspace and workspace.active_design_version_id == version.id:
        next_version = (
            db.query(DesignVersion)
            .filter(
                DesignVersion.deck_id == deck_id,
                DesignVersion.id != version.id,
                DesignVersion.status != "discarded",
            )
            .order_by(DesignVersion.created_at.desc())
            .first()
        )
        next_slides = sorted(next_version.generated_slides, key=lambda item: item.slide_number) if next_version else []
        workspace.active_design_version_id = next_version.id if next_version else None
        workspace.active_generated_slide_id = next_slides[0].id if next_slides else None
        preference = db.query(SmartDeckPreference).filter(SmartDeckPreference.workspace_id == workspace.id).first()
        if preference:
            preference.active_design_version_id = workspace.active_design_version_id
            preference.active_generated_slide_id = workspace.active_generated_slide_id
    db.flush()
    _rewrite_design_version_manifest(db, version, "discarded", "discard")
    apply_retention(db, deck_id)
    db.commit()
    return list_design_versions(db, deck_id)


def restore_design_version(db: Session, deck_id: str, version_id: str) -> dict | None:
    source_version = (
        db.query(DesignVersion)
        .options(
            selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
        )
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == version_id)
        .first()
    )
    if source_version is None:
        return None

    now = datetime.utcnow()
    restore_version = DesignVersion(
        id=generate_id("designver"),
        deck_id=deck_id,
        generation_job_id=source_version.generation_job_id,
        name=f"Restore of {source_version.name}"[:255],
        status="restored",
        is_active=True,
        summary=f"Restored from design version {source_version.id}.",
        created_at=now,
        updated_at=now,
        applied_at=now,
    )
    db.add(restore_version)
    db.flush()

    created_slides: list[GeneratedSlide] = []
    for source_slide in sorted(source_version.generated_slides, key=lambda item: item.slide_number):
        restored_slide = GeneratedSlide(
            id=generate_id("genslide"),
            deck_id=deck_id,
            design_version_id=restore_version.id,
            generation_job_id=source_slide.generation_job_id,
            source_slide_id=source_slide.source_slide_id,
            slide_number=source_slide.slide_number,
            title=source_slide.title,
            status="ready",
            render_schema_json=source_slide.render_schema_json,
            design_tokens_json=source_slide.design_tokens_json,
            preview_image_url=source_slide.preview_image_url,
            validation_status=source_slide.validation_status,
        )
        db.add(restored_slide)
        db.flush()
        created_slides.append(restored_slide)
        source_code = _latest_code_version(source_slide)
        code_version_id = generate_id("codever")
        restored_render_schema = source_code.render_schema_json if source_code else source_slide.render_schema_json
        render_schema_artifact = _write_render_schema_json_artifact(
            user_id=source_version.deck.user_id if source_version.deck else None,
            deck_id=deck_id,
            design_version_id=restore_version.id,
            generated_slide_id=restored_slide.id,
            code_version_id=code_version_id,
            render_schema=restored_render_schema,
        )
        code_json = {
            **(source_code.code_json if source_code and isinstance(source_code.code_json, dict) else {}),
            "sourceDesignVersionId": source_version.id,
            "lifecycle": "accepted",
            "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
            "renderSchemaStorageProvider": render_schema_artifact["storageProvider"],
            "renderSchemaStoragePath": render_schema_artifact["storagePath"],
            "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
        }
        code_metadata_artifact = _write_code_metadata_json_artifact(
            user_id=source_version.deck.user_id if source_version.deck else None,
            deck_id=deck_id,
            design_version_id=restore_version.id,
            generated_slide_id=restored_slide.id,
            code_version_id=code_version_id,
            code_json=code_json,
        )
        code_json = {
            **code_json,
            "codeJsonHash": code_metadata_artifact["codeJsonHash"],
            "codeJsonStorageProvider": code_metadata_artifact["storageProvider"],
            "codeJsonStoragePath": code_metadata_artifact["storagePath"],
            "bucketCodeJsonKey": code_metadata_artifact["storagePath"],
        }
        code_version = GeneratedSlideCodeVersion(
            id=code_version_id,
            generated_slide_id=restored_slide.id,
            version_number=1,
            code_kind=source_code.code_kind if source_code else "render_schema",
            schema_version=source_code.schema_version if source_code else "smart-deck-render-schema.v1",
            render_schema_json=restored_render_schema,
            code_json=code_json,
            bucket_render_schema_key=render_schema_artifact["storagePath"],
            bucket_code_key=code_metadata_artifact["storagePath"],
            bucket_thumbnail_key=None,
            status=source_code.status if source_code else "valid",
            validation_errors_json=source_code.validation_errors_json if source_code else [],
        )
        db.add(code_version)
        restored_slide.current_version_id = code_version.id
        _record_design_tokens(
            db,
            deck_id=deck_id,
            design_version_id=restore_version.id,
            generated_slide_id=restored_slide.id,
        )

    for candidate in (
        db.query(DesignVersion)
        .options(selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions))
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id != restore_version.id)
        .all()
    ):
        candidate.is_active = False
        if candidate.status in {"applied", "restored"}:
            candidate.status = "draft"
        for slide in candidate.generated_slides:
            latest_code = _latest_code_version(slide)
            if latest_code:
                _set_code_version_lifecycle(latest_code, "superseded")

    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).first()
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if deck:
        deck.current_design_version_id = restore_version.id
    if workspace:
        workspace.status = "ready"
        workspace.active_design_version_id = restore_version.id
        workspace.active_generated_slide_id = created_slides[0].id if created_slides else None
        preference = db.query(SmartDeckPreference).filter(SmartDeckPreference.workspace_id == workspace.id).first()
        if preference:
            preference.active_design_version_id = restore_version.id
            preference.active_generated_slide_id = workspace.active_generated_slide_id

    db.flush()
    db.refresh(restore_version)
    _record_design_version_snapshot_artifact(db, deck_id, restore_version, "restore")
    db.commit()
    return list_design_versions(db, deck_id)


def get_generated_slide_code(db: Session, deck_id: str, generated_slide_id: str) -> tuple[dict, dict] | None:
    slide = (
        db.query(GeneratedSlide)
        .options(
            selectinload(GeneratedSlide.code_versions),
            selectinload(GeneratedSlide.design_version).selectinload(DesignVersion.generation_job),
            selectinload(GeneratedSlide.design_version).selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
        )
        .filter(GeneratedSlide.deck_id == deck_id, GeneratedSlide.id == generated_slide_id)
        .first()
    )
    if slide is None or not slide.code_versions:
        return None
    if not design_version_is_visible(slide.design_version):
        return None
    current_code = _current_code_version(slide)
    if slide.current_version_id and current_code is None:
        return None
    code_version = current_code or _latest_code_version(slide)
    if code_version is None:
        return None
    return _map_generated_slide(slide), _map_code_version(
        code_version,
        render_schema_override=slide.render_schema_json,
    )


def update_generated_slide_typography(
    db: Session,
    deck_id: str,
    generated_slide_id: str,
    *,
    heading_font: str,
    body_font: str,
) -> tuple[dict, dict] | None:
    slide = (
        db.query(GeneratedSlide)
        .options(selectinload(GeneratedSlide.code_versions))
        .filter(GeneratedSlide.deck_id == deck_id, GeneratedSlide.id == generated_slide_id)
        .first()
    )
    if slide is None or not slide.code_versions:
        return None

    design_tokens = dict(slide.design_tokens_json or DESIGN_TOKENS)
    design_tokens["brand.headingFont"] = heading_font.strip()
    design_tokens["brand.bodyFont"] = body_font.strip()
    slide.design_tokens_json = design_tokens

    for token_name, token_value in (
        ("brand.headingFont", design_tokens["brand.headingFont"]),
        ("brand.bodyFont", design_tokens["brand.bodyFont"]),
    ):
        token = (
            db.query(DesignToken)
            .filter(
                DesignToken.deck_id == deck_id,
                DesignToken.generated_slide_id == generated_slide_id,
                DesignToken.token_name == token_name,
            )
            .first()
        )
        if token is None:
            db.add(
                DesignToken(
                    id=generate_id("dstok"),
                    deck_id=deck_id,
                    design_version_id=slide.design_version_id,
                    generated_slide_id=generated_slide_id,
                    token_name=token_name,
                    token_value=token_value,
                    token_type="font",
                    source="user_typography",
                )
            )
        else:
            token.token_value = token_value
            token.token_type = "font"
            token.source = "user_typography"

    db.commit()
    db.refresh(slide)
    code_version = _current_code_version(slide) or _latest_code_version(slide)
    if code_version is None:
        return None
    return _map_generated_slide(slide), _map_code_version(code_version)


def get_generated_slide_code_artifact_urls(
    db: Session,
    deck_id: str,
    generated_slide_id: str,
    code_version_id: str,
) -> dict | None:
    slide = (
        db.query(GeneratedSlide)
        .options(
            selectinload(GeneratedSlide.code_versions),
            selectinload(GeneratedSlide.design_version).selectinload(DesignVersion.generation_job),
            selectinload(GeneratedSlide.design_version).selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
        )
        .filter(GeneratedSlide.deck_id == deck_id, GeneratedSlide.id == generated_slide_id)
        .first()
    )
    if slide is None or not design_version_is_visible(slide.design_version):
        return None
    current_code = _current_code_version(slide)
    if slide.current_version_id and current_code is None:
        return None
    effective_code = current_code or _latest_code_version(slide)
    if effective_code is None or effective_code.id != code_version_id:
        return None
    code_version = effective_code

    bucket_service = get_bucket_artifact_service()

    def signed_url(key: str | None) -> str | None:
        if not key:
            return None
        return bucket_service.create_signed_url_sync(key=key)

    return {
        "render_schema_url": signed_url(code_version.bucket_render_schema_key),
        "code_url": signed_url(code_version.bucket_code_key),
        "thumbnail_url": signed_url(code_version.bucket_thumbnail_key),
    }


def save_generated_slide_code_thumbnail(
    db: Session,
    deck_id: str,
    generated_slide_id: str,
    code_version_id: str,
    payload: bytes,
    content_type: str,
) -> dict | None:
    if not payload:
        raise ValueError("Thumbnail payload is required.")
    if len(payload) > 5 * 1024 * 1024:
        raise ValueError("Thumbnail payload must be 5 MB or smaller.")
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("Thumbnail must be a PNG, JPEG, or WebP image.")

    result = (
        db.query(GeneratedSlideCodeVersion, GeneratedSlide, Deck)
        .join(GeneratedSlide, GeneratedSlide.id == GeneratedSlideCodeVersion.generated_slide_id)
        .join(Deck, Deck.id == GeneratedSlide.deck_id)
        .filter(
            Deck.id == deck_id,
            GeneratedSlide.id == generated_slide_id,
            GeneratedSlideCodeVersion.id == code_version_id,
        )
        .first()
    )
    if result is None:
        return None
    code_version, slide, deck = result
    bucket_service = get_bucket_artifact_service()
    thumbnail_key = bucket_service.make_thumbnail_key(
        user_id=deck.user_id,
        deck_id=deck.id,
        design_version_id=slide.design_version_id,
        generated_slide_id=slide.id,
        code_version_id=code_version.id,
    )
    bucket_service.put_bytes_sync(key=thumbnail_key, data=payload, content_type=content_type)
    code_version.bucket_thumbnail_key = thumbnail_key
    code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
    code_version.code_json = {
        **code_json,
        "bucketThumbnailKey": thumbnail_key,
        "thumbnailContentType": content_type,
        "thumbnailUpdatedAt": datetime.utcnow().isoformat() + "Z",
    }
    db.commit()
    return {
        "generated_slide_id": slide.id,
        "code_version_id": code_version.id,
        "bucket_thumbnail_key": thumbnail_key,
        "thumbnail_url": bucket_service.create_signed_url_sync(key=thumbnail_key),
    }


def update_smart_deck_preferences(db: Session, deck_id: str, payload: UpdateSmartDeckPreferenceInput) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    workspace, preference = _ensure_workspace_state(db, deck)
    source_ids = {slide.id for slide in deck.slides}
    generated_by_id = {slide.id: slide for slide in deck.generated_slides}
    version_by_id = {version.id: version for version in deck.design_versions}

    effective_version_id = (
        payload.activeDesignVersionId
        if "activeDesignVersionId" in payload.model_fields_set
        else workspace.active_design_version_id
    )
    effective_generated_id = (
        payload.activeGeneratedSlideId
        if "activeGeneratedSlideId" in payload.model_fields_set
        else workspace.active_generated_slide_id
    )
    effective_source_id = (
        payload.activeSourceSlideId
        if "activeSourceSlideId" in payload.model_fields_set
        else workspace.active_source_slide_id
    )

    def generated_source_ids(slide: GeneratedSlide) -> set[str]:
        return {
            source_id
            for source_id in [slide.source_slide_id, *(entry.source_slide_id for entry in slide.source_lineage)]
            if source_id
        }

    tuple_fields = {"activeDesignVersionId", "activeGeneratedSlideId", "activeSourceSlideId"}
    if payload.model_fields_set & tuple_fields:
        effective_version = version_by_id.get(effective_version_id) if effective_version_id is not None else None
        if effective_version_id is not None and effective_version is None:
            raise ValueError("activeDesignVersionId does not belong to this deck.")
        effective_generated = generated_by_id.get(effective_generated_id) if effective_generated_id is not None else None
        if effective_generated_id is not None and effective_generated is None:
            raise ValueError("activeGeneratedSlideId does not belong to this deck.")
        if effective_source_id is not None and effective_source_id not in source_ids:
            raise ValueError("activeSourceSlideId does not belong to this deck.")
        if effective_generated is not None:
            if effective_version is None or effective_generated.design_version_id != effective_version.id:
                raise ValueError("activeGeneratedSlideId requires a matching activeDesignVersionId.")
            if effective_source_id is not None and effective_source_id not in generated_source_ids(effective_generated):
                raise ValueError("activeSourceSlideId does not belong to activeGeneratedSlideId lineage.")
        elif effective_source_id is not None and effective_version is not None:
            version_source_ids = {
                source_id
                for slide in effective_version.generated_slides
                for source_id in generated_source_ids(slide)
            }
            if effective_source_id not in version_source_ids:
                raise ValueError("activeSourceSlideId does not belong to activeDesignVersionId lineage.")

    if payload.selectedSourceSlideIds is not None:
        missing_ids = [slide_id for slide_id in payload.selectedSourceSlideIds if slide_id not in source_ids]
        if missing_ids:
            raise ValueError(f"Selected source slides do not belong to this deck: {', '.join(missing_ids)}")
        preference.selected_source_slide_ids_json = payload.selectedSourceSlideIds
    if "activeSourceSlideId" in payload.model_fields_set:
        if payload.activeSourceSlideId is not None and payload.activeSourceSlideId not in source_ids:
            raise ValueError("activeSourceSlideId does not belong to this deck.")
        workspace.active_source_slide_id = payload.activeSourceSlideId
        preference.active_source_slide_id = payload.activeSourceSlideId
    if "activeDesignVersionId" in payload.model_fields_set:
        workspace.active_design_version_id = payload.activeDesignVersionId
        preference.active_design_version_id = payload.activeDesignVersionId
    if "activeGeneratedSlideId" in payload.model_fields_set:
        workspace.active_generated_slide_id = payload.activeGeneratedSlideId
        preference.active_generated_slide_id = payload.activeGeneratedSlideId
    if "selectedElementId" in payload.model_fields_set:
        if payload.selectedElementId is None:
            workspace.selected_element_id = None
            preference.selected_element_id = None
        else:
            element = (
                db.query(GeneratedSlideElement)
                .filter(GeneratedSlideElement.deck_id == deck_id, GeneratedSlideElement.id == payload.selectedElementId)
                .first()
            )
            if element is None:
                raise ValueError("selectedElementId does not belong to this deck.")
            workspace.selected_element_id = payload.selectedElementId
            preference.selected_element_id = payload.selectedElementId
    if "audience" in payload.model_fields_set:
        preference.audience = payload.audience
    if "deckType" in payload.model_fields_set:
        preference.deck_type = payload.deckType
    if "preferredModel" in payload.model_fields_set:
        preference.preferred_model = payload.preferredModel
    if "selectedSubject" in payload.model_fields_set:
        preference.selected_subject = payload.selectedSubject
    if "selectedActionId" in payload.model_fields_set:
        preference.selected_action_id = payload.selectedActionId
    if payload.zoomLevel is not None:
        preference.zoom_level = payload.zoomLevel
    if payload.canvasFitMode is not None:
        preference.canvas_fit_mode = payload.canvasFitMode
    if payload.rightPanelOpen is not None:
        preference.right_panel_open = payload.rightPanelOpen
    if payload.slideRailOpen is not None:
        preference.slide_rail_open = payload.slideRailOpen

    db.commit()
    return _map_preference(preference)


def list_smart_deck_messages(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    workspace, _ = _ensure_workspace_state(db, deck)
    db.commit()
    messages = (
        db.query(SmartDeckMessage)
        .filter(SmartDeckMessage.workspace_id == workspace.id)
        .order_by(SmartDeckMessage.created_at.asc())
        .all()
    )
    return {"messages": [_map_message(message) for message in messages]}


def get_smart_deck_assistant_run(db: Session, run_id: str) -> dict | None:
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.artifact_type == SMART_DECK_ASSISTANT_ARTIFACT_TYPE,
            DeckLlmArtifact.artifact_key == run_id,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if artifact is None:
        return None

    payload = load_deck_llm_artifact_payload(artifact)
    if not payload:
        return None
    insight = payload.get("insight") if isinstance(payload, dict) else None
    assistant_message_ids = (payload.get("messageIds") if isinstance(payload, dict) else {}) or {}
    assistant_message_id = assistant_message_ids.get("assistant") if isinstance(assistant_message_ids, dict) else None
    assistant_message = None
    if assistant_message_id:
        assistant_message = (
            db.query(SmartDeckMessage)
            .filter(SmartDeckMessage.id == assistant_message_id)
            .first()
        )

    if not isinstance(payload, dict):
        return None

    return {
        "runId": payload.get("runId") or run_id,
        "deckId": artifact.deck_id,
        "intentType": payload.get("intentType"),
        "scope": payload.get("scope"),
        "status": "completed",
        "outputType": ASSISTANT_OUTPUT_TYPES.get(payload.get("intentType"), "insight"),
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "inputContext": payload.get("inputContext") or {},
        "insight": insight or {},
        "assistantMessage": _map_message(assistant_message) if assistant_message is not None else None,
        "savedArtifactId": artifact.id,
    }


def get_generated_slide_scene_graph(db: Session, deck_id: str, generated_slide_id: str) -> dict | None:
    slide = (
        db.query(GeneratedSlide)
        .options(
            selectinload(GeneratedSlide.code_versions),
            selectinload(GeneratedSlide.elements).selectinload(GeneratedSlideElement.versions),
        )
        .filter(GeneratedSlide.deck_id == deck_id, GeneratedSlide.id == generated_slide_id)
        .first()
    )
    if slide is None:
        return None

    elements = sorted(slide.elements, key=lambda item: item.z_index)
    active_versions = [
        latest
        for latest in (_latest_element_version(element) for element in elements)
        if latest is not None
    ]
    return {
        "generatedSlide": _map_generated_slide(slide),
        "elements": [_map_generated_slide_element(element) for element in elements],
        "activeElementVersions": [_map_generated_slide_element_version(version) for version in active_versions],
    }


def create_manual_edit_job(
    db: Session,
    deck_id: str,
    generated_slide_id: str,
    payload: CreateManualEditJobInput,
) -> tuple[dict, dict, dict]:
    """Clone the current full design into an idempotent manual-edit candidate."""

    request_fingerprint = _json_hash(
        {
            "baseDesignVersionId": payload.baseDesignVersionId,
            "baseGeneratedSlideId": generated_slide_id,
            "sourceSlideId": payload.sourceSlideId,
            "operations": [operation.model_dump(mode="json") for operation in payload.operations],
        }
    )

    try:
        deck = db.query(Deck).populate_existing().filter(Deck.id == deck_id).with_for_update().one_or_none()
        if deck is None:
            raise ManualEditConflictError("base_design_version_mismatch", "Deck does not exist.")

        replay_artifact = (
            db.query(DeckLlmArtifact)
            .filter(
                DeckLlmArtifact.deck_id == deck_id,
                DeckLlmArtifact.artifact_type == "smart_deck_manual_edit_job",
                DeckLlmArtifact.artifact_key == payload.idempotencyKey,
                DeckLlmArtifact.status == "ready",
            )
            .order_by(DeckLlmArtifact.created_at.desc())
            .first()
        )
        if replay_artifact is not None:
            replay_payload = replay_artifact.payload_json if isinstance(replay_artifact.payload_json, dict) else {}
            if replay_payload.get("requestFingerprint") != request_fingerprint:
                raise ManualEditConflictError(
                    "idempotency_key_reused",
                    "idempotencyKey was already used for a different manual edit request.",
                )
            replay_version_id = replay_payload.get("candidateDesignVersionId")
            replay_slide_id = replay_payload.get("candidateGeneratedSlideId")
            replay_version = (
                db.query(DesignVersion)
                .options(
                    selectinload(DesignVersion.generation_job),
                    selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
                    selectinload(DesignVersion.generated_slides)
                    .selectinload(GeneratedSlide.elements)
                    .selectinload(GeneratedSlideElement.versions),
                )
                .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == replay_version_id)
                .one_or_none()
            )
            replay_slide = next(
                (slide for slide in replay_version.generated_slides if slide.id == replay_slide_id),
                None,
            ) if replay_version else None
            if replay_version is None or replay_slide is None:
                raise ManualEditConflictError(
                    "idempotency_replay_unavailable",
                    "The prior manual edit result is no longer available.",
                )
            replay_result = (
                {key: value for key, value in replay_payload.items() if key != "requestFingerprint"},
                _map_design_version(replay_version),
                _map_generated_slide(replay_slide),
            )
            db.commit()
            return replay_result

        base_version = (
            db.query(DesignVersion)
            .options(
                selectinload(DesignVersion.generation_job),
                selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
                selectinload(DesignVersion.generated_slides)
                .selectinload(GeneratedSlide.elements)
                .selectinload(GeneratedSlideElement.versions),
            )
            .populate_existing()
            .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == payload.baseDesignVersionId)
            .with_for_update()
            .one_or_none()
        )
        if base_version is None:
            raise ManualEditConflictError(
                "base_design_version_mismatch",
                "baseDesignVersionId does not belong to this deck.",
            )
        workspace = (
            db.query(SmartDeckWorkspace)
            .populate_existing()
            .filter(SmartDeckWorkspace.deck_id == deck_id)
            .with_for_update()
            .one_or_none()
        )
        preference = (
            db.query(SmartDeckPreference)
            .populate_existing()
            .filter(SmartDeckPreference.workspace_id == workspace.id)
            .with_for_update()
            .one_or_none()
            if workspace is not None
            else None
        )
        if (
            base_version.status == "discarded"
            or not base_version.is_active
            or deck.current_design_version_id != base_version.id
            or (workspace is not None and workspace.active_design_version_id not in {None, base_version.id})
            or (preference is not None and preference.active_design_version_id not in {None, base_version.id})
        ):
            raise ManualEditConflictError(
                "base_design_version_stale",
                "baseDesignVersionId is not the deck's currently selected design version.",
            )

        base_slide = next((slide for slide in base_version.generated_slides if slide.id == generated_slide_id), None)
        if base_slide is None:
            raise ManualEditConflictError(
                "base_design_version_stale",
                "generatedSlideId is not part of baseDesignVersionId.",
            )
        if base_slide.source_slide_id != payload.sourceSlideId:
            raise ManualEditConflictError(
                "source_slide_mismatch",
                "sourceSlideId does not match generatedSlideId.",
            )
        source_slide_exists = (
            db.query(DeckSlide.id)
            .filter(DeckSlide.deck_id == deck_id, DeckSlide.id == payload.sourceSlideId)
            .first()
        )
        if source_slide_exists is None:
            raise ManualEditConflictError(
                "source_slide_mismatch",
                "sourceSlideId does not belong to this deck.",
            )

        base_elements = list(base_slide.elements)
        elements_by_id = {element.id: element for element in base_elements}
        if len(elements_by_id) != len(base_elements):
            raise ManualEditConflictError("element_identity_mismatch", "Generated slide element identities are invalid.")
        elements_by_key = {element.element_key: element for element in base_elements}
        if len(elements_by_key) != len(base_elements):
            raise ManualEditConflictError("element_identity_mismatch", "Persisted element keys are not unique.")

        base_render_schema = RenderSchema.model_validate(base_slide.render_schema_json).model_dump()
        base_layout_warnings = set(_collect_render_schema_reviewable_layout_warnings(base_render_schema))
        render_elements = base_render_schema["elements"]
        render_elements_by_key = {str(element["id"]): element for element in render_elements}
        if len(render_elements_by_key) != len(render_elements):
            raise ManualEditConflictError("element_identity_mismatch", "Render element keys are not unique.")
        if set(elements_by_key) != set(render_elements_by_key):
            raise ManualEditConflictError(
                "element_identity_mismatch",
                "Persisted elements do not match the base render schema.",
            )
        for element in base_elements:
            if (
                element.deck_id != deck_id
                or element.design_version_id != base_version.id
                or element.source_slide_id != payload.sourceSlideId
            ):
                raise ManualEditConflictError(
                    "element_identity_mismatch",
                    "Persisted element ownership does not match the requested slide.",
                )
            render_element = render_elements_by_key[element.element_key]
            persisted_geometry = {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            }
            if persisted_geometry != {key: int(render_element[key]) for key in persisted_geometry}:
                raise ManualEditConflictError(
                    "base_geometry_stale",
                    "Persisted element geometry does not match the base render schema.",
                )

        changed_geometry: dict[str, dict[str, int]] = {}
        changed_operation_types: dict[str, list[str]] = {}
        for operation in payload.operations:
            element = elements_by_id.get(operation.persistedElementId)
            if element is None:
                raise ManualEditConflictError(
                    "element_identity_mismatch",
                    "persistedElementId does not belong to generatedSlideId.",
                )
            if element.element_key != operation.elementKey:
                raise ManualEditConflictError(
                    "element_identity_mismatch",
                    "Persisted element ownership or elementKey does not match the request.",
                )
            if element.locked:
                raise ValueError("Locked elements cannot be moved or resized.")
            render_element = render_elements_by_key.get(operation.elementKey)
            if render_element is None:
                raise ManualEditConflictError(
                    "element_identity_mismatch",
                    "elementKey does not exist in the generated slide render schema.",
                )
            persisted_geometry = {
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
            }
            geometry = changed_geometry.setdefault(element.id, dict(persisted_geometry))
            changed_operation_types.setdefault(element.id, []).append(operation.operation)
            if operation.operation == "move":
                geometry["x"] = operation.x
                geometry["y"] = operation.y
            else:
                geometry["width"] = operation.width
                geometry["height"] = operation.height

        for element_id, geometry in changed_geometry.items():
            if geometry["x"] + geometry["width"] > base_render_schema["width"]:
                raise ValueError(f"Manual edit for element {elements_by_id[element_id].element_key} exceeds the slide width.")
            if geometry["y"] + geometry["height"] > base_render_schema["height"]:
                raise ValueError(f"Manual edit for element {elements_by_id[element_id].element_key} exceeds the slide height.")
            render_element = render_elements_by_key[elements_by_id[element_id].element_key]
            render_element.update(geometry)

        candidate_analytics = base_render_schema.setdefault("analytics", {})
        candidate_provider_warnings = [
            str(item).strip()
            for item in candidate_analytics.get("qualityWarnings") or []
            if str(item).strip() and str(item).strip() not in base_layout_warnings
        ]
        candidate_detected_warnings = _collect_render_schema_reviewable_layout_warnings(base_render_schema)
        candidate_analytics["qualityWarnings"] = _cap_render_schema_quality_warnings(
            candidate_provider_warnings,
            candidate_detected_warnings,
        )
        candidate_render_schema = RenderSchema.model_validate(base_render_schema).model_dump()
        candidate_validation_warnings = _persisted_generated_slide_validation_warnings(candidate_render_schema)
        now = datetime.utcnow()
        manual_edit_job_id = generate_id("manedit")
        candidate_version = DesignVersion(
            id=generate_id("designver"),
            deck_id=deck_id,
            generation_job_id=base_slide.generation_job_id,
            name=f"Manual layout edit for {base_slide.title}"[:255],
            status="draft",
            is_active=False,
            summary=f"Reviewable manual layout edit with {len(payload.operations)} operation(s).",
            created_at=now,
            updated_at=now,
        )
        db.add(candidate_version)
        db.flush()
        candidate_slide_by_base_id: dict[str, GeneratedSlide] = {}
        candidate_slide_id_by_base_id: dict[str, str] = {
            slide.id: generate_id("genslide") for slide in base_version.generated_slides
        }
        candidate_target_slide: GeneratedSlide | None = None
        for source_slide in sorted(base_version.generated_slides, key=lambda item: item.slide_number):
            is_target_slide = source_slide.id == base_slide.id
            render_schema = copy.deepcopy(candidate_render_schema if is_target_slide else source_slide.render_schema_json)
            candidate_slide = GeneratedSlide(
                id=candidate_slide_id_by_base_id[source_slide.id],
                deck_id=deck_id,
                design_version_id=candidate_version.id,
                generation_job_id=source_slide.generation_job_id,
                source_slide_id=source_slide.source_slide_id,
                slide_number=source_slide.slide_number,
                title=source_slide.title,
                status=source_slide.status,
                render_schema_json=render_schema,
                design_tokens_json=copy.deepcopy(source_slide.design_tokens_json),
                preview_image_url=None if is_target_slide else source_slide.preview_image_url,
                validation_status=(
                    "warning" if candidate_validation_warnings else "valid"
                ) if is_target_slide else source_slide.validation_status,
                created_at=now,
                updated_at=now,
            )
            db.add(candidate_slide)
            db.flush()
            candidate_slide_by_base_id[source_slide.id] = candidate_slide
            if is_target_slide:
                candidate_target_slide = candidate_slide

            source_elements = list(source_slide.elements)
            candidate_element_ids = {element.id: generate_id("gselem") for element in source_elements}
            candidate_elements_by_base_id: dict[str, GeneratedSlideElement] = {}
            for source_element in sorted(source_elements, key=lambda item: item.z_index):
                geometry = changed_geometry.get(
                    source_element.id,
                    {
                        "x": source_element.x,
                        "y": source_element.y,
                        "width": source_element.width,
                        "height": source_element.height,
                    },
                )
                candidate_element = GeneratedSlideElement(
                    id=candidate_element_ids[source_element.id],
                    generated_slide_id=candidate_slide.id,
                    deck_id=deck_id,
                    design_version_id=candidate_version.id,
                    source_slide_id=source_element.source_slide_id,
                    element_key=source_element.element_key,
                    element_type=source_element.element_type,
                    parent_element_id=None,
                    z_index=source_element.z_index,
                    x=geometry["x"],
                    y=geometry["y"],
                    width=geometry["width"],
                    height=geometry["height"],
                    rotation=source_element.rotation,
                    locked=source_element.locked,
                    visible=source_element.visible,
                    style_json=copy.deepcopy(source_element.style_json),
                    content_json=copy.deepcopy(source_element.content_json),
                    created_at=now,
                    updated_at=now,
                )
                db.add(candidate_element)
                candidate_elements_by_base_id[source_element.id] = candidate_element
                for source_version in sorted(source_element.versions, key=lambda item: item.version_number):
                    db.add(
                        GeneratedSlideElementVersion(
                            id=generate_id("gsever"),
                            element_id=candidate_element.id,
                            generated_slide_id=candidate_slide.id,
                            design_version_id=candidate_version.id,
                            version_number=source_version.version_number,
                            source=source_version.source,
                            status=source_version.status,
                            style_json=copy.deepcopy(source_version.style_json),
                            content_json=copy.deepcopy(source_version.content_json),
                            change_summary=source_version.change_summary,
                            created_at=source_version.created_at,
                        )
                    )
                if source_element.id in changed_geometry:
                    next_version_number = max(
                        (version.version_number for version in source_element.versions),
                        default=0,
                    ) + 1
                    db.add(
                        GeneratedSlideElementVersion(
                            id=generate_id("gsever"),
                            element_id=candidate_element.id,
                            generated_slide_id=candidate_slide.id,
                            design_version_id=candidate_version.id,
                            version_number=next_version_number,
                            source="manual_layout_edit",
                            status="candidate",
                            style_json=copy.deepcopy(candidate_element.style_json),
                            content_json=copy.deepcopy(candidate_element.content_json),
                            change_summary=f"Manual {' and '.join(changed_operation_types[source_element.id])}.",
                            created_at=now,
                        )
                    )

            db.flush()
            for source_element in source_elements:
                candidate_elements_by_base_id[source_element.id].parent_element_id = candidate_element_ids.get(
                    source_element.parent_element_id
                )

            source_code = _current_code_version(source_slide) or _latest_code_version(source_slide)
            code_version_id = generate_id("codever")
            render_schema_artifact = _write_render_schema_json_artifact(
                user_id=deck.user_id,
                deck_id=deck_id,
                design_version_id=candidate_version.id,
                generated_slide_id=candidate_slide.id,
                code_version_id=code_version_id,
                render_schema=render_schema,
            )
            code_json = {
                **(copy.deepcopy(source_code.code_json) if source_code and isinstance(source_code.code_json, dict) else {}),
                "renderer": "GeneratedSlideRenderer",
                "source": "manual_layout_edit" if is_target_slide else "manual_edit_full_design_clone",
                "lifecycle": "candidate",
                "state": "candidate",
                "manualEditJobId": manual_edit_job_id,
                "idempotencyKey": payload.idempotencyKey,
                "baseDesignVersionId": base_version.id,
                "baseGeneratedSlideId": source_slide.id,
                "baseCodeVersionId": source_code.id if source_code else None,
                "operationCount": len(payload.operations) if is_target_slide else 0,
                "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
                "renderSchemaStorageProvider": render_schema_artifact["storageProvider"],
                "renderSchemaStoragePath": render_schema_artifact["storagePath"],
                "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
            }
            code_metadata_artifact = _write_code_metadata_json_artifact(
                user_id=deck.user_id,
                deck_id=deck_id,
                design_version_id=candidate_version.id,
                generated_slide_id=candidate_slide.id,
                code_version_id=code_version_id,
                code_json=code_json,
            )
            code_json.update(
                {
                    "codeJsonHash": code_metadata_artifact["codeJsonHash"],
                    "codeJsonStorageProvider": code_metadata_artifact["storageProvider"],
                    "codeJsonStoragePath": code_metadata_artifact["storagePath"],
                    "bucketCodeJsonKey": code_metadata_artifact["storagePath"],
                }
            )
            code_version = GeneratedSlideCodeVersion(
                id=code_version_id,
                generated_slide_id=candidate_slide.id,
                version_number=1,
                code_kind=source_code.code_kind if source_code else "render_schema",
                schema_version=source_code.schema_version if source_code else "smart-deck-render-schema.v1",
                render_schema_json=copy.deepcopy(render_schema),
                code_json=code_json,
                bucket_render_schema_key=render_schema_artifact["storagePath"],
                bucket_code_key=code_metadata_artifact["storagePath"],
                bucket_thumbnail_key=None,
                status=(
                    "warning" if candidate_validation_warnings else "valid"
                ) if is_target_slide else (source_code.status if source_code else "valid"),
                validation_errors_json=(
                    [{"message": warning, "severity": "warning"} for warning in candidate_validation_warnings]
                    if is_target_slide
                    else (copy.deepcopy(source_code.validation_errors_json) if source_code else [])
                ),
                created_at=now,
            )
            db.add(code_version)
            candidate_slide.current_version_id = code_version.id
            _record_llm_artifact(
                db,
                deck_id=deck_id,
                artifact_type="generated_slide_render_schema",
                artifact_key=candidate_slide.id,
                summary=f"Manual edit candidate render schema for generated slide {candidate_slide.id}.",
                payload_json={
                    "generatedSlideId": candidate_slide.id,
                    "sourceSlideId": candidate_slide.source_slide_id,
                    "designVersionId": candidate_version.id,
                    "codeVersionId": code_version.id,
                    "renderSchema": render_schema,
                    "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
                    "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
                    "designTokens": candidate_slide.design_tokens_json,
                    "baseGeneratedSlideId": source_slide.id,
                },
                metrics_json={
                    "elementCount": len(render_schema.get("elements", [])),
                    "slideNumber": candidate_slide.slide_number,
                    "manuallyEdited": is_target_slide,
                },
            )
            _record_llm_artifact(
                db,
                deck_id=deck_id,
                artifact_type="generated_slide_code_version",
                artifact_key=code_version.id,
                summary=f"Manual edit candidate code version {code_version.id}.",
                payload_json={
                    "generatedSlideId": candidate_slide.id,
                    "codeVersionId": code_version.id,
                    "codeKind": code_version.code_kind,
                    "schemaVersion": code_version.schema_version,
                    "renderSchema": render_schema,
                    "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
                    "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
                    "codeJson": code_json,
                },
                metrics_json={"validationErrorCount": len(code_version.validation_errors_json or []), "versionNumber": 1},
            )

        if candidate_target_slide is None:
            raise ManualEditConflictError("generated_slide_mismatch", "The requested slide could not be cloned.")

        base_tokens = db.query(DesignToken).filter(DesignToken.design_version_id == base_version.id).all()
        for token in base_tokens:
            db.add(
                DesignToken(
                    id=generate_id("dstok"),
                    deck_id=deck_id,
                    design_version_id=candidate_version.id,
                    generated_slide_id=candidate_slide_id_by_base_id.get(token.generated_slide_id),
                    token_name=token.token_name,
                    token_value=token.token_value,
                    token_type=token.token_type,
                    source=token.source,
                    created_at=token.created_at,
                    updated_at=now,
                )
            )

        workspace, preference = _ensure_workspace_state(db, deck)
        workspace.status = "reviewing"
        workspace.active_design_version_id = candidate_version.id
        workspace.active_source_slide_id = payload.sourceSlideId
        workspace.active_generated_slide_id = candidate_target_slide.id
        preference.active_design_version_id = candidate_version.id
        preference.active_source_slide_id = payload.sourceSlideId
        preference.active_generated_slide_id = candidate_target_slide.id
        db.flush()
        _rewrite_design_version_manifest(db, candidate_version, "preview", "manual_edit")

        job_payload = {
            "id": manual_edit_job_id,
            "status": "completed",
            "baseDesignVersionId": payload.baseDesignVersionId,
            "baseGeneratedSlideId": generated_slide_id,
            "sourceSlideId": payload.sourceSlideId,
            "candidateDesignVersionId": candidate_version.id,
            "candidateGeneratedSlideId": candidate_target_slide.id,
            "idempotencyKey": payload.idempotencyKey,
            "operationCount": len(payload.operations),
            "createdAt": _iso(now) or "",
        }
        _record_llm_artifact(
            db,
            deck_id=deck_id,
            artifact_type="smart_deck_manual_edit_job",
            artifact_key=payload.idempotencyKey,
            summary=f"Idempotent manual edit job {manual_edit_job_id}.",
            payload_json={**job_payload, "requestFingerprint": request_fingerprint},
            metrics_json={"operationCount": len(payload.operations), "slideCount": len(candidate_slide_by_base_id)},
            store_payload=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    reloaded_version = (
        db.query(DesignVersion)
        .options(
            selectinload(DesignVersion.generation_job),
            selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions),
            selectinload(DesignVersion.generated_slides)
            .selectinload(GeneratedSlide.elements)
            .selectinload(GeneratedSlideElement.versions),
        )
        .filter(DesignVersion.id == candidate_version.id, DesignVersion.deck_id == deck_id)
        .one()
    )
    reloaded_slide = next(slide for slide in reloaded_version.generated_slides if slide.id == job_payload["candidateGeneratedSlideId"])
    return job_payload, _map_design_version(reloaded_version), _map_generated_slide(reloaded_slide)


def update_smart_deck_selection(db: Session, deck_id: str, payload) -> dict | None:
    # Compatibility adapter: session-state fields are forwarded without
    # materialising omitted values as None, then committed once by the owner.
    return update_smart_deck_preferences(
        db,
        deck_id,
        UpdateSmartDeckPreferenceInput(**payload.model_dump(exclude_unset=True)),
    )


def create_element_variation_job(db: Session, deck_id: str, generated_slide_id: str, element_id: str, payload) -> tuple[dict, dict, dict, dict, dict, dict] | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    workspace, preference = _ensure_workspace_state(db, deck)
    slide = (
        db.query(GeneratedSlide)
        .options(
            selectinload(GeneratedSlide.code_versions),
            selectinload(GeneratedSlide.elements).selectinload(GeneratedSlideElement.versions),
            selectinload(GeneratedSlide.source_slide).selectinload(DeckSlide.blocks),
        )
        .filter(GeneratedSlide.deck_id == deck_id, GeneratedSlide.id == generated_slide_id)
        .first()
    )
    if slide is None:
        raise ValueError("generatedSlideId does not belong to this deck.")
    element = next((item for item in slide.elements if item.id == element_id), None)
    if element is None:
        raise ValueError("elementId does not belong to generatedSlideId.")

    base_version = _latest_element_version(element)
    normalized_instruction = payload.instruction.strip()
    replay = _load_completed_element_variation_replay(
        db,
        deck_id=deck.id,
        workspace_id=workspace.id,
        base_element_version_id=base_version.id if base_version else None,
        instruction=normalized_instruction,
        variation_count=payload.variationCount,
    )
    if replay is not None:
        return replay
    base_render_schema = (_current_code_version(slide) or _latest_code_version(slide))
    base_render_schema_json = base_render_schema.render_schema_json if base_render_schema else slide.render_schema_json
    audience_profile = _load_audience_profile(db, deck.audience)
    audience_context = build_vc_prompt_context(
        audience=deck.audience,
        purpose=deck.purpose,
        user_role=deck.workspace.user.role if deck.workspace and deck.workspace.user else None,
        audience_profile=audience_profile,
        deck_metadata=deck.metadata_json,
        brand_evidence=deck.brand_profile.raw_evidence_json if deck.brand_profile else None,
        slide_texts=[slide.source_slide.raw_text if slide.source_slide else ""],
    )
    archetype_context = build_slide_archetype_context(
        audience=deck.audience,
        purpose=deck.purpose,
        slide_texts=[slide.source_slide.raw_text if slide.source_slide else ""],
        slide_titles=[slide.source_slide.title if slide.source_slide else ""],
        slide_roles=[slide.source_slide.role if slide.source_slide else ""],
    )
    retrieval_context = build_element_variation_retrieval_context(
        deck=deck,
        generated_slide=slide,
        element=element,
        instruction=normalized_instruction,
        design_tokens=build_brand_design_tokens(deck.brand_profile),
        audience_context=audience_context,
        archetype_context=archetype_context,
    )
    now = datetime.utcnow()
    preview_version = DesignVersion(
        id=generate_id("designver"),
        deck_id=deck.id,
        generation_job_id=slide.generation_job_id,
        name=f"Element refinement for {slide.title}"[:255],
        status="draft",
        is_active=False,
        summary=f"Candidate element refinement for {slide.title}.",
        created_at=now,
        updated_at=now,
    )
    db.add(preview_version)
    db.flush()

    job = ElementVariationJob(
        id=generate_id("elvar"),
        deck_id=deck.id,
        workspace_id=workspace.id,
        generated_slide_id=slide.id,
        element_id=element.id,
        base_element_version_id=base_version.id if base_version else None,
        user_id=deck.user_id,
        instruction=normalized_instruction,
        variation_count=payload.variationCount,
        retrieval_context_json=retrieval_context,
        status="running",
        started_at=now,
    )
    db.add(job)
    db.flush()

    try:
        content, style, position = _generate_element_variation(
            db,
            deck,
            element,
            instruction=normalized_instruction,
            retrieval_context=retrieval_context,
            render_schema_json=base_render_schema_json,
        )
        candidate_render_schema = _render_schema_with_element_variation(
            base_render_schema_json,
            element,
            content,
            style,
            position,
        )
        candidate_slide = GeneratedSlide(
            id=generate_id("genslide"),
            deck_id=deck.id,
            design_version_id=preview_version.id,
            generation_job_id=slide.generation_job_id,
            source_slide_id=slide.source_slide_id,
            slide_number=slide.slide_number,
            title=slide.title,
            status="ready",
            render_schema_json=candidate_render_schema,
            design_tokens_json=slide.design_tokens_json,
            preview_image_url=slide.preview_image_url,
            validation_status="valid",
        )
        db.add(candidate_slide)
        db.flush()

        selected_candidate_element: GeneratedSlideElement | None = None
        next_version: GeneratedSlideElementVersion | None = None
        for source_element in sorted(slide.elements, key=lambda item: item.z_index):
            is_selected = source_element.id == element.id
            candidate_element = GeneratedSlideElement(
                id=generate_id("gselem"),
                generated_slide_id=candidate_slide.id,
                deck_id=deck.id,
                design_version_id=preview_version.id,
                source_slide_id=source_element.source_slide_id,
                element_key=source_element.element_key,
                element_type=source_element.element_type,
                parent_element_id=source_element.parent_element_id,
                z_index=source_element.z_index,
                x=int(position.get("x", source_element.x)) if is_selected else source_element.x,
                y=int(position.get("y", source_element.y)) if is_selected else source_element.y,
                width=int(position.get("width", source_element.width)) if is_selected else source_element.width,
                height=int(position.get("height", source_element.height)) if is_selected else source_element.height,
                rotation=source_element.rotation,
                locked=source_element.locked,
                visible=source_element.visible,
                style_json=style if is_selected else source_element.style_json,
                content_json=content if is_selected else source_element.content_json,
            )
            db.add(candidate_element)
            db.flush()
            element_version = GeneratedSlideElementVersion(
                id=generate_id("gsever"),
                element_id=candidate_element.id,
                generated_slide_id=candidate_slide.id,
                design_version_id=preview_version.id,
                version_number=1,
                source="element_variation_job" if is_selected else "copied_from_current",
                status="candidate" if is_selected else "active",
                style_json=candidate_element.style_json,
                content_json=candidate_element.content_json,
                change_summary=f"Variation from instruction: {normalized_instruction}" if is_selected else "Copied from current slide.",
            )
            db.add(element_version)
            if is_selected:
                selected_candidate_element = candidate_element
                next_version = element_version

        if selected_candidate_element is None or next_version is None:
            raise ValueError("Selected element could not be cloned into preview design version.")

        code_version_id = generate_id("codever")
        render_schema_artifact = _write_render_schema_json_artifact(
            user_id=deck.user_id,
            deck_id=deck.id,
            design_version_id=preview_version.id,
            generated_slide_id=candidate_slide.id,
            code_version_id=code_version_id,
            render_schema=candidate_render_schema,
        )
        code_json = {
            "renderer": "GeneratedSlideRenderer",
            "source": "element_variation_job",
            "lifecycle": "candidate",
            "state": "candidate",
            "baseGeneratedSlideId": slide.id,
            "baseCodeVersionId": base_render_schema.id if base_render_schema else None,
            "baseElementId": element.id,
            "candidateElementId": selected_candidate_element.id,
            "elementVariationJobId": job.id,
            "renderSchemaHash": render_schema_artifact["renderSchemaHash"],
            "renderSchemaStorageProvider": render_schema_artifact["storageProvider"],
            "renderSchemaStoragePath": render_schema_artifact["storagePath"],
            "bucketRenderSchemaKey": render_schema_artifact["storagePath"],
        }
        code_metadata_artifact = _write_code_metadata_json_artifact(
            user_id=deck.user_id,
            deck_id=deck.id,
            design_version_id=preview_version.id,
            generated_slide_id=candidate_slide.id,
            code_version_id=code_version_id,
            code_json=code_json,
        )
        code_version = GeneratedSlideCodeVersion(
            id=code_version_id,
            generated_slide_id=candidate_slide.id,
            version_number=1,
            code_kind="render_schema",
            schema_version="smart-deck-render-schema.v1",
            render_schema_json=candidate_render_schema,
            code_json={
                **code_json,
                "codeJsonHash": code_metadata_artifact["codeJsonHash"],
                "codeJsonStorageProvider": code_metadata_artifact["storageProvider"],
                "codeJsonStoragePath": code_metadata_artifact["storagePath"],
                "bucketCodeJsonKey": code_metadata_artifact["storagePath"],
            },
            bucket_render_schema_key=render_schema_artifact["storagePath"],
            bucket_code_key=code_metadata_artifact["storagePath"],
            bucket_thumbnail_key=None,
            status="valid",
            validation_errors_json=[],
        )
        db.add(code_version)
        candidate_slide.current_version_id = code_version.id
        _record_design_tokens(
            db,
            deck_id=deck.id,
            design_version_id=preview_version.id,
            generated_slide_id=candidate_slide.id,
        )
        job.generated_slide_id = candidate_slide.id
        job.element_id = selected_candidate_element.id
        job.status = "completed"
        job.output_element_version_id = next_version.id
        job.completed_at = datetime.utcnow()
        workspace.status = "reviewing"
        workspace.active_design_version_id = preview_version.id
        workspace.active_generated_slide_id = candidate_slide.id
        workspace.selected_element_id = selected_candidate_element.id
        preference.active_design_version_id = preview_version.id
        preference.active_generated_slide_id = candidate_slide.id
        preference.selected_element_id = selected_candidate_element.id
        db.flush()
        _rewrite_design_version_manifest(db, preview_version, "preview", "element_variation")
        db.commit()
    except Exception as exc:
        job.status = "failed"
        job.error_message = _safe_generation_failure_message(exc)
        job.completed_at = datetime.utcnow()
        db.commit()
        raise

    reloaded_element = (
        db.query(GeneratedSlideElement)
        .options(selectinload(GeneratedSlideElement.versions))
        .filter(GeneratedSlideElement.id == job.element_id)
        .one()
    )
    reloaded_job = db.query(ElementVariationJob).filter(ElementVariationJob.id == job.id).one()
    reloaded_version = (
        db.query(GeneratedSlideElementVersion)
        .filter(GeneratedSlideElementVersion.id == job.output_element_version_id)
        .one()
    )
    reloaded_slide = (
        db.query(GeneratedSlide)
        .options(selectinload(GeneratedSlide.code_versions), selectinload(GeneratedSlide.elements).selectinload(GeneratedSlideElement.versions))
        .filter(GeneratedSlide.id == reloaded_job.generated_slide_id)
        .one()
    )
    reloaded_design_version = (
        db.query(DesignVersion)
        .options(selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions))
        .filter(DesignVersion.id == reloaded_slide.design_version_id)
        .one()
    )
    workspace_payload = get_smart_deck_workspace(db, deck_id)
    return (
        _map_variation_job(reloaded_job),
        _map_generated_slide_element(reloaded_element),
        _map_generated_slide_element_version(reloaded_version),
        _map_generated_slide(reloaded_slide),
        _map_design_version(reloaded_design_version),
        workspace_payload,
    )


def apply_element_version(db: Session, deck_id: str, generated_slide_id: str, element_id: str, version_id: str) -> tuple[dict, dict, dict] | None:
    slide = (
        db.query(GeneratedSlide)
        .options(selectinload(GeneratedSlide.elements).selectinload(GeneratedSlideElement.versions))
        .filter(GeneratedSlide.deck_id == deck_id, GeneratedSlide.id == generated_slide_id)
        .first()
    )
    if slide is None:
        return None
    element = next((item for item in slide.elements if item.id == element_id), None)
    if element is None:
        raise ValueError("elementId does not belong to generatedSlideId.")
    version = next((item for item in element.versions if item.id == version_id), None)
    if version is None:
        raise ValueError("versionId does not belong to elementId.")

    element.content_json = version.content_json
    element.style_json = version.style_json
    position = (version.content_json or {}).get("position") if isinstance(version.content_json, dict) else None
    if isinstance(position, dict):
        element.x = int(position.get("x", element.x))
        element.y = int(position.get("y", element.y))
        element.width = int(position.get("width", element.width))
        element.height = int(position.get("height", element.height))
    version.status = "active"
    for candidate in element.versions:
        if candidate.id != version.id and candidate.status == "active":
            candidate.status = "superseded"
    _apply_element_to_render_schema(slide, element)
    latest_code = sorted(slide.code_versions, key=lambda item: item.version_number, reverse=True)[0] if slide.code_versions else None
    if latest_code is not None:
        latest_code.render_schema_json = slide.render_schema_json
    from app.services.platform.shell.shell_service import record_accepted_deck_version

    record_accepted_deck_version(
        db,
        deck_id,
        source_surface="smart_edit_element",
        source_artifact_id=version.id,
        design_version_id=slide.design_version_id,
        changed_slide_ids=[slide.source_slide_id] if slide.source_slide_id else [],
        change_summary=f"Accepted element change on {slide.title}.",
    )
    db.commit()
    return _map_generated_slide_element(element), _map_generated_slide_element_version(version), _map_generated_slide(slide)


def create_smart_deck_message(db: Session, deck_id: str, payload: CreateSmartDeckMessageInput) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    workspace, _ = _ensure_workspace_state(db, deck)
    source_ids = {slide.id for slide in deck.slides}
    missing_ids = [slide_id for slide_id in payload.selectedSourceSlideIds if slide_id not in source_ids]
    if missing_ids:
        raise ValueError(f"Selected source slides do not belong to this deck: {', '.join(missing_ids)}")
    if payload.generationJobId is not None:
        job = db.query(GenerationJob).filter(GenerationJob.deck_id == deck_id, GenerationJob.id == payload.generationJobId).first()
        if job is None:
            raise ValueError("generationJobId does not belong to this deck.")
    message = _record_smart_deck_message(
        db,
        workspace_id=workspace.id,
        deck_id=deck.id,
        role=payload.role,
        content=payload.content,
        generation_job_id=payload.generationJobId,
        selected_source_slide_ids=payload.selectedSourceSlideIds,
        metadata_json=payload.metadata,
    )
    db.commit()
    return _map_message(message)


def _assistant_slide_summary(slide: DeckSlide) -> dict:
    blocks = sorted(slide.blocks, key=lambda item: item.block_index)
    return {
        "id": slide.id,
        "slideNumber": _source_slide_number(slide),
        "title": slide.title,
        "role": slide.semantic_slide_type or slide.role,
        "summary": _fit_text(slide.summary or slide.raw_text or "", 1200),
        "metricSignals": [
            metric
            for metric in _fit_text(slide.raw_text or "", 1600).replace("\n", " ").split(" ")
            if any(char.isdigit() for char in metric)
        ][:12],
        "blocks": [
            {
                "id": block.id,
                "type": block.block_type,
                "text": _fit_text(block.raw_text or block.normalized_text or "", 240),
            }
            for block in blocks[:10]
        ],
    }


def _assistant_artifact_payloads(deck: Deck) -> dict:
    artifacts: dict[str, dict] = {}
    for artifact in deck.llm_artifacts:
        if artifact.status != "ready" or not artifact.payload_json:
            continue
        if artifact.artifact_type in {"deck_profile", "slide_catalog", "prompt_context"}:
            artifacts[artifact.artifact_type] = load_deck_llm_artifact_payload(artifact)
    prior_insights = [
        {
            "id": artifact.id,
            "artifactKey": artifact.artifact_key,
            "summary": artifact.summary,
            "payload": load_deck_llm_artifact_payload(artifact),
            "createdAt": _iso(artifact.created_at),
        }
        for artifact in sorted(deck.llm_artifacts, key=lambda item: item.created_at, reverse=True)
        if artifact.artifact_type == SMART_DECK_ASSISTANT_ARTIFACT_TYPE and artifact.status == "ready"
    ][:5]
    if prior_insights:
        artifacts["priorAssistantRuns"] = {"runs": prior_insights}
    return artifacts


def _assistant_scope_slides(
    deck: Deck,
    workspace: SmartDeckWorkspace,
    preference: SmartDeckPreference,
    payload: CreateSmartDeckAssistantRunInput,
) -> list[DeckSlide]:
    slide_lookup = {slide.id: slide for slide in deck.slides}
    if payload.scope == "whole_deck":
        return sorted(deck.slides, key=lambda item: (item.slide_index, item.id))

    if payload.scope == "selected_slides":
        selected_ids = payload.selectedSourceSlideIds
    else:
        selected_ids = [
            payload.activeSourceSlideId
            or preference.active_source_slide_id
            or workspace.active_source_slide_id
            or (preference.selected_source_slide_ids_json or [None])[0]
        ]

    missing_ids = [slide_id for slide_id in selected_ids if slide_id and slide_id not in slide_lookup]
    if missing_ids:
        raise ValueError(f"Selected source slides do not belong to this deck: {', '.join(missing_ids)}")

    selected = [slide_lookup[slide_id] for slide_id in selected_ids if slide_id in slide_lookup]
    selected.sort(key=lambda item: (item.slide_index, item.id))
    return selected


def _build_assistant_context(
    deck: Deck,
    selected_slides: list[DeckSlide],
    payload: CreateSmartDeckAssistantRunInput,
    audience_profile: dict | None = None,
) -> dict:
    session = deck._sa_instance_state.session
    canonical_deck_intelligence = build_canonical_deck_intelligence(session, deck.id) if session is not None else None
    intent = ASSISTANT_INTENTS[payload.intentType]
    active_design_version = next((version for version in deck.design_versions if version.is_active), None)
    brand_profile = deck.brand_profile
    brand_context = build_brand_llm_context(brand_profile)
    workspace = deck.workspace
    workspace_user = workspace.user if workspace else None
    user_profile = workspace_user.profile if workspace_user else None
    company_profile = workspace.company_profiles[0] if workspace and workspace.company_profiles else None
    target_audience = payload.audience or deck.audience
    audience_context = build_vc_prompt_context(
        audience=target_audience,
        purpose=deck.purpose,
        user_role=workspace_user.role if workspace_user else None,
        audience_profile=audience_profile,
        deck_metadata=deck.metadata_json,
        brand_evidence=brand_profile.raw_evidence_json if brand_profile else None,
        slide_texts=[slide.raw_text or "" for slide in selected_slides],
    )
    archetype_context = build_slide_archetype_context(
        audience=target_audience,
        purpose=deck.purpose,
        slide_texts=[slide.raw_text or "" for slide in selected_slides],
        slide_titles=[slide.title or "" for slide in selected_slides],
        slide_roles=[slide.role or "" for slide in selected_slides],
    )
    runtime_capabilities = build_smart_deck_runtime_capabilities()
    detected_subjects = [
        {
            **detect_smart_deck_subject(slide.title, slide.raw_text, [item for item in [slide.role, slide.semantic_slide_type] if item]),
            "slideId": slide.id,
            "slideTitle": slide.title,
        }
        for slide in selected_slides
    ]
    return {
        "schemaVersion": "smart-deck-assistant-context.v1",
        "intent": {
            "type": payload.intentType,
            "label": intent["label"],
            "template": intent["template"],
        },
        "scope": payload.scope,
        "instruction": payload.instruction,
        "audience": target_audience,
        "audienceContext": audience_context,
        "canonicalDeckIntelligence": canonical_deck_intelligence,
        "subjectContext": {
            "deckType": "vc_fund_pitch" if "fund" in (target_audience or "").lower() else "startup_pitch",
            "selectedSubject": payload.intentType,
            "detectedSubjects": detected_subjects,
            "actionId": payload.intentType,
            "actionPrompt": intent["template"],
            "userPrompt": payload.instruction,
            "latestBatchId": active_design_version.id if active_design_version else None,
        },
        "slideArchetypeContext": archetype_context,
        "runtimeCapabilities": runtime_capabilities,
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "status": deck.status,
            "slideCount": len(deck.slides),
        },
        "workspace": {
            "id": workspace.id if workspace else None,
            "name": workspace.name if workspace else None,
        },
        "user": {
            "id": workspace_user.id if workspace_user else None,
            "role": workspace_user.role if workspace_user else None,
            "displayName": user_profile.display_name if user_profile else (workspace_user.name if workspace_user else None),
            "headline": user_profile.headline if user_profile else None,
            "jobTitle": user_profile.job_title if user_profile else None,
            "companyName": user_profile.company_name if user_profile else None,
        },
        "company": {
            "canonicalName": company_profile.canonical_name if company_profile else None,
            "websiteUrl": company_profile.website_url if company_profile else None,
            "inferredStage": company_profile.inferred_stage if company_profile else None,
            "founderName": company_profile.founder_name if company_profile else None,
            "teamSummary": company_profile.team_summary if company_profile else None,
        },
        "brand": {
            **brand_context,
            "industry": (brand_profile.raw_evidence_json or {}).get("industry") if brand_profile else None,
        },
        "selectedSlides": [_assistant_slide_summary(slide) for slide in selected_slides],
        "activeDesignVersion": {
            "id": active_design_version.id,
            "name": active_design_version.name,
            "status": active_design_version.status,
            "generatedSlideCount": len(active_design_version.generated_slides),
        }
        if active_design_version
        else None,
        "artifacts": _assistant_artifact_payloads(deck),
        "rules": [
            "Use saved deck, slide, artifact, brand, and generated-version context before making recommendations.",
            "Use audienceContext.matchedPersona to prioritize the right VC decision criteria and tone.",
            "Use subjectContext to identify the slide topic and apply the corresponding corpus-backed logic.",
            "Use slideArchetypeContext to understand the slide's narrative role and adjacency in the pitch sequence.",
            "Use slideArchetypeContext knowledge modules for deck recipes, diagnostics, generation contracts, writing rules, hallucination constraints, and quality rubrics.",
            "Use runtimeCapabilities from the architecture runtime pack for task routing, guardrails, due diligence gaps, review surfaces, and AI change safety.",
            "Use brand.colors, brand.palette, and brand.tokens when recommending deck visuals, refinements, or redesign prompts.",
            "Do not invent external market facts; mark assumptions and missing evidence when the deck lacks support.",
            "Call out whether each recommendation helps market conviction, traction proof, unit economics, competition, team credibility, raise logic, or risk reduction.",
            "Return structured JSON only.",
        ],
    }


def _build_anthropic_assistant_prompt(context: dict) -> str:
    context = {
        **context,
        "promptPackage": {
            "name": "smart_deck",
            "version": load_prompt_package("smart_deck")["version"],
            "section": "assistant",
        },
    }
    return build_prompt_package_text(
        "smart_deck",
        "assistant",
        context_label="Assistant context",
        context=context,
        output_schema=SmartDeckAssistantInsightResponse.model_json_schema(),
    )


def _call_anthropic_assistant_insight(context: dict, model: str, api_key: str) -> dict:
    response_payload = call_anthropic_message(
        api_key=api_key,
        model=model,
        max_tokens=min(settings.anthropic_max_tokens, SMART_DECK_ASSISTANT_MAX_OUTPUT_TOKENS),
        system="You output only valid JSON for a backend-validated deck assistant insight.",
        user=_build_anthropic_assistant_prompt(context),
        timeout=settings.anthropic_timeout_seconds,
    )
    return _extract_json_payload(extract_anthropic_text(response_payload))


def _call_openai_assistant_insight(context: dict, model: str, api_key: str) -> dict:
    response_payload = call_openai_response(
        api_key=api_key,
        model=model,
        system="You output only valid JSON for a backend-validated deck assistant insight.",
        user=_build_anthropic_assistant_prompt(context),
        timeout=settings.openai_timeout_seconds,
        max_output_tokens=SMART_DECK_ASSISTANT_MAX_OUTPUT_TOKENS,
        response_format={"type": "json_object"},
    )
    return _extract_json_payload(extract_openai_text(response_payload))


def _call_openrouter_assistant_insight(context: dict, model: str, api_key: str) -> dict:
    response_payload = call_openrouter_chat_completion(
        api_key=api_key,
        model=model,
        system="You output only valid JSON for a backend-validated deck assistant insight.",
        user=_build_anthropic_assistant_prompt(context),
        timeout=60,
        response_format={"type": "json_object"},
    )
    return _extract_json_payload(extract_openrouter_text(response_payload))


def _call_dashscope_assistant_insight(context: dict, model: str, api_key: str) -> dict:
    response_payload = call_dashscope_chat_completion(
        api_key=api_key,
        model=model,
        system="You output only valid JSON for a backend-validated deck assistant insight.",
        user=_build_anthropic_assistant_prompt(context),
        timeout=min(settings.effective_qwen_timeout, 60),
        response_format={"type": "json_object"},
    )
    return _extract_json_payload(extract_dashscope_text(response_payload))


_ASSISTANT_INSIGHT_PROVIDERS: dict[str, object] = {
    "anthropic": _call_anthropic_assistant_insight,
    "openai": _call_openai_assistant_insight,
    "openrouter": _call_openrouter_assistant_insight,
    "dashscope": _call_dashscope_assistant_insight,
}


def _generate_assistant_insight(provider: str, context: dict, model: str | None, api_key: str | None) -> dict:
    fn = _ASSISTANT_INSIGHT_PROVIDERS.get(provider)  # type: ignore[assignment]
    if fn is None:
        raise SmartDeckProviderUnavailableError("AI generation provider is unavailable.")
    if not model or not api_key:
        raise SmartDeckProviderUnavailableError("AI generation provider credentials are missing.")
    return fn(context, model, api_key)  # type: ignore[no-any-return]


def _validate_assistant_insight(raw: dict, fallback_action: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Assistant response must be a JSON object.")
    confidence = raw.get("confidence") if raw.get("confidence") in {"low", "medium", "high"} else "medium"
    action = raw.get("recommendedAction") if raw.get("recommendedAction") in {"save_insight", "add_to_slide", "create_version", "none"} else fallback_action
    summary = _fit_text(str(raw.get("summary") or ""), 1200)
    if not summary:
        raise ValueError("Assistant response did not include a summary.")
    return {
        "title": _fit_text(str(raw.get("title") or "Assistant insight"), 140),
        "summary": summary,
        "content": raw.get("content") if isinstance(raw.get("content"), dict) else {},
        "confidence": confidence,
        "assumptions": [str(item)[:500] for item in raw.get("assumptions", []) if str(item).strip()][:12],
        "missingEvidence": [str(item)[:500] for item in raw.get("missingEvidence", []) if str(item).strip()][:12],
        "suggestedSlideUpdate": _fit_text(str(raw["suggestedSlideUpdate"]), 1000)
        if raw.get("suggestedSlideUpdate") is not None
        else None,
        "recommendedAction": action,
    }


def create_smart_deck_assistant_run(
    db: Session,
    deck_id: str,
    payload: CreateSmartDeckAssistantRunInput,
) -> dict | None:
    deck = _load_deck(db, deck_id)
    if deck is None:
        return None
    workspace, preference = _ensure_workspace_state(db, deck)
    selected_slides = _assistant_scope_slides(deck, workspace, preference, payload)
    if not selected_slides:
        raise ValueError("Assistant run requires at least one source slide in scope.")

    run_id = generate_id("sdasst")
    claude_config = get_generation_provider_config(
        db,
        deck,
        preference.preferred_model,
        strict=True,
        use_case="smart_deck",
    )
    provider = claude_config["provider"]
    resolved_model = claude_config["model"]
    audience_profile = _load_audience_profile(db, payload.audience or deck.audience)
    context = _build_assistant_context(deck, selected_slides, payload, audience_profile)
    selected_slide_ids = [slide.id for slide in selected_slides]

    user_message = _record_smart_deck_message(
        db,
        workspace_id=workspace.id,
        deck_id=deck.id,
        role="user",
        content=payload.instruction,
        selected_source_slide_ids=selected_slide_ids,
        metadata_json={
            "assistantRunId": run_id,
            "intentType": payload.intentType,
            "scope": payload.scope,
            "audience": payload.audience,
        },
    )
    db.flush()

    raw_insight = _generate_assistant_insight(provider, context, resolved_model, claude_config.get("apiKey"))
    insight = _validate_assistant_insight(raw_insight, ASSISTANT_INTENTS[payload.intentType]["action"])
    assistant_message = _record_smart_deck_message(
        db,
        workspace_id=workspace.id,
        deck_id=deck.id,
        role="assistant",
        content=insight["summary"],
        selected_source_slide_ids=selected_slide_ids,
        metadata_json={
            "assistantRunId": run_id,
            "intentType": payload.intentType,
            "scope": payload.scope,
            "provider": provider,
            "model": resolved_model if provider in {"anthropic", "openai", "openrouter", "dashscope"} else None,
            "credentialSource": claude_config.get("source"),
            "insight": insight,
            "userMessageId": user_message.id,
        },
    )
    artifact_payload = {
        "runId": run_id,
        "intentType": payload.intentType,
        "scope": payload.scope,
        "outputType": ASSISTANT_OUTPUT_TYPES.get(payload.intentType, "insight"),
        "provider": provider,
        "model": resolved_model if provider in {"anthropic", "openai", "openrouter", "dashscope"} else None,
        "credentialSource": claude_config.get("source"),
        "inputContext": context,
        "insight": insight,
        "saveInsight": payload.saveInsight,
        "messageIds": {
            "user": user_message.id,
            "assistant": assistant_message.id,
        },
    }
    artifact_pointer = _write_json_artifact_to_storage(
        db,
        deck.id,
        run_id,
        artifact_payload,
    )
    artifact = _record_llm_artifact(
        db,
        deck_id=deck.id,
        artifact_type=SMART_DECK_ASSISTANT_ARTIFACT_TYPE,
        artifact_key=run_id,
        summary=insight["summary"],
        payload_json=artifact_pointer,
        metrics_json={
            "selectedSlideCount": len(selected_slides),
            "instructionLength": len(payload.instruction),
            "missingEvidenceCount": len(insight["missingEvidence"]),
            "artifactStoragePath": artifact_pointer["storagePath"],
            "artifactStorageProvider": artifact_pointer["storageProvider"],
        },
        store_payload=False,
    )
    db.commit()
    db.refresh(assistant_message)
    db.refresh(artifact)
    return {
        "runId": run_id,
        "deckId": deck.id,
        "intentType": payload.intentType,
        "scope": payload.scope,
        "status": "completed",
        "outputType": ASSISTANT_OUTPUT_TYPES.get(payload.intentType, "insight"),
        "provider": provider,
        "model": resolved_model if provider in {"anthropic", "openai", "openrouter", "dashscope"} else None,
        "inputContext": context,
        "insight": insight,
        "assistantMessage": _map_message(assistant_message),
        "savedArtifactId": artifact.id,
    }


def list_design_tokens(db: Session, deck_id: str) -> dict | None:
    from app.services.visualizer.slide_read_model import list_design_tokens as _impl
    return _impl(db, deck_id)
