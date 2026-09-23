"""Add core product developer-tools event storage."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260715_0003_core_developer_tools"
down_revision: Union[str, None] = "20260715_0002_core_reconciliation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # API, worker, and test-runner predeploys can migrate concurrently.
        # Serialize this table check/create pair within PostgreSQL.
        bind.execute(sa.text("SELECT pg_advisory_xact_lock(202607150003)"))
    inspector = sa.inspect(bind)
    if "developer_tool_events" in inspector.get_table_names():
        return
    op.create_table(
        "developer_tool_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("surface", sa.String(), nullable=False),
        sa.Column("event_name", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("workflow_id", sa.String(), nullable=True),
        sa.Column("workflow_job_id", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("artifact_id", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("workspace_id", "deck_id", "user_id", "surface", "event_name", "request_id", "workflow_id", "workflow_job_id", "run_id", "artifact_id", "created_at"):
        op.create_index(f"ix_developer_tool_events_{column}", "developer_tool_events", [column])


def downgrade() -> None:
    op.drop_table("developer_tool_events")
