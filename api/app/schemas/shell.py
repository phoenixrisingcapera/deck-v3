from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from app.schemas.save_confirmation import SaveConfirmationResponse


class DeckFileRef(BaseModel):
    id: str
    filename: str
    mimeType: str
    size: int
    uploadedAt: str


class DeckGraphDeck(BaseModel):
    id: str
    workspaceId: str
    title: str
    audience: str
    purpose: str
    status: str
    summary: str
    createdAt: str
    updatedAt: str
    file: DeckFileRef | None = None


class DeckGraphSlide(BaseModel):
    id: str
    versionId: str | None = None
    deckId: str
    versionNumber: int | None = None
    slideIndex: int
    title: str
    role: str
    rawText: str
    narrativeNotes: str


class DeckGraphBlock(BaseModel):
    id: str
    slideId: str
    blockIndex: int
    rawText: str
    normalizedText: str
    blockType: str
    position: str | None = None
    style: str | None = None


class DeckGraphClassification(BaseModel):
    id: str
    blockId: str
    semanticTag: str
    diligenceCategory: str
    confidence: float


class DeckGraphFinding(BaseModel):
    id: str
    deckId: str
    slideId: str
    blockId: str | None = None
    title: str
    detail: str
    severity: str
    category: str


class DeckGraphSuggestion(BaseModel):
    id: str
    deckId: str
    slideId: str
    blockId: str | None = None
    title: str
    reason: str
    suggestedText: str
    status: str
    audience: str


class DeckGraphSmartEditSuggestion(BaseModel):
    id: str
    runId: str
    deckId: str
    slideId: str
    blockId: str
    originalText: str
    suggestedText: str
    reason: str
    riskLevel: str
    status: str


class DeckGraphRevision(BaseModel):
    id: str
    deckId: str
    slideId: str
    blockId: str
    previousText: str
    nextText: str
    reason: str
    createdAt: str


class DeckGraphResponse(BaseModel):
    deck: DeckGraphDeck
    slides: list[DeckGraphSlide]
    blocks: list[DeckGraphBlock]
    classifications: list[DeckGraphClassification]
    findings: list[DeckGraphFinding]
    suggestions: list[DeckGraphSuggestion]
    smartEditSuggestions: list[DeckGraphSmartEditSuggestion]
    revisions: list[DeckGraphRevision]


class DeckShellProperties(BaseModel):
    deckId: str
    companyName: str | None = None
    companyWebsiteUrl: str | None = None
    contactEmail: str | None = None
    companyStage: str | None = None
    founderName: str | None = None
    teamSummary: str | None = None
    brandSummary: str | None = None
    visualDirection: str | None = None
    audienceLabel: str | None = None
    primaryGoal: str | None = None
    processingStatus: str = "ready"
    sourceFileName: str | None = None
    brandReady: bool = False
    sourcesUsed: list[str] = []
    brandAssetLabels: list[str] = []
    updatedAt: str | None = None


class UpdateDeckShellPropertiesRequest(BaseModel):
    companyName: str | None = None
    companyWebsiteUrl: str | None = None
    founderName: str | None = None
    teamSummary: str | None = None
    brandSummary: str | None = None
    visualDirection: str | None = None
    audienceLabel: str | None = None
    primaryGoal: str | None = None


class GeneratedSlideCandidateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    iterationId: str = Field(
        alias="iteration_id",
        validation_alias=AliasChoices("iterationId", "iteration_id", "batchId", "batch_id"),
        serialization_alias="iterationId",
    )
    batchId: str | None = None
    sourceSlideId: str | None = None
    slideIndex: int
    title: str
    headline: str
    summary: str
    status: str


class DesignBatchPreviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    versionId: str | None = None
    deckId: str
    versionNumber: int | None = None
    iterationNumber: int = Field(
        alias="iteration_number",
        validation_alias=AliasChoices("iterationNumber", "iteration_number", "batchNumber", "batch_number"),
        serialization_alias="iterationNumber",
    )
    batchNumber: int | None = None
    iterationName: str | None = Field(
        default=None,
        alias="iteration_name",
        validation_alias=AliasChoices("iterationName", "iteration_name", "batchName", "batch_name"),
        serialization_alias="iterationName",
    )
    batchName: str | None = None
    versionName: str | None = None
    scopeType: str
    selectedSlideCount: int
    status: str
    sourceSurface: str | None = None
    sourceArtifactId: str | None = None
    sourceDesignVersionId: str | None = None
    changeSummary: str | None = None
    acceptedByUserId: str | None = None
    acceptedAt: str | None = None
    createdAt: str


class DesignBatchDetailResponse(DesignBatchPreviewResponse):
    prompt: str
    audienceLabel: str | None = None
    selectedSlideIds: list[str]
    candidateSlides: list[GeneratedSlideCandidateResponse]
    snapshot: dict | None = None


class CreateDesignBatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scopeType: str
    prompt: str = Field(min_length=1)
    iterationName: str | None = Field(
        default=None,
        alias="iteration_name",
        validation_alias=AliasChoices("iterationName", "iteration_name", "batchName", "batch_name"),
        serialization_alias="iterationName",
    )
    audienceLabel: str | None = None
    selectedSlideIds: list[str] = Field(default_factory=list)
    useBrandProfile: bool = True
    useWebsiteContext: bool = True
    useBlockClassifications: bool = True


class CreateDeckSlideRequest(BaseModel):
    title: str | None = None
    role: str | None = None
    rawText: str | None = None


class ReviewGeneratedSlideCandidateRequest(BaseModel):
    decision: str


class SaveBatchSlideDecisionRequest(BaseModel):
    choice: str
    generatedSlideVersionId: str | None = None


class PrepareFullDeckRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    iterationId: str | None = Field(
        default=None,
        alias="iteration_id",
        validation_alias=AliasChoices("iterationId", "iteration_id", "batchId", "batch_id"),
        serialization_alias="iterationId",
    )
    batchId: str | None = None
    title: str | None = None
    latestSlideVersionId: str | None = None


class BatchSlideDecisionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    deckId: str
    iterationId: str = Field(
        alias="iteration_id",
        validation_alias=AliasChoices("iterationId", "iteration_id", "batchId", "batch_id"),
        serialization_alias="iterationId",
    )
    batchId: str | None = None
    slideId: str
    generatedSlideVersionId: str | None = None
    choice: str
    decidedAt: str


class PrepareFullDeckResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deckId: str
    iterationId: str = Field(
        alias="iteration_id",
        validation_alias=AliasChoices("iterationId", "iteration_id", "batchId", "batch_id"),
        serialization_alias="iterationId",
    )
    batchId: str | None = None
    compiledDeckId: str
    status: str
    title: str
    slideCount: int
    latestSlideVersionId: str | None = None
    finalizedAt: str
    manifest: dict
    slides: list[dict]
    redirectTo: str
    featuredCard: dict


class DeckSlideWithBlocksResponse(BaseModel):
    id: str
    deckId: str
    slideNumber: int
    title: str
    rawText: str
    summary: str | None = None
    slideRole: str
    blocks: list[dict]


class DeckShellPropertiesRouteResponse(BaseModel):
    deckId: str
    properties: DeckShellProperties
    confirmation: SaveConfirmationResponse | None = None


class DeckLatestConfirmationResponse(BaseModel):
    deckId: str
    confirmation: SaveConfirmationResponse | None = None


class DesignBatchListRouteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deckId: str
    versions: list[DesignBatchPreviewResponse] = Field(default_factory=list)
    iterations: list[DesignBatchPreviewResponse] = Field(
        alias="iterations",
        validation_alias=AliasChoices("iterations", "batches"),
        serialization_alias="iterations",
    )
    batches: list[DesignBatchPreviewResponse] | None = None


class DesignBatchCreateRouteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deckId: str
    version: DesignBatchDetailResponse | None = None
    iteration: DesignBatchDetailResponse = Field(
        alias="iteration",
        validation_alias=AliasChoices("iteration", "batch"),
        serialization_alias="iteration",
    )
    batch: DesignBatchDetailResponse | None = None


class DesignBatchDetailRouteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deckId: str
    version: DesignBatchDetailResponse | None = None
    iteration: DesignBatchDetailResponse = Field(
        alias="iteration",
        validation_alias=AliasChoices("iteration", "batch"),
        serialization_alias="iteration",
    )
    batch: DesignBatchDetailResponse | None = None


class BatchSlideDecisionRouteResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deckId: str
    iterationId: str = Field(
        alias="iteration_id",
        validation_alias=AliasChoices("iterationId", "iteration_id", "batchId", "batch_id"),
        serialization_alias="iterationId",
    )
    batchId: str | None = None
    decision: BatchSlideDecisionResponse
    iteration: DesignBatchDetailResponse = Field(
        alias="iteration",
        validation_alias=AliasChoices("iteration", "batch"),
        serialization_alias="iteration",
    )
    batch: DesignBatchDetailResponse | None = None


class GeneratedSlideCodeResponse(BaseModel):
    generatedSlideId: str
    schemaJson: dict
    renderSchema: dict
    validationStatus: str
    validationMessages: list[str]


class DeckSlideCreateRouteResponse(BaseModel):
    deckId: str
    slide: DeckSlideWithBlocksResponse


class DeckBlockUpdateRouteResponse(BaseModel):
    deckId: str
    block: DeckGraphBlock
    confirmation: SaveConfirmationResponse | None = None
