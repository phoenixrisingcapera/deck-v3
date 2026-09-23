"""initial schema placeholder

Revision ID: 0001_initial
Revises: None
Create Date: 2026-06-10 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("SELECT 1"))


def downgrade() -> None:
    op.execute(sa.text("SELECT 1"))
