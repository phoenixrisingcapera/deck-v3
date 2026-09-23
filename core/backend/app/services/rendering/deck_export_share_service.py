from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckExport, DeckExportShare
from app.services.rendering.export_service import shareable_html_export_payload


PUBLIC_SHARE_PREFIX = "/api/public/deck-shares"


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _share_item(share: DeckExportShare, design_version_id: str) -> dict[str, Any]:
    return {
        "shareId": share.id,
        "deckId": share.deck_id,
        "exportId": share.deck_export_id,
        "designVersionId": design_version_id,
        "status": share.status,
        "createdAt": share.created_at,
        "expiresAt": share.expires_at,
        "revokedAt": share.revoked_at,
        "lastAccessedAt": share.last_accessed_at,
        "accessCount": int(share.access_count or 0),
    }


def create_export_share(
    db: Session,
    *,
    deck_id: str,
    export_id: str,
    user_id: str,
    expires_in_days: int | None = None,
) -> dict[str, Any]:
    # Lock the immutable export row so concurrent rotations cannot leave two
    # owner-created active links for the same export.
    deck_export = (
        db.query(DeckExport)
        .filter(DeckExport.deck_id == deck_id, DeckExport.id == export_id)
        .with_for_update()
        .one_or_none()
    )
    if deck_export is None:
        raise ValueError("Export not found.")
    _verified_export, design_version_id = shareable_html_export_payload(db, deck_id, export_id)

    now = datetime.utcnow()
    active_shares = (
        db.query(DeckExportShare)
        .filter(
            DeckExportShare.deck_id == deck_id,
            DeckExportShare.deck_export_id == export_id,
            DeckExportShare.status == "active",
            DeckExportShare.revoked_at.is_(None),
        )
        .all()
    )
    for active in active_shares:
        active.status = "revoked"
        active.revoked_at = now

    share_token = secrets.token_urlsafe(32)
    share = DeckExportShare(
        id=generate_id("deckshare"),
        deck_export_id=export_id,
        deck_id=deck_id,
        token_hash=_token_hash(share_token),
        created_by_user_id=user_id,
        status="active",
        expires_at=now + timedelta(days=expires_in_days) if expires_in_days is not None else None,
        access_count=0,
        created_at=now,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return _share_item(share, design_version_id) | {
        "shareToken": share_token,
        "publicPath": f"{PUBLIC_SHARE_PREFIX}/{share.id}/{share_token}",
    }


def list_export_shares(db: Session, *, deck_id: str, export_id: str) -> list[dict[str, Any]]:
    _deck_export, design_version_id = shareable_html_export_payload(db, deck_id, export_id)
    shares = (
        db.query(DeckExportShare)
        .filter(DeckExportShare.deck_id == deck_id, DeckExportShare.deck_export_id == export_id)
        .order_by(DeckExportShare.created_at.desc(), DeckExportShare.id.desc())
        .all()
    )
    return [_share_item(share, design_version_id) for share in shares]


def revoke_export_share(
    db: Session,
    *,
    deck_id: str,
    export_id: str,
    share_id: str,
) -> dict[str, Any] | None:
    _deck_export, design_version_id = shareable_html_export_payload(db, deck_id, export_id)
    share = (
        db.query(DeckExportShare)
        .filter(
            DeckExportShare.id == share_id,
            DeckExportShare.deck_id == deck_id,
            DeckExportShare.deck_export_id == export_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if share is None:
        return None
    if share.status != "revoked" or share.revoked_at is None:
        share.status = "revoked"
        share.revoked_at = datetime.utcnow()
        db.commit()
        db.refresh(share)
    return _share_item(share, design_version_id)


def resolve_public_export_share(
    db: Session,
    *,
    share_id: str,
    share_token: str,
) -> tuple[str, str, str] | None:
    """Return persisted HTML, deck ID, and DesignVersion ID for a valid link."""
    if not share_token or len(share_token) > 256:
        return None
    share = (
        db.query(DeckExportShare)
        .filter(DeckExportShare.id == share_id)
        .with_for_update()
        .one_or_none()
    )
    if share is None or not secrets.compare_digest(share.token_hash, _token_hash(share_token)):
        return None
    now = datetime.utcnow()
    if share.status != "active" or share.revoked_at is not None or (share.expires_at is not None and share.expires_at <= now):
        return None
    try:
        deck_export, design_version_id = shareable_html_export_payload(
            db,
            share.deck_id,
            share.deck_export_id,
        )
    except ValueError:
        return None
    content = deck_export.content
    deck_id = share.deck_id
    share.last_accessed_at = now
    share.access_count = int(share.access_count or 0) + 1
    db.commit()
    # The database transaction is complete before the response body is handed
    # to the ASGI server. No provider, queue, compiler, or storage wait occurs.
    return content, deck_id, design_version_id
