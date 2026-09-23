from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _build_session_factory(url: str, *, pool_prefix: str):
    engine = create_engine(
        url,
        pool_pre_ping=True,
        # DISABLED: The 3+2 fallback exhausted under the deployed dashboard and
        # workflow smoke, producing 500s across graph, versions, and settings.
        # pool_size=...os.getenv("DB_POOL_SIZE", "3")
        # max_overflow=...os.getenv("DB_MAX_OVERFLOW", "2")
        pool_size=max(1, int(os.getenv(f"{pool_prefix}_POOL_SIZE", os.getenv("DB_POOL_SIZE", "5")))),
        max_overflow=max(0, int(os.getenv(f"{pool_prefix}_MAX_OVERFLOW", os.getenv("DB_MAX_OVERFLOW", "5")))),
        pool_timeout=max(1, int(os.getenv(f"{pool_prefix}_POOL_TIMEOUT_SECONDS", os.getenv("DB_POOL_TIMEOUT_SECONDS", "30")))),
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, factory


_engine = None
_engine_error: Exception | None = None
_session_factory = None

_ai_engine = None
_ai_engine_error: Exception | None = None
_ai_session_factory = None


def get_engine():
    global _engine, _engine_error, _session_factory
    if _engine is not None and _session_factory is not None:
        return _engine
    if _engine_error is not None:
        raise _engine_error
    try:
        _engine, _session_factory = _build_session_factory(settings.database_url, pool_prefix="CORE_DB")
        return _engine
    except Exception as exc:  # pragma: no cover
        _engine_error = exc
        raise


def SessionLocal() -> Session:
    global _session_factory
    get_engine()
    return _session_factory()


def get_ai_engine():
    """Get or create the independent AI database engine."""
    global _ai_engine, _ai_engine_error, _ai_session_factory
    if not str(settings.ai_database_url or "").strip():
        if settings.is_production:
            raise RuntimeError("AI_DATABASE_URL is required in production")
        # Local/unit-test mode may deliberately share the test engine. Production
        # validation never permits this compatibility path.
        return get_engine()
    if _ai_engine is not None and _ai_session_factory is not None:
        return _ai_engine
    if _ai_engine_error is not None:
        raise _ai_engine_error
    try:
        _ai_engine, _ai_session_factory = _build_session_factory(settings.ai_database_url, pool_prefix="AI_DB")
        return _ai_engine
    except Exception as exc:  # pragma: no cover
        _ai_engine_error = exc
        raise


def AiSessionLocal() -> Session:
    """Get a session for the independent AI database."""
    global _ai_session_factory
    if not str(settings.ai_database_url or "").strip():
        if settings.is_production:
            raise RuntimeError("AI_DATABASE_URL is required for AiSessionLocal")
        # Local/unit-test mode may deliberately share the test engine. Production
        # validation never permits this compatibility path.
        return SessionLocal()
    get_ai_engine()
    return _ai_session_factory()


# Backward-compatible attribute used by diagnostics.
engine = None
