"""Add explicit processing stage columns to deck_extraction_runs

Revision ID: 0021_add_processing_stage_columns
Revises: 20260625_0005_processing_checksum
Create Date: 2026-07-14

This migration adds explicit columns for processing stage tracking instead of
relying solely on metadata_json. This improves query performance and makes it
easier to filter/sort by processing state.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0021_add_processing_stage_columns'
down_revision = '20260625_0005_processing_checksum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration was added after some deployments had already created the
    # columns. Inspect first rather than relying on PostgreSQL-only ``IF NOT
    # EXISTS`` syntax: the same repair must be runnable by the local SQLite
    # development runtime.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("deck_extraction_runs")}
    requested_columns = (
        sa.Column("current_stage", sa.String(100), nullable=True),
        sa.Column("current_stage_label", sa.String(200), nullable=True),
        sa.Column("next_action", sa.String(100), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=True, server_default="3"),
        sa.Column("locked_by", sa.String(200), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )
    for column in requested_columns:
        if column.name not in columns:
            op.add_column("deck_extraction_runs", column)

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("deck_extraction_runs")}
    if "ix_deck_extraction_runs_current_stage" not in indexes:
        op.create_index("ix_deck_extraction_runs_current_stage", "deck_extraction_runs", ["current_stage"])
    if "ix_deck_extraction_runs_status_stage" not in indexes:
        op.create_index(
            "ix_deck_extraction_runs_status_stage",
            "deck_extraction_runs",
            ["status", "current_stage"],
        )


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_deck_extraction_runs_status_stage', table_name='deck_extraction_runs')
    op.drop_index('ix_deck_extraction_runs_current_stage', table_name='deck_extraction_runs')
    
    # Remove columns
    op.drop_column('deck_extraction_runs', 'heartbeat_at')
    op.drop_column('deck_extraction_runs', 'locked_at')
    op.drop_column('deck_extraction_runs', 'locked_by')
    op.drop_column('deck_extraction_runs', 'max_attempts')
    op.drop_column('deck_extraction_runs', 'attempt_count')
    op.drop_column('deck_extraction_runs', 'next_action')
    op.drop_column('deck_extraction_runs', 'current_stage_label')
    op.drop_column('deck_extraction_runs', 'current_stage')
