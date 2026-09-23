"""Provide durable budget reservations for the local shared-database mode.

Revision ID: 20260820_0001_local_ai_budget_reservations
Revises: 20260819_0002_smart_deck_preferred_model

The production topology keeps this table in the independent AI database.  In
local development ``AI_DATABASE_URL`` may deliberately be unset, in which
case quota operations share the Core session and still need their durable,
idempotent reservation record.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0001_local_ai_budget_reservations"
down_revision = "20260819_0002_smart_deck_preferred_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the reservation table without modifying historical quota rows."""
    inspector = sa.inspect(op.get_bind())
    if "ai_budget_reservations" not in inspector.get_table_names():
        op.create_table(
            "ai_budget_reservations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("reservation_key", sa.String(), nullable=False, unique=True),
            sa.Column("bucket_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("operation", sa.String(), nullable=False),
            sa.Column("estimated_tokens", sa.Integer(), nullable=False),
            sa.Column("actual_tokens", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="reserved"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        )

    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("ai_budget_reservations")}
    for column in ("reservation_key", "bucket_id", "user_id", "operation", "status", "created_at"):
        index_name = f"ix_ai_budget_reservations_{column}"
        if index_name not in indexes:
            op.create_index(index_name, "ai_budget_reservations", [column], unique=False)


def downgrade() -> None:
    # Reservation evidence is retained; forward migrations own retirement.
    pass
