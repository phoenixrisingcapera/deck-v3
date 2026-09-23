"""add pgvector-backed vector_chunks table

Revision ID: 0038_vector_chunks_pgvector
Revises: 0037_repair_deck_llm_artifact_bucket_payload_key
Create Date: 2026-07-07 11:20:00.000000
"""

from __future__ import annotations

# DISABLED: This historical revision remains in the core lineage only as a
# no-op compatibility marker. Vector storage belongs exclusively to the AI
# database and is created by alembic_ai/versions/0001_ai_baseline.py.
# from alembic import op
# import sqlalchemy as sa
# from pgvector.sqlalchemy import Vector


revision = "0038_vector_chunks_pgvector"
down_revision = "0037_repair_deck_llm_artifact_bucket_payload_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DISABLED for the core lineage: vector persistence is created by alembic_ai.
    # Keeping this revision import-safe is important because core deployments
    # must not require the pgvector Python package or extension.
    return
    # DISABLED legacy DDL retained in git history; it must never run against
    # the core database. The AI baseline owns the equivalent AI tables.


def downgrade() -> None:
    # DISABLED: core rollback must not drop AI-owned vector tables.
    pass
