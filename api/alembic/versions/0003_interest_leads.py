"""add interest leads table

Revision ID: 0003_interest_leads
Revises: 0002_user_access
Create Date: 2026-06-10 21:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_interest_leads"
down_revision: Union[str, None] = "0002_user_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interest_leads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("company_website_url", sa.String(), nullable=True),
        sa.Column("role_label", sa.String(), nullable=True),
        sa.Column("use_case", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.Column("source_page", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_interest_leads_email", "interest_leads", ["email"], unique=False)
    op.create_index("ix_interest_leads_status", "interest_leads", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interest_leads_status", table_name="interest_leads")
    op.drop_index("ix_interest_leads_email", table_name="interest_leads")
    op.drop_table("interest_leads")
