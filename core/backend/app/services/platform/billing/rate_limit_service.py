from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import RateLimitBucket


_requests: dict[str, deque[float]] = defaultdict(deque)


def _too_many_requests() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please try again later.",
    )


def _enforce_memory_rate_limit(actor_key: str, *, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    bucket = _requests[actor_key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()

    if len(bucket) >= limit:
        raise _too_many_requests()

    bucket.append(now)


def enforce_rate_limit(
    actor_key: str,
    *,
    limit: int,
    window_seconds: int,
    db: Session | None = None,
) -> None:
    if db is None:
        _enforce_memory_rate_limit(actor_key, limit=limit, window_seconds=window_seconds)
        return

    now = datetime.utcnow()
    window_delta = timedelta(seconds=window_seconds)
    try:
        bucket = (
            db.query(RateLimitBucket)
            .filter(RateLimitBucket.actor_key == actor_key)
            .with_for_update()
            .one_or_none()
        )
        if bucket is None:
            db.add(RateLimitBucket(actor_key=actor_key, window_start=now, request_count=1))
            db.commit()
            return

        if now - bucket.window_start >= window_delta:
            bucket.window_start = now
            bucket.request_count = 1
            bucket.updated_at = now
            db.commit()
            return

        if bucket.request_count >= limit:
            db.rollback()
            raise _too_many_requests()

        bucket.request_count += 1
        bucket.updated_at = now
        db.commit()
    except IntegrityError:
        db.rollback()
        enforce_rate_limit(actor_key, limit=limit, window_seconds=window_seconds, db=db)
    except SQLAlchemyError:
        db.rollback()
        _enforce_memory_rate_limit(actor_key, limit=limit, window_seconds=window_seconds)


def enforce_rate_limits(
    limits: list[tuple[str, int, int]],
    *,
    db: Session | None = None,
) -> None:
    if db is None:
        for actor_key, limit, window_seconds in limits:
            _enforce_memory_rate_limit(actor_key, limit=limit, window_seconds=window_seconds)
        return

    now = datetime.utcnow()
    try:
        actor_keys = sorted({actor_key for actor_key, _limit, _window_seconds in limits})
        existing = {
            bucket.actor_key: bucket
            for bucket in db.query(RateLimitBucket)
            .filter(RateLimitBucket.actor_key.in_(actor_keys))
            .with_for_update()
            .all()
        }

        for actor_key, limit, window_seconds in limits:
            bucket = existing.get(actor_key)
            window_delta = timedelta(seconds=window_seconds)
            if bucket is None:
                bucket = RateLimitBucket(actor_key=actor_key, window_start=now, request_count=1, updated_at=now)
                db.add(bucket)
                existing[actor_key] = bucket
                continue

            if now - bucket.window_start >= window_delta:
                bucket.window_start = now
                bucket.request_count = 1
                bucket.updated_at = now
                continue

            if bucket.request_count >= limit:
                db.rollback()
                raise _too_many_requests()

            bucket.request_count += 1
            bucket.updated_at = now

        db.commit()
    except IntegrityError:
        db.rollback()
        enforce_rate_limits(limits, db=db)
    except SQLAlchemyError:
        db.rollback()
        for actor_key, limit, window_seconds in limits:
            _enforce_memory_rate_limit(actor_key, limit=limit, window_seconds=window_seconds)
