"""add workspace ai credential key versions

Revision ID: 0026_workspace_ai_key_versions
Revises: 0025_ai_usage_buckets
Create Date: 2026-06-13 14:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_workspace_ai_key_versions"
down_revision = "0025_ai_usage_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_ai_credentials",
        sa.Column("key_version", sa.String(), nullable=False, server_default="legacy"),
    )
    op.create_index(
        "ix_workspace_ai_credentials_key_version",
        "workspace_ai_credentials",
        ["key_version"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_ai_credentials_key_version", table_name="workspace_ai_credentials")
    op.drop_column("workspace_ai_credentials", "key_version")
