"""create smart deck intake persistence tables

Revision ID: 0006_smart_deck_intake_sources
Revises: 0005_deck_workspace_and_shell
Create Date: 2026-06-10 23:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_smart_deck_intake_sources"
down_revision = "0005_deck_workspace_and_shell"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "company_profiles" not in existing:
        op.create_table(
            "company_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("website_url", sa.String(), nullable=True),
            sa.Column("contact_email", sa.String(), nullable=True),
            sa.Column("inferred_stage", sa.String(), nullable=True),
            sa.Column("founder_name", sa.String(), nullable=True),
            sa.Column("team_summary", sa.Text(), nullable=True),
            sa.Column("linkedin_urls_json", sa.Text(), nullable=True),
            sa.Column("source_notes_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_company_profiles_workspace_id"), "company_profiles", ["workspace_id"], unique=False)
        op.create_index(op.f("ix_company_profiles_canonical_name"), "company_profiles", ["canonical_name"], unique=False)
        op.create_index(op.f("ix_company_profiles_website_url"), "company_profiles", ["website_url"], unique=False)

    if "deck_input_sources" not in existing:
        op.create_table(
            "deck_input_sources",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("original_filename", sa.String(), nullable=True),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("external_url", sa.String(), nullable=True),
            sa.Column("text_value", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="ready"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_deck_input_sources_deck_id"), "deck_input_sources", ["deck_id"], unique=False)
        op.create_index(op.f("ix_deck_input_sources_source_type"), "deck_input_sources", ["source_type"], unique=False)

    if "deck_brand_assets" not in existing:
        op.create_table(
            "deck_brand_assets",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("deck_id", sa.String(), nullable=False),
            sa.Column("source_input_id", sa.String(), nullable=True),
            sa.Column("asset_type", sa.String(), nullable=False),
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_input_id"], ["deck_input_sources.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_deck_brand_assets_deck_id"), "deck_brand_assets", ["deck_id"], unique=False)
        op.create_index(op.f("ix_deck_brand_assets_asset_type"), "deck_brand_assets", ["asset_type"], unique=False)


def downgrade() -> None:
    existing = _existing_tables()

    for index_name, table_name in [
        (op.f("ix_deck_brand_assets_asset_type"), "deck_brand_assets"),
        (op.f("ix_deck_brand_assets_deck_id"), "deck_brand_assets"),
        (op.f("ix_deck_input_sources_source_type"), "deck_input_sources"),
        (op.f("ix_deck_input_sources_deck_id"), "deck_input_sources"),
        (op.f("ix_company_profiles_website_url"), "company_profiles"),
        (op.f("ix_company_profiles_canonical_name"), "company_profiles"),
        (op.f("ix_company_profiles_workspace_id"), "company_profiles"),
    ]:
        if table_name in existing:
            op.drop_index(index_name, table_name=table_name)

    for table_name in ["deck_brand_assets", "deck_input_sources", "company_profiles"]:
        if table_name in existing:
            op.drop_table(table_name)
