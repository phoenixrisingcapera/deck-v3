from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.deck_workflow import WorkflowJobStatus, WorkflowJobType, WorkflowPhase


class DeckStructureBlockResponse(BaseModel):
    id: str
    blockIndex: int
    rawText: str
    normalizedText: str
    blockType: str
    sourceKind: str | None = None
    metadataJson: dict | None = None


class DeckStructureAssetResponse(BaseModel):
    id: str
    assetType: str
    label: str | None = None
    mimeType: str | None = None
    storageProvider: str | None = None
    storagePath: str | None = None
    assetUrl: str | None = None
    pageNumber: int | None = None
    width: int | None = None
    height: int | None = None
    metadataJson: dict | None = None


class DeckStructureSlideResponse(BaseModel):
    id: str
    slideIndex: int
    sourcePageNumber: int | None = None
    title: str
    role: str
    rawText: str
    summary: str | None = None
    thumbnailPath: str | None = None
    thumbnailMimeType: str | None = None
    widthPoints: float | None = None
    heightPoints: float | None = None
    metadataJson: dict | None = None
    blocks: list[DeckStructureBlockResponse] = Field(default_factory=list)
    assets: list[DeckStructureAssetResponse] = Field(default_factory=list)


class DeckStructureSourceFileResponse(BaseModel):
    id: str | None = None
    filename: str | None = None
    mimeType: str | None = None
    pageCount: int | None = None


class DeckExtractionRunResponse(BaseModel):
    id: str
    status: str
    workflowId: str | None = None
    workflowJobId: str | None = None
    workflowJobType: WorkflowJobType | None = None
    workflowJobStatus: WorkflowJobStatus | None = None
    workflowPhase: WorkflowPhase | None = None
    sourceFormat: str | None = None
    slideCount: int
    blockCount: int
    assetCount: int
    errorMessage: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None


class DeckLlmArtifactResponse(BaseModel):
    id: str
    artifactType: str
    artifactKey: str
    schemaVersion: str
    status: str
    summary: str | None = None
    payloadJson: dict | None = None
    metricsJson: dict | None = None
    createdAt: str
    updatedAt: str


class DeckLlmArtifactBundleResponse(BaseModel):
    deckId: str
    workflowId: str | None = None
    workflowPhase: WorkflowPhase | None = None
    workflowStatus: WorkflowJobStatus | None = None
    extractionRunId: str | None = None
    artifacts: list[DeckLlmArtifactResponse] = Field(default_factory=list)


class DeckStructureResponse(BaseModel):
    deckId: str
    title: str
    status: str
    workflowId: str | None = None
    workflowPhase: WorkflowPhase | None = None
    workflowStatus: WorkflowJobStatus | None = None
    sourceFile: DeckStructureSourceFileResponse
    extractionRun: DeckExtractionRunResponse | None = None
    slides: list[DeckStructureSlideResponse] = Field(default_factory=list)
