"""add deck structure extraction tables

Revision ID: 0012_add_deck_structure_tables
Revises: 0011_welcome_back_resume_state
Create Date: 2026-06-11 20:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_add_deck_structure_tables"
down_revision = "0011_welcome_back_resume_state"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _existing_columns(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    file_columns = _existing_columns("deck_files")
    slide_columns = _existing_columns("deck_slides")
    block_columns = _existing_columns("deck_slide_blocks")

    with op.batch_alter_table("deck_files") as batch_op:
        if "original_filename" not in file_columns:
            batch_op.add_column(sa.Column("original_filename", sa.String(), nullable=True))
        if "storage_path" not in file_columns:
            batch_op.add_column(sa.Column("storage_path", sa.String(), nullable=True))
        if "checksum_sha256" not in file_columns:
            batch_op.add_column(sa.Column("checksum_sha256", sa.String(length=64), nullable=True))
        if "page_count" not in file_columns:
            batch_op.add_column(sa.Column("page_count", sa.Integer(), nullable=True))

    with op.batch_alter_table("deck_slides") as batch_op:
        if "source_file_id" not in slide_columns:
            batch_op.add_column(sa.Column("source_file_id", sa.String(), nullable=True))
            batch_op.create_foreign_key("fk_deck_slides_source_file_id", "deck_files", ["source_file_id"], ["id"], ondelete="SET NULL")
        if "source_page_number" not in slide_columns:
            batch_op.add_column(sa.Column("source_page_number", sa.Integer(), nullable=True))
        if "thumbnail_path" not in slide_columns:
            batch_op.add_column(sa.Column("thumbnail_path", sa.String(), nullable=True))
        if "thumbnail_mime_type" not in slide_columns:
            batch_op.add_column(sa.Column("thumbnail_mime_type", sa.String(), nullable=True))
        if "width_points" not in slide_columns:
            batch_op.add_column(sa.Column("width_points", sa.Float(), nullable=True))
        if "height_points" not in slide_columns:
            batch_op.add_column(sa.Column("height_points", sa.Float(), nullable=True))
        if "metadata_json" not in slide_columns:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))
        if "created_at" not in slide_columns:
            batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        if "updated_at" not in slide_columns:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE deck_slides SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE deck_slides SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")

    with op.batch_alter_table("deck_slides") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False)
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)

    with op.batch_alter_table("deck_slide_blocks") as batch_op:
        if "source_kind" not in block_columns:
            batch_op.add_column(sa.Column("source_kind", sa.String(), nullable=True))
        if "metadata_json" not in block_columns:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))
        if "created_at" not in block_columns:
            batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        if "updated_at" not in block_columns:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE deck_slide_blocks SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE deck_slide_blocks SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")

    with op.batch_alter_table("deck_slide_blocks") as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DateTime(), nullable=False)
        batch_op.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)

    if not _has_table("deck_slide_assets"):
        op.create_table(
            "deck_slide_assets",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="CASCADE"), nullable=False),
            sa.Column("asset_type", sa.String(), nullable=False),
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_deck_slide_assets_deck_id", "deck_slide_assets", ["deck_id"])
        op.create_index("ix_deck_slide_assets_slide_id", "deck_slide_assets", ["slide_id"])
        op.create_index("ix_deck_slide_assets_asset_type", "deck_slide_assets", ["asset_type"])

    if not _has_table("deck_extraction_runs"):
        op.create_table(
            "deck_extraction_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_file_id", sa.String(), sa.ForeignKey("deck_files.id", ondelete="SET NULL"), nullable=True),
            sa.Column("extractor_name", sa.String(), nullable=False),
            sa.Column("source_format", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("slide_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("block_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_deck_extraction_runs_deck_id", "deck_extraction_runs", ["deck_id"])
        op.create_index("ix_deck_extraction_runs_status", "deck_extraction_runs", ["status"])


def downgrade() -> None:
    if _has_table("deck_extraction_runs"):
        op.drop_index("ix_deck_extraction_runs_status", table_name="deck_extraction_runs")
        op.drop_index("ix_deck_extraction_runs_deck_id", table_name="deck_extraction_runs")
        op.drop_table("deck_extraction_runs")

    if _has_table("deck_slide_assets"):
        op.drop_index("ix_deck_slide_assets_asset_type", table_name="deck_slide_assets")
        op.drop_index("ix_deck_slide_assets_slide_id", table_name="deck_slide_assets")
        op.drop_index("ix_deck_slide_assets_deck_id", table_name="deck_slide_assets")
        op.drop_table("deck_slide_assets")

    slide_columns = _existing_columns("deck_slides")
    with op.batch_alter_table("deck_slide_blocks") as batch_op:
        for column_name in ["updated_at", "created_at", "metadata_json", "source_kind"]:
            if column_name in _existing_columns("deck_slide_blocks"):
                batch_op.drop_column(column_name)

    with op.batch_alter_table("deck_slides") as batch_op:
        if "source_file_id" in slide_columns:
            batch_op.drop_constraint("fk_deck_slides_source_file_id", type_="foreignkey")
        for column_name in [
            "updated_at",
            "created_at",
            "metadata_json",
            "height_points",
            "width_points",
            "thumbnail_mime_type",
            "thumbnail_path",
            "source_page_number",
            "source_file_id",
        ]:
            if column_name in slide_columns:
                batch_op.drop_column(column_name)

    with op.batch_alter_table("deck_files") as batch_op:
        for column_name in ["page_count", "checksum_sha256", "storage_path", "original_filename"]:
            if column_name in _existing_columns("deck_files"):
                batch_op.drop_column(column_name)
