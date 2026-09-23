"""add agent regression cases

Revision ID: 0031_agent_regression_cases
Revises: 0030_agent_telemetry_events
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_agent_regression_cases"
down_revision = "0030_agent_telemetry_events"
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
    if not _has_table("agent_regression_cases"):
        op.create_table(
            "agent_regression_cases",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("source_event_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=True),
            sa.Column("deck_id", sa.String(), nullable=True),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("run_type", sa.String(), nullable=False),
            sa.Column("event_name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("failure_category", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("fixture_json", sa.JSON(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["source_event_id"], ["agent_telemetry_events.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_event_id", name="uq_agent_regression_case_source_event"),
        )

    for column in (
        "source_event_id",
        "workspace_id",
        "deck_id",
        "user_id",
        "run_id",
        "run_type",
        "event_name",
        "status",
        "failure_category",
        "created_at",
    ):
        index_name = op.f(f"ix_agent_regression_cases_{column}")
        if not _has_index("agent_regression_cases", index_name):
            op.create_index(index_name, "agent_regression_cases", [column], unique=False)


def downgrade() -> None:
    if not _has_table("agent_regression_cases"):
        return

    for column in (
        "created_at",
        "failure_category",
        "status",
        "event_name",
        "run_type",
        "run_id",
        "user_id",
        "deck_id",
        "workspace_id",
        "source_event_id",
    ):
        op.drop_index(op.f(f"ix_agent_regression_cases_{column}"), table_name="agent_regression_cases")
    op.drop_table("agent_regression_cases")
