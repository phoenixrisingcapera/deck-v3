"""add auth sessions

Revision ID: 0022_auth_sessions
Revises: 0021_security_audit_events
Create Date: 2026-06-13 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_auth_sessions"
down_revision = "0021_security_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "auth_sessions" not in inspector.get_table_names():
        op.create_table(
            "auth_sessions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_jti", sa.String(), nullable=False),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    existing_indexes = {index["name"] for index in inspector.get_indexes("auth_sessions")}
    if "ix_auth_sessions_user_id" not in existing_indexes:
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    if "ix_auth_sessions_token_jti" not in existing_indexes:
        op.create_index("ix_auth_sessions_token_jti", "auth_sessions", ["token_jti"], unique=True)
    if "ix_auth_sessions_expires_at" not in existing_indexes:
        op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    if "ix_auth_sessions_revoked_at" not in existing_indexes:
        op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])


def downgrade() -> None:
    for index_name in [
        "ix_auth_sessions_revoked_at",
        "ix_auth_sessions_expires_at",
        "ix_auth_sessions_token_jti",
        "ix_auth_sessions_user_id",
    ]:
        op.drop_index(index_name, table_name="auth_sessions")
    op.drop_table("auth_sessions")
