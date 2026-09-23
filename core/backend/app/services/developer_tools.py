from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeveloperToolEvent, User

SENSITIVE_KEYS = {
    "authorization", "cookie", "email", "password", "prompt", "token",
    "api_key", "provider_api_key", "secret", "raw_text", "raw_slide_text",
    "generated_output", "output", "user_instruction", "signed_url",
}


def _redact(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if str(key).lower() in SENSITIVE_KEYS else _redact(nested, depth + 1)
            for key, nested in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [_redact(item, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return " ".join(value.split())[:500]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:500]


def record_developer_tool_event(
    db: Session,
    *,
    actor: User,
    deck: Deck,
    surface: str,
    event_name: str,
    request: Request,
    metadata: dict[str, Any] | None = None,
) -> DeveloperToolEvent:
    event = DeveloperToolEvent(
        id=generate_id("devtool"),
        workspace_id=deck.workspace_id,
        deck_id=deck.id,
        user_id=actor.id,
        surface=surface[:80],
        event_name=event_name[:120],
        request_id=getattr(request.state, "request_id", None),
        workflow_id=str((metadata or {}).get("workflowId"))[:128] if (metadata or {}).get("workflowId") else None,
        workflow_job_id=str((metadata or {}).get("workflowJobId"))[:128] if (metadata or {}).get("workflowJobId") else None,
        run_id=str((metadata or {}).get("runId"))[:128] if (metadata or {}).get("runId") else None,
        artifact_id=str((metadata or {}).get("artifactId"))[:128] if (metadata or {}).get("artifactId") else None,
        metadata_json=_redact(metadata or {}),
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_developer_tool_summary(db: Session, *, deck: Deck, surface: str | None = None) -> dict[str, Any]:
    query = db.query(DeveloperToolEvent).filter(DeveloperToolEvent.deck_id == deck.id)
    if surface:
        query = query.filter(DeveloperToolEvent.surface == surface[:80])
    events = query.order_by(DeveloperToolEvent.created_at.desc()).limit(50).all()
    counts = (
        db.query(DeveloperToolEvent.event_name, func.count(DeveloperToolEvent.id))
        .filter(DeveloperToolEvent.deck_id == deck.id)
        .group_by(DeveloperToolEvent.event_name)
        .all()
    )
    return {
        "deckId": deck.id,
        "workspaceId": deck.workspace_id,
        "surface": surface,
        "eventCounts": {name: count for name, count in counts},
        "recentEvents": [
            {
                "id": event.id,
                "surface": event.surface,
                "eventName": event.event_name,
                "requestId": event.request_id,
                "workflowId": event.workflow_id,
                "workflowJobId": event.workflow_job_id,
                "runId": event.run_id,
                "artifactId": event.artifact_id,
                "metadata": event.metadata_json or {},
                "createdAt": event.created_at.isoformat(),
            }
            for event in events
        ],
    }
