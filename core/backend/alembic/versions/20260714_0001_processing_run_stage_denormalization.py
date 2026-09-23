"""denormalize processing stage columns on deck_extraction_runs

Revision ID: 20260714_0001_processing_run_stage
Revises: 20260625_0005_processing_checksum
Create Date: 2026-07-14 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260714_0001_processing_run_stage"
down_revision: Union[str, None] = "20260625_0005_processing_checksum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _table_exists("deck_extraction_runs"):
        return

    columns_to_add = [
        ("current_stage", sa.String(100), True),
        ("current_stage_label", sa.String(200), True),
        ("next_action", sa.String(100), True),
        ("attempt_count", sa.Integer(), True),
        ("max_attempts", sa.Integer(), True),
        ("locked_by", sa.String(200), True),
        ("locked_at", sa.DateTime(), True),
        ("heartbeat_at", sa.DateTime(), True),
    ]

    for col_name, col_type, nullable in columns_to_add:
        if not _column_exists("deck_extraction_runs", col_name):
            op.add_column(
                "deck_extraction_runs",
                sa.Column(col_name, col_type, nullable=nullable),
            )

    if not _column_exists("deck_extraction_runs", "ix_deck_extraction_runs_current_stage"):
        op.create_index(
            "ix_deck_extraction_runs_current_stage",
            "deck_extraction_runs",
            ["current_stage"],
        )


def downgrade() -> None:
    if not _table_exists("deck_extraction_runs"):
        return

    op.drop_index("ix_deck_extraction_runs_current_stage", table_name="deck_extraction_runs")

    for col_name in [
        "heartbeat_at",
        "locked_at",
        "locked_by",
        "max_attempts",
        "attempt_count",
        "next_action",
        "current_stage_label",
        "current_stage",
    ]:
        if _column_exists("deck_extraction_runs", col_name):
            op.drop_column("deck_extraction_runs", col_name)
