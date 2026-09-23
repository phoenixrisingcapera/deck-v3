"""Bind Instant HTML capabilities during a rolling deployment."""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0002_render_cap_binding"
down_revision = "20260806_0001_openai_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instant_deck_render_capabilities", sa.Column("scope", sa.String(), nullable=False, server_default="section"))
    op.add_column("instant_deck_render_capabilities", sa.Column("design_version_id", sa.String(), nullable=True))
    op.add_column("instant_deck_render_capabilities", sa.Column("artifact_encryption_key_version", sa.String(), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.execute(sa.text(
            "UPDATE instant_deck_render_capabilities AS capability "
            "SET design_version_id = artifact.design_version_id, "
            "artifact_encryption_key_version = artifact.encryption_key_version "
            "FROM instant_deck_html_artifacts AS artifact "
            "WHERE artifact.id = capability.artifact_id"
        ))
        op.create_foreign_key("fk_render_capability_design_version", "instant_deck_render_capabilities", "design_versions", ["design_version_id"], ["id"], ondelete="CASCADE")
        op.create_check_constraint("ck_instant_deck_render_capability_scope", "instant_deck_render_capabilities", "scope in ('section','full_deck')")
    else:
        with op.batch_alter_table("instant_deck_render_capabilities") as batch_op:
            batch_op.create_foreign_key("fk_render_capability_design_version", "design_versions", ["design_version_id"], ["id"], ondelete="CASCADE")
            batch_op.create_check_constraint("ck_instant_deck_render_capability_scope", "scope in ('section','full_deck')")
    op.create_index("ix_instant_deck_render_capabilities_design_version_id", "instant_deck_render_capabilities", ["design_version_id"])


def downgrade() -> None:
    op.drop_constraint("ck_instant_deck_render_capability_scope", "instant_deck_render_capabilities", type_="check")
    op.drop_index("ix_instant_deck_render_capabilities_design_version_id", table_name="instant_deck_render_capabilities")
    op.drop_constraint("fk_render_capability_design_version", "instant_deck_render_capabilities", type_="foreignkey")
    op.drop_column("instant_deck_render_capabilities", "artifact_encryption_key_version")
    op.drop_column("instant_deck_render_capabilities", "design_version_id")
    op.drop_column("instant_deck_render_capabilities", "scope")
