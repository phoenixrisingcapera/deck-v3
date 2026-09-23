"""Add transactional Due Diligence chat exchange reservations.

Revision ID: 20260727_0001_diligence_chat_reservations
Revises: 20260722_0001_ai_budget_reservations
"""

from alembic import op
import sqlalchemy as sa


revision = "20260727_0001_diligence_chat_reservations"
down_revision = "20260722_0001_ai_budget_reservations"
branch_labels = None
depends_on = None

_TABLE = "deck_llm_artifacts"
_UNIQUE = "uq_deck_llm_artifacts_diligence_exchange"


def _columns() -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def _indexes() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    names = {index["name"] for index in inspector.get_indexes(_TABLE)}
    names.update(constraint["name"] for constraint in inspector.get_unique_constraints(_TABLE))
    return names


def upgrade() -> None:
    if _TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    columns = _columns()
    with op.batch_alter_table(_TABLE) as batch:
        if "identity_user_id" not in columns:
            batch.add_column(sa.Column("identity_user_id", sa.String(), nullable=True))
        if "identity_audience" not in columns:
            batch.add_column(sa.Column("identity_audience", sa.String(), nullable=True))
        if "client_exchange_key" not in columns:
            batch.add_column(sa.Column("client_exchange_key", sa.String(length=120), nullable=True))
        if op.get_bind().dialect.name == "sqlite" and _UNIQUE not in _indexes():
            batch.create_unique_constraint(
                _UNIQUE,
                ["deck_id", "artifact_type", "identity_user_id", "identity_audience", "client_exchange_key"],
            )
    if op.get_bind().dialect.name != "sqlite" and _UNIQUE not in _indexes():
        op.create_unique_constraint(
            _UNIQUE,
            _TABLE,
            ["deck_id", "artifact_type", "identity_user_id", "identity_audience", "client_exchange_key"],
        )


def downgrade() -> None:
    if _TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    if _UNIQUE in _indexes():
        op.drop_constraint(_UNIQUE, _TABLE, type_="unique")
    columns = _columns()
    with op.batch_alter_table(_TABLE) as batch:
        for column in ("client_exchange_key", "identity_audience", "identity_user_id"):
            if column in columns:
                batch.drop_column(column)
