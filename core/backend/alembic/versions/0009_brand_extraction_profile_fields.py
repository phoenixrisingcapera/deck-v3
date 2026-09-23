"""add brand extraction profile fields

Revision ID: 0009_brand_profile_fields
Revises: 0008_deck_generation_workspace
Create Date: 2026-06-11 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_brand_profile_fields"
down_revision = "0008_deck_generation_workspace"
branch_labels = None
depends_on = None


def _existing_columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    profile_columns = _existing_columns("deck_brand_profiles")
    asset_columns = _existing_columns("deck_brand_assets")

    with op.batch_alter_table("deck_brand_profiles") as batch_op:
        if "logo_url" not in profile_columns:
            batch_op.add_column(sa.Column("logo_url", sa.String(), nullable=True))
        if "favicon_url" not in profile_columns:
            batch_op.add_column(sa.Column("favicon_url", sa.String(), nullable=True))
        if "visual_style" not in profile_columns:
            batch_op.add_column(sa.Column("visual_style", sa.String(), nullable=True))
        if "primary_color" not in profile_columns:
            batch_op.add_column(sa.Column("primary_color", sa.String(), nullable=True))
        if "secondary_color" not in profile_columns:
            batch_op.add_column(sa.Column("secondary_color", sa.String(), nullable=True))
        if "accent_color" not in profile_columns:
            batch_op.add_column(sa.Column("accent_color", sa.String(), nullable=True))
        if "background_color" not in profile_columns:
            batch_op.add_column(sa.Column("background_color", sa.String(), nullable=True))
        if "text_color" not in profile_columns:
            batch_op.add_column(sa.Column("text_color", sa.String(), nullable=True))
        if "palette_json" not in profile_columns:
            batch_op.add_column(sa.Column("palette_json", sa.JSON(), nullable=True))
        if "font_candidates_json" not in profile_columns:
            batch_op.add_column(sa.Column("font_candidates_json", sa.JSON(), nullable=True))
        if "confidence_score" not in profile_columns:
            batch_op.add_column(sa.Column("confidence_score", sa.Float(), nullable=True))
        if "source_mode" not in profile_columns:
            batch_op.add_column(sa.Column("source_mode", sa.String(), nullable=True))
        if "warnings_json" not in profile_columns:
            batch_op.add_column(sa.Column("warnings_json", sa.JSON(), nullable=True))
        if "raw_evidence_json" not in profile_columns:
            batch_op.add_column(sa.Column("raw_evidence_json", sa.JSON(), nullable=True))
        if "branding_json" not in profile_columns:
            batch_op.add_column(sa.Column("branding_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("deck_brand_assets") as batch_op:
        if "source" not in asset_columns:
            batch_op.add_column(sa.Column("source", sa.String(), nullable=True))
        if "mime_type" not in asset_columns:
            batch_op.add_column(sa.Column("mime_type", sa.String(), nullable=True))
        if "public_url" not in asset_columns:
            batch_op.add_column(sa.Column("public_url", sa.String(), nullable=True))


def downgrade() -> None:
    profile_columns = _existing_columns("deck_brand_profiles")
    asset_columns = _existing_columns("deck_brand_assets")

    with op.batch_alter_table("deck_brand_assets") as batch_op:
        for column_name in ["public_url", "mime_type", "source"]:
            if column_name in asset_columns:
                batch_op.drop_column(column_name)

    with op.batch_alter_table("deck_brand_profiles") as batch_op:
        for column_name in [
            "branding_json",
            "raw_evidence_json",
            "warnings_json",
            "source_mode",
            "confidence_score",
            "font_candidates_json",
            "palette_json",
            "text_color",
            "background_color",
            "accent_color",
            "secondary_color",
            "primary_color",
            "visual_style",
            "favicon_url",
            "logo_url",
        ]:
            if column_name in profile_columns:
                batch_op.drop_column(column_name)
