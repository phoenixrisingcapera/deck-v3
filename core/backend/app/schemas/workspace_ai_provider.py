from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WorkspaceAiProvider = Literal["openai", "openrouter", "claude", "qwen"]


class SaveWorkspaceAiProviderRequest(BaseModel):
    provider: WorkspaceAiProvider
    workspaceId: str | None = None
    apiKey: str = Field(default="", min_length=0)
    preferredModel: str | None = None
    reasoningModel: str | None = None
    embeddingModel: str | None = None
    skipForNow: bool = False


class WorkspaceAiModelDescriptor(BaseModel):
    id: str
    label: str
    category: Literal["chat", "reasoning", "embedding", "vision"]
    supportsChat: bool
    supportsReasoning: bool
    supportsEmbeddings: bool
    supportsVision: bool
    enabled: bool


class WorkspaceAiProviderSummary(BaseModel):
    provider: WorkspaceAiProvider | None
    preferred_model: str | None
    reasoning_model: str | None
    embedding_model: str | None
    api_key_last4: str | None
    key_version: str | None = None
    is_configured: bool
    configured_at: datetime | None
    skipped_at: datetime | None
    provider_label: str | None = None
    provider_enabled: bool = True
    discovery_supported: bool = False
    validation_status: Literal["unconfigured", "validated", "skipped", "degraded"] = "unconfigured"
    available_models: list[WorkspaceAiModelDescriptor] = Field(default_factory=list)
    defaults: dict[str, str | None] = Field(default_factory=dict)


class WorkspaceAiUsageSummary(BaseModel):
    provider: WorkspaceAiProvider | None
    model: str | None
    reasoningModel: str | None = None
    embeddingModel: str | None = None
    trackedInputTokens24h: int = 0
    trackedOutputTokens24h: int = 0
    trackedTotalTokens24h: int = 0
    applicationTokenBudget24h: int
    estimatedTrackedTokensRemaining24h: int
    generationRequestsUsed24h: int = 0
    generationRequestsLimit24h: int
    generationRequestsRemaining24h: int
    providerQuotaRemaining: int | None = None
    providerQuotaSource: Literal["provider_api", "not_exposed"] = "not_exposed"
    trackingCoverage: Literal["partial", "complete"] = "partial"
    lastTrackedAt: datetime | None = None


class SaveWorkspaceAiProviderResponse(BaseModel):
    summary: WorkspaceAiProviderSummary
    next_url: str


class RevokeWorkspaceAiProviderResponse(BaseModel):
    summary: WorkspaceAiProviderSummary
    revoked: bool
