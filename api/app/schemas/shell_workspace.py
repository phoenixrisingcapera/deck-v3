from pydantic import BaseModel


class DeckWorkspacePreferences(BaseModel):
    deckId: str
    activeTool: str = "slides"
    leftPanelOpen: bool = True
    selectedSlideId: str | None = None
    lastBatchId: str | None = None
    lastSlideVersionId: str | None = None
    selectedElementType: str | None = None
    selectedDataView: str | None = None
    chatOpen: bool = False
    updatedAt: str | None = None


class UpdateDeckWorkspacePreferencesRequest(BaseModel):
    activeTool: str | None = None
    leftPanelOpen: bool | None = None
    selectedSlideId: str | None = None
    lastBatchId: str | None = None
    lastSlideVersionId: str | None = None
    selectedElementType: str | None = None
    selectedDataView: str | None = None
    chatOpen: bool | None = None


class DeckWorkspacePreferencesRouteResponse(BaseModel):
    deckId: str
    workspace: DeckWorkspacePreferences
