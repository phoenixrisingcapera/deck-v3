"""add persistent rate limit buckets

Revision ID: 0024_rate_limit_buckets
Revises: 0023_security_audit_request_ids
Create Date: 2026-06-13 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0024_rate_limit_buckets"
down_revision = "0023_security_audit_request_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    tables = set(inspector.get_table_names())

    if "rate_limit_buckets" not in tables:
        op.create_table(
            "rate_limit_buckets",
            sa.Column("actor_key", sa.String(), primary_key=True),
            sa.Column("window_start", sa.DateTime(), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # Keep this migration idempotent for partially-applied Railway deploys.
    inspector = inspect(conn)
    indexes = {index["name"] for index in inspector.get_indexes("rate_limit_buckets")}

    if "ix_rate_limit_buckets_window_start" not in indexes:
        op.create_index(
            "ix_rate_limit_buckets_window_start",
            "rate_limit_buckets",
            ["window_start"],
        )

    if "ix_rate_limit_buckets_updated_at" not in indexes:
        op.create_index(
            "ix_rate_limit_buckets_updated_at",
            "rate_limit_buckets",
            ["updated_at"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    if "rate_limit_buckets" not in set(inspector.get_table_names()):
        return

    indexes = {index["name"] for index in inspector.get_indexes("rate_limit_buckets")}

    if "ix_rate_limit_buckets_updated_at" in indexes:
        op.drop_index("ix_rate_limit_buckets_updated_at", table_name="rate_limit_buckets")

    if "ix_rate_limit_buckets_window_start" in indexes:
        op.drop_index("ix_rate_limit_buckets_window_start", table_name="rate_limit_buckets")

    op.drop_table("rate_limit_buckets")
