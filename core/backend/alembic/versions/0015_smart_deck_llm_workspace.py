"""add smart deck llm workspace tables

Revision ID: 0015_smart_deck_llm_workspace
Revises: 0014_add_deck_save_confirmations
Create Date: 2026-06-12 19:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_smart_deck_llm_workspace"
down_revision = "0014_add_deck_save_confirmations"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _existing_columns(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    deck_columns = _existing_columns("decks")
    deck_file_columns = _existing_columns("deck_files")
    slide_columns = _existing_columns("deck_slides")
    block_columns = _existing_columns("deck_slide_blocks")
    asset_columns = _existing_columns("deck_slide_assets")
    extraction_run_columns = _existing_columns("deck_extraction_runs")

    with op.batch_alter_table("decks") as batch_op:
        if "user_id" not in deck_columns:
            batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))
        if "original_filename" not in deck_columns:
            batch_op.add_column(sa.Column("original_filename", sa.String(), nullable=True))
        if "source_type" not in deck_columns:
            batch_op.add_column(sa.Column("source_type", sa.String(), nullable=True))
        if "slide_count" not in deck_columns:
            batch_op.add_column(sa.Column("slide_count", sa.Integer(), nullable=True))
        if "description" not in deck_columns:
            batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        if "metadata_json" not in deck_columns:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("deck_files") as batch_op:
        if "file_role" not in deck_file_columns:
            batch_op.add_column(sa.Column("file_role", sa.String(), nullable=False, server_default="original_upload"))
        if "file_extension" not in deck_file_columns:
            batch_op.add_column(sa.Column("file_extension", sa.String(), nullable=True))
        if "storage_provider" not in deck_file_columns:
            batch_op.add_column(sa.Column("storage_provider", sa.String(), nullable=False, server_default="local"))
        if "metadata_json" not in deck_file_columns:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("deck_slides") as batch_op:
        if "extraction_run_id" not in slide_columns:
            batch_op.add_column(sa.Column("extraction_run_id", sa.String(), nullable=True))
        if "slide_number" not in slide_columns:
            batch_op.add_column(sa.Column("slide_number", sa.Integer(), nullable=True))
        if "page_index" not in slide_columns:
            batch_op.add_column(sa.Column("page_index", sa.Integer(), nullable=True))
        if "text_hash" not in slide_columns:
            batch_op.add_column(sa.Column("text_hash", sa.String(length=64), nullable=True))
        if "rendered_image_path" not in slide_columns:
            batch_op.add_column(sa.Column("rendered_image_path", sa.String(), nullable=True))
        if "block_count" not in slide_columns:
            batch_op.add_column(sa.Column("block_count", sa.Integer(), nullable=False, server_default="0"))
        if "asset_count" not in slide_columns:
            batch_op.add_column(sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"))
        if "semantic_slide_type" not in slide_columns:
            batch_op.add_column(sa.Column("semantic_slide_type", sa.String(), nullable=True))
        if "summary" not in slide_columns:
            batch_op.add_column(sa.Column("summary", sa.Text(), nullable=True))

    with op.batch_alter_table("deck_slide_blocks") as batch_op:
        if "deck_id" not in block_columns:
            batch_op.add_column(sa.Column("deck_id", sa.String(), nullable=True))
        if "extraction_run_id" not in block_columns:
            batch_op.add_column(sa.Column("extraction_run_id", sa.String(), nullable=True))
        if "parent_block_id" not in block_columns:
            batch_op.add_column(sa.Column("parent_block_id", sa.String(), nullable=True))
        if "block_kind" not in block_columns:
            batch_op.add_column(sa.Column("block_kind", sa.String(), nullable=True))
        if "extraction_stage" not in block_columns:
            batch_op.add_column(sa.Column("extraction_stage", sa.String(), nullable=False, server_default="raw"))
        if "extraction_source" not in block_columns:
            batch_op.add_column(sa.Column("extraction_source", sa.String(), nullable=False, server_default="pdf_text"))
        if "semantic_role" not in block_columns:
            batch_op.add_column(sa.Column("semantic_role", sa.String(), nullable=True))
        if "text" not in block_columns:
            batch_op.add_column(sa.Column("text", sa.Text(), nullable=True))
        if "html_text" not in block_columns:
            batch_op.add_column(sa.Column("html_text", sa.Text(), nullable=True))
        if "alt_text" not in block_columns:
            batch_op.add_column(sa.Column("alt_text", sa.Text(), nullable=True))
        if "asset_id" not in block_columns:
            batch_op.add_column(sa.Column("asset_id", sa.String(), nullable=True))
        for column_name in [
            "bbox_left",
            "bbox_top",
            "bbox_width",
            "bbox_height",
            "source_left",
            "source_top",
            "source_width",
            "source_height",
            "rotation",
            "confidence",
            "font_size",
        ]:
            if column_name not in block_columns:
                batch_op.add_column(sa.Column(column_name, sa.Float(), nullable=True))
        for column_name in ["z_index", "source_page_object_index", "sort_order"]:
            if column_name not in block_columns:
                batch_op.add_column(sa.Column(column_name, sa.Integer(), nullable=True))
        for column_name in ["font_family", "font_weight", "font_style", "color_hex", "source_object_id"]:
            if column_name not in block_columns:
                batch_op.add_column(sa.Column(column_name, sa.String(), nullable=True))
        for column_name in ["style_json", "raw_json"]:
            if column_name not in block_columns:
                batch_op.add_column(sa.Column(column_name, sa.JSON(), nullable=True))
        if "content_hash" not in block_columns:
            batch_op.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        if "is_visible" not in block_columns:
            batch_op.add_column(sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()))

    with op.batch_alter_table("deck_slide_assets") as batch_op:
        if "extraction_run_id" not in asset_columns:
            batch_op.add_column(sa.Column("extraction_run_id", sa.String(), nullable=True))
        if "asset_kind" not in asset_columns:
            batch_op.add_column(sa.Column("asset_kind", sa.String(), nullable=True))
        if "storage_provider" not in asset_columns:
            batch_op.add_column(sa.Column("storage_provider", sa.String(), nullable=False, server_default="local"))
        if "filename" not in asset_columns:
            batch_op.add_column(sa.Column("filename", sa.String(), nullable=True))
        if "file_size_bytes" not in asset_columns:
            batch_op.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))
        if "sha256" not in asset_columns:
            batch_op.add_column(sa.Column("sha256", sa.String(length=64), nullable=True))
        for column_name in [
            "bbox_left",
            "bbox_top",
            "bbox_width",
            "bbox_height",
            "source_left",
            "source_top",
            "source_width",
            "source_height",
        ]:
            if column_name not in asset_columns:
                batch_op.add_column(sa.Column(column_name, sa.Float(), nullable=True))
        if "source_object_id" not in asset_columns:
            batch_op.add_column(sa.Column("source_object_id", sa.String(), nullable=True))
        if "source_page_object_index" not in asset_columns:
            batch_op.add_column(sa.Column("source_page_object_index", sa.Integer(), nullable=True))
        if "raw_json" not in asset_columns:
            batch_op.add_column(sa.Column("raw_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("deck_extraction_runs") as batch_op:
        if "run_type" not in extraction_run_columns:
            batch_op.add_column(sa.Column("run_type", sa.String(), nullable=False, server_default="deterministic_pdf"))
        if "extractor_version" not in extraction_run_columns:
            batch_op.add_column(sa.Column("extractor_version", sa.String(), nullable=False, server_default="v1"))
        if "error_json" not in extraction_run_columns:
            batch_op.add_column(sa.Column("error_json", sa.JSON(), nullable=True))
        if "metrics_json" not in extraction_run_columns:
            batch_op.add_column(sa.Column("metrics_json", sa.JSON(), nullable=True))

    if not _has_table("generation_jobs"):
        op.create_table(
            "generation_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("provider", sa.String(), nullable=False, server_default="deterministic"),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("selected_source_slide_ids_json", sa.JSON(), nullable=False),
            sa.Column("style_id", sa.String(), nullable=True),
            sa.Column("brand_product_id", sa.String(), nullable=True),
            sa.Column("additional_context", sa.Text(), nullable=True),
            sa.Column("llm_context_json", sa.JSON(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_generation_jobs_deck_id", "generation_jobs", ["deck_id"])
        op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    if not _has_table("design_versions"):
        op.create_table(
            "design_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("generation_job_id", sa.String(), sa.ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("applied_at", sa.DateTime(), nullable=True),
            sa.Column("discarded_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_design_versions_deck_id", "design_versions", ["deck_id"])
        op.create_index("ix_design_versions_generation_job_id", "design_versions", ["generation_job_id"])
        op.create_index("ix_design_versions_status", "design_versions", ["status"])

    if not _has_table("generated_slides"):
        op.create_table(
            "generated_slides",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("generation_job_id", sa.String(), sa.ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("slide_number", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="ready"),
            sa.Column("render_schema_json", sa.JSON(), nullable=False),
            sa.Column("design_tokens_json", sa.JSON(), nullable=True),
            sa.Column("preview_image_url", sa.String(), nullable=True),
            sa.Column("validation_status", sa.String(), nullable=False, server_default="valid"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_generated_slides_deck_id", "generated_slides", ["deck_id"])
        op.create_index("ix_generated_slides_design_version_id", "generated_slides", ["design_version_id"])
        op.create_index("ix_generated_slides_generation_job_id", "generated_slides", ["generation_job_id"])
        op.create_index("ix_generated_slides_source_slide_id", "generated_slides", ["source_slide_id"])

    if not _has_table("generated_slide_code_versions"):
        op.create_table(
            "generated_slide_code_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("code_kind", sa.String(), nullable=False, server_default="render_schema"),
            sa.Column("schema_version", sa.String(), nullable=False, server_default="smart-deck-render-schema.v1"),
            sa.Column("render_schema_json", sa.JSON(), nullable=False),
            sa.Column("code_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="valid"),
            sa.Column("validation_errors_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_generated_slide_code_versions_generated_slide_id", "generated_slide_code_versions", ["generated_slide_id"])

    if not _has_table("assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("asset_type", sa.String(), nullable=False),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("public_url", sa.String(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_assets_deck_id", "assets", ["deck_id"])
        op.create_index("ix_assets_source_slide_id", "assets", ["source_slide_id"])
        op.create_index("ix_assets_generated_slide_id", "assets", ["generated_slide_id"])
        op.create_index("ix_assets_asset_type", "assets", ["asset_type"])


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_assets_asset_type", "assets"),
        ("ix_assets_generated_slide_id", "assets"),
        ("ix_assets_source_slide_id", "assets"),
        ("ix_assets_deck_id", "assets"),
        ("ix_generated_slide_code_versions_generated_slide_id", "generated_slide_code_versions"),
        ("ix_generated_slides_source_slide_id", "generated_slides"),
        ("ix_generated_slides_generation_job_id", "generated_slides"),
        ("ix_generated_slides_design_version_id", "generated_slides"),
        ("ix_generated_slides_deck_id", "generated_slides"),
        ("ix_design_versions_status", "design_versions"),
        ("ix_design_versions_generation_job_id", "design_versions"),
        ("ix_design_versions_deck_id", "design_versions"),
        ("ix_generation_jobs_status", "generation_jobs"),
        ("ix_generation_jobs_deck_id", "generation_jobs"),
    ]:
        if _has_table(table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in [
        "assets",
        "generated_slide_code_versions",
        "generated_slides",
        "design_versions",
        "generation_jobs",
    ]:
        if _has_table(table_name):
            op.drop_table(table_name)
