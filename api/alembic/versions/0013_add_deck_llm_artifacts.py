"""add deck llm artifacts

Revision ID: 0013_add_deck_llm_artifacts
Revises: 0012_add_deck_structure_tables
Create Date: 2026-06-12 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_add_deck_llm_artifacts"
down_revision = "0012_add_deck_structure_tables"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _has_table("deck_llm_artifacts"):
        return

    op.create_table(
        "deck_llm_artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extraction_run_id", sa.String(), sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("artifact_key", sa.String(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False, server_default="deck-llm-artifacts.v1"),
        sa.Column("status", sa.String(), nullable=False, server_default="ready"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_deck_llm_artifacts_deck_id", "deck_llm_artifacts", ["deck_id"])
    op.create_index("ix_deck_llm_artifacts_extraction_run_id", "deck_llm_artifacts", ["extraction_run_id"])
    op.create_index("ix_deck_llm_artifacts_artifact_type", "deck_llm_artifacts", ["artifact_type"])
    op.create_index("ix_deck_llm_artifacts_artifact_key", "deck_llm_artifacts", ["artifact_key"])
    op.create_index("ix_deck_llm_artifacts_status", "deck_llm_artifacts", ["status"])


def downgrade() -> None:
    if not _has_table("deck_llm_artifacts"):
        return

    op.drop_index("ix_deck_llm_artifacts_status", table_name="deck_llm_artifacts")
    op.drop_index("ix_deck_llm_artifacts_artifact_key", table_name="deck_llm_artifacts")
    op.drop_index("ix_deck_llm_artifacts_artifact_type", table_name="deck_llm_artifacts")
    op.drop_index("ix_deck_llm_artifacts_extraction_run_id", table_name="deck_llm_artifacts")
    op.drop_index("ix_deck_llm_artifacts_deck_id", table_name="deck_llm_artifacts")
    op.drop_table("deck_llm_artifacts")
