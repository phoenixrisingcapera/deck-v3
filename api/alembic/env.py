from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from sqlalchemy import String, engine_from_config, inspect, pool, text

os.environ.setdefault("APP_ROLE", "core-migration")

from app.core.config import settings
from app.db.base import CoreBase
from app.db import models as model_registry  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = CoreBase.metadata


def configured_core_revision_ids() -> frozenset[str]:
    """Return exact revision IDs from this environment's configured core graph."""
    script = ScriptDirectory.from_config(config)
    return frozenset(revision.revision for revision in script.walk_revisions())


def hand_off_legacy_core_version_table(connection) -> None:
    """Preserve a legacy core stamp; never silently replay from an empty new table."""
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if "alembic_version" not in table_names:
        return
    legacy_rows = connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalars().all()
    if not legacy_rows:
        return
    if "alembic_version_core" in table_names:
        raise RuntimeError(
            "Populated legacy alembic_version and alembic_version_core both exist. "
            "Migration state is ambiguous; reconcile the version tables explicitly before retrying."
        )
    columns = inspector.get_columns("alembic_version")
    valid_core_revisions = configured_core_revision_ids()
    if (
        len(columns) != 1
        or columns[0].get("name") != "version_num"
        or not valid_core_revisions
        or len(set(legacy_rows)) != len(legacy_rows)
        or any(
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or value not in valid_core_revisions
            for value in legacy_rows
        )
    ):
        raise RuntimeError(
            "Populated legacy alembic_version has an unexpected shape or a stamp "
            "outside the configured core Alembic graph. "
            "Reconcile it explicitly before retrying core migrations."
        )
    connection.execute(text("ALTER TABLE alembic_version RENAME TO alembic_version_core"))
    connection.commit()


def widen_alembic_version_column(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())
    if "alembic_version_core" not in table_names:
        return
    columns = {
        column["name"]: column
        for column in inspector.get_columns("alembic_version_core")
    }
    version_column = columns.get("version_num")
    if version_column is None:
        return
    column_type = version_column["type"]
    current_length = getattr(column_type, "length", None)
    if current_length is not None and current_length < 255:
        connection.execute(
            text("ALTER TABLE alembic_version_core ALTER COLUMN version_num TYPE VARCHAR(255)")
        )
        connection.commit()


def use_wide_core_version_type_for_table_creation() -> None:
    """Override Alembic 1.13's hard-coded VARCHAR(32) for a new core table."""
    context.get_context()._version.c.version_num.type = String(255)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        version_table="alembic_version_core",
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    use_wide_core_version_type_for_table_creation()
    with context.begin_transaction():
        context.run_migrations()



def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        hand_off_legacy_core_version_table(connection)
        widen_alembic_version_column(connection)
        # SQLAlchemy inspection starts an implicit transaction even when no
        # widening DDL runs. Close it so Alembic owns and commits the migration.
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version_core",
        )
        use_wide_core_version_type_for_table_creation()
        with context.begin_transaction():
            context.run_migrations()



if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
