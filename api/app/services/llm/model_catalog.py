from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProviderSlug = Literal["openai", "openrouter", "claude", "qwen"]
ModelCategory = Literal["chat", "reasoning", "embedding", "vision"]


@dataclass(frozen=True)
class ModelCapability:
    id: str
    label: str
    provider: ProviderSlug
    category: ModelCategory
    supports_chat: bool = False
    supports_reasoning: bool = False
    supports_embeddings: bool = False
    supports_vision: bool = False
    default_for_category: bool = False
    discovery_supported: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class ProviderCapability:
    id: ProviderSlug
    label: str
    api_key_placeholder: str
    enabled: bool
    discovery_supported: bool
    chat_default_model: str | None = None
    reasoning_default_model: str | None = None
    embedding_default_model: str | None = None
    vision_default_model: str | None = None


PROVIDER_CAPABILITIES: dict[ProviderSlug, ProviderCapability] = {
    "qwen": ProviderCapability(
        id="qwen",
        label="Qwen — Alibaba Cloud",
        api_key_placeholder="sk-...",
        enabled=False,
        discovery_supported=True,
        chat_default_model="qwen-plus-2025-07-28",
        reasoning_default_model="qwen-plus-2025-07-28",
        embedding_default_model="text-embedding-v3",
        vision_default_model="qwen-vl-ocr-2025-11-20",
    ),
    "openai": ProviderCapability(
        id="openai",
        label="OpenAI",
        api_key_placeholder="sk-...",
        enabled=True,
        discovery_supported=False,
        chat_default_model="gpt-5",
        reasoning_default_model="gpt-5",
        embedding_default_model="text-embedding-3-small",
        vision_default_model="gpt-5",
    ),
    "openrouter": ProviderCapability(
        id="openrouter",
        label="OpenRouter",
        api_key_placeholder="sk-or-...",
        enabled=False,
        discovery_supported=False,
    ),
    "claude": ProviderCapability(
        id="claude",
        label="Claude",
        api_key_placeholder="sk-ant-...",
        enabled=False,
        discovery_supported=False,
    ),
}


MODEL_CAPABILITIES: tuple[ModelCapability, ...] = (
    ModelCapability(
        id="gpt-5",
        label="OpenAI · GPT-5",
        provider="openai",
        category="chat",
        supports_chat=True,
        supports_reasoning=True,
        supports_vision=True,
        default_for_category=True,
    ),
    ModelCapability(
        id="text-embedding-3-small",
        label="OpenAI · Text Embedding 3 Small",
        provider="openai",
        category="embedding",
        supports_embeddings=True,
        default_for_category=True,
    ),
    ModelCapability(
        id="qwen-plus-2025-07-28",
        label="Qwen · Plus",
        provider="qwen",
        category="chat",
        supports_chat=True,
        supports_reasoning=True,
        default_for_category=True,
    ),
    ModelCapability(
        id="qwen-max",
        label="Qwen · Max",
        provider="qwen",
        category="reasoning",
        supports_chat=True,
        supports_reasoning=True,
    ),
    ModelCapability(
        id="text-embedding-v3",
        label="Qwen · Text Embedding v3",
        provider="qwen",
        category="embedding",
        supports_embeddings=True,
        default_for_category=True,
    ),
    ModelCapability(
        id="qwen-vl-ocr-2025-11-20",
        label="Qwen · Vision OCR",
        provider="qwen",
        category="vision",
        supports_vision=True,
        default_for_category=True,
    ),
)


def list_provider_capabilities() -> list[ProviderCapability]:
    return list(PROVIDER_CAPABILITIES.values())


def list_models_for_provider(provider: ProviderSlug, *, include_disabled: bool = False) -> list[ModelCapability]:
    return [
        model
        for model in MODEL_CAPABILITIES
        if model.provider == provider and (include_disabled or model.enabled)
    ]


def list_models_for_category(provider: ProviderSlug, category: ModelCategory) -> list[ModelCapability]:
    capability_name = {
        "chat": "supports_chat",
        "reasoning": "supports_reasoning",
        "embedding": "supports_embeddings",
        "vision": "supports_vision",
    }[category]
    return [model for model in list_models_for_provider(provider) if getattr(model, capability_name)]


def get_model_capability(model_id: str) -> ModelCapability | None:
    for model in MODEL_CAPABILITIES:
        if model.id == model_id:
            return model
    return None


def get_provider_capability(provider: ProviderSlug) -> ProviderCapability:
    return PROVIDER_CAPABILITIES[provider]


def get_default_model(provider: ProviderSlug, category: ModelCategory) -> str | None:
    provider_capability = get_provider_capability(provider)
    if category == "chat":
        return provider_capability.chat_default_model
    if category == "reasoning":
        return provider_capability.reasoning_default_model
    if category == "embedding":
        return provider_capability.embedding_default_model
    if category == "vision":
        return provider_capability.vision_default_model
    return None


def validate_model_for_category(provider: ProviderSlug, model_id: str | None, category: ModelCategory) -> str | None:
    if not model_id:
        return get_default_model(provider, category)
    model = get_model_capability(model_id)
    capability_name = {
        "chat": "supports_chat",
        "reasoning": "supports_reasoning",
        "embedding": "supports_embeddings",
        "vision": "supports_vision",
    }[category]
    if model is None or model.provider != provider or not getattr(model, capability_name):
        raise ValueError(f"{model_id} is not a valid {category} model for {provider}")
    return model.id


def summarize_provider_catalog(
    provider: ProviderSlug,
    available_model_ids: set[str] | None = None,
) -> dict[str, object]:
    provider_capability = get_provider_capability(provider)
    models = [
        model
        for model in list_models_for_provider(provider)
        if available_model_ids is None or model.id in available_model_ids
    ]
    return {
        "provider": provider_capability.id,
        "label": provider_capability.label,
        "enabled": provider_capability.enabled,
        "discovery_supported": provider_capability.discovery_supported,
        "defaults": {
            "chat": provider_capability.chat_default_model,
            "reasoning": provider_capability.reasoning_default_model,
            "embedding": provider_capability.embedding_default_model,
            "vision": provider_capability.vision_default_model,
        },
        "models": [
            {
                "id": model.id,
                "label": model.label,
                "category": model.category,
                "supportsChat": model.supports_chat,
                "supportsReasoning": model.supports_reasoning,
                "supportsEmbeddings": model.supports_embeddings,
                "supportsVision": model.supports_vision,
                "enabled": model.enabled,
            }
            for model in models
        ],
    }
