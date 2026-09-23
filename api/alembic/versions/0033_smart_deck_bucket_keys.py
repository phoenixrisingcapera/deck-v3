"""add smart deck bucket keys

Revision ID: 0033_smart_deck_bucket_keys
Revises: 0032_remove_mock_provider_defaults
Create Date: 2026-06-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0033_smart_deck_bucket_keys"
down_revision = "0032_remove_mock_provider_defaults"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(index_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes("decks")}


def upgrade() -> None:
    if not _column_exists("decks", "current_design_version_id"):
        op.add_column("decks", sa.Column("current_design_version_id", sa.String(), nullable=True))
    if not _index_exists(op.f("ix_decks_current_design_version_id")):
        op.create_index(op.f("ix_decks_current_design_version_id"), "decks", ["current_design_version_id"], unique=False)

    if not _column_exists("deck_llm_artifacts", "bucket_payload_key"):
        op.add_column("deck_llm_artifacts", sa.Column("bucket_payload_key", sa.String(), nullable=True))

    if not _column_exists("design_versions", "bucket_manifest_key"):
        op.add_column("design_versions", sa.Column("bucket_manifest_key", sa.String(), nullable=True))

    if not _column_exists("generated_slides", "current_version_id"):
        op.add_column("generated_slides", sa.Column("current_version_id", sa.String(), nullable=True))
    if not inspect(op.get_bind()).get_indexes("generated_slides") or op.f("ix_generated_slides_current_version_id") not in {
        index["name"] for index in inspect(op.get_bind()).get_indexes("generated_slides")
    }:
        op.create_index(op.f("ix_generated_slides_current_version_id"), "generated_slides", ["current_version_id"], unique=False)

    if not _column_exists("generated_slide_code_versions", "bucket_render_schema_key"):
        op.add_column("generated_slide_code_versions", sa.Column("bucket_render_schema_key", sa.String(), nullable=True))
    if not _column_exists("generated_slide_code_versions", "bucket_code_key"):
        op.add_column("generated_slide_code_versions", sa.Column("bucket_code_key", sa.String(), nullable=True))
    if not _column_exists("generated_slide_code_versions", "bucket_thumbnail_key"):
        op.add_column("generated_slide_code_versions", sa.Column("bucket_thumbnail_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_slide_code_versions", "bucket_thumbnail_key")
    op.drop_column("generated_slide_code_versions", "bucket_code_key")
    op.drop_column("generated_slide_code_versions", "bucket_render_schema_key")

    op.drop_index(op.f("ix_generated_slides_current_version_id"), table_name="generated_slides")
    op.drop_column("generated_slides", "current_version_id")

    op.drop_column("design_versions", "bucket_manifest_key")

    op.drop_column("deck_llm_artifacts", "bucket_payload_key")

    op.drop_index(op.f("ix_decks_current_design_version_id"), table_name="decks")
    op.drop_column("decks", "current_design_version_id")
