"""repair missing deck generation workspace table

Revision ID: 0036_repair_deck_generation_workspaces
Revises: 0035_failure_tickets
Create Date: 2026-07-03 10:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0036_repair_deck_generation_workspaces"
down_revision = "0035_failure_tickets"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "deck_generation_workspaces" not in existing:
        op.create_table(
            "deck_generation_workspaces",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("generation_status", sa.String(), nullable=False, server_default="idle"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("deck_id"),
        )
        op.create_index(
            op.f("ix_deck_generation_workspaces_deck_id"),
            "deck_generation_workspaces",
            ["deck_id"],
            unique=True,
        )
        op.create_index(
            op.f("ix_deck_generation_workspaces_generation_status"),
            "deck_generation_workspaces",
            ["generation_status"],
            unique=False,
        )


def downgrade() -> None:
    existing = _existing_tables()

    if "deck_generation_workspaces" in existing:
        op.drop_index(op.f("ix_deck_generation_workspaces_generation_status"), table_name="deck_generation_workspaces")
        op.drop_index(op.f("ix_deck_generation_workspaces_deck_id"), table_name="deck_generation_workspaces")
        op.drop_table("deck_generation_workspaces")
