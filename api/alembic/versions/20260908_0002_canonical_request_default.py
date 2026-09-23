"""Align the default for future operations; preserve historical row limits."""
from alembic import op
import sqlalchemy as sa

revision = "20260908_0002_request_default"
down_revision = "20260908_0001_instant_cost"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("instant_deck_operations") as batch:
        batch.alter_column("max_provider_request_starts", existing_type=sa.Integer(), server_default="2")


def downgrade():
    with op.batch_alter_table("instant_deck_operations") as batch:
        batch.alter_column("max_provider_request_starts", existing_type=sa.Integer(), server_default="3")
