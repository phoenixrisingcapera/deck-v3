from pydantic import BaseModel


class SaveConfirmationResponse(BaseModel):
    id: str
    deck_id: str
    workspace_id: str | None = None
    user_id: str | None = None
    event_type: str
    entity_type: str
    entity_id: str | None = None
    tone: str = "success"
    title: str
    message: str
    cta_label: str | None = None
    cta_href: str | None = None
    source_surface: str | None = None
    source_route: str | None = None
    created_at: str
    metadata: dict | None = None
