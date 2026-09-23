from __future__ import annotations

from typing import Any

from sqlalchemy import text


SMART_DECK_RUNTIME_REPAIR_DDL = (
    # Railway can start from a database whose Alembic history says "done" while
    # individual Smart Deck tables are missing. These CREATE IF NOT EXISTS
    # statements are the production safety net used by API and worker startup.
    """
    CREATE TABLE IF NOT EXISTS deck_generation_workspaces (
        id VARCHAR PRIMARY KEY,
        deck_id VARCHAR REFERENCES decks(id) ON DELETE CASCADE UNIQUE,
        generation_status VARCHAR DEFAULT 'idle',
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deck_generation_runs (
        id VARCHAR PRIMARY KEY,
        deck_generation_workspace_id VARCHAR REFERENCES deck_generation_workspaces(id) ON DELETE CASCADE,
        deck_id VARCHAR REFERENCES decks(id) ON DELETE CASCADE,
        status VARCHAR DEFAULT 'queued',
        provider VARCHAR DEFAULT 'mock',
        model VARCHAR,
        generation_mode VARCHAR DEFAULT 'mock',
        scope_type VARCHAR DEFAULT 'whole_deck',
        request_payload_json TEXT DEFAULT '{}',
        generated_deck_json TEXT,
        quality_score DOUBLE PRECISION,
        error_message TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deck_slide_versions (
        id VARCHAR PRIMARY KEY,
        deck_generation_workspace_id VARCHAR REFERENCES deck_generation_workspaces(id) ON DELETE CASCADE,
        generation_run_id VARCHAR REFERENCES deck_generation_runs(id) ON DELETE CASCADE,
        source_slide_id VARCHAR REFERENCES deck_slides(id) ON DELETE SET NULL,
        slide_index INTEGER DEFAULT 0,
        source_slide_title VARCHAR,
        version_number INTEGER DEFAULT 1,
        title VARCHAR DEFAULT '',
        status VARCHAR DEFAULT 'reviewable',
        generated_slide_json TEXT DEFAULT '{}',
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deck_feedback_events (
        id VARCHAR PRIMARY KEY,
        deck_generation_workspace_id VARCHAR REFERENCES deck_generation_workspaces(id) ON DELETE CASCADE,
        generation_run_id VARCHAR REFERENCES deck_generation_runs(id) ON DELETE SET NULL,
        slide_version_id VARCHAR REFERENCES deck_slide_versions(id) ON DELETE CASCADE,
        source_slide_id VARCHAR REFERENCES deck_slides(id) ON DELETE SET NULL,
        event_type VARCHAR DEFAULT 'unknown',
        notes TEXT,
        payload_json TEXT,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_deck_generation_workspaces_generation_status ON deck_generation_workspaces (generation_status)",
    "CREATE INDEX IF NOT EXISTS ix_deck_generation_runs_deck_generation_workspace_id ON deck_generation_runs (deck_generation_workspace_id)",
    "CREATE INDEX IF NOT EXISTS ix_deck_generation_runs_deck_id ON deck_generation_runs (deck_id)",
    "CREATE INDEX IF NOT EXISTS ix_deck_generation_runs_status ON deck_generation_runs (status)",
    "CREATE INDEX IF NOT EXISTS ix_deck_slide_versions_deck_generation_workspace_id ON deck_slide_versions (deck_generation_workspace_id)",
    "CREATE INDEX IF NOT EXISTS ix_deck_slide_versions_generation_run_id ON deck_slide_versions (generation_run_id)",
    "CREATE INDEX IF NOT EXISTS ix_deck_slide_versions_status ON deck_slide_versions (status)",
    "CREATE INDEX IF NOT EXISTS ix_deck_feedback_events_deck_generation_workspace_id ON deck_feedback_events (deck_generation_workspace_id)",
    "CREATE INDEX IF NOT EXISTS ix_deck_feedback_events_event_type ON deck_feedback_events (event_type)",
    "CREATE INDEX IF NOT EXISTS ix_deck_feedback_events_slide_version_id ON deck_feedback_events (slide_version_id)",
    "ALTER TABLE IF EXISTS deck_llm_artifacts ADD COLUMN IF NOT EXISTS bucket_payload_key VARCHAR",
)


def _is_postgres_executor(executor: Any) -> bool:
    """Return True when the executor is backed by PostgreSQL.

    The runtime repair is production safety net logic. On SQLite test fixtures we
    keep it as a no-op so the repair helper does not introduce dialect-specific
    churn into lightweight unit tests.
    """

    bind = getattr(executor, "bind", None)
    if bind is None:
        bind = getattr(executor, "engine", None)
    dialect = getattr(bind, "dialect", None)
    return bool(getattr(dialect, "name", "") == "postgresql")


def ensure_smart_deck_runtime_schema(executor: Any) -> None:
    """Repair the Smart Deck runtime schema before any worker or service queries.

    This keeps the live pipeline from failing on a stale deploy when the worker
    tries to delete generation-workspace rows, write source V1 generation runs,
    or touch the legacy bucket key column.
    """

    if not _is_postgres_executor(executor):
        return

    for statement in SMART_DECK_RUNTIME_REPAIR_DDL:
        executor.execute(text(statement))
