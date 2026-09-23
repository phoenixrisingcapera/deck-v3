"""Alembic environment for AI database migrations.

This migration chain targets the AI database (AI_DATABASE_URL) and only
includes AI-specific tables: vector_chunks, agent_telemetry_events,
agent_regression_cases, agent_learning_memories, ai_runs, ai_run_steps,
ai_usage_buckets.

When AI_DATABASE_URL is not configured, this migration chain is a no-op.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import String, engine_from_config, inspect, pool, text

os.environ.setdefault("APP_ROLE", "ai-migration")

from app.core.config import settings
from app.db.base import AiBase

# Import only AI models to ensure their tables are in the metadata
from app.db.models import ai as ai_models  # noqa: F401

config = context.config

# Only configure if AI_DATABASE_URL is set
if settings.ai_database_url:
    config.set_main_option("sqlalchemy.url", settings.ai_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Only include AI tables in metadata
AI_TABLE_NAMES = {
    "vector_chunks",
    "agent_telemetry_events",
    "agent_regression_cases",
    "agent_learning_memories",
    "ai_runs",
    "ai_run_steps",
    "ai_usage_buckets",
    "embedding_model_registry",
    "embedding_ingestion_runs",
    "retrieval_traces",
    "ai_dead_letters",
}

target_metadata = AiBase.metadata


def filter_metadata_for_ai():
    """Create a metadata object containing only AI tables."""
    from sqlalchemy import MetaData
    ai_metadata = MetaData()
    for table_name in AI_TABLE_NAMES:
        if table_name in AiBase.metadata.tables:
            table = AiBase.metadata.tables[table_name]
            table.tometadata(ai_metadata)
    return ai_metadata


target_metadata = filter_metadata_for_ai()


def widen_alembic_version_column(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if "alembic_version_ai" not in table_names and "alembic_version" in table_names:
        connection.execute(text("ALTER TABLE alembic_version RENAME TO alembic_version_ai"))
        connection.commit()
        table_names.add("alembic_version_ai")
    if "alembic_version_ai" not in table_names:
        return
    columns = {
        column["name"]: column
        for column in inspector.get_columns("alembic_version_ai")
    }
    version_column = columns.get("version_num")
    if version_column is None:
        return
    column_type = version_column["type"]
    current_length = getattr(column_type, "length", None)
    if current_length is None or current_length < 255:
        connection.execute(
            text("ALTER TABLE alembic_version_ai ALTER COLUMN version_num TYPE VARCHAR(255)")
        )
        connection.commit()


def use_wide_ai_version_type_for_table_creation() -> None:
    """Override Alembic 1.13's hard-coded VARCHAR(32) for a new AI table."""
    context.get_context()._version.c.version_num.type = String(255)


def run_migrations_offline() -> None:
    if not settings.ai_database_url:
        return

    context.configure(
        url=settings.ai_database_url,
        target_metadata=target_metadata,
        version_table="alembic_version_ai",
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    use_wide_ai_version_type_for_table_creation()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if not settings.ai_database_url:
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        widen_alembic_version_column(connection)
        # SQLAlchemy inspection starts an implicit transaction even when no
        # widening DDL runs. Close it so Alembic owns and commits the migration.
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version_ai",
        )
        use_wide_ai_version_type_for_table_creation()
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
