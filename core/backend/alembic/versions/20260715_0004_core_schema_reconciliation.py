"""Merge Core migration branches and reconcile processing indexes.

The processing-stage denormalization work was accidentally split between the
legacy ``0021`` branch and the dated ``20260714`` branch.  Existing deployments
may contain either branch's physical schema, so this merge must be idempotent.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260715_0004_core_schema_reconciliation"
down_revision = ("0021_add_processing_stage_columns", "20260715_0003_core_developer_tools")
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # API and worker deployments must not concurrently create the same
        # reconciliation index while an older deployment is still draining.
        bind.execute(sa.text("SELECT pg_advisory_xact_lock(202607150004)"))

    inspector = sa.inspect(bind)
    if "deck_extraction_runs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("deck_extraction_runs")}
    if "status" not in columns or "current_stage" not in columns:
        return

    indexes = {index["name"] for index in inspector.get_indexes("deck_extraction_runs")}
    if "ix_deck_extraction_runs_status_stage" not in indexes:
        op.create_index(
            "ix_deck_extraction_runs_status_stage",
            "deck_extraction_runs",
            ["status", "current_stage"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "deck_extraction_runs" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("deck_extraction_runs")}
        if "ix_deck_extraction_runs_status_stage" in indexes:
            op.drop_index("ix_deck_extraction_runs_status_stage", table_name="deck_extraction_runs")
