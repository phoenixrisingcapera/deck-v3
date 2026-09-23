"""create deck generation workspace tables

Revision ID: 0008_deck_generation_workspace
Revises: 0007_shell_workspace_preferences
Create Date: 2026-06-10 23:59:30.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_deck_generation_workspace"
down_revision = "0007_shell_workspace_preferences"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "deck_generation_workspaces" not in existing:
        op.create_table(
            "deck_generation_workspaces",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("generation_status", sa.String(), nullable=False, server_default="idle"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("deck_id"),
        )
        op.create_index(op.f("ix_deck_generation_workspaces_deck_id"), "deck_generation_workspaces", ["deck_id"], unique=True)
        op.create_index(op.f("ix_deck_generation_workspaces_generation_status"), "deck_generation_workspaces", ["generation_status"], unique=False)

    if "deck_generation_runs" not in existing:
        op.create_table(
            "deck_generation_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_generation_workspace_id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("provider", sa.String(), nullable=False, server_default="mock"),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("generation_mode", sa.String(), nullable=False, server_default="mock"),
            sa.Column("scope_type", sa.String(), nullable=False, server_default="whole_deck"),
            sa.Column("request_payload_json", sa.Text(), nullable=False),
            sa.Column("generated_deck_json", sa.Text(), nullable=True),
            sa.Column("quality_score", sa.Float(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["deck_generation_workspace_id"], ["deck_generation_workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_deck_generation_runs_deck_generation_workspace_id"), "deck_generation_runs", ["deck_generation_workspace_id"], unique=False)
        op.create_index(op.f("ix_deck_generation_runs_deck_id"), "deck_generation_runs", ["deck_id"], unique=False)
        op.create_index(op.f("ix_deck_generation_runs_status"), "deck_generation_runs", ["status"], unique=False)

    if "deck_slide_versions" not in existing:
        op.create_table(
            "deck_slide_versions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_generation_workspace_id", sa.String(), nullable=False),
            sa.Column("generation_run_id", sa.String(), nullable=False),
            sa.Column("source_slide_id", sa.String(), nullable=True),
            sa.Column("slide_index", sa.Integer(), nullable=False),
            sa.Column("source_slide_title", sa.String(), nullable=True),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="reviewable"),
            sa.Column("generated_slide_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_generation_workspace_id"], ["deck_generation_workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["generation_run_id"], ["deck_generation_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_slide_id"], ["deck_slides.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_deck_slide_versions_deck_generation_workspace_id"), "deck_slide_versions", ["deck_generation_workspace_id"], unique=False)
        op.create_index(op.f("ix_deck_slide_versions_generation_run_id"), "deck_slide_versions", ["generation_run_id"], unique=False)
        op.create_index(op.f("ix_deck_slide_versions_status"), "deck_slide_versions", ["status"], unique=False)

    if "deck_feedback_events" not in existing:
        op.create_table(
            "deck_feedback_events",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_generation_workspace_id", sa.String(), nullable=False),
            sa.Column("generation_run_id", sa.String(), nullable=True),
            sa.Column("slide_version_id", sa.String(), nullable=False),
            sa.Column("source_slide_id", sa.String(), nullable=True),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_generation_workspace_id"], ["deck_generation_workspaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["generation_run_id"], ["deck_generation_runs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["slide_version_id"], ["deck_slide_versions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_slide_id"], ["deck_slides.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_deck_feedback_events_deck_generation_workspace_id"), "deck_feedback_events", ["deck_generation_workspace_id"], unique=False)
        op.create_index(op.f("ix_deck_feedback_events_event_type"), "deck_feedback_events", ["event_type"], unique=False)
        op.create_index(op.f("ix_deck_feedback_events_slide_version_id"), "deck_feedback_events", ["slide_version_id"], unique=False)


def downgrade() -> None:
    existing = _existing_tables()

    if "deck_feedback_events" in existing:
        op.drop_index(op.f("ix_deck_feedback_events_slide_version_id"), table_name="deck_feedback_events")
        op.drop_index(op.f("ix_deck_feedback_events_event_type"), table_name="deck_feedback_events")
        op.drop_index(op.f("ix_deck_feedback_events_deck_generation_workspace_id"), table_name="deck_feedback_events")
        op.drop_table("deck_feedback_events")

    if "deck_slide_versions" in existing:
        op.drop_index(op.f("ix_deck_slide_versions_status"), table_name="deck_slide_versions")
        op.drop_index(op.f("ix_deck_slide_versions_generation_run_id"), table_name="deck_slide_versions")
        op.drop_index(op.f("ix_deck_slide_versions_deck_generation_workspace_id"), table_name="deck_slide_versions")
        op.drop_table("deck_slide_versions")

    if "deck_generation_runs" in existing:
        op.drop_index(op.f("ix_deck_generation_runs_status"), table_name="deck_generation_runs")
        op.drop_index(op.f("ix_deck_generation_runs_deck_id"), table_name="deck_generation_runs")
        op.drop_index(op.f("ix_deck_generation_runs_deck_generation_workspace_id"), table_name="deck_generation_runs")
        op.drop_table("deck_generation_runs")

    if "deck_generation_workspaces" in existing:
        op.drop_index(op.f("ix_deck_generation_workspaces_generation_status"), table_name="deck_generation_workspaces")
        op.drop_index(op.f("ix_deck_generation_workspaces_deck_id"), table_name="deck_generation_workspaces")
        op.drop_table("deck_generation_workspaces")
