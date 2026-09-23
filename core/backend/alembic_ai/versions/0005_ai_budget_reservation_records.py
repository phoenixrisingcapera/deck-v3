"""Store one durable row per reserved provider operation."""

from alembic import op
import sqlalchemy as sa

revision = "0005_ai_budget_reservation_records"
down_revision = "0004_ai_budget_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_budget_reservations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("reservation_key", sa.String(), nullable=False),
        sa.Column("bucket_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_key"),
    )
    for column in ("reservation_key", "bucket_id", "user_id", "operation", "status", "created_at"):
        op.create_index(f"ix_ai_budget_reservations_{column}", "ai_budget_reservations", [column], unique=False)


def downgrade() -> None:
    # Preserve budget evidence; forward corrective migrations own retirement.
    pass
