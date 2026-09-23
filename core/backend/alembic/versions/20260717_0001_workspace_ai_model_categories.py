"""Add explicit reasoning and embedding model selections to workspace AI settings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0001_workspace_ai_model_categories"
down_revision = "20260716_0007_due_diligence_workflow_job"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspace_ai_provider_settings", sa.Column("reasoning_model", sa.String(), nullable=True))
    op.add_column("workspace_ai_provider_settings", sa.Column("embedding_model", sa.String(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE workspace_ai_provider_settings
            SET reasoning_model = COALESCE(preferred_model, 'qwen-plus-2025-07-28'),
                embedding_model = 'text-embedding-v3'
            WHERE provider IN ('qwen', 'dashscope')
            """
        )
    )


def downgrade() -> None:
    op.drop_column("workspace_ai_provider_settings", "embedding_model")
    op.drop_column("workspace_ai_provider_settings", "reasoning_model")
