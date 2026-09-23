"""repair security audit request id column

Revision ID: 0034_repair_security_audit_request_id
Revises: 0033_smart_deck_bucket_keys
Create Date: 2026-06-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0034_repair_security_audit_request_id"
down_revision = "0033_smart_deck_bucket_keys"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_column("security_audit_events", "request_id"):
        op.add_column("security_audit_events", sa.Column("request_id", sa.String(), nullable=True))

    if not _has_index("security_audit_events", "ix_security_audit_events_request_id"):
        op.create_index(
            "ix_security_audit_events_request_id",
            "security_audit_events",
            ["request_id"],
        )


def downgrade() -> None:
    if _has_index("security_audit_events", "ix_security_audit_events_request_id"):
        op.drop_index("ix_security_audit_events_request_id", table_name="security_audit_events")

    if _has_column("security_audit_events", "request_id"):
        op.drop_column("security_audit_events", "request_id")
