"""Reconcile legacy core column widths without changing ownership."""

from typing import Sequence, Union

from alembic import op


revision: str = "20260715_0002_core_reconciliation"
down_revision: Union[str, None] = "20260715_0001_science_backed_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite TEXT has no length distinction and cannot ALTER COLUMN. The
    # reconciliation is already satisfied on fresh local SQLite databases.
    if op.get_bind().dialect.name == "sqlite":
        return
    op.execute("ALTER TABLE IF EXISTS deck_extraction_runs ALTER COLUMN error_message TYPE TEXT")
    op.execute("ALTER TABLE IF EXISTS workflow_jobs ALTER COLUMN error_message TYPE TEXT")


def downgrade() -> None:
    # Keep widened diagnostics columns during rollback; narrowing can truncate
    # production failure context and requires an explicit operator decision.
    pass
