"""workspace ai provider

Revision ID: 0004_workspace_ai_provider
Revises: 0003_interest_leads
Create Date: 2026-06-10 02:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_workspace_ai_provider"
down_revision = "0003_interest_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_ai_credentials",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("encrypted_api_key", sa.LargeBinary(), nullable=False),
        sa.Column("api_key_last4", sa.String(length=4), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspace_ai_credentials_provider"), "workspace_ai_credentials", ["provider"], unique=False)
    op.create_index(op.f("ix_workspace_ai_credentials_workspace_id"), "workspace_ai_credentials", ["workspace_id"], unique=False)

    op.create_table(
        "workspace_ai_provider_settings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("preferred_model", sa.String(), nullable=True),
        sa.Column("credential_id", sa.String(), nullable=True),
        sa.Column("use_for_smart_deck", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_for_smart_edit", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_for_analysis", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configured_at", sa.DateTime(), nullable=True),
        sa.Column("skipped_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["workspace_ai_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        op.f("ix_workspace_ai_provider_settings_provider"),
        "workspace_ai_provider_settings",
        ["provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workspace_ai_provider_settings_provider"), table_name="workspace_ai_provider_settings")
    op.drop_table("workspace_ai_provider_settings")
    op.drop_index(op.f("ix_workspace_ai_credentials_workspace_id"), table_name="workspace_ai_credentials")
    op.drop_index(op.f("ix_workspace_ai_credentials_provider"), table_name="workspace_ai_credentials")
    op.drop_table("workspace_ai_credentials")
