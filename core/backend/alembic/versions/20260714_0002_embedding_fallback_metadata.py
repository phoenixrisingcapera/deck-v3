"""add embedding fallback metadata and align vector storage dimensions

Revision ID: 20260714_0002_embedding_fallback_metadata
Revises: 20260714_0001_processing_run_stage_denormalization
"""

from __future__ import annotations

# DISABLED: This historical revision belongs to the former core vector layout.
# Vector storage is now created and evolved only by alembic_ai. Keeping the
# imports commented makes core Alembic safe when pgvector is installed only in
# the AI migration/runtime environment.
# from alembic import op
# import sqlalchemy as sa
# from pgvector.sqlalchemy import Vector


revision = "20260714_0002_embedding_fallback_metadata"
down_revision = "20260714_0001_processing_run_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DISABLED: all vector schema changes are AI-database migrations.
    return


def downgrade() -> None:
    # DISABLED: never mutate AI-owned vector storage from core rollback.
    pass
