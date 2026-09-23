from __future__ import annotations

"""Workspace-scoped AI provider configuration for Smart Deck and related tools.

This module owns the user-configured provider/key path that should override the
default built-in provider when available.
"""

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.llm import default_registry
from app.services.llm.dashscope_provider import discover_dashscope_model_ids
from app.core.security import generate_id
from app.core.workspace_ai_crypto import get_workspace_ai_fernet
from app.db.models import AgentTelemetryEvent, AiUsageBucket, Workspace, WorkspaceAiCredential, WorkspaceAiProviderSetting
from app.db.session import AiSessionLocal
from app.services.llm.model_catalog import (
    get_provider_capability,
    summarize_provider_catalog,
    validate_model_for_category,
)
from app.schemas.workspace_ai_provider import (
    SaveWorkspaceAiProviderRequest,
    WorkspaceAiProviderSummary,
    WorkspaceAiUsageSummary,
)


# Validate the provided credential before we persist it so the workspace never
# appears configured with a dead key.
def _validate_connection(provider: str, api_key: str, model: str) -> set[str] | None:
    if not default_registry.get(provider).validate_connection(api_key=api_key, model=model):
        raise ValueError(f"Could not connect to {provider} with the provided API key.")
    if provider == "dashscope":
        try:
            return discover_dashscope_model_ids(api_key=api_key)
        except ValueError:
            return None
    return None


def _provider_alias(provider: str) -> str:
    return "anthropic" if provider == "claude" else ("dashscope" if provider == "qwen" else provider)


def _catalog_payload(
    provider: str,
    available_model_ids: set[str] | None = None,
) -> dict[str, object]:
    return summarize_provider_catalog(provider, available_model_ids)  # type: ignore[arg-type]


def _build_summary(
    setting: WorkspaceAiProviderSetting | None,
    credential: WorkspaceAiCredential | None = None,
    available_model_ids: set[str] | None = None,
) -> WorkspaceAiProviderSummary:
    default_provider = "openai" if settings.deck_generation_mode.strip().lower() == "openai" else "qwen"
    provider = setting.provider if setting and setting.provider else default_provider
    catalog = _catalog_payload(provider, available_model_ids)
    if setting is None:
        return WorkspaceAiProviderSummary(
            provider=None,
            preferred_model=None,
            reasoning_model=None,
            embedding_model=None,
            api_key_last4=None,
            key_version=None,
            is_configured=False,
            configured_at=None,
            skipped_at=None,
            provider_label=None,
            provider_enabled=True,
            discovery_supported=False,
            validation_status="unconfigured",
            available_models=[],
            defaults=catalog["defaults"],
        )

    active_credential = credential
    if active_credential is None and setting.credential_id:
        active_credential = setting.credential  # type: ignore[attr-defined]

    return WorkspaceAiProviderSummary(
        provider=setting.provider,  # type: ignore[arg-type]
        preferred_model=setting.preferred_model,
        reasoning_model=setting.reasoning_model,
        embedding_model=setting.embedding_model,
        api_key_last4=active_credential.api_key_last4 if active_credential else None,
        key_version=active_credential.key_version if active_credential else None,
        is_configured=bool(setting.configured_at and active_credential and active_credential.is_active),
        configured_at=setting.configured_at,
        skipped_at=setting.skipped_at,
        provider_label=catalog["label"],
        provider_enabled=bool(catalog["enabled"]),
        discovery_supported=bool(catalog["discovery_supported"]),
        validation_status="validated" if active_credential and active_credential.is_active else "skipped",
        available_models=catalog["models"],
        defaults=catalog["defaults"],
    )


def _resolve_workspace(
    db: Session,
    user_id: str,
    *,
    workspace_id: str | None = None,
    create_missing: bool = False,
) -> Workspace | None:
    query = db.query(Workspace).filter(Workspace.user_id == user_id)
    workspace = (
        query.filter(Workspace.id == workspace_id).first()
        if workspace_id
        else query.order_by(Workspace.created_at.asc()).first()
    )
    if workspace_id and workspace is None:
        return None
    if workspace is None and create_missing:
        workspace = Workspace(
            id=generate_id("ws"),
            user_id=user_id,
            name="Deck Workspace",
        )
        db.add(workspace)
        db.flush()
    return workspace


def get_workspace_ai_provider_summary(
    db: Session,
    user_id: str,
    workspace_id: str | None = None,
) -> WorkspaceAiProviderSummary:
    workspace = _resolve_workspace(db, user_id, workspace_id=workspace_id)
    if workspace is None:
        return _build_summary(None)
    setting = (
        db.query(WorkspaceAiProviderSetting)
        .filter(WorkspaceAiProviderSetting.workspace_id == workspace.id)
        .first()
    )

    credential = None
    if setting and setting.credential_id:
        credential = db.query(WorkspaceAiCredential).filter(WorkspaceAiCredential.id == setting.credential_id).first()

    return _build_summary(setting, credential)


def get_workspace_ai_usage_summary(
    db: Session,
    user_id: str,
    workspace_id: str | None = None,
) -> WorkspaceAiUsageSummary:
    """Return truthful app-tracked usage without inventing provider quota data."""
    workspace = _resolve_workspace(db, user_id, workspace_id=workspace_id)
    provider_summary = get_workspace_ai_provider_summary(db, user_id, workspace_id)
    since = datetime.utcnow() - timedelta(hours=24)
    telemetry_db = AiSessionLocal() if settings.ai_database_url else db
    owns_telemetry_session = telemetry_db is not db
    try:
        telemetry_filters = [
            AgentTelemetryEvent.user_id == user_id,
            AgentTelemetryEvent.created_at >= since,
        ]
        if workspace is not None:
            telemetry_filters.append(AgentTelemetryEvent.workspace_id == workspace.id)
        elif workspace_id:
            telemetry_filters.append(AgentTelemetryEvent.workspace_id == "__unavailable_workspace__")
        tracked_input, tracked_output = (
            telemetry_db.query(
                func.coalesce(func.sum(AgentTelemetryEvent.input_tokens), 0),
                func.coalesce(func.sum(AgentTelemetryEvent.output_tokens), 0),
            )
            .filter(*telemetry_filters)
            .one()
        )
        latest_event = (
            telemetry_db.query(AgentTelemetryEvent)
            .filter(
                *telemetry_filters,
                (AgentTelemetryEvent.input_tokens.isnot(None) | AgentTelemetryEvent.output_tokens.isnot(None)),
            )
            .order_by(AgentTelemetryEvent.created_at.desc())
            .first()
        )
        quota_bucket = (
            telemetry_db.query(AiUsageBucket)
            .filter(AiUsageBucket.user_id == user_id, AiUsageBucket.quota_key == "daily_generation")
            .one_or_none()
        )
    finally:
        if owns_telemetry_session:
            telemetry_db.close()

    tracked_input_tokens = int(tracked_input or 0)
    tracked_output_tokens = int(tracked_output or 0)
    tracked_total_tokens = tracked_input_tokens + tracked_output_tokens
    token_budget = max(0, int(settings.qwen_max_tokens_per_workspace_day))
    request_limit = max(0, int(settings.ai_daily_generation_quota))
    requests_used = int(quota_bucket.usage_count or 0) if quota_bucket and quota_bucket.window_start >= since else 0
    return WorkspaceAiUsageSummary(
        provider=provider_summary.provider or ("openai" if settings.deck_generation_mode.strip().lower() == "openai" else "qwen"),
        model=provider_summary.preferred_model or provider_summary.defaults.get("chat"),
        reasoningModel=provider_summary.reasoning_model or provider_summary.defaults.get("reasoning"),
        embeddingModel=provider_summary.embedding_model or provider_summary.defaults.get("embedding"),
        trackedInputTokens24h=tracked_input_tokens,
        trackedOutputTokens24h=tracked_output_tokens,
        trackedTotalTokens24h=tracked_total_tokens,
        applicationTokenBudget24h=token_budget,
        estimatedTrackedTokensRemaining24h=max(0, token_budget - tracked_total_tokens),
        generationRequestsUsed24h=requests_used,
        generationRequestsLimit24h=request_limit,
        generationRequestsRemaining24h=max(0, request_limit - requests_used),
        providerQuotaRemaining=None,
        providerQuotaSource="not_exposed",
        trackingCoverage="partial",
        lastTrackedAt=latest_event.created_at if latest_event else None,
    )


# Save or skip workspace AI configuration. Skip mode must clear any active
# credential binding so Smart Deck does not silently keep using an old key.
def save_workspace_ai_provider(db: Session, user_id: str, payload: SaveWorkspaceAiProviderRequest) -> dict:
    workspace = _resolve_workspace(
        db,
        user_id,
        workspace_id=payload.workspaceId,
        create_missing=payload.workspaceId is None,
    )
    if workspace is None:
        raise ValueError("Workspace not found")
    provider_capability = get_provider_capability(payload.provider)
    # CHANGED: OpenAI is the only shared production provider, while Qwen stays
    # available solely as an explicit encrypted workspace BYOK choice.
    production_byok_providers = {"openai", "qwen"}
    if settings.is_production and payload.provider not in production_byok_providers:
        raise ValueError("Only OpenAI and workspace-owned Qwen are enabled in production")
    if not provider_capability.enabled and settings.is_production and payload.provider != "qwen":
        raise ValueError(f"{provider_capability.label} is not enabled in the current production deployment")
    setting = (
        db.query(WorkspaceAiProviderSetting)
        .filter(WorkspaceAiProviderSetting.workspace_id == workspace.id)
        .first()
    )
    active_credential = None
    if setting and setting.credential_id:
        active_credential = (
            db.query(WorkspaceAiCredential)
            .filter(
                WorkspaceAiCredential.id == setting.credential_id,
                WorkspaceAiCredential.workspace_id == workspace.id,
                WorkspaceAiCredential.is_active.is_(True),
            )
            .first()
        )

    if payload.skipForNow:
        preferred_model = validate_model_for_category(payload.provider, payload.preferredModel, "chat")
        reasoning_model = validate_model_for_category(payload.provider, payload.reasoningModel, "reasoning")
        embedding_model = validate_model_for_category(payload.provider, payload.embeddingModel, "embedding")
        if setting is None:
            setting = WorkspaceAiProviderSetting(
                id=generate_id("wais"),
                workspace_id=workspace.id,
                provider=payload.provider,
                preferred_model=preferred_model,
                reasoning_model=reasoning_model,
                embedding_model=embedding_model,
                skipped_at=datetime.utcnow(),
            )
            db.add(setting)
        else:
            setting.provider = payload.provider
            setting.preferred_model = preferred_model
            setting.reasoning_model = reasoning_model
            setting.embedding_model = embedding_model
            setting.credential_id = None
            setting.configured_at = None
            setting.skipped_at = datetime.utcnow()
        (
            db.query(WorkspaceAiCredential)
            .filter(
                WorkspaceAiCredential.workspace_id == workspace.id,
                WorkspaceAiCredential.is_active.is_(True),
            )
            .update(
                {
                    WorkspaceAiCredential.is_active: False,
                    WorkspaceAiCredential.revoked_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        db.refresh(setting)
        return {
            "summary": _build_summary(setting),
            "next_url": "/welcome",
        }

    preferred_model = validate_model_for_category(payload.provider, payload.preferredModel, "chat")
    reasoning_model = validate_model_for_category(payload.provider, payload.reasoningModel, "reasoning")
    embedding_model = validate_model_for_category(payload.provider, payload.embeddingModel, "embedding")

    if preferred_model is None:
        raise ValueError("A primary LLM model is required")

    clean_api_key = payload.apiKey.strip()

    if not clean_api_key:
        if setting is None or active_credential is None or setting.provider != payload.provider:
            raise ValueError("API key is required")
        setting.preferred_model = preferred_model
        setting.reasoning_model = reasoning_model
        setting.embedding_model = embedding_model
        setting.skipped_at = None
        db.commit()
        db.refresh(setting)
        return {
            "summary": _build_summary(setting, active_credential),
            "next_url": "/welcome",
        }

    try:
        discovered_model_ids = _validate_connection(
            provider=_provider_alias(payload.provider),
            api_key=clean_api_key,
            model=preferred_model,
        )
    except ValueError as exc:
        raise ValueError(f"Could not connect to {payload.provider} with the provided API key: {exc}") from exc

    (
        db.query(WorkspaceAiCredential)
        .filter(
            WorkspaceAiCredential.workspace_id == workspace.id,
            WorkspaceAiCredential.is_active.is_(True),
        )
        .update(
            {
                WorkspaceAiCredential.is_active: False,
                WorkspaceAiCredential.revoked_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )

    encrypted_key = get_workspace_ai_fernet().encrypt(clean_api_key.encode())
    credential = WorkspaceAiCredential(
        id=generate_id("waic"),
        workspace_id=workspace.id,
        provider=payload.provider,
        encrypted_api_key=encrypted_key,
        api_key_last4=clean_api_key[-4:],
        key_version=settings.workspace_ai_fernet_key_version,
        created_by_user_id=user_id,
        is_active=True,
    )
    db.add(credential)
    db.flush()

    if setting is None:
        setting = WorkspaceAiProviderSetting(
            id=generate_id("wais"),
            workspace_id=workspace.id,
            provider=payload.provider,
            preferred_model=preferred_model,
            reasoning_model=reasoning_model,
            embedding_model=embedding_model,
            credential_id=credential.id,
            configured_at=datetime.utcnow(),
            skipped_at=None,
        )
        db.add(setting)
    else:
        setting.provider = payload.provider
        setting.preferred_model = preferred_model
        setting.reasoning_model = reasoning_model
        setting.embedding_model = embedding_model
        setting.credential_id = credential.id
        setting.configured_at = datetime.utcnow()
        setting.skipped_at = None

    db.commit()
    db.refresh(setting)
    selected_model_ids = {
        model
        for model in (preferred_model, reasoning_model, embedding_model)
        if model
    }
    return {
        "summary": _build_summary(
            setting,
            credential,
            discovered_model_ids | selected_model_ids
            if isinstance(discovered_model_ids, set)
            else None,
        ),
        "next_url": "/welcome",
    }


def revoke_workspace_ai_provider(
    db: Session,
    user_id: str,
    workspace_id: str | None = None,
) -> dict:
    workspace = _resolve_workspace(db, user_id, workspace_id=workspace_id)
    if workspace is None:
        return {
            "summary": _build_summary(None),
            "revoked": False,
        }
    setting = (
        db.query(WorkspaceAiProviderSetting)
        .filter(WorkspaceAiProviderSetting.workspace_id == workspace.id)
        .first()
    )
    if setting is None or not setting.credential_id:
        return {
            "summary": _build_summary(setting),
            "revoked": False,
        }

    credential = (
        db.query(WorkspaceAiCredential)
        .filter(
            WorkspaceAiCredential.id == setting.credential_id,
            WorkspaceAiCredential.workspace_id == workspace.id,
        )
        .first()
    )
    if credential is None or not credential.is_active:
        setting.credential_id = None
        setting.configured_at = None
        db.commit()
        db.refresh(setting)
        return {
            "summary": _build_summary(setting),
            "revoked": False,
        }

    credential.is_active = False
    credential.revoked_at = datetime.utcnow()
    setting.credential_id = None
    setting.configured_at = None
    db.commit()
    db.refresh(setting)
    return {
        "summary": _build_summary(setting),
        "revoked": True,
    }
