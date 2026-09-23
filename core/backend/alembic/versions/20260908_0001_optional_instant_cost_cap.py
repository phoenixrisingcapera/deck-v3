"""Allow uncapped Instant operations without changing existing operation limits.

Revision ID: 20260908_0001_instant_cost
Revises: 20260822_0001_local_findings
"""
from alembic import op
import sqlalchemy as sa

revision = "20260908_0001_instant_cost"
down_revision = "20260822_0001_local_findings"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("instant_deck_operations") as batch:
        batch.drop_constraint("ck_instant_deck_operation_max_cost", type_="check")
        batch.alter_column("max_cost_cents", existing_type=sa.Float(), nullable=True, server_default=None)
        batch.create_check_constraint("ck_instant_deck_operation_max_cost", "max_cost_cents IS NULL OR max_cost_cents >= 0")


def downgrade():
    # Never silently clamp an operation's explicit spend authorization.
    incompatible = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM instant_deck_operations WHERE max_cost_cents IS NULL OR max_cost_cents > 500"
    )).scalar()
    if incompatible:
        raise RuntimeError("Cannot restore the old cost cap while uncapped or higher-limit operations exist.")
    with op.batch_alter_table("instant_deck_operations") as batch:
        batch.drop_constraint("ck_instant_deck_operation_max_cost", type_="check")
        batch.alter_column("max_cost_cents", existing_type=sa.Float(), nullable=False)
        batch.create_check_constraint("ck_instant_deck_operation_max_cost", "max_cost_cents >= 0 AND max_cost_cents <= 500")
