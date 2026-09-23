"""Repair SQLite analysis-finding read columns skipped by the historical migration.

Revision ID: 20260822_0001_local_findings
Revises: 20260821_0001_archive_misplaced_local_ai_tables

The Due Diligence integrity migration is intentionally PostgreSQL-only, but
the shared deck graph is mounted by Instant Deck and selects these additive
finding columns on every supported database.  Repair both fresh and already
stamped local SQLite databases without rewriting or dropping finding rows.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260822_0001_local_findings"
down_revision = "20260821_0001_archive_misplaced_local_ai_tables"
branch_labels = None
depends_on = None


FINDING_COLUMNS = (
    sa.Column("report_id", sa.String(), nullable=True),
    sa.Column("analysis_run_id", sa.String(), nullable=True),
    sa.Column("audience", sa.String(), nullable=True),
    sa.Column("field_key", sa.String(), nullable=True),
    sa.Column("target_snapshot_json", sa.JSON(), nullable=True),
    sa.Column("evidence_json", sa.JSON(), nullable=True),
    sa.Column(
        "validation_verdict",
        sa.String(),
        nullable=False,
        server_default="unverified",
    ),
)

FINDING_INDEXES = {
    "ix_analysis_findings_report_id": ["report_id"],
    "ix_analysis_findings_analysis_run_id": ["analysis_run_id"],
    "ix_analysis_findings_audience": ["audience"],
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    inspector = sa.inspect(bind)
    if "analysis_findings" not in set(inspector.get_table_names()):
        return
    existing_columns = {
        str(item["name"])
        for item in inspector.get_columns("analysis_findings")
    }
    for column in FINDING_COLUMNS:
        if column.name not in existing_columns:
            op.add_column("analysis_findings", column)

    existing_indexes = {
        str(item["name"])
        for item in sa.inspect(bind).get_indexes("analysis_findings")
        if item.get("name")
    }
    for name, columns in FINDING_INDEXES.items():
        if name not in existing_indexes:
            op.create_index(name, "analysis_findings", columns)


def downgrade() -> None:
    # The repair is additive and may contain local historical evidence.
    pass
