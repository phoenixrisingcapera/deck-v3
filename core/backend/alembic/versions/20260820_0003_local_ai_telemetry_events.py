"""Provide durable AI telemetry for local shared-database execution.

Revision ID: 20260820_0003_local_ai_telemetry_events
Revises: 20260820_0002_local_ai_quota_reservation_count
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_0003_local_ai_telemetry_events"
down_revision = "20260820_0002_local_ai_quota_reservation_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the local audit table without altering any core business rows."""
    inspector = sa.inspect(op.get_bind())
    if "agent_telemetry_events" not in inspector.get_table_names():
        op.create_table(
            "agent_telemetry_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("deck_id", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("run_type", sa.String(), nullable=False),
            sa.Column("step_id", sa.String(), nullable=True),
            sa.Column("step_name", sa.String(), nullable=True),
            sa.Column("event_name", sa.String(), nullable=False),
            sa.Column("event_level", sa.String(), nullable=True),
            sa.Column("provider", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("input_tokens", sa.Integer(), nullable=True),
            sa.Column("output_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("estimated_cost_cents", sa.Float(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_category", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("error_message_redacted", sa.Text(), nullable=True),
            sa.Column("trace_id", sa.String(), nullable=True),
            sa.Column("span_id", sa.String(), nullable=True),
            sa.Column("request_id", sa.String(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("agent_telemetry_events")}
    for column in ("workspace_id", "deck_id", "user_id", "run_id", "run_type", "event_name", "status", "created_at"):
        index_name = f"ix_agent_telemetry_events_{column}"
        if index_name not in indexes:
            op.create_index(index_name, "agent_telemetry_events", [column], unique=False)


def downgrade() -> None:
    # Telemetry is durable audit evidence and is never dropped by downgrade.
    pass
