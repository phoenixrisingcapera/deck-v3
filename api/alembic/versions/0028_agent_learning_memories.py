"""agent learning memories

Revision ID: 0028_agent_learning_memories
Revises: 0027_repair_auth_sessions_table
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_agent_learning_memories"
down_revision = "0027_repair_auth_sessions_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DISABLED for the core lineage: AI persistence is created by alembic_ai.
    return
    op.create_table(
        "agent_learning_memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_run_id", sa.String(), nullable=True),
        sa.Column("source_run_type", sa.String(), nullable=True),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("feedback_label", sa.String(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source_run_id", "memory_type", name="uq_agent_learning_memory_source_type"),
    )
    op.create_index("ix_agent_learning_memories_workspace_id", "agent_learning_memories", ["workspace_id"])
    op.create_index("ix_agent_learning_memories_deck_id", "agent_learning_memories", ["deck_id"])
    op.create_index("ix_agent_learning_memories_user_id", "agent_learning_memories", ["user_id"])
    op.create_index("ix_agent_learning_memories_source_run_id", "agent_learning_memories", ["source_run_id"])
    op.create_index("ix_agent_learning_memories_source_run_type", "agent_learning_memories", ["source_run_type"])
    op.create_index("ix_agent_learning_memories_memory_type", "agent_learning_memories", ["memory_type"])
    op.create_index("ix_agent_learning_memories_status", "agent_learning_memories", ["status"])
    op.create_index("ix_agent_learning_memories_feedback_label", "agent_learning_memories", ["feedback_label"])
    op.create_index("ix_agent_learning_memories_created_at", "agent_learning_memories", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_learning_memories_created_at", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_feedback_label", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_status", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_memory_type", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_source_run_type", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_source_run_id", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_user_id", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_deck_id", table_name="agent_learning_memories")
    op.drop_index("ix_agent_learning_memories_workspace_id", table_name="agent_learning_memories")
    op.drop_table("agent_learning_memories")
