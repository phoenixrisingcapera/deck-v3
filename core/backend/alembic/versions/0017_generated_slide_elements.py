"""add generated slide element persistence

Revision ID: 0017_generated_slide_elements
Revises: 0016_smart_deck_batch_state
Create Date: 2026-06-12 22:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_generated_slide_elements"
down_revision = "0016_smart_deck_batch_state"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("generated_slide_elements"):
        op.create_table(
            "generated_slide_elements",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("element_key", sa.String(), nullable=False),
            sa.Column("element_type", sa.String(), nullable=False),
            sa.Column("parent_element_id", sa.String(), sa.ForeignKey("generated_slide_elements.id", ondelete="SET NULL"), nullable=True),
            sa.Column("z_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("x", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("y", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("width", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("height", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("rotation", sa.Float(), nullable=False, server_default="0"),
            sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("style_json", sa.JSON(), nullable=True),
            sa.Column("content_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_generated_slide_elements_generated_slide_id", "generated_slide_elements", ["generated_slide_id"])
        op.create_index("ix_generated_slide_elements_deck_id", "generated_slide_elements", ["deck_id"])
        op.create_index("ix_generated_slide_elements_design_version_id", "generated_slide_elements", ["design_version_id"])
        op.create_index("ix_generated_slide_elements_source_slide_id", "generated_slide_elements", ["source_slide_id"])
        op.create_index("ix_generated_slide_elements_element_key", "generated_slide_elements", ["element_key"])
        op.create_index("ix_generated_slide_elements_element_type", "generated_slide_elements", ["element_type"])

    if not _has_table("generated_slide_element_versions"):
        op.create_table(
            "generated_slide_element_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("element_id", sa.String(), sa.ForeignKey("generated_slide_elements.id", ondelete="CASCADE"), nullable=False),
            sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
            sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source", sa.String(), nullable=False, server_default="initial_generation"),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("style_json", sa.JSON(), nullable=True),
            sa.Column("content_json", sa.JSON(), nullable=True),
            sa.Column("change_summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_generated_slide_element_versions_element_id", "generated_slide_element_versions", ["element_id"])
        op.create_index("ix_generated_slide_element_versions_generated_slide_id", "generated_slide_element_versions", ["generated_slide_id"])
        op.create_index("ix_generated_slide_element_versions_design_version_id", "generated_slide_element_versions", ["design_version_id"])
        op.create_index("ix_generated_slide_element_versions_status", "generated_slide_element_versions", ["status"])


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_generated_slide_element_versions_status", "generated_slide_element_versions"),
        ("ix_generated_slide_element_versions_design_version_id", "generated_slide_element_versions"),
        ("ix_generated_slide_element_versions_generated_slide_id", "generated_slide_element_versions"),
        ("ix_generated_slide_element_versions_element_id", "generated_slide_element_versions"),
        ("ix_generated_slide_elements_element_type", "generated_slide_elements"),
        ("ix_generated_slide_elements_element_key", "generated_slide_elements"),
        ("ix_generated_slide_elements_source_slide_id", "generated_slide_elements"),
        ("ix_generated_slide_elements_design_version_id", "generated_slide_elements"),
        ("ix_generated_slide_elements_deck_id", "generated_slide_elements"),
        ("ix_generated_slide_elements_generated_slide_id", "generated_slide_elements"),
    ]:
        if _has_table(table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in ["generated_slide_element_versions", "generated_slide_elements"]:
        if _has_table(table_name):
            op.drop_table(table_name)
