"""repair auth sessions table

Revision ID: 0027_repair_auth_sessions_table
Revises: 0026_workspace_ai_key_versions
Create Date: 2026-06-15 13:35:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0027_repair_auth_sessions_table"
down_revision = "0026_workspace_ai_key_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "auth_sessions" in inspector.get_table_names():
        return

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
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_jti", "auth_sessions", ["token_jti"], unique=True)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"])


def downgrade() -> None:
    # This repair migration is intentionally non-destructive on downgrade.
    # The canonical table lifecycle remains documented in 0022_auth_sessions.
    pass
