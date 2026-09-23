"""Track every promoted Instant HTML object until DB publication is durable."""

from alembic import op
import sqlalchemy as sa


revision = "20260807_0001_html_cleanup"
down_revision = "20260806_0004_upload_request_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instant_deck_artifact_cleanup_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("deck_id", sa.String(), nullable=True),
        sa.Column("operation_id", sa.String(), nullable=True),
        sa.Column("provider_attempt_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_by", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operation_id"], ["instant_deck_operations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_attempt_id"], ["instant_deck_provider_attempts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_instant_deck_cleanup_storage_key"),
    )
    for column in ("deck_id", "operation_id", "provider_attempt_id", "status", "locked_by", "created_at"):
        op.create_index(f"ix_instant_deck_artifact_cleanup_tasks_{column}", "instant_deck_artifact_cleanup_tasks", [column])


def downgrade() -> None:
    op.drop_table("instant_deck_artifact_cleanup_tasks")
