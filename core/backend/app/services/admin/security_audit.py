from __future__ import annotations

import logging

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import SecurityAuditEvent, User

logger = logging.getLogger(__name__)


def client_ip_from_request(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def request_id_from_request(request: Request | None) -> str | None:
    if request is None:
        return None
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    header_request_id = request.headers.get("x-request-id")
    return header_request_id.strip() if header_request_id else None


def record_security_event(
    db: Session,
    *,
    action: str,
    result: str,
    actor: User | None = None,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request: Request | None = None,
    details: dict | None = None,
    commit: bool = False,
) -> SecurityAuditEvent:
    event = SecurityAuditEvent(
        id=generate_id("secaud"),
        actor_user_id=actor.id if actor is not None else None,
        actor_email=actor.email if actor is not None else actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        source_ip=client_ip_from_request(request),
        request_id=request_id_from_request(request),
        user_agent=request.headers.get("user-agent") if request is not None else None,
        details_json=details or None,
    )
    db.add(event)
    if commit:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Security audit event persistence failed", extra={"action": action, "result": result})
    return event
