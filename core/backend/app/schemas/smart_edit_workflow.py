from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SmartEditClassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=4000)
    blockId: str | None = Field(default=None, max_length=255)
    audienceType: str = Field(default="investment_committee", min_length=1, max_length=120)


class SmartEditPatchRequest(SmartEditClassifyRequest):
    model_config = ConfigDict(extra="forbid")


class SmartEditSlideSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False


class SmartEditSlideSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deckId: str
    slideId: str
    summary: str
    status: Literal["ready"] = "ready"
    persisted: bool = True
    cached: bool = False
    provider: str | None = None
    model: str | None = None
    updatedAt: str | None = None


class SmartEditIntentClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    confidence: Literal["low", "medium", "high"] = "medium"
    rationale: str | None = None
    missingInputs: list[str] = Field(default_factory=list)


class SmartEditPatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    beforeText: str
    afterText: str
    layoutPatch: dict = Field(default_factory=dict)
    elementPatches: list[dict] = Field(default_factory=list)
    riskControls: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    requiresReview: bool = True
    sourceFactsUsed: list[str] = Field(default_factory=list)
    sourceFactIds: list[str] = Field(default_factory=list)
    missingInputs: list[str] = Field(default_factory=list)


class ProductDeveloperDependencyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["workflow-job", "smart-edit-artifact", "smart-edit-suggestion"]
    status: str
    resourceId: str | None = None


class ProductDeveloperArtifactLineage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runId: str
    workflowJobId: str | None = None
    artifactId: str | None = None
    suggestionId: str | None = None


class ProductDeveloperEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["product-developer-envelope.v1"] = "product-developer-envelope.v1"
    dependencies: list[ProductDeveloperDependencyStatus] = Field(default_factory=list)
    artifactLineage: ProductDeveloperArtifactLineage
    degradation: Literal["ready", "pending", "degraded"]
    failureStage: Literal["queue", "worker", "artifact", "suggestion"] | None = None
    errorCode: str | None = None


class SmartEditWorkflowRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runId: str
    deckId: str
    slideId: str
    blockId: str | None = None
    status: Literal["queued", "running", "failed_retryable", "failed_final", "timed_out", "pending", "previewed", "completed", "no_change", "accepted", "rejected", "applied", "failed"]
    intent: SmartEditIntentClassificationResponse | None = None
    patch: SmartEditPatchResponse | None = None
    artifactId: str | None = None
    suggestionId: str | None = None
    cached: bool = False
    system: dict = Field(default_factory=dict)
    error: dict | None = None
    developer: ProductDeveloperEnvelope | None = None
