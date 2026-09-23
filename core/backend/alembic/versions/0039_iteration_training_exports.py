"""add workspace training policy and iteration training snapshots

Revision ID: 0039_iteration_training_exports
Revises: 0038_vector_chunks_pgvector
Create Date: 2026-07-07 15:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0039_iteration_training_exports"
down_revision = "0038_vector_chunks_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("allow_model_training", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("workspaces", sa.Column("model_training_policy", sa.String(), nullable=False, server_default="disabled"))
    op.create_index("ix_workspaces_allow_model_training", "workspaces", ["allow_model_training"])
    op.create_index("ix_workspaces_model_training_policy", "workspaces", ["model_training_policy"])

    op.create_table(
        "iteration_training_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("deck_id", sa.String(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("source_surface", sa.String(), nullable=False, server_default="iteration_history"),
        sa.Column("visibility_state", sa.String(), nullable=False, server_default="visible"),
        sa.Column("export_state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["batch_id"], ["design_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id"),
    )
    op.create_index("ix_iteration_training_snapshots_deck_id", "iteration_training_snapshots", ["deck_id"])
    op.create_index("ix_iteration_training_snapshots_batch_id", "iteration_training_snapshots", ["batch_id"])
    op.create_index("ix_iteration_training_snapshots_source_surface", "iteration_training_snapshots", ["source_surface"])
    op.create_index("ix_iteration_training_snapshots_visibility_state", "iteration_training_snapshots", ["visibility_state"])
    op.create_index("ix_iteration_training_snapshots_export_state", "iteration_training_snapshots", ["export_state"])


def downgrade() -> None:
    op.drop_index("ix_iteration_training_snapshots_export_state", table_name="iteration_training_snapshots")
    op.drop_index("ix_iteration_training_snapshots_visibility_state", table_name="iteration_training_snapshots")
    op.drop_index("ix_iteration_training_snapshots_source_surface", table_name="iteration_training_snapshots")
    op.drop_index("ix_iteration_training_snapshots_batch_id", table_name="iteration_training_snapshots")
    op.drop_index("ix_iteration_training_snapshots_deck_id", table_name="iteration_training_snapshots")
    op.drop_table("iteration_training_snapshots")

    op.drop_index("ix_workspaces_model_training_policy", table_name="workspaces")
    op.drop_index("ix_workspaces_allow_model_training", table_name="workspaces")
    op.drop_column("workspaces", "model_training_policy")
    op.drop_column("workspaces", "allow_model_training")
