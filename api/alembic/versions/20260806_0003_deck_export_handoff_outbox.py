"""Add durable admin handoff outbox state to deck exports."""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0003_export_handoff"
down_revision = "20260806_0002_render_cap_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deck_exports", sa.Column("handoff_status", sa.String(), nullable=False, server_default="ready"))
    op.add_column("deck_exports", sa.Column("handoff_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("deck_exports", sa.Column("handoff_error", sa.Text(), nullable=True))
    op.add_column("deck_exports", sa.Column("handoff_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("deck_exports", sa.Column("handoff_ready_at", sa.DateTime(), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("deck_exports") as batch_op:
            batch_op.alter_column("handoff_status", server_default="pending")
    else:
        op.alter_column("deck_exports", "handoff_status", server_default="pending")
    op.create_index("ix_deck_exports_handoff_status", "deck_exports", ["handoff_status"])


def downgrade() -> None:
    op.drop_index("ix_deck_exports_handoff_status", table_name="deck_exports")
    op.drop_column("deck_exports", "handoff_ready_at")
    op.drop_column("deck_exports", "handoff_attempted_at")
    op.drop_column("deck_exports", "handoff_error")
    op.drop_column("deck_exports", "handoff_attempts")
    op.drop_column("deck_exports", "handoff_status")
