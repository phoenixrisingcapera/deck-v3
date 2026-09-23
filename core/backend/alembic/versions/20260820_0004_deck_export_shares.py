"""Add revocable public capabilities for persisted HTML deck exports.

Revision ID: 20260820_0004_deck_export_shares
Revises: 20260820_0003_local_ai_telemetry_events
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0004_deck_export_shares"
down_revision = "20260820_0003_local_ai_telemetry_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the additive share table without rewriting existing exports."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "deck_export_shares" not in inspector.get_table_names():
        op.create_table(
            "deck_export_shares",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "deck_export_id",
                sa.String(),
                sa.ForeignKey("deck_exports.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "deck_id",
                sa.String(),
                sa.ForeignKey("decks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "created_by_user_id",
                sa.String(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
            sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("status in ('active','revoked')", name="ck_deck_export_shares_status"),
            sa.UniqueConstraint("token_hash", name="uq_deck_export_shares_token_hash"),
        )

    inspector = sa.inspect(bind)
    existing_indexes = {item["name"] for item in inspector.get_indexes("deck_export_shares")}
    for column in (
        "deck_export_id",
        "deck_id",
        "token_hash",
        "created_by_user_id",
        "status",
        "expires_at",
        "revoked_at",
        "created_at",
    ):
        index_name = f"ix_deck_export_shares_{column}"
        if index_name not in existing_indexes:
            op.create_index(index_name, "deck_export_shares", [column], unique=column == "token_hash")


def downgrade() -> None:
    # Public-link audit records are durable. A downgrade must not silently
    # delete link history or alter the DeckExport artifacts they reference.
    pass
