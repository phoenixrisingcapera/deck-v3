from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import AuthSession

def _jwt_timestamp_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value, UTC).replace(tzinfo=None)


def ensure_auth_sessions_table(db: Session) -> None:
    # DISABLED: auth_sessions is owned by CoreBase and created by the core
    # Alembic lineage. Runtime table creation masked failed migrations.
    return


def create_auth_session(db: Session, *, user_id: str, token_payload: dict) -> AuthSession:
    session = AuthSession(
        id=generate_id("authsess"),
        user_id=user_id,
        token_jti=token_payload["jti"],
        issued_at=_jwt_timestamp_to_datetime(int(token_payload["iat"])),
        expires_at=_jwt_timestamp_to_datetime(int(token_payload["exp"])),
    )
    db.add(session)
    db.flush()
    return session


def is_auth_session_active(db: Session, *, user_id: str, token_jti: str) -> bool:
    session = db.query(AuthSession).filter(AuthSession.token_jti == token_jti).one_or_none()
    if session is None:
        return False
    if session.user_id != user_id:
        return False
    if session.revoked_at is not None:
        return False
    return session.expires_at >= datetime.now(UTC).replace(tzinfo=None)


def revoke_auth_session(db: Session, *, user_id: str, token_jti: str) -> bool:
    session = db.query(AuthSession).filter(AuthSession.token_jti == token_jti).one_or_none()
    if session is None or session.user_id != user_id:
        return False
    if session.revoked_at is None:
        session.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        db.add(session)
        db.commit()
    return True
