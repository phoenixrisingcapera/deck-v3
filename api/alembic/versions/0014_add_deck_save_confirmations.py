"""add deck save confirmations

Revision ID: 0014_add_deck_save_confirmations
Revises: 0013_add_deck_llm_artifacts
Create Date: 2026-06-12 16:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_add_deck_save_confirmations"
down_revision = "0013_add_deck_llm_artifacts"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("deck_save_confirmations"):
        return

    op.create_table(
        "deck_save_confirmations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(), nullable=False, server_default="success"),
        sa.Column("cta_label", sa.String(), nullable=True),
        sa.Column("cta_href", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="confirmed"),
        sa.Column("source_surface", sa.String(), nullable=True),
        sa.Column("source_route", sa.String(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_deck_save_confirmations_deck_id", "deck_save_confirmations", ["deck_id"])
    op.create_index("ix_deck_save_confirmations_workspace_id", "deck_save_confirmations", ["workspace_id"])
    op.create_index("ix_deck_save_confirmations_user_id", "deck_save_confirmations", ["user_id"])
    op.create_index("ix_deck_save_confirmations_event_type", "deck_save_confirmations", ["event_type"])
    op.create_index("ix_deck_save_confirmations_entity_type", "deck_save_confirmations", ["entity_type"])
    op.create_index("ix_deck_save_confirmations_status", "deck_save_confirmations", ["status"])
    op.create_index("ix_deck_save_confirmations_dedupe_key", "deck_save_confirmations", ["dedupe_key"])
    op.create_index("ix_deck_save_confirmations_created_at", "deck_save_confirmations", ["created_at"])


def downgrade() -> None:
    if not _has_table("deck_save_confirmations"):
        return

    op.drop_index("ix_deck_save_confirmations_created_at", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_dedupe_key", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_status", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_entity_type", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_event_type", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_user_id", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_workspace_id", table_name="deck_save_confirmations")
    op.drop_index("ix_deck_save_confirmations_deck_id", table_name="deck_save_confirmations")
    op.drop_table("deck_save_confirmations")
