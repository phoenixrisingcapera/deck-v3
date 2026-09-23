"""Harden AI quota and learning contracts without removing data."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_ai_contract_hardening"
down_revision = "0002_ai_learning_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {item["name"] for item in inspector.get_unique_constraints("ai_usage_buckets")}
    if "uq_ai_usage_buckets_user_quota" not in constraints:
        duplicates = bind.execute(
            sa.text(
                "SELECT user_id, quota_key FROM ai_usage_buckets "
                "GROUP BY user_id, quota_key HAVING COUNT(*) > 1 LIMIT 1"
            )
        ).first()
        if duplicates is not None:
            raise RuntimeError("Cannot add AI quota uniqueness while duplicate buckets exist")
        op.create_unique_constraint(
            "uq_ai_usage_buckets_user_quota",
            "ai_usage_buckets",
            ["user_id", "quota_key"],
        )


def downgrade() -> None:
    # Preserve the concurrency invariant during rollback.
    pass
