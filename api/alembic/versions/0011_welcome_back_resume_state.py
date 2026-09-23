"""add welcome back resume state fields

Revision ID: 0011_welcome_back_resume_state
Revises: 0010_account_billing_parity
Create Date: 2026-06-11 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_welcome_back_resume_state"
down_revision = "0010_account_billing_parity"
branch_labels = None
depends_on = None


def _existing_columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _existing_columns("deck_workspace_preferences")

    with op.batch_alter_table("deck_workspace_preferences") as batch_op:
        if "selected_slide_id" not in columns:
            batch_op.add_column(sa.Column("selected_slide_id", sa.String(), nullable=True))
        if "last_batch_id" not in columns:
            batch_op.add_column(sa.Column("last_batch_id", sa.String(), nullable=True))
        if "last_slide_version_id" not in columns:
            batch_op.add_column(sa.Column("last_slide_version_id", sa.String(), nullable=True))


def downgrade() -> None:
    columns = _existing_columns("deck_workspace_preferences")

    with op.batch_alter_table("deck_workspace_preferences") as batch_op:
        for column_name in ["last_slide_version_id", "last_batch_id", "selected_slide_id"]:
            if column_name in columns:
                batch_op.drop_column(column_name)
