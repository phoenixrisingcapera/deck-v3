from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import JSON, bindparam, func, text
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, DeckExport, DeckFeedbackEvent, DeckGenerationRun, User

SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "email",
    "generated_output",
    "output",
    "password",
    "prompt",
    "provider_api_key",
    "raw_slide_text",
    "raw_text",
    "secret",
    "token",
    "user_email",
    "user_instruction",
}

MAX_STRING_LENGTH = 500
MAX_RECENT_EVENTS = 50


def _clean_string(value: str, *, max_length: int = MAX_STRING_LENGTH) -> str:
    cleaned = " ".join(str(value).strip().split())
    return cleaned[:max_length]


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_KEYS:
                redacted[key_text] = "[redacted]"
            else:
                redacted[key_text] = _redact_value(nested)
        return redacted
    if isinstance(value, list):
        return [_redact_value(item) for item in value[:50]]
    if isinstance(value, str):
        return _clean_string(value)
    return value


def ensure_product_analytics_schema(db: Session) -> None:
    """Create the analytics table at runtime when migrations lag behind deploys.

    This mirrors the existing Railway runtime schema safety approach and keeps
    export analytics from breaking production while Alembic catches up.
    """

    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS deck_product_events (
                id VARCHAR PRIMARY KEY,
                workspace_id VARCHAR,
                user_id VARCHAR,
                deck_id VARCHAR,
                session_id VARCHAR,
                event_name VARCHAR,
                surface VARCHAR,
                route TEXT,
                entity_type VARCHAR,
                entity_id VARCHAR,
                event_version INTEGER DEFAULT 1,
                metadata_json JSON,
                source_ip VARCHAR,
                user_agent TEXT,
                request_id VARCHAR,
                created_at TIMESTAMP WITHOUT TIME ZONE
            )
            """
        )
    )
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_deck_product_events_workspace_id ON deck_product_events (workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_deck_product_events_user_id ON deck_product_events (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_deck_product_events_deck_id ON deck_product_events (deck_id)",
        "CREATE INDEX IF NOT EXISTS ix_deck_product_events_event_name ON deck_product_events (event_name)",
        "CREATE INDEX IF NOT EXISTS ix_deck_product_events_surface ON deck_product_events (surface)",
        "CREATE INDEX IF NOT EXISTS ix_deck_product_events_created_at ON deck_product_events (created_at)",
    ):
        db.execute(text(statement))


def record_deck_product_event(
    db: Session,
    *,
    event_name: str,
    actor: User | None = None,
    deck: Deck | None = None,
    request: Request | None = None,
    surface: str = "unknown",
    entity_type: str | None = None,
    entity_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = False,
) -> dict[str, Any] | None:
    try:
        ensure_product_analytics_schema(db)
        event_id = generate_id("event")
        source_ip = request.client.host if request is not None and request.client is not None else None
        user_agent = request.headers.get("user-agent") if request is not None else None
        request_id = getattr(getattr(request, "state", None), "request_id", None) if request is not None else None
        route = str(request.url.path) if request is not None else None
        payload = _redact_value(metadata or {})
        insert_event = text(
            """
            INSERT INTO deck_product_events (
                id, workspace_id, user_id, deck_id, session_id, event_name,
                surface, route, entity_type, entity_id, event_version,
                metadata_json, source_ip, user_agent, request_id, created_at
            ) VALUES (
                :id, :workspace_id, :user_id, :deck_id, :session_id, :event_name,
                :surface, :route, :entity_type, :entity_id, :event_version,
                :metadata_json, :source_ip, :user_agent, :request_id, :created_at
            )
            """
        ).bindparams(bindparam("metadata_json", type_=JSON))
        db.execute(
            insert_event,
            {
                "id": event_id,
                "workspace_id": deck.workspace_id if deck is not None else None,
                "user_id": actor.id if actor is not None else None,
                "deck_id": deck.id if deck is not None else None,
                "session_id": _clean_string(session_id, max_length=128) if session_id else None,
                "event_name": _clean_string(event_name, max_length=120),
                "surface": _clean_string(surface, max_length=80),
                "route": route,
                "entity_type": _clean_string(entity_type, max_length=80) if entity_type else None,
                "entity_id": _clean_string(entity_id, max_length=128) if entity_id else None,
                "event_version": 1,
                "metadata_json": payload,
                "source_ip": source_ip,
                "user_agent": user_agent,
                "request_id": request_id,
                "created_at": datetime.utcnow(),
            },
        )
        if commit:
            db.commit()
        return {"id": event_id, "eventName": event_name, "deckId": deck.id if deck else None}
    except Exception:
        if commit:
            db.rollback()
        return None


def get_product_analytics_metrics(db: Session) -> dict[str, Any]:
    ensure_product_analytics_schema(db)

    total_events = db.execute(text("SELECT COUNT(*) FROM deck_product_events")).scalar() or 0
    event_rows = db.execute(
        text("SELECT event_name, COUNT(*) FROM deck_product_events GROUP BY event_name ORDER BY COUNT(*) DESC")
    ).all()
    surface_rows = db.execute(
        text("SELECT surface, COUNT(*) FROM deck_product_events GROUP BY surface ORDER BY COUNT(*) DESC")
    ).all()
    export_rows = db.execute(
        text("SELECT event_name, COUNT(*) FROM deck_product_events WHERE event_name LIKE 'export.%' GROUP BY event_name")
    ).all()
    recent_rows = db.execute(
        text(
            """
            SELECT id, deck_id, user_id, event_name, surface, entity_type, entity_id, metadata_json, created_at
            FROM deck_product_events
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": MAX_RECENT_EVENTS},
    ).mappings().all()

    feedback_counts = {
        str(event_type): count
        for event_type, count in db.query(DeckFeedbackEvent.event_type, func.count(DeckFeedbackEvent.id))
        .group_by(DeckFeedbackEvent.event_type)
        .all()
    }
    generation_count = db.query(DeckGenerationRun).count()
    generation_with_quality = db.query(DeckGenerationRun).filter(DeckGenerationRun.quality_score.isnot(None)).count()
    export_count = db.query(DeckExport).count()
    exported_deck_count = db.query(DeckExport.deck_id).distinct().count()

    export_funnel = {str(name): count for name, count in export_rows}
    generated = export_funnel.get("export.generate.succeeded", 0) or export_funnel.get("export.generated", 0)
    downloaded = export_funnel.get("export.download.clicked", 0) + export_funnel.get("export.downloaded", 0)

    return {
        "summary": {
            "totalProductEvents": total_events,
            "exportArtifacts": export_count,
            "exportedDecks": exported_deck_count,
            "generationRuns": generation_count,
            "generationRunsWithQualityScore": generation_with_quality,
        },
        "eventCounts": {str(name): count for name, count in event_rows},
        "surfaceCounts": {str(name or "unknown"): count for name, count in surface_rows},
        "exportFunnel": {
            **export_funnel,
            "generatedToDownloadedRatio": round(downloaded / generated, 4) if generated else None,
        },
        "feedbackLabels": feedback_counts,
        "modelReadiness": {
            "hasExportLabels": export_count > 0,
            "hasFeedbackLabels": sum(feedback_counts.values()) > 0,
            "hasQualityScores": generation_with_quality > 0,
            "recommendedNextModel": "export_likelihood" if export_count >= 50 else "continue_collecting_export_labels",
            "privacyPolicy": "Product analytics stores behavioural labels, counts, IDs, and redacted metadata. Raw slide text, prompts, generated outputs, emails, and secrets are not stored here.",
        },
        "recentEvents": [dict(row) for row in recent_rows],
    }
