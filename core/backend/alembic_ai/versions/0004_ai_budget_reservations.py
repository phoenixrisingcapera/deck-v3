"""Add atomic AI budget reservation fields to the AI-owned quota table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_ai_budget_reservations"
down_revision = "0003_ai_contract_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "ai_usage_buckets" not in table_names:
        raise RuntimeError("AI migration requires AI-owned ai_usage_buckets")

    column_names = {
        column["name"] for column in inspector.get_columns("ai_usage_buckets")
    }
    if "reserved_count" not in column_names:
        op.add_column(
            "ai_usage_buckets",
            sa.Column("reserved_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if "reservation_key" not in column_names:
        op.add_column(
            "ai_usage_buckets",
            sa.Column("reservation_key", sa.String(), nullable=True),
        )

    # Refresh inspection after additive DDL so partially applied environments
    # can converge without duplicating indexes or constraints.
    inspector = sa.inspect(bind)
    index_names = {
        item["name"] for item in inspector.get_indexes("ai_usage_buckets")
    }
    if "ix_ai_usage_buckets_reservation_key" not in index_names:
        op.create_index(
            "ix_ai_usage_buckets_reservation_key",
            "ai_usage_buckets",
            ["reservation_key"],
            unique=False,
        )

    constraint_names = {
        item["name"] for item in inspector.get_unique_constraints("ai_usage_buckets")
    }
    if "uq_ai_usage_buckets_reservation_key" not in constraint_names:
        op.create_unique_constraint(
            "uq_ai_usage_buckets_reservation_key",
            "ai_usage_buckets",
            ["reservation_key"],
        )


def downgrade() -> None:
    # Preserve quota reservation data and the concurrency invariant. This
    # repository's migration policy uses forward corrective migrations.
    pass
