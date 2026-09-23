"""Reconcile missing Core columns against the product ORM contract.

Existing Core databases were created from several historical migration branches.
The tables exist, but a few later columns were absent while Alembic reported an
older branch revision. This migration is intentionally additive and idempotent.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260715_0005_core_data_contract_reconciliation"
down_revision = "20260715_0004_core_schema_reconciliation"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing(
        "workspace_ai_credentials",
        sa.Column("key_version", sa.String(), nullable=False, server_default="legacy"),
    )
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("workspace_ai_credentials")}
    if "ix_workspace_ai_credentials_key_version" not in indexes:
        op.create_index(
            "ix_workspace_ai_credentials_key_version",
            "workspace_ai_credentials",
            ["key_version"],
        )

    for name in ("bucket_code_key", "bucket_render_schema_key", "bucket_thumbnail_key"):
        _add_column_if_missing("generated_slide_code_versions", sa.Column(name, sa.String(), nullable=True))


def downgrade() -> None:
    # Preserve production data during rollback. The additive reconciliation is
    # intentionally not destructive; a later explicit cleanup can remove fields.
    pass
