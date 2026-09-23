"""create deck workspace and smart shell tables

Revision ID: 0005_deck_workspace_and_shell
Revises: 0004_workspace_ai_provider
Create Date: 2026-06-10 23:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_deck_workspace_and_shell"
down_revision = "0004_workspace_ai_provider"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "decks" not in existing:
        op.create_table(
            "decks",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("audience", sa.String(), nullable=False),
            sa.Column("purpose", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_decks_status"), "decks", ["status"], unique=False)

    if "deck_files" not in existing:
        op.create_table(
            "deck_files",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("mime_type", sa.String(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("deck_id"),
        )

    if "deck_brand_profiles" not in existing:
        op.create_table(
            "deck_brand_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("company_name", sa.String(), nullable=True),
            sa.Column("company_website_url", sa.String(), nullable=True),
            sa.Column("founder_name", sa.String(), nullable=True),
            sa.Column("team_summary", sa.Text(), nullable=True),
            sa.Column("brand_summary", sa.Text(), nullable=True),
            sa.Column("visual_direction", sa.Text(), nullable=True),
            sa.Column("audience_label", sa.String(), nullable=True),
            sa.Column("primary_goal", sa.Text(), nullable=True),
            sa.Column("processing_status", sa.String(), nullable=False, server_default="ready"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("deck_id"),
        )
        op.create_index(op.f("ix_deck_brand_profiles_deck_id"), "deck_brand_profiles", ["deck_id"], unique=True)

    if "deck_slides" not in existing:
        op.create_table(
            "deck_slides",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("slide_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("narrative_notes", sa.Text(), nullable=False, server_default=""),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "deck_slide_blocks" not in existing:
        op.create_table(
            "deck_slide_blocks",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("block_index", sa.Integer(), nullable=False),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("normalized_text", sa.Text(), nullable=False),
            sa.Column("block_type", sa.String(), nullable=False),
            sa.Column("position", sa.String(), nullable=True),
            sa.Column("style", sa.String(), nullable=True),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "block_classifications" not in existing:
        op.create_table(
            "block_classifications",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("block_id", sa.String(), nullable=False),
            sa.Column("semantic_tag", sa.String(), nullable=False),
            sa.Column("diligence_category", sa.String(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.ForeignKeyConstraint(["block_id"], ["deck_slide_blocks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "analysis_runs" not in existing:
        op.create_table(
            "analysis_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "analysis_findings" not in existing:
        op.create_table(
            "analysis_findings",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("block_id", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["block_id"], ["deck_slide_blocks.id"]),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "audience_profiles" not in existing:
        op.create_table(
            "audience_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("focus", sa.Text(), nullable=False),
            sa.Column("tone", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("label"),
        )

    if "adaptation_runs" not in existing:
        op.create_table(
            "adaptation_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("audience", sa.String(), nullable=False),
            sa.Column("purpose", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "adaptation_suggestions" not in existing:
        op.create_table(
            "adaptation_suggestions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("block_id", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("suggested_text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("audience", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["block_id"], ["deck_slide_blocks.id"]),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "smart_edit_runs" not in existing:
        op.create_table(
            "smart_edit_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("block_id", sa.String(), nullable=False),
            sa.Column("instruction", sa.Text(), nullable=False),
            sa.Column("audience_type", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["block_id"], ["deck_slide_blocks.id"]),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "smart_edit_suggestions" not in existing:
        op.create_table(
            "smart_edit_suggestions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("block_id", sa.String(), nullable=False),
            sa.Column("original_text", sa.Text(), nullable=False),
            sa.Column("suggested_text", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("risk_level", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(["block_id"], ["deck_slide_blocks.id"]),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["smart_edit_runs.id"]),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "deck_slide_revisions" not in existing:
        op.create_table(
            "deck_slide_revisions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("block_id", sa.String(), nullable=False),
            sa.Column("previous_text", sa.Text(), nullable=False),
            sa.Column("next_text", sa.Text(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["block_id"], ["deck_slide_blocks.id"]),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "deck_exports" not in existing:
        op.create_table(
            "deck_exports",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "design_batches" not in existing:
        op.create_table(
            "design_batches",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("batch_number", sa.Integer(), nullable=False),
            sa.Column("batch_name", sa.String(), nullable=True),
            sa.Column("scope_type", sa.String(), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("audience_label", sa.String(), nullable=True),
            sa.Column("selected_slide_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(), nullable=False, server_default="completed"),
            sa.Column("use_brand_profile", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("use_website_context", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("use_block_classifications", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_design_batches_deck_id"), "design_batches", ["deck_id"], unique=False)
        op.create_index(op.f("ix_design_batches_scope_type"), "design_batches", ["scope_type"], unique=False)
        op.create_index(op.f("ix_design_batches_status"), "design_batches", ["status"], unique=False)

    if "design_batch_slides" not in existing:
        op.create_table(
            "design_batch_slides",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("batch_id", sa.String(), nullable=False),
            sa.Column("slide_id", sa.String(), nullable=False),
            sa.Column("slide_index_snapshot", sa.Integer(), nullable=False),
            sa.Column("slide_title_snapshot", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["batch_id"], ["design_batches.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["slide_id"], ["deck_slides.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_design_batch_slides_batch_id"), "design_batch_slides", ["batch_id"], unique=False)
        op.create_index(op.f("ix_design_batch_slides_slide_id"), "design_batch_slides", ["slide_id"], unique=False)

    if "generated_slide_candidates" not in existing:
        op.create_table(
            "generated_slide_candidates",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("batch_id", sa.String(), nullable=False),
            sa.Column("source_slide_id", sa.String(), nullable=True),
            sa.Column("slide_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("headline", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="reviewable"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["batch_id"], ["design_batches.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_slide_id"], ["deck_slides.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_generated_slide_candidates_batch_id"), "generated_slide_candidates", ["batch_id"], unique=False)


def downgrade() -> None:
    existing = _existing_tables()

    for index_name, table_name in [
        (op.f("ix_generated_slide_candidates_batch_id"), "generated_slide_candidates"),
        (op.f("ix_design_batch_slides_slide_id"), "design_batch_slides"),
        (op.f("ix_design_batch_slides_batch_id"), "design_batch_slides"),
        (op.f("ix_design_batches_status"), "design_batches"),
        (op.f("ix_design_batches_scope_type"), "design_batches"),
        (op.f("ix_design_batches_deck_id"), "design_batches"),
        (op.f("ix_deck_brand_profiles_deck_id"), "deck_brand_profiles"),
        (op.f("ix_decks_status"), "decks"),
    ]:
        if table_name in existing:
            op.drop_index(index_name, table_name=table_name)

    for table_name in [
        "generated_slide_candidates",
        "design_batch_slides",
        "design_batches",
        "deck_exports",
        "deck_slide_revisions",
        "smart_edit_suggestions",
        "smart_edit_runs",
        "adaptation_suggestions",
        "adaptation_runs",
        "audience_profiles",
        "analysis_findings",
        "analysis_runs",
        "block_classifications",
        "deck_slide_blocks",
        "deck_slides",
        "deck_brand_profiles",
        "deck_files",
        "decks",
    ]:
        if table_name in existing:
            op.drop_table(table_name)
