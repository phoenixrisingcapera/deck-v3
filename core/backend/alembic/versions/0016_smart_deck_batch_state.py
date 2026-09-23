"""add smart deck batch workspace state

Revision ID: 0016_smart_deck_batch_state
Revises: 0015_smart_deck_llm_workspace
Create Date: 2026-06-12 20:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_smart_deck_batch_state"
down_revision = "0015_smart_deck_llm_workspace"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("smart_deck_workspaces"):
        op.create_table(
            "smart_deck_workspaces",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active_design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active_source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active_generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="ready"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_smart_deck_workspaces_deck_id", "smart_deck_workspaces", ["deck_id"], unique=True)
        op.create_index("ix_smart_deck_workspaces_user_id", "smart_deck_workspaces", ["user_id"])
        op.create_index("ix_smart_deck_workspaces_status", "smart_deck_workspaces", ["status"])

    if not _has_table("smart_deck_preferences"):
        op.create_table(
            "smart_deck_preferences",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("smart_deck_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("selected_source_slide_ids_json", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("active_source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active_design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active_generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("zoom_level", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("canvas_fit_mode", sa.String(), nullable=False, server_default="fit"),
            sa.Column("right_panel_open", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("slide_rail_open", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_smart_deck_preferences_workspace_id", "smart_deck_preferences", ["workspace_id"], unique=True)
        op.create_index("ix_smart_deck_preferences_deck_id", "smart_deck_preferences", ["deck_id"])

    if not _has_table("smart_deck_messages"):
        op.create_table(
            "smart_deck_messages",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("smart_deck_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("generation_job_id", sa.String(), sa.ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("selected_source_slide_ids_json", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_smart_deck_messages_workspace_id", "smart_deck_messages", ["workspace_id"])
        op.create_index("ix_smart_deck_messages_deck_id", "smart_deck_messages", ["deck_id"])
        op.create_index("ix_smart_deck_messages_generation_job_id", "smart_deck_messages", ["generation_job_id"])

    if not _has_table("design_tokens"):
        op.create_table(
            "design_tokens",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=True),
            sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=True),
            sa.Column("token_name", sa.String(), nullable=False),
            sa.Column("token_value", sa.String(), nullable=False),
            sa.Column("token_type", sa.String(), nullable=False, server_default="color"),
            sa.Column("source", sa.String(), nullable=False, server_default="smart_deck_llm"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_design_tokens_deck_id", "design_tokens", ["deck_id"])
        op.create_index("ix_design_tokens_design_version_id", "design_tokens", ["design_version_id"])
        op.create_index("ix_design_tokens_generated_slide_id", "design_tokens", ["generated_slide_id"])


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_design_tokens_generated_slide_id", "design_tokens"),
        ("ix_design_tokens_design_version_id", "design_tokens"),
        ("ix_design_tokens_deck_id", "design_tokens"),
        ("ix_smart_deck_messages_generation_job_id", "smart_deck_messages"),
        ("ix_smart_deck_messages_deck_id", "smart_deck_messages"),
        ("ix_smart_deck_messages_workspace_id", "smart_deck_messages"),
        ("ix_smart_deck_preferences_deck_id", "smart_deck_preferences"),
        ("ix_smart_deck_preferences_workspace_id", "smart_deck_preferences"),
        ("ix_smart_deck_workspaces_status", "smart_deck_workspaces"),
        ("ix_smart_deck_workspaces_user_id", "smart_deck_workspaces"),
        ("ix_smart_deck_workspaces_deck_id", "smart_deck_workspaces"),
    ]:
        if _has_table(table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in ["design_tokens", "smart_deck_messages", "smart_deck_preferences", "smart_deck_workspaces"]:
        if _has_table(table_name):
            op.drop_table(table_name)
