"""add smart deck retrieval selection and variation jobs

Revision ID: 0018_retrieval_variations
Revises: 0017_generated_slide_elements
Create Date: 2026-06-12 22:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_retrieval_variations"
down_revision = "0017_generated_slide_elements"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_selected_element_column(table_name: str) -> None:
    """Add the optional selection with a SQLite-safe named foreign key."""
    foreign_key_name = f"fk_{table_name}_selected_element_id"
    column = sa.Column("selected_element_id", sa.String(), nullable=True)
    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot ALTER TABLE ADD CONSTRAINT. Batch mode recreates only
        # this table and preserves all existing rows and constraints.
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(column)
            batch_op.create_foreign_key(
                foreign_key_name,
                "generated_slide_elements",
                ["selected_element_id"],
                ["id"],
                ondelete="SET NULL",
            )
        return
    op.add_column(
        table_name,
        sa.Column(
            "selected_element_id",
            sa.String(),
            sa.ForeignKey("generated_slide_elements.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def upgrade() -> None:
    if _has_table("smart_deck_workspaces") and not _has_column("smart_deck_workspaces", "selected_element_id"):
        _add_selected_element_column("smart_deck_workspaces")

    if _has_table("smart_deck_preferences") and not _has_column("smart_deck_preferences", "selected_element_id"):
        _add_selected_element_column("smart_deck_preferences")

    if not _has_table("element_variation_jobs"):
        op.create_table(
            "element_variation_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("smart_deck_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
            sa.Column("element_id", sa.String(), sa.ForeignKey("generated_slide_elements.id", ondelete="CASCADE"), nullable=False),
            sa.Column("base_element_version_id", sa.String(), sa.ForeignKey("generated_slide_element_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("instruction", sa.Text(), nullable=False),
            sa.Column("variation_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("retrieval_context_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("output_element_version_id", sa.String(), sa.ForeignKey("generated_slide_element_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_element_variation_jobs_deck_id", "element_variation_jobs", ["deck_id"])
        op.create_index("ix_element_variation_jobs_workspace_id", "element_variation_jobs", ["workspace_id"])
        op.create_index("ix_element_variation_jobs_generated_slide_id", "element_variation_jobs", ["generated_slide_id"])
        op.create_index("ix_element_variation_jobs_element_id", "element_variation_jobs", ["element_id"])
        op.create_index("ix_element_variation_jobs_base_element_version_id", "element_variation_jobs", ["base_element_version_id"])
        op.create_index("ix_element_variation_jobs_status", "element_variation_jobs", ["status"])
        op.create_index("ix_element_variation_jobs_output_element_version_id", "element_variation_jobs", ["output_element_version_id"])


def downgrade() -> None:
    for index_name in [
        "ix_element_variation_jobs_output_element_version_id",
        "ix_element_variation_jobs_status",
        "ix_element_variation_jobs_base_element_version_id",
        "ix_element_variation_jobs_element_id",
        "ix_element_variation_jobs_generated_slide_id",
        "ix_element_variation_jobs_workspace_id",
        "ix_element_variation_jobs_deck_id",
    ]:
        if _has_table("element_variation_jobs"):
            op.drop_index(index_name, table_name="element_variation_jobs")

    if _has_table("element_variation_jobs"):
        op.drop_table("element_variation_jobs")

    if _has_column("smart_deck_preferences", "selected_element_id"):
        op.drop_column("smart_deck_preferences", "selected_element_id")

    if _has_column("smart_deck_workspaces", "selected_element_id"):
        op.drop_column("smart_deck_workspaces", "selected_element_id")
