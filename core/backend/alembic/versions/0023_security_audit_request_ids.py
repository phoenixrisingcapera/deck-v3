"""add request ids to security audit events

Revision ID: 0023_security_audit_request_ids
Revises: 0022_auth_sessions
Create Date: 2026-06-13 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0023_security_audit_request_ids"
down_revision = "0022_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists before adding
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('security_audit_events')]
    
    if 'request_id' not in columns:
        op.add_column("security_audit_events", sa.Column("request_id", sa.String(), nullable=True))
    
    # Check if index already exists before creating
    indexes = [idx['name'] for idx in inspector.get_indexes('security_audit_events')]
    if 'ix_security_audit_events_request_id' not in indexes:
        op.create_index("ix_security_audit_events_request_id", "security_audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_events_request_id", table_name="security_audit_events")
    op.drop_column("security_audit_events", "request_id")

