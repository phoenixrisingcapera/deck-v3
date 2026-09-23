"""Make design batches the canonical accepted deck version records."""

from alembic import op
import sqlalchemy as sa


revision = "20260731_0001_unified_deck_versions"
down_revision = "20260730_0001_instant_deck_workflow_job_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite supports these table constraints through Alembic's
        # copy-and-move operation, not ALTER TABLE ADD CONSTRAINT.
        with op.batch_alter_table("design_batches") as batch_op:
            batch_op.add_column(sa.Column("source_surface", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("version_number", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("source_artifact_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("source_design_version_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("change_summary", sa.Text(), nullable=True))
            batch_op.add_column(sa.Column("snapshot_json", sa.JSON(), nullable=True))
            batch_op.add_column(sa.Column("accepted_by_user_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("accepted_at", sa.DateTime(), nullable=True))
            batch_op.create_foreign_key(
                "fk_design_batches_source_design_version",
                "design_versions",
                ["source_design_version_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_foreign_key(
                "fk_design_batches_accepted_by_user",
                "users",
                ["accepted_by_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_unique_constraint("uq_design_batches_deck_version_number", ["deck_id", "version_number"])
            batch_op.create_unique_constraint(
                "uq_design_batches_source_artifact",
                ["deck_id", "source_surface", "source_artifact_id"],
            )
        op.create_index("ix_design_batches_source_surface", "design_batches", ["source_surface"])
        op.create_index("ix_design_batches_source_artifact_id", "design_batches", ["source_artifact_id"])
        op.create_index(
            "ix_design_batches_source_design_version_id",
            "design_batches",
            ["source_design_version_id"],
        )
        op.create_index("ix_design_batches_accepted_by_user_id", "design_batches", ["accepted_by_user_id"])
        op.create_index("ix_design_batches_accepted_at", "design_batches", ["accepted_at"])
        return

    op.add_column("design_batches", sa.Column("source_surface", sa.String(), nullable=True))
    op.add_column("design_batches", sa.Column("version_number", sa.Integer(), nullable=True))
    op.add_column("design_batches", sa.Column("source_artifact_id", sa.String(), nullable=True))
    op.add_column("design_batches", sa.Column("source_design_version_id", sa.String(), nullable=True))
    op.add_column("design_batches", sa.Column("change_summary", sa.Text(), nullable=True))
    op.add_column("design_batches", sa.Column("snapshot_json", sa.JSON(), nullable=True))
    op.add_column("design_batches", sa.Column("accepted_by_user_id", sa.String(), nullable=True))
    op.add_column("design_batches", sa.Column("accepted_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_design_batches_source_design_version",
        "design_batches",
        "design_versions",
        ["source_design_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_design_batches_accepted_by_user",
        "design_batches",
        "users",
        ["accepted_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_design_batches_source_surface", "design_batches", ["source_surface"])
    op.create_index("ix_design_batches_source_artifact_id", "design_batches", ["source_artifact_id"])
    op.create_index("ix_design_batches_source_design_version_id", "design_batches", ["source_design_version_id"])
    op.create_index("ix_design_batches_accepted_by_user_id", "design_batches", ["accepted_by_user_id"])
    op.create_index("ix_design_batches_accepted_at", "design_batches", ["accepted_at"])
    op.create_unique_constraint("uq_design_batches_deck_version_number", "design_batches", ["deck_id", "version_number"])
    op.create_unique_constraint(
        "uq_design_batches_source_artifact",
        "design_batches",
        ["deck_id", "source_surface", "source_artifact_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_design_batches_source_artifact", "design_batches", type_="unique")
    op.drop_constraint("uq_design_batches_deck_version_number", "design_batches", type_="unique")
    op.drop_index("ix_design_batches_accepted_at", table_name="design_batches")
    op.drop_index("ix_design_batches_accepted_by_user_id", table_name="design_batches")
    op.drop_index("ix_design_batches_source_design_version_id", table_name="design_batches")
    op.drop_index("ix_design_batches_source_artifact_id", table_name="design_batches")
    op.drop_index("ix_design_batches_source_surface", table_name="design_batches")
    op.drop_constraint("fk_design_batches_accepted_by_user", "design_batches", type_="foreignkey")
    op.drop_constraint("fk_design_batches_source_design_version", "design_batches", type_="foreignkey")
    op.drop_column("design_batches", "accepted_at")
    op.drop_column("design_batches", "accepted_by_user_id")
    op.drop_column("design_batches", "snapshot_json")
    op.drop_column("design_batches", "change_summary")
    op.drop_column("design_batches", "source_design_version_id")
    op.drop_column("design_batches", "source_artifact_id")
    op.drop_column("design_batches", "source_surface")
    op.drop_column("design_batches", "version_number")
