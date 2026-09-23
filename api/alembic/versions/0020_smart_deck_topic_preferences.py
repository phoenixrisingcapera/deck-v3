"""add smart deck topic preferences

Revision ID: 0020_topic_preferences
Revises: 0019_batch_compiled_decks
Create Date: 2026-06-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_topic_preferences"
down_revision = "0019_batch_compiled_decks"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if not _has_table("smart_deck_preferences"):
        return

    columns = [
        ("audience", sa.String()),
        ("deck_type", sa.String()),
        ("selected_subject", sa.String()),
        ("selected_action_id", sa.String()),
    ]
    for column_name, column_type in columns:
        if not _has_column("smart_deck_preferences", column_name):
            op.add_column("smart_deck_preferences", sa.Column(column_name, column_type, nullable=True))


def downgrade() -> None:
    if not _has_table("smart_deck_preferences"):
        return

    for column_name in ["selected_action_id", "selected_subject", "deck_type", "audience"]:
        if _has_column("smart_deck_preferences", column_name):
            op.drop_column("smart_deck_preferences", column_name)
