"""add ai usage quota buckets

Revision ID: 0025_ai_usage_buckets
Revises: 0024_rate_limit_buckets
Create Date: 2026-06-13 13:45:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0025_ai_usage_buckets"
down_revision = "0024_rate_limit_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if table already exists
    tables = inspector.get_table_names()
    
    if 'ai_usage_buckets' not in tables:
        op.create_table(
            "ai_usage_buckets",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quota_key", sa.String(), nullable=False),
            sa.Column("window_start", sa.DateTime(), nullable=False),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "quota_key", name="uq_ai_usage_buckets_user_quota"),
        )
        op.create_index("ix_ai_usage_buckets_user_id", "ai_usage_buckets", ["user_id"])
        op.create_index("ix_ai_usage_buckets_quota_key", "ai_usage_buckets", ["quota_key"])
        op.create_index("ix_ai_usage_buckets_window_start", "ai_usage_buckets", ["window_start"])
        op.create_index("ix_ai_usage_buckets_updated_at", "ai_usage_buckets", ["updated_at"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("ai_usage_buckets") as batch_op:
            batch_op.drop_constraint("uq_ai_usage_buckets_user_quota", type_="unique")
    else:
        op.drop_constraint("uq_ai_usage_buckets_user_quota", "ai_usage_buckets", type_="unique")
    op.drop_index("ix_ai_usage_buckets_updated_at", table_name="ai_usage_buckets")
    op.drop_index("ix_ai_usage_buckets_window_start", table_name="ai_usage_buckets")
    op.drop_index("ix_ai_usage_buckets_quota_key", table_name="ai_usage_buckets")
    op.drop_index("ix_ai_usage_buckets_user_id", table_name="ai_usage_buckets")
    op.drop_table("ai_usage_buckets")
