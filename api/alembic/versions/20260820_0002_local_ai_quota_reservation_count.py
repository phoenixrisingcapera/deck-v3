"""Align local shared quota buckets with durable reservation accounting.

Revision ID: 20260820_0002_local_ai_quota_reservation_count
Revises: 20260820_0001_local_ai_budget_reservations
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0002_local_ai_quota_reservation_count"
down_revision = "20260820_0001_local_ai_budget_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the local reservation counter without changing quota usage."""
    inspector = sa.inspect(op.get_bind())
    if "ai_usage_buckets" not in inspector.get_table_names():
        # Production keeps quota buckets in the separate AI database. The Core
        # table only exists when local development shares one database.
        return
    try:
        columns = {
            item["name"]
            for item in inspector.get_columns("ai_usage_buckets")
        }
    except sa.exc.NoSuchTableError:
        # A split production topology can expose a stale/reflected table name
        # while the Core connection has no Core-owned quota table. Treat that
        # the same as the authoritative absent-table case above; the AI
        # lineage owns the production quota schema.
        return
    if "reserved_count" not in columns:
        op.add_column(
            "ai_usage_buckets",
            sa.Column("reserved_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    # Keep quota reservation history and counters intact.
    pass
