from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.core.openai_full_html_policy import FULL_HTML_MAX_SOURCE_SLIDES


WorkflowJobType = Literal[
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "brand_extraction",
    "smart_deck_context",
    "db_publisher",
    "llm_generation",
    "instant_deck_generation",
    "selected_slide_generation",
    "schema_validation",
    "preview_render",
    "apply_version",
    "compile_final_deck",
    "export",
    "due_diligence",
    "deck_map_analysis",
    "market_research",
    "media_processing",
    "smart_edit",
]

WorkflowJobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed_retryable",
    "failed_final",
    "blocked",
    "timed_out",
]

WorkflowPhase = Literal[
    "upload_accepted",
    "source_file_saved",
    "source_ingestion_queued",
    "source_ingestion_running",
    "source_extraction_queued",
    "source_extraction_running",
    "miniatures_queued",
    "miniatures_running",
    "brand_extraction_queued",
    "brand_extraction_running",
    "smart_deck_context_queued",
    "smart_deck_context_running",
    "source_ready",
    "ai_vc_understanding",
    "ai_vc_research",
    "ai_vc_analysis",
    "narrative_reconstruction",
    "visual_direction",
    "visual_asset_planning",
    "generation_queued",
    "generation_running",
    "selected_slide_generation_queued",
    "selected_slide_generation_running",
    "selected_slide_generation_ready",
    "schema_validation_queued",
    "schema_validation_running",
    "preview_render_queued",
    "preview_render_running",
    "preview_ready",
    "apply_queued",
    "apply_running",
    "applied",
    "compile_final_queued",
    "compile_final_running",
    "compiled_deck_ready",
    "export_queued",
    "export_running",
    "export_ready",
    "due_diligence_queued",
    "due_diligence_running",
    "due_diligence_ready",
    "deck_map_analysis_queued",
    "deck_map_analysis_running",
    "deck_map_analysis_ready",
    "market_research_queued",
    "market_research_running",
    "market_research_ready",
    "media_processing_queued",
    "media_processing_running",
    "media_ready",
    "smart_edit_queued",
    "smart_edit_running",
    "smart_edit_ready",
    # DISABLED: These duplicate literal members were introduced with the media
    # phases. The canonical entries remain immediately above the media phases.
    # "deck_map_analysis_queued",
    # "deck_map_analysis_running",
    # "deck_map_analysis_ready",
    # "market_research_queued",
    # "market_research_running",
    # "market_research_ready",
    "smart_deck_ready",
    "failed_retryable",
    "failed_final",
    "needs_manual_review",
]

WorkflowNextAction = Literal[
    "continue_upload",
    "view_processing",
    "apply_preview",
    "open_smart_deck",
    "configure_provider",
    "retry_job",
    "manual_review",
    "create_smart_deck",
]

WorkflowBlockingReason = Literal[
    "provider_not_configured",
    "dependency_failed",
    "worker_timeout",
    "worker_lease_expired",
    "worker_heartbeat_expired",
    "smart_deck_not_ready",
    "preview_not_ready",
    "export_not_ready",
    "idempotency_key_conflict",
    "source_extraction_failed",
    "thumbnail_generation_failed",
    "brand_extraction_failed",
    "smart_deck_context_failed",
    "llm_generation_failed",
    "selected_slide_generation_failed",
    "schema_validation_failed",
    "preview_render_failed",
    "db_publisher_failed",
    "apply_version_failed",
    "export_failed",
    "due_diligence_failed",
    "deck_map_analysis_failed",
    "market_research_failed",
]

WorkflowPublishedPhase = Literal[
    "ai_vc_understanding",
    "ai_vc_research",
    "ai_vc_analysis",
    "narrative_reconstruction",
    "visual_direction",
    "visual_asset_planning",
    "smart_deck_ready",
    "preview_ready",
    "applied",
    "export_ready",
]

WorkflowLivenessStatus = Literal[
    "queued",
    "active",
    "recovering",
    "stalled",
    "terminal",
]


class WorkflowJobErrorResponse(BaseModel):
    code: str
    message: str
    recoverable: bool
    nextAction: WorkflowNextAction | None = None


class WorkflowJobEventResponse(BaseModel):
    eventType: str
    fromStatus: str | None = None
    toStatus: str
    message: str | None = None
    createdAt: str


class WorkflowJobArtifactResponse(BaseModel):
    artifactType: str
    artifactId: str | None = None
    storageKey: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowJobSummaryResponse(BaseModel):
    jobId: str
    workflowId: str | None = None
    rootJobId: str | None = None
    generationJobId: str | None = None
    parentJobId: str | None = None
    dependencyJobIds: list[str] = Field(default_factory=list)
    authoritative: bool = False
    jobType: WorkflowJobType
    status: WorkflowJobStatus
    phase: WorkflowPhase
    attemptCount: int | None = None
    maxAttempts: int | None = None
    recoveryCount: int | None = None
    progress: int | None = None
    queuedAt: str | None = None
    startedAt: str | None = None
    heartbeatAt: str | None = None
    updatedAt: str | None = None
    lockedUntil: str | None = None
    lastRecoveredAt: str | None = None
    lastRecoveredBy: str | None = None
    completedAt: str | None = None
    failedAt: str | None = None
    publishedPhase: WorkflowPublishedPhase | None = None
    publishedAt: str | None = None
    workerId: str | None = None
    terminal: bool = False
    terminalReason: str | None = None
    retryEligible: bool = False
    # Default preserves API availability during rolling deployments where a
    # newer response schema can temporarily run beside an older read model.
    livenessStatus: WorkflowLivenessStatus = "queued"
    heartbeatAgeSeconds: int | None = None
    leaseExpiresAt: str | None = None
    operationDeadlineAt: str | None = None
    recoverable: bool = False
    nextAction: WorkflowNextAction | None = None
    error: WorkflowJobErrorResponse | None = None


class WorkflowSourceEnrichmentResponse(BaseModel):
    source: str | None = None
    llmStatus: str | None = None
    provider: str | None = None
    model: str | None = None
    message: str | None = None
    badge: str | None = None


class WorkflowSourceBlockResponse(BaseModel):
    id: str | None = None
    blockIndex: int
    rawText: str
    normalizedText: str
    blockType: str
    sourceKind: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("metadata", "metadataJson"))


class WorkflowSourceAssetResponse(BaseModel):
    id: str | None = None
    assetType: str
    label: str | None = None
    mimeType: str | None = None
    assetUrl: str | None = None
    pageNumber: int | None = None
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("metadata", "metadataJson"))


class WorkflowSourceSlideResponse(BaseModel):
    id: str | None = None
    slideIndex: int
    title: str
    role: str
    rawText: str
    sourcePageNumber: int | None = None
    thumbnailPath: str | None = None
    thumbnailMimeType: str | None = None
    thumbnailUrl: str | None = None
    previewImageUrl: str | None = None
    previewUrl: str | None = None
    widthPoints: float | None = None
    heightPoints: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("metadata", "metadataJson"))
    blocks: list[WorkflowSourceBlockResponse] = Field(default_factory=list)
    assets: list[WorkflowSourceAssetResponse] = Field(default_factory=list)


class WorkflowSourceStateResponse(BaseModel):
    inputSourceId: str | None = None
    sourceVersionId: str | None = None
    fileSaved: bool
    extractionReady: bool
    slideCount: int
    assetCount: int
    thumbnailCount: int
    thumbnailsRequired: bool = True
    brandExtractionReady: bool
    sourceEnrichment: WorkflowSourceEnrichmentResponse | None = None
    slides: list[WorkflowSourceSlideResponse] = Field(default_factory=list)


class WorkflowSmartDeckStateResponse(BaseModel):
    workspaceId: str | None = None
    ready: bool
    sourceSlideCount: int
    generatedSlideCount: int
    activeDesignVersionId: str | None = None
    hasRenderableSchema: bool


class WorkflowProviderStateResponse(BaseModel):
    configured: bool
    blockingReason: WorkflowBlockingReason | None = None
    provider: str | None = None
    model: str | None = None


class WorkflowBrandStateResponse(BaseModel):
    profileId: str | None = None
    status: str = "idle"
    ready: bool = False
    sourceMode: str | None = None
    profile: dict[str, Any] | None = None


class WorkflowLinksResponse(BaseModel):
    processingUrl: str
    smartDeckUrl: str


class WorkflowPhaseResponse(BaseModel):
    key: str
    label: str
    description: str | None = None
    status: str
    active: bool | None = None
    completed: bool | None = None
    started_at: str | None = None
    completed_at: str | None = None
    error: dict | None = None
    blocking_for_visualizer: bool = False
    blocking_for_export: bool = True
    count: int | None = None


class WorkflowChainIdentityResponse(BaseModel):
    workflowId: str
    rootJobId: str
    generationJobId: str
    chainJobIds: list[str] = Field(default_factory=list)
    schemaValidationJobId: str | None = None
    previewRenderJobId: str | None = None
    publisherJobId: str | None = None


class DeckWorkflowStateResponse(BaseModel):
    factualReview: dict[str, Any] | None = None
    deckId: str
    workflowId: str
    authoritativeInstantChain: WorkflowChainIdentityResponse | None = None
    phase: WorkflowPhase
    activeStage: str | None = None
    stages: list[WorkflowPhaseResponse] = Field(default_factory=list)
    status: WorkflowJobStatus
    lifecycleStatus: str
    nextAction: WorkflowNextAction
    blockingReason: WorkflowBlockingReason | None = None
    message: str | None = None
    sourceFileStatus: str | None = None
    sourceFileSaved: bool = False
    deckExtractionStatus: str | None = None
    processingStage: str | None = None
    processingStageLabel: str | None = None
    workerState: str | None = None
    workerMessage: str | None = None
    retryUrl: str | None = None
    canRemove: bool = False
    canOpenSmartDeck: bool = False
    canOpenInstantDeck: bool = False
    canGenerate: bool = False
    canRetry: bool = False
    degradedMode: bool = False
    missingArtifacts: list[str] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)
    workerHeartbeat: dict[str, Any] | None = None
    updatedAt: str | None = None
    activeJob: WorkflowJobSummaryResponse | None = None
    failedJob: WorkflowJobSummaryResponse | None = None
    latestJobs: list[WorkflowJobSummaryResponse] = Field(default_factory=list)
    phases: list[WorkflowPhaseResponse] = Field(default_factory=list)
    source: WorkflowSourceStateResponse
    smartDeck: WorkflowSmartDeckStateResponse
    provider: WorkflowProviderStateResponse
    brand: WorkflowBrandStateResponse
    links: WorkflowLinksResponse


class WorkflowJobResponse(BaseModel):
    jobId: str
    deckId: str
    workflowId: str
    rootJobId: str | None = None
    generationJobId: str | None = None
    parentJobId: str | None = None
    dependencyJobIds: list[str] = Field(default_factory=list)
    authoritative: bool = False
    jobType: WorkflowJobType
    status: WorkflowJobStatus
    phase: WorkflowPhase
    attemptCount: int | None = None
    maxAttempts: int | None = None
    recoveryCount: int | None = None
    priority: int | None = None
    idempotencyKey: str | None = None
    workerId: str | None = None
    progress: int | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    artifacts: list[WorkflowJobArtifactResponse] = Field(default_factory=list)
    error: WorkflowJobErrorResponse | None = None
    queuedAt: str | None = None
    startedAt: str | None = None
    heartbeatAt: str | None = None
    updatedAt: str | None = None
    lockedUntil: str | None = None
    lastRecoveredAt: str | None = None
    lastRecoveredBy: str | None = None
    completedAt: str | None = None
    failedAt: str | None = None
    publishedPhase: WorkflowPublishedPhase | None = None
    publishedAt: str | None = None
    terminal: bool = False
    terminalReason: str | None = None
    retryEligible: bool = False
    # Default preserves API availability during rolling deployments where a
    # newer response schema can temporarily run beside an older read model.
    livenessStatus: WorkflowLivenessStatus = "queued"
    heartbeatAgeSeconds: int | None = None
    leaseExpiresAt: str | None = None
    operationDeadlineAt: str | None = None
    recoverable: bool = False
    nextAction: WorkflowNextAction | None = None
    designVersion: dict[str, Any] | None = None
    workspace: dict[str, Any] | None = None
    events: list[WorkflowJobEventResponse] = Field(default_factory=list)


class WorkflowCommandAcceptedResponse(BaseModel):
    accepted: bool = True
    jobId: str
    jobType: WorkflowJobType
    status: WorkflowJobStatus
    phase: WorkflowPhase
    workflowStateUrl: str
    jobUrl: str


class WorkflowSourceExtractionRequest(BaseModel):
    idempotencyKey: str | None = Field(default=None, max_length=255)


class WorkflowGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    selectedSourceSlideIds: list[str] = Field(min_length=1)
    idempotencyKey: str = Field(min_length=1, max_length=255)
    activeSourceSlideId: str | None = Field(default=None, max_length=120)
    sourceVersionId: str | None = Field(default=None, max_length=120)
    styleId: str | None = Field(default=None, max_length=120)
    brandProductId: str | None = Field(default="deck-aistack-codes", max_length=120)
    additionalContext: str | None = Field(default=None, max_length=4000)
    deckType: str | None = Field(default=None, max_length=40)
    audience: str | None = Field(default=None, max_length=120)
    preferredModel: str | None = Field(default=None, max_length=120)
    selectedElementId: str | None = Field(default=None, max_length=120)
    selectedSubject: str | None = Field(default=None, max_length=80)
    actionId: str | None = Field(default=None, max_length=120)
    actionPrompt: str | None = Field(default=None, max_length=4000)
    userPrompt: str | None = Field(default=None, max_length=4000)
    latestBatchId: str | None = Field(default=None, max_length=120)
    detectedSubjects: list[dict[str, Any]] | None = None
    subjectConfidence: float | None = Field(default=None, ge=0.0, le=1.0)
    designContext: dict[str, Any] | None = None
    provenance: "WorkflowGenerationProvenance | None" = None
    generationMode: Literal["standard", "instant_deck"] = "standard"
    outputContract: Literal["render_schema.v1", "full_html_deck.v1"] = "render_schema.v1"
    baseDesignVersionId: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_unique_selected_slides(self) -> "WorkflowGenerationRequest":
        if len(set(self.selectedSourceSlideIds)) != len(self.selectedSourceSlideIds):
            raise ValueError("selectedSourceSlideIds must not contain duplicates.")
        if self.outputContract == "full_html_deck.v1" and self.generationMode != "instant_deck":
            raise ValueError("full_html_deck.v1 is supported only for instant_deck generation.")
        if self.outputContract == "full_html_deck.v1" and len(self.selectedSourceSlideIds) > FULL_HTML_MAX_SOURCE_SLIDES:
            raise ValueError(
                f"full_html_deck.v1 supports at most {FULL_HTML_MAX_SOURCE_SLIDES} selected source slides."
            )
        if self.outputContract == "render_schema.v1" and self.baseDesignVersionId is not None:
            raise ValueError("baseDesignVersionId is reserved for full_html_deck.v1 generation.")
        return self

    model_config = ConfigDict(populate_by_name=True)


class WorkflowGenerationProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["due_diligence_full_deck"]
    audience: str = Field(min_length=1, max_length=120)
    audienceArtifactId: str | None = Field(default=None, max_length=120)
    diligenceArtifactIds: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_unique_artifacts(self) -> "WorkflowGenerationProvenance":
        if len(set(self.diligenceArtifactIds)) != len(self.diligenceArtifactIds):
            raise ValueError("diligenceArtifactIds must not contain duplicates.")
        return self


class WorkflowFailedSlideRetryRequest(BaseModel):
    priorGenerationJobId: str = Field(min_length=1, max_length=120)
    idempotencyKey: str = Field(min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid")


class WorkflowSelectedSlideGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    selectedSourceSlideIds: list[str] = Field(min_length=1, max_length=40)
    idempotencyKey: str = Field(min_length=1, max_length=255)
    partitionCount: int = Field(default=4, ge=1, le=32)
    batchSize: int = Field(default=8, ge=1, le=64)
    preferredModel: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_unique_selected_slides(self) -> "WorkflowSelectedSlideGenerationRequest":
        if len(set(self.selectedSourceSlideIds)) != len(self.selectedSourceSlideIds):
            raise ValueError("selectedSourceSlideIds must not contain duplicates.")
        return self


class WorkflowApplyRequest(BaseModel):
    designVersionId: str = Field(min_length=1, max_length=120)
    idempotencyKey: str = Field(min_length=1, max_length=255)


class WorkflowExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    designVersionId: str | None = Field(default=None, min_length=1, max_length=120)
    format: Literal["html"] | None = None
    type: str | None = Field(default=None, min_length=1, max_length=80)
    exportType: str | None = Field(default=None, min_length=1, max_length=80)
    idempotencyKey: str = Field(min_length=1, max_length=255)

    @property
    def normalized_type(self) -> str | None:
        value = self.type or self.exportType or ("final_deck" if self.format == "html" else None)
        return value.strip().lower() if value else None

    @model_validator(mode="after")
    def validate_export_contract(self) -> "WorkflowExportRequest":
        supplied_types = [str(value).strip().lower() for value in (self.type, self.exportType) if value is not None]
        if len(set(supplied_types)) > 1:
            raise ValueError("type and exportType must identify the same export type.")
        if self.normalized_type == "provisional_html" and (self.format != "html" or not self.designVersionId):
            raise ValueError("provisional_html export requires format=html and designVersionId.")
        if self.format == "html" and (self.normalized_type not in {"final_deck", "provisional_html"} or not self.designVersionId):
            raise ValueError("final_deck HTML export or provisional_html HTML export requires designVersionId.")
        if self.designVersionId and self.format != "html":
            raise ValueError("designVersionId is supported only for HTML export.")
        return self


WorkflowCommandName = Literal[
    "start_source_extraction",
    "start_source_processing",
    "create_smart_deck",
    "retry",
    "generate_preview",
    "run_selected_slide_generation",
    "apply_design_version",
    "export",
]


class WorkflowCommandRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    command: WorkflowCommandName
    idempotencyKey: str | None = Field(default=None, max_length=255)
    generation: WorkflowGenerationRequest | None = None
    selectedSlideGeneration: WorkflowSelectedSlideGenerationRequest | None = Field(
        default=None,
        alias="selected_slide_generation",
        validation_alias=AliasChoices("selectedSlideGeneration", "selected_slide_generation"),
        serialization_alias="selectedSlideGeneration",
    )
    apply: WorkflowApplyRequest | None = None
    export: WorkflowExportRequest | None = None
