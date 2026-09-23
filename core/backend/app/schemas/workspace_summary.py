from typing import Literal

from pydantic import BaseModel
from app.schemas.save_confirmation import SaveConfirmationResponse

from app.schemas.deck import DeckSummary


class FirstTimeTemplatePreview(BaseModel):
    id: str
    title: str
    audience_label: str
    description: str
    tags: list[str]
    cta_label: str


class WorkspaceRef(BaseModel):
    id: str
    name: str


class WorkspaceSummaryResponse(BaseModel):
    workspace: WorkspaceRef
    deck_count: int
    active_deck_id: str | None
    latest_decks: list[DeckSummary]
    processing_deck_count: int
    ready_deck_count: int
    export_count: int
    first_time_templates: list[FirstTimeTemplatePreview]


class FirstDeckUploadResponse(BaseModel):
    ok: bool
    deck_id: str
    filename: str
    idempotent_replay: bool = False
    duplicate_of_deck_id: str | None = None
    upload_success: bool = True
    upload_status: str = "uploaded"
    source_file_status: str = "uploaded"
    original_file_url: str | None = None
    source_file_name: str | None = None
    source_file_size_bytes: int | None = None
    source_file_mime_type: str | None = None
    source_file_extension: str | None = None
    source_file_display_name: str | None = None
    source_file_uploaded_at: str | None = None
    deck_extraction_status: str = "uploaded"
    status: str = "uploaded"
    state: str = "uploaded"
    deckStatus: str = "uploaded"
    ui_state: str = "uploaded"
    upload_message: str | None = None
    next_step_message: str | None = None
    next_action: str | None = None
    create_smart_deck_url: str | None = None
    processing_status_url: str | None = None
    smart_deck_url: str | None = None
    preferred_workspace: Literal["smart_deck", "instant_deck"] | None = None
    preferred_workspace_url: str | None = None
    intake_run_id: str | None = None
    intakeRunId: str | None = None
    storage_warning: dict | None = None
    processing: dict | None = None
    queueError: str | None = None
    queueFailureTicketId: str | None = None
    confirmation: SaveConfirmationResponse | None = None
    workspace: WorkspaceSummaryResponse


WelcomeEntryView = Literal["welcome", "dashboard"]
DeckOwnershipStatus = Literal["none", "single", "many"]


class WelcomeDeckBrandCard(BaseModel):
    primary: str | None = None
    secondary: str | None = None
    accent: str | None = None
    background: str | None = None
    text: str | None = None
    palette: list[str] = []


class WelcomeDeckMiniature(BaseModel):
    deckId: str
    title: str
    status: str
    state: str | None = None
    deckStatus: str | None = None
    updatedAt: str | None = None
    brand: WelcomeDeckBrandCard | None = None


class WelcomeResumeCard(BaseModel):
    deckId: str | None = None
    title: str | None = None
    status: str | None = None
    state: str | None = None
    deckStatus: str | None = None
    slideId: str | None = None
    slideTitle: str | None = None
    batchId: str | None = None
    slideVersionId: str | None = None
    brand: WelcomeDeckBrandCard | None = None


class WelcomeProviderCard(BaseModel):
    provider: str | None = None
    providerLabel: str | None = None
    providerLogo: str | None = None
    preferredModel: str | None = None
    isConfigured: bool = False


class WelcomeStateResponse(BaseModel):
    workspace: WorkspaceRef
    hasDeck: bool
    deckOwnershipStatus: DeckOwnershipStatus
    deckCount: int
    activeDeckId: str | None
    latestDeckTitle: str | None
    latestDeckStatus: str | None = None
    latestDeckState: str | None = None
    lastVisitedDeckId: str | None = None
    latestAcceptedSlideId: str | None = None
    latestAcceptedSlideVersionId: str | None = None
    latestAcceptedSlideTitle: str | None = None
    lastViewedSlideId: str | None = None
    lastViewedBatchId: str | None = None
    lastViewedSlideVersionId: str | None = None
    resumeCard: WelcomeResumeCard | None = None
    deckMiniatures: list[WelcomeDeckMiniature] = []
    providerCard: WelcomeProviderCard | None = None
    entryView: WelcomeEntryView
    entryRoute: str
