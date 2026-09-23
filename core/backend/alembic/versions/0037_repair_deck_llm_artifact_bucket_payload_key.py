"""repair missing deck_llm_artifacts bucket_payload_key column

Revision ID: 0037_repair_deck_llm_artifact_bucket_payload_key
Revises: 0036_repair_deck_generation_workspaces
Create Date: 2026-07-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0037_repair_deck_llm_artifact_bucket_payload_key"
down_revision = "0036_repair_deck_generation_workspaces"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if _column_exists("deck_llm_artifacts", "bucket_payload_key"):
        return

    op.add_column("deck_llm_artifacts", sa.Column("bucket_payload_key", sa.String(), nullable=True))


def downgrade() -> None:
    if not _column_exists("deck_llm_artifacts", "bucket_payload_key"):
        return

    op.drop_column("deck_llm_artifacts", "bucket_payload_key")
