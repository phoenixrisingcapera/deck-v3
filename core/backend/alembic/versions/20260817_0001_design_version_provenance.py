"""Add Instant Deck provenance fields to design versions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0001_design_version_provenance"
down_revision = "20260807_0002_cleanup_xfer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column(
        "design_versions",
        sa.Column("generation_context_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "design_versions",
        sa.Column("transformation_plan_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "design_versions",
        sa.Column("validation_report_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "design_versions",
        sa.Column("repair_history_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("LOCK TABLE design_versions IN ACCESS EXCLUSIVE MODE")
    has_provenance = op.get_bind().execute(sa.text("""
        SELECT EXISTS (
            SELECT 1
            FROM design_versions
            WHERE generation_context_hash IS NOT NULL
               OR transformation_plan_hash IS NOT NULL
               OR validation_report_json IS NOT NULL
               OR repair_history_json IS NOT NULL
        )
    """)).scalar()
    if has_provenance:
        raise RuntimeError("Downgrade blocked: design version provenance data exists.")

    op.drop_column("design_versions", "repair_history_json")
    op.drop_column("design_versions", "validation_report_json")
    op.drop_column("design_versions", "transformation_plan_hash")
    op.drop_column("design_versions", "generation_context_hash")
