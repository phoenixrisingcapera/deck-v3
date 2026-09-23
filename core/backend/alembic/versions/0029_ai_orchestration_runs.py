"""add ai orchestration run audit tables

Revision ID: 0029_ai_orchestration_runs
Revises: 0028_agent_learning_memories
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_ai_orchestration_runs"
down_revision = "0028_agent_learning_memories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("deck_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("intent", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("user_instruction", sa.Text(), nullable=False),
        sa.Column("selected_slide_ids_json", sa.JSON(), nullable=False),
        sa.Column("audience", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_runs_created_at"), "ai_runs", ["created_at"], unique=False)
    op.create_index(op.f("ix_ai_runs_deck_id"), "ai_runs", ["deck_id"], unique=False)
    op.create_index(op.f("ix_ai_runs_intent"), "ai_runs", ["intent"], unique=False)
    op.create_index(op.f("ix_ai_runs_mode"), "ai_runs", ["mode"], unique=False)
    op.create_index(op.f("ix_ai_runs_status"), "ai_runs", ["status"], unique=False)
    op.create_index(op.f("ix_ai_runs_user_id"), "ai_runs", ["user_id"], unique=False)
    op.create_index(op.f("ix_ai_runs_workspace_id"), "ai_runs", ["workspace_id"], unique=False)

    op.create_table(
        "ai_run_steps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("ai_run_id", sa.String(), nullable=False),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_run_steps_ai_run_id"), "ai_run_steps", ["ai_run_id"], unique=False)
    op.create_index(op.f("ix_ai_run_steps_created_at"), "ai_run_steps", ["created_at"], unique=False)
    op.create_index(op.f("ix_ai_run_steps_status"), "ai_run_steps", ["status"], unique=False)
    op.create_index(op.f("ix_ai_run_steps_step_name"), "ai_run_steps", ["step_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_run_steps_step_name"), table_name="ai_run_steps")
    op.drop_index(op.f("ix_ai_run_steps_status"), table_name="ai_run_steps")
    op.drop_index(op.f("ix_ai_run_steps_created_at"), table_name="ai_run_steps")
    op.drop_index(op.f("ix_ai_run_steps_ai_run_id"), table_name="ai_run_steps")
    op.drop_table("ai_run_steps")
    op.drop_index(op.f("ix_ai_runs_workspace_id"), table_name="ai_runs")
    op.drop_index(op.f("ix_ai_runs_user_id"), table_name="ai_runs")
    op.drop_index(op.f("ix_ai_runs_status"), table_name="ai_runs")
    op.drop_index(op.f("ix_ai_runs_mode"), table_name="ai_runs")
    op.drop_index(op.f("ix_ai_runs_intent"), table_name="ai_runs")
    op.drop_index(op.f("ix_ai_runs_deck_id"), table_name="ai_runs")
    op.drop_index(op.f("ix_ai_runs_created_at"), table_name="ai_runs")
    op.drop_table("ai_runs")
