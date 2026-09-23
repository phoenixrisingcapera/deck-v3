"""Align AI learning metadata with the telemetry promotion contract."""

from alembic import op
import sqlalchemy as sa


revision = "0002_ai_learning_contract"
down_revision = "0001_ai_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agent_learning_memories")}
    for column in (
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("source_run_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("feedback_label", sa.String(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("tags_json", sa.JSON(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    ):
        if column.name not in columns:
            op.add_column("agent_learning_memories", column)
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("agent_learning_memories")}
    if "ix_agent_learning_memories_user_id" not in indexes:
        op.create_index("ix_agent_learning_memories_user_id", "agent_learning_memories", ["user_id"])
    if "ix_agent_learning_memories_status" not in indexes:
        op.create_index("ix_agent_learning_memories_status", "agent_learning_memories", ["status"])


def downgrade() -> None:
    # Preserve AI-derived learning history during rollback.
    pass
