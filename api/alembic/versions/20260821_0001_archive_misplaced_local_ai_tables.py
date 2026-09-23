"""Archive misplaced local-AI compatibility tables in split deployments.

Revision ID: 20260821_0001_archive_misplaced_local_ai_tables
Revises: 20260820_0004_deck_export_shares

The Core lineage historically creates two compatibility tables for local
development when no independent AI database is configured. A production
deployment with separate Core and AI databases must not expose those AI-owned
table names from Core. Preserve any rows by renaming the misplaced Core tables;
never copy from, alter, or drop the canonical AI tables.
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa


revision = "20260821_0001_archive_misplaced_local_ai_tables"
down_revision = "20260820_0004_deck_export_shares"
branch_labels = None
depends_on = None


ARCHIVE_TABLES = {
    "ai_budget_reservations": "legacy_core_ai_budget_reservations_20260820",
    "agent_telemetry_events": "legacy_core_agent_telemetry_events_20260820",
}


def _uses_split_ai_database() -> bool:
    core_url = str(os.getenv("DATABASE_URL") or "").strip()
    ai_url = str(os.getenv("AI_DATABASE_URL") or "").strip()
    return bool(core_url and ai_url and core_url != ai_url)


def upgrade() -> None:
    """Remove AI-owned names from Core while retaining every historical row."""
    if not _uses_split_ai_database():
        return

    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    for source_name, archive_name in ARCHIVE_TABLES.items():
        if source_name not in table_names:
            continue
        if archive_name in table_names:
            raise RuntimeError(
                f"Cannot archive {source_name}: preserved table {archive_name} already exists"
            )
        op.rename_table(source_name, archive_name)
        table_names.remove(source_name)
        table_names.add(archive_name)


def downgrade() -> None:
    # Archived evidence is deliberately retained under its unambiguous name.
    pass
