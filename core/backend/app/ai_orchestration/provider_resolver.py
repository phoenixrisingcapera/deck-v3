from __future__ import annotations

from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from app.ai_orchestration.providers import BaseLlmProvider
from app.ai_orchestration.providers.anthropic_provider import AnthropicLlmProvider
from app.ai_orchestration.providers.openai_provider import OpenAiLlmProvider
from app.ai_orchestration.providers.openrouter_provider import OpenRouterLlmProvider
from app.core.config import settings
from app.core.workspace_ai_crypto import get_workspace_ai_fernet
from app.db.models import Deck, WorkspaceAiCredential, WorkspaceAiProviderSetting
from app.ai_orchestration.providers.dashscope_provider import DashScopeLlmProvider


WORKSPACE_PROVIDER_CONFIGURATION_ERROR = "AI generation provider is unavailable."


class WorkspaceProviderConfigurationError(ValueError):
    """Safe failure for an explicitly configured but unusable workspace provider."""


def resolve_orchestration_provider(
    db: Session,
    deck: Deck,
    *,
    preferred_model: str | None = None,
) -> BaseLlmProvider:
    mode = (settings.deck_generation_mode or "").strip().lower()
    if mode == "mock":
        raise ValueError("Mock AI orchestration has moved to the Deck local_testing harness.")
    workspace_provider = _resolve_workspace_provider(db, deck, preferred_model=preferred_model)
    if workspace_provider is not None:
        return workspace_provider

    # CHANGED: Railway's shared provider must be OpenAI in production, but an
    # explicitly configured, workspace-owned Qwen credential is resolved above.
    if settings.is_production and mode != "openai":
        raise ValueError("Production platform AI orchestration requires OpenAI.")

    provider_name = "dashscope" if mode in {"dashscope", "qwen", "alibaba"} else mode
    if provider_name == "dashscope" and settings.effective_qwen_api_key:
        return DashScopeLlmProvider(
            api_key=settings.effective_qwen_api_key,
            model=preferred_model or settings.effective_qwen_model,
        )

    if provider_name == "openai" and settings.openai_api_key:
        return OpenAiLlmProvider(
            api_key=settings.openai_api_key,
            model=preferred_model or settings.openai_model,
        )
    # DISABLED FOR NOW: direct Anthropic and OpenRouter environment routing.
    # if provider_name == "claude" and settings.anthropic_api_key:
    #     return AnthropicLlmProvider(
    #         api_key=settings.anthropic_api_key,
    #         model=preferred_model or settings.anthropic_model,
    #     )
    # if provider_name == "openrouter" and settings.openrouter_api_key:
    #     return OpenRouterLlmProvider(
    #         api_key=settings.openrouter_api_key,
    #         model=preferred_model or settings.openrouter_model,
    #     )

    if provider_name != "openai" and settings.effective_qwen_api_key:
        return DashScopeLlmProvider(
            api_key=settings.effective_qwen_api_key,
            model=preferred_model or settings.effective_qwen_model,
        )

    # DISABLED FOR NOW: non-Qwen fallback providers.
    # if settings.openai_api_key:
    #     return OpenAiLlmProvider(
    #         api_key=settings.openai_api_key,
    #         model=preferred_model or settings.openai_model,
    #     )
    # if settings.openrouter_api_key:
    #     return OpenRouterLlmProvider(
    #         api_key=settings.openrouter_api_key,
    #         model=preferred_model or settings.openrouter_model,
    #     )
    # if settings.anthropic_api_key:
    #     return AnthropicLlmProvider(
    #         api_key=settings.anthropic_api_key,
    #         model=preferred_model or settings.anthropic_model,
    #     )

    raise ValueError("No AI provider is configured for the selected generation mode.")


def _resolve_workspace_provider(
    db: Session,
    deck: Deck,
    *,
    preferred_model: str | None = None,
) -> BaseLlmProvider | None:
    setting = (
        db.query(WorkspaceAiProviderSetting)
        .filter(
            WorkspaceAiProviderSetting.workspace_id == deck.workspace_id,
            WorkspaceAiProviderSetting.use_for_smart_deck.is_(True),
            WorkspaceAiProviderSetting.configured_at.is_not(None),
        )
        .first()
    )
    if setting is None:
        return None

    if not setting.credential_id:
        raise WorkspaceProviderConfigurationError(WORKSPACE_PROVIDER_CONFIGURATION_ERROR)

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
    api_key = _decrypt_workspace_api_key(credential)
    if not api_key:
        raise WorkspaceProviderConfigurationError(WORKSPACE_PROVIDER_CONFIGURATION_ERROR)

    model = preferred_model or setting.preferred_model
    if setting.provider == "openai":
        return OpenAiLlmProvider(api_key=api_key, model=model or settings.openai_model)
    # DISABLED FOR NOW: workspace-level Anthropic and OpenRouter providers.
    # if setting.provider == "claude":
    #     return AnthropicLlmProvider(api_key=api_key, model=model or settings.anthropic_model)
    # if setting.provider == "openrouter":
    #     return OpenRouterLlmProvider(api_key=api_key, model=model or settings.openrouter_model)
    if setting.provider in {"qwen", "dashscope"}:
        return DashScopeLlmProvider(api_key=api_key, model=model or settings.effective_qwen_model)
    raise WorkspaceProviderConfigurationError(WORKSPACE_PROVIDER_CONFIGURATION_ERROR)


def _decrypt_workspace_api_key(credential: WorkspaceAiCredential | None) -> str | None:
    if credential is None or not credential.is_active:
        return None
    if credential.key_version != settings.workspace_ai_fernet_key_version:
        return None
    try:
        return get_workspace_ai_fernet().decrypt(credential.encrypted_api_key).decode()
    except (InvalidToken, RuntimeError, ValueError):
        return None
