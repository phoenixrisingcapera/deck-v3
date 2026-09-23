from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import AiBudgetReservation, AiUsageBucket, User
from app.db.session import AiSessionLocal

DAILY_AI_QUOTA_KEY = "daily_generation"
DAILY_AI_QUOTA_WINDOW_SECONDS = 24 * 60 * 60
CONSERVATIVE_OPERATION_LIMITS = {
    "smart_deck_generation": 200_000,
    "smart_deck_retry": 80_000,
    "smart_edit": 40_000,
    "due_diligence": 120_000,
}


def _quota_exceeded() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Daily AI generation quota exceeded. Please try again later.",
    )


def enforce_ai_generation_quota(
    db: Session,
    user: User,
    *,
    units: int = 1,
    quota: int | None = None,
    window_seconds: int = DAILY_AI_QUOTA_WINDOW_SECONDS,
) -> None:
    allowed = quota if quota is not None else settings.ai_daily_generation_quota
    if allowed <= 0:
        raise _quota_exceeded()
    if units <= 0:
        return

    quota_db = AiSessionLocal() if settings.ai_database_url else db
    owns_quota_session = quota_db is not db

    def close_quota_session() -> None:
        if owns_quota_session:
            quota_db.close()

    now = datetime.utcnow()
    window_delta = timedelta(seconds=window_seconds)
    try:
        bucket = (
            quota_db.query(AiUsageBucket)
            .filter(AiUsageBucket.user_id == user.id, AiUsageBucket.quota_key == DAILY_AI_QUOTA_KEY)
            .with_for_update()
            .one_or_none()
        )
        if bucket is None:
            if units > allowed:
                close_quota_session()
                raise _quota_exceeded()
            quota_db.add(
                AiUsageBucket(
                    id=generate_id("aiusage"),
                    user_id=user.id,
                    quota_key=DAILY_AI_QUOTA_KEY,
                    window_start=now,
                    usage_count=units,
                    updated_at=now,
                )
            )
            quota_db.commit()
            close_quota_session()
            return

        if now - bucket.window_start >= window_delta:
            if units > allowed:
                close_quota_session()
                raise _quota_exceeded()
            bucket.window_start = now
            bucket.usage_count = units
            bucket.updated_at = now
            quota_db.commit()
            close_quota_session()
            return

        if bucket.usage_count + units > allowed:
            quota_db.rollback()
            close_quota_session()
            raise _quota_exceeded()

        bucket.usage_count += units
        bucket.updated_at = now
        quota_db.commit()
        close_quota_session()
    except IntegrityError:
        quota_db.rollback()
        close_quota_session()
        enforce_ai_generation_quota(db, user, units=units, quota=allowed, window_seconds=window_seconds)
    finally:
        # The AI database can be separate from the request's core database.
        # Always release its connection, including quota and query failures.
        close_quota_session()


def reserve_ai_operation_budget(
    db: Session,
    user: User,
    *,
    operation: str,
    reservation_key: str,
    estimated_tokens: int,
    daily_limit: int,
) -> AiUsageBucket:
    """Atomically reserve an idempotent operation budget before provider work."""
    operation_limit = CONSERVATIVE_OPERATION_LIMITS.get(operation)
    if operation_limit is None or estimated_tokens <= 0 or estimated_tokens > operation_limit:
        raise _quota_exceeded()
    quota_db = AiSessionLocal() if settings.ai_database_url else db
    try:
        existing = quota_db.query(AiBudgetReservation).filter(AiBudgetReservation.reservation_key == reservation_key).one_or_none()
        if existing is not None:
            return quota_db.query(AiUsageBucket).filter(AiUsageBucket.id == existing.bucket_id).one()
        now = datetime.utcnow()
        bucket = (
            quota_db.query(AiUsageBucket)
            .filter(AiUsageBucket.user_id == user.id, AiUsageBucket.quota_key == DAILY_AI_QUOTA_KEY)
            .with_for_update()
            .one_or_none()
        )
        if bucket is None:
            # NEW: PostgreSQL row locks cannot protect a row that does not yet
            # exist. Insert the unique aggregate first, then retry after an
            # insert race so every concurrent reservation locks the same row.
            bucket = AiUsageBucket(
                id=generate_id("aiusage"),
                user_id=user.id,
                quota_key=DAILY_AI_QUOTA_KEY,
                window_start=now,
                usage_count=0,
                reserved_count=0,
            )
            quota_db.add(bucket)
            try:
                quota_db.flush()
            except IntegrityError:
                quota_db.rollback()
                return reserve_ai_operation_budget(
                    db,
                    user,
                    operation=operation,
                    reservation_key=reservation_key,
                    estimated_tokens=estimated_tokens,
                    daily_limit=daily_limit,
                )
        if now - bucket.window_start >= timedelta(seconds=DAILY_AI_QUOTA_WINDOW_SECONDS):
            bucket.window_start = now
            bucket.usage_count = 0
            bucket.reserved_count = 0
        if bucket.usage_count + bucket.reserved_count + estimated_tokens > daily_limit:
            quota_db.rollback()
            raise _quota_exceeded()
        bucket.reserved_count += estimated_tokens
        bucket.updated_at = now
        quota_db.add(AiBudgetReservation(
            id=generate_id("aibudget"),
            reservation_key=reservation_key,
            bucket_id=bucket.id,
            user_id=user.id,
            operation=operation,
            estimated_tokens=estimated_tokens,
            status="reserved",
        ))
        quota_db.commit()
        quota_db.refresh(bucket)
        return bucket
    except IntegrityError:
        quota_db.rollback()
        existing = quota_db.query(AiBudgetReservation).filter(AiBudgetReservation.reservation_key == reservation_key).one_or_none()
        if existing is None:
            raise _quota_exceeded()
        return quota_db.query(AiUsageBucket).filter(AiUsageBucket.id == existing.bucket_id).one()
    finally:
        if quota_db is not db:
            quota_db.close()


def reconcile_ai_operation_budget(
    db: Session,
    *,
    reservation_key: str,
    actual_tokens: int,
) -> None:
    """Replace a reservation with actual usage exactly once."""
    quota_db = AiSessionLocal() if settings.ai_database_url else db
    try:
        reservation = (
            quota_db.query(AiBudgetReservation)
            .filter(AiBudgetReservation.reservation_key == reservation_key)
            .with_for_update()
            .one_or_none()
        )
        if reservation is None or reservation.status == "reconciled":
            return
        bucket = quota_db.query(AiUsageBucket).filter(AiUsageBucket.id == reservation.bucket_id).with_for_update().one()
        bucket.usage_count += max(0, actual_tokens)
        bucket.reserved_count = max(0, bucket.reserved_count - reservation.estimated_tokens)
        bucket.updated_at = datetime.utcnow()
        reservation.actual_tokens = max(0, actual_tokens)
        reservation.status = "reconciled"
        reservation.reconciled_at = datetime.utcnow()
        quota_db.commit()
    finally:
        if quota_db is not db:
            quota_db.close()


def ai_operation_budget_status(db: Session, *, reservation_key: str) -> str | None:
    """Read the durable reservation outcome without mutating quota."""
    quota_db = AiSessionLocal() if settings.ai_database_url else db
    try:
        reservation = quota_db.query(AiBudgetReservation).filter(
            AiBudgetReservation.reservation_key == reservation_key
        ).one_or_none()
        return reservation.status if reservation is not None else None
    finally:
        if quota_db is not db:
            quota_db.close()


def cancel_ai_operation_budget(db: Session, *, reservation_key: str) -> bool:
    """Release an unused reservation exactly once.

    Reconciled reservations represent consumed usage and cannot be rewritten as
    refunds by this abstraction. Reserved capacity can be truthfully cancelled.
    """
    quota_db = AiSessionLocal() if settings.ai_database_url else db
    try:
        reservation = (
            quota_db.query(AiBudgetReservation)
            .filter(AiBudgetReservation.reservation_key == reservation_key)
            .with_for_update()
            .one_or_none()
        )
        if reservation is None or reservation.status == "cancelled":
            return reservation is not None
        if reservation.status == "reconciled":
            return False
        bucket = quota_db.query(AiUsageBucket).filter(AiUsageBucket.id == reservation.bucket_id).with_for_update().one()
        bucket.reserved_count = max(0, bucket.reserved_count - reservation.estimated_tokens)
        bucket.updated_at = datetime.utcnow()
        reservation.status = "cancelled"
        reservation.actual_tokens = 0
        reservation.reconciled_at = datetime.utcnow()
        quota_db.commit()
        return True
    finally:
        if quota_db is not db:
            quota_db.close()


def cancel_ai_operation_budget_owner_bound(
    db: Session,
    *,
    reservation_key: str,
    expected_user_id: str,
    expected_operation: str,
    expected_quota_key: str,
) -> str:
    """Cancel only when reservation and bucket ownership exactly agree.

    The returned category is intentionally bounded and contains no customer or
    provider content. The reservation and bucket stay locked through any
    mutation so callers can safely reconcile the independent core record.
    """
    quota_db = AiSessionLocal() if settings.ai_database_url else db
    try:
        reservation = (
            quota_db.query(AiBudgetReservation)
            .filter(AiBudgetReservation.reservation_key == reservation_key)
            .with_for_update()
            .one_or_none()
        )
        if reservation is None:
            return "missing"
        bucket = (
            quota_db.query(AiUsageBucket)
            .filter(AiUsageBucket.id == reservation.bucket_id)
            .with_for_update()
            .one_or_none()
        )
        if (
            bucket is None
            or reservation.reservation_key != reservation_key
            or reservation.user_id != expected_user_id
            or reservation.operation != expected_operation
            or bucket.user_id != expected_user_id
            or bucket.quota_key != expected_quota_key
            or reservation.bucket_id != bucket.id
            or int(reservation.estimated_tokens or 0) <= 0
            or int(bucket.usage_count or 0) < 0
            or int(bucket.reserved_count or 0) < 0
        ):
            return "ownership_mismatch"
        if reservation.status not in {"reserved", "cancelled", "reconciled"}:
            return "unknown_status"
        if reservation.status == "reserved" and (
            reservation.actual_tokens is not None
            or reservation.reconciled_at is not None
        ):
            return "accounting_mismatch"
        if reservation.status == "cancelled" and (
            reservation.actual_tokens != 0
            or reservation.reconciled_at is None
        ):
            return "accounting_mismatch"
        if reservation.status == "reconciled" and (
            reservation.actual_tokens is None
            or int(reservation.actual_tokens) < 0
            or reservation.reconciled_at is None
            or int(bucket.usage_count or 0) < int(reservation.actual_tokens)
        ):
            return "accounting_mismatch"
        reserved_rows = (
            quota_db.query(AiBudgetReservation)
            .filter(
                AiBudgetReservation.bucket_id == bucket.id,
                AiBudgetReservation.status == "reserved",
            )
            .with_for_update()
            .all()
        )
        if any(
            int(row.estimated_tokens or 0) <= 0
            or row.user_id != expected_user_id
            or row.actual_tokens is not None
            or row.reconciled_at is not None
            for row in reserved_rows
        ):
            return "accounting_mismatch"
        expected_reserved_count = sum(int(row.estimated_tokens) for row in reserved_rows)
        if int(bucket.reserved_count or 0) != expected_reserved_count:
            return "accounting_mismatch"
        if reservation.status == "reconciled":
            reconciled_rows = (
                quota_db.query(AiBudgetReservation)
                .filter(
                    AiBudgetReservation.bucket_id == bucket.id,
                    AiBudgetReservation.status == "reconciled",
                )
                .with_for_update()
                .all()
            )
            if any(
                row.user_id != expected_user_id
                or row.reconciled_at is None
                or row.actual_tokens is None
                or int(row.actual_tokens) < 0
                for row in reconciled_rows
            ):
                return "accounting_mismatch"
            current_window_actual_tokens = sum(
                int(row.actual_tokens)
                for row in reconciled_rows
                if row.reconciled_at >= bucket.window_start
            )
            if int(bucket.usage_count or 0) < current_window_actual_tokens:
                return "accounting_mismatch"
        if reservation.status == "reserved":
            bucket.reserved_count -= reservation.estimated_tokens
            bucket.updated_at = datetime.utcnow()
            reservation.status = "cancelled"
            reservation.actual_tokens = 0
            reservation.reconciled_at = datetime.utcnow()
            quota_db.commit()
            return "cancelled"
        if reservation.status == "cancelled":
            return "already_cancelled"
        if reservation.status == "reconciled":
            return "reconciled"
        raise RuntimeError("Owner-bound cancellation reached an unsupported status.")
    except Exception:
        quota_db.rollback()
        raise
    finally:
        if quota_db is not db:
            quota_db.close()


def actual_tokens_from_usage(usage: dict | None) -> int:
    """Return the provider-reported total without retaining provider content."""
    if not isinstance(usage, dict):
        return 0
    return max(
        0,
        int(
            usage.get("total_tokens")
            or usage.get("totalTokens")
            or (int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0))
        ),
    )
