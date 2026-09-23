"""add shell workspace preference persistence

Revision ID: 0007_shell_workspace_preferences
Revises: 0006_smart_deck_intake_sources
Create Date: 2026-06-10 02:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_shell_workspace_preferences"
down_revision = "0006_smart_deck_intake_sources"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "deck_workspace_preferences" not in existing:
        op.create_table(
            "deck_workspace_preferences",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("active_tool", sa.String(), nullable=False, server_default="slides"),
            sa.Column("left_panel_open", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("selected_element_type", sa.String(), nullable=True),
            sa.Column("selected_data_view", sa.String(), nullable=True),
            sa.Column("chat_open", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("deck_id", "user_id", name="uq_deck_workspace_preferences_deck_user"),
        )
        op.create_index(
            op.f("ix_deck_workspace_preferences_deck_id"),
            "deck_workspace_preferences",
            ["deck_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_deck_workspace_preferences_user_id"),
            "deck_workspace_preferences",
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    existing = _existing_tables()

    if "deck_workspace_preferences" in existing:
        op.drop_index(op.f("ix_deck_workspace_preferences_user_id"), table_name="deck_workspace_preferences")
        op.drop_index(op.f("ix_deck_workspace_preferences_deck_id"), table_name="deck_workspace_preferences")
        op.drop_table("deck_workspace_preferences")
