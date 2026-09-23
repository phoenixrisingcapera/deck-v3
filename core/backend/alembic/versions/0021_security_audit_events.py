"""add security audit events

Revision ID: 0021_security_audit_events
Revises: 0020_topic_preferences
Create Date: 2026-06-13 09:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_security_audit_events"
down_revision = "0020_topic_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("source_ip", sa.String(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_security_audit_events_actor_user_id", "security_audit_events", ["actor_user_id"])
    op.create_index("ix_security_audit_events_action", "security_audit_events", ["action"])
    op.create_index("ix_security_audit_events_resource_type", "security_audit_events", ["resource_type"])
    op.create_index("ix_security_audit_events_resource_id", "security_audit_events", ["resource_id"])
    op.create_index("ix_security_audit_events_result", "security_audit_events", ["result"])
    op.create_index("ix_security_audit_events_created_at", "security_audit_events", ["created_at"])


def downgrade() -> None:
    for index_name in [
        "ix_security_audit_events_created_at",
        "ix_security_audit_events_result",
        "ix_security_audit_events_resource_id",
        "ix_security_audit_events_resource_type",
        "ix_security_audit_events_action",
        "ix_security_audit_events_actor_user_id",
    ]:
        op.drop_index(index_name, table_name="security_audit_events")
    op.drop_table("security_audit_events")
