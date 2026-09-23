"""Add the persisted Smart Deck preferred model column.

Revision ID: 20260819_0002_smart_deck_preferred_model
Revises: 20260819_0001_workflow_job_type_constraint
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260819_0002_smart_deck_preferred_model"
down_revision = "20260819_0001_workflow_job_type_constraint"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return any(
        column.get("name") == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )


def upgrade() -> None:
    if _has_table("smart_deck_preferences") and not _has_column(
        "smart_deck_preferences", "preferred_model"
    ):
        op.add_column(
            "smart_deck_preferences",
            sa.Column("preferred_model", sa.String(), nullable=True),
        )


def downgrade() -> None:
    if _has_table("smart_deck_preferences") and _has_column(
        "smart_deck_preferences", "preferred_model"
    ):
        op.drop_column("smart_deck_preferences", "preferred_model")
