"""record AI budget reservation ownership in the Core lineage

Revision ID: 20260722_0001_ai_budget_reservations
Revises: 20260721_0001_durable_smart_edit
"""

revision = "20260722_0001_ai_budget_reservations"
down_revision = "20260721_0001_durable_smart_edit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CORRECTED: PR #126 originally altered ``ai_usage_buckets`` here, but the
    # table is owned by the separate AI database and AI Alembic lineage. Keep
    # this published revision as a no-op history marker so existing Core
    # databases can advance safely. The schema change now lives in
    # alembic_ai/versions/0004_ai_budget_reservations.py.
    pass


def downgrade() -> None:
    # The Core lineage does not own AI schema and must not remove AI columns.
    pass
