from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.core.utils import request_id
from app.db.models import FailureTicket, User

FAILURE_TICKET_STATUSES = {"new", "acknowledged", "investigating", "fixed", "ignored"}
FAILURE_TICKET_SEVERITIES = {"low", "medium", "high", "critical"}
FAILURE_TICKET_SOURCES = {"frontend", "api", "backend", "loader", "fallback"}
MAX_TEXT = 8000
MAX_STACK = 20000


def _clean_text(value: Any, *, limit: int = MAX_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def _clean_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_choice(value: Any, allowed: set[str], fallback: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    return normalized if normalized in allowed else fallback


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None



def _ticket_summary(ticket: FailureTicket) -> dict[str, Any]:
    context = ticket.context_json or {}
    failure_stage = context.get("failureStage") or context.get("failure_stage") or context.get("stage")
    action = context.get("action") or context.get("actionName")
    return {
        "id": ticket.id,
        "route": ticket.route,
        "pageUrl": ticket.page_url,
        "apiPath": ticket.api_path,
        "statusCode": ticket.status_code,
        "userId": ticket.user_id,
        "userEmail": ticket.user_email,
        "deckId": ticket.deck_id,
        "errorName": ticket.error_name,
        "errorMessage": ticket.error_message,
        "hasStack": bool(ticket.error_stack),
        "contextKeys": sorted((ticket.context_json or {}).keys()),
        "failureStage": failure_stage,
        "action": action,
        "severity": ticket.severity,
        "source": ticket.source,
        "status": ticket.status,
        "requestId": ticket.request_id,
        "adminNotes": ticket.admin_notes,
        "createdAt": _iso(ticket.created_at),
        "updatedAt": _iso(ticket.updated_at),
        "acknowledgedAt": _iso(ticket.acknowledged_at),
        "fixedAt": _iso(ticket.fixed_at),
        "ignoredAt": _iso(ticket.ignored_at),
    }


def _ticket_detail(ticket: FailureTicket) -> dict[str, Any]:
    return {
        **_ticket_summary(ticket),
        "errorStack": ticket.error_stack,
        "context": ticket.context_json or {},
    }


def create_failure_ticket(
    db: Session,
    payload: dict[str, Any],
    *,
    request: Any | None = None,
    current_user: User | None = None,
    commit: bool = True,
) -> FailureTicket:
    context = _clean_dict(payload.get("context") or payload.get("contextJson"))
    user_id = _clean_text(payload.get("userId") or context.get("userId"))
    user_email = _clean_text(payload.get("userEmail") or context.get("userEmail"))
    if current_user is not None:
        user_id = current_user.id
        user_email = current_user.email

    ticket = FailureTicket(
        id=generate_id("fail"),
        route=_clean_text(payload.get("route")),
        page_url=_clean_text(payload.get("pageUrl") or payload.get("page_url")),
        api_path=_clean_text(payload.get("apiPath") or payload.get("api_path")),
        status_code=_clean_int(payload.get("statusCode") or payload.get("status_code")),
        user_id=user_id,
        user_email=user_email,
        deck_id=_clean_text(payload.get("deckId") or payload.get("deck_id") or context.get("deckId")),
        error_name=_clean_text(payload.get("errorName") or payload.get("error_name")),
        error_message=_clean_text(payload.get("errorMessage") or payload.get("error_message")),
        error_stack=_clean_text(payload.get("errorStack") or payload.get("error_stack"), limit=MAX_STACK),
        context_json=context,
        severity=_normalize_choice(payload.get("severity"), FAILURE_TICKET_SEVERITIES, "medium"),
        source=_normalize_choice(payload.get("source"), FAILURE_TICKET_SOURCES, "frontend"),
        status="new",
        request_id=_clean_text(payload.get("requestId") or payload.get("request_id") or request_id(request), limit=128),
    )
    db.add(ticket)
    if commit:
        db.commit()
        db.refresh(ticket)
    return ticket


def create_failure_ticket_from_exception(
    db: Session,
    *,
    request: Any,
    exc: BaseException,
    commit: bool = True,
) -> FailureTicket:
    return create_failure_ticket(
        db,
        {
            "route": getattr(getattr(request, "scope", {}), "get", lambda *_: None)("route"),
            "pageUrl": str(getattr(request, "url", "")),
            "apiPath": getattr(getattr(request, "url", None), "path", None),
            "statusCode": 500,
            "errorName": exc.__class__.__name__,
            "errorMessage": str(exc),
            "errorStack": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            "severity": "critical",
            "source": "backend",
            "context": {
                "method": getattr(request, "method", None),
                "query": str(getattr(getattr(request, "url", None), "query", "")),
            },
        },
        request=request,
        commit=commit,
    )


def list_failure_tickets(
    db: Session,
    *,
    limit: int = 100,
    status: str | None = None,
    severity: str | None = None,
    source: str | None = None,
    deck_id: str | None = None,
) -> dict[str, Any]:
    query = db.query(FailureTicket)
    if status:
        query = query.filter(FailureTicket.status == status)
    if severity:
        query = query.filter(FailureTicket.severity == severity)
    if source:
        query = query.filter(FailureTicket.source == source)
    if deck_id:
        query = query.filter(FailureTicket.deck_id == deck_id)

    total = query.count()
    tickets = query.order_by(FailureTicket.created_at.desc()).limit(limit).all()
    status_counts = dict(db.query(FailureTicket.status, func.count(FailureTicket.id)).group_by(FailureTicket.status).all())
    severity_counts = dict(
        db.query(FailureTicket.severity, func.count(FailureTicket.id)).group_by(FailureTicket.severity).all()
    )
    source_counts = dict(db.query(FailureTicket.source, func.count(FailureTicket.id)).group_by(FailureTicket.source).all())
    return {
        "tickets": [_ticket_summary(ticket) for ticket in tickets],
        "total": total,
        "limit": limit,
        "filters": {
            "status": status,
            "severity": severity,
            "source": source,
            "deckId": deck_id,
        },
        "statusCounts": status_counts,
        "severityCounts": severity_counts,
        "sourceCounts": source_counts,
        "redaction": {
            "sensitiveFieldsRedacted": ["errorStack", "context"],
            "detailPolicy": "List view keeps technical context collapsed. Open a ticket for stack traces and payload context.",
        },
    }


def list_smart_deck_failure_events(
    db: Session,
    *,
    limit: int = 100,
    deck_id: str | None = None,
) -> dict[str, Any]:
    query = db.query(FailureTicket)
    if deck_id:
        query = query.filter(FailureTicket.deck_id == deck_id)

    tickets = query.order_by(FailureTicket.created_at.desc()).limit(limit).all()
    smart_deck_tickets = [
        ticket
        for ticket in tickets
        if (ticket.route or "").find("smart-deck") >= 0
        or (ticket.context_json or {}).get("failureStage") is not None
        or (ticket.context_json or {}).get("failure_stage") is not None
        or (ticket.context_json or {}).get("stage") is not None
    ]
    return {
        "tickets": [_ticket_summary(ticket) for ticket in smart_deck_tickets],
        "total": len(smart_deck_tickets),
        "limit": limit,
        "filters": {
            "deckId": deck_id,
        },
        "redaction": {
            "sensitiveFieldsRedacted": ["errorStack", "context"],
            "detailPolicy": "Smart Deck failures are summarized for admin review; open the ticket for technical details.",
        },
    }


def get_failure_ticket(db: Session, ticket_id: str) -> dict[str, Any] | None:
    ticket = db.get(FailureTicket, ticket_id)
    if ticket is None:
        return None
    return {
        "ticket": _ticket_detail(ticket),
        "redaction": {
            "detailPolicy": "This admin-only page can show technical context. Do not copy stack traces into user-facing replies.",
        },
    }


def update_failure_ticket(
    db: Session,
    ticket_id: str,
    *,
    status: str | None = None,
    admin_notes: str | None = None,
    commit: bool = True,
) -> dict[str, Any] | None:
    ticket = db.get(FailureTicket, ticket_id)
    if ticket is None:
        return None
    now = datetime.utcnow()
    if status is not None:
        normalized = _normalize_choice(status, FAILURE_TICKET_STATUSES, "")
        if not normalized:
            raise ValueError("Unsupported failure ticket status.")
        ticket.status = normalized
        if normalized == "acknowledged":
            ticket.acknowledged_at = ticket.acknowledged_at or now
        elif normalized == "fixed":
            ticket.fixed_at = ticket.fixed_at or now
        elif normalized == "ignored":
            ticket.ignored_at = ticket.ignored_at or now
    if admin_notes is not None:
        ticket.admin_notes = _clean_text(admin_notes, limit=MAX_TEXT)
    ticket.updated_at = now
    if commit:
        db.commit()
        db.refresh(ticket)
    return {"ticket": _ticket_detail(ticket)}
