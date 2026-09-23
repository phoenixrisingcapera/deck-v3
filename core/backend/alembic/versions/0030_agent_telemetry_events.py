"""add agent telemetry events

Revision ID: 0030_agent_telemetry_events
Revises: 0029_ai_orchestration_runs
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_agent_telemetry_events"
down_revision = "0029_ai_orchestration_runs"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in _inspector().get_indexes(table_name))


def upgrade() -> None:
    # DISABLED for the core lineage: AI persistence is created by alembic_ai.
    return
    if not _has_table("agent_telemetry_events"):
        op.create_table(
            "agent_telemetry_events",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("deck_id", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("run_type", sa.String(), nullable=False),
            sa.Column("step_id", sa.String(), nullable=True),
            sa.Column("event_name", sa.String(), nullable=False),
            sa.Column("event_level", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("provider", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("input_tokens", sa.Integer(), nullable=True),
            sa.Column("output_tokens", sa.Integer(), nullable=True),
            sa.Column("estimated_cost_cents", sa.Float(), nullable=True),
            sa.Column("error_category", sa.String(), nullable=True),
            sa.Column("error_message_redacted", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.String(), nullable=True),
            sa.Column("span_id", sa.String(), nullable=True),
            sa.Column("request_id", sa.String(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    for column in (
        "workspace_id",
        "deck_id",
        "user_id",
        "run_id",
        "run_type",
        "step_id",
        "event_name",
        "event_level",
        "status",
        "provider",
        "error_category",
        "trace_id",
        "span_id",
        "request_id",
        "created_at",
    ):
        index_name = op.f(f"ix_agent_telemetry_events_{column}")
        if not _has_index("agent_telemetry_events", index_name):
            op.create_index(index_name, "agent_telemetry_events", [column], unique=False)


def downgrade() -> None:
    if not _has_table("agent_telemetry_events"):
        return

    for column in (
        "created_at",
        "request_id",
        "span_id",
        "trace_id",
        "error_category",
        "provider",
        "status",
        "event_level",
        "event_name",
        "step_id",
        "run_type",
        "run_id",
        "user_id",
        "deck_id",
        "workspace_id",
    ):
        op.drop_index(op.f(f"ix_agent_telemetry_events_{column}"), table_name="agent_telemetry_events")
    op.drop_table("agent_telemetry_events")
