from __future__ import annotations

from pydantic import BaseModel

from app.schemas.deck_workflow import WorkflowJobStatus, WorkflowJobType, WorkflowNextAction, WorkflowPhase
from app.schemas.deck_structure import DeckStructureResponse
from app.schemas.save_confirmation import SaveConfirmationResponse


class DeckIntakeStepResponse(BaseModel):
    key: str
    label: str
    status: str


class DeckIntakeStatusResponse(BaseModel):
    deck_id: str
    deckId: str | None = None
    workflowId: str | None = None
    workflowPhase: WorkflowPhase | None = None
    workflowStatus: WorkflowJobStatus | None = None
    workflowJobId: str | None = None
    workflowJobType: WorkflowJobType | None = None
    workflowJobStatus: WorkflowJobStatus | None = None
    upload_status: str
    source_file_status: str
    original_file_url: str | None = None
    source_file_name: str | None = None
    source_file_size_bytes: int | None = None
    source_file_mime_type: str | None = None
    source_file_extension: str | None = None
    source_file_display_name: str | None = None
    source_file_uploaded_at: str | None = None
    deck_extraction_status: str
    status: str | None = None
    state: str | None = None
    deckStatus: str | None = None
    ui_state: str = "idle"
    upload_message: str | None = None
    next_step_message: str | None = None
    next_action: WorkflowNextAction | None = None
    brand_status: str = "idle"
    brand_profile_id: str | None = None
    slide_count: int | None = None
    summary: str | None = None
    steps: list[DeckIntakeStepResponse] = []
    latest_confirmation: SaveConfirmationResponse | None = None


class DeckStructureExtractionResponse(BaseModel):
    ok: bool
    structure: DeckStructureResponse
