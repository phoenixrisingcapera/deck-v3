"""remove mock provider defaults

Revision ID: 0032_remove_mock_provider_defaults
Revises: 0031_agent_regression_cases
Create Date: 2026-06-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_remove_mock_provider_defaults"
down_revision = "0031_agent_regression_cases"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _alter_default_if_present(table_name: str, column_name: str, default: str) -> None:
    if _has_column(table_name, column_name):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.alter_column(column_name, existing_type=sa.String(), server_default=default)
        else:
            op.alter_column(table_name, column_name, existing_type=sa.String(), server_default=default)


def upgrade() -> None:
    _alter_default_if_present("ai_runs", "provider", "provider_pending")
    _alter_default_if_present("deck_generation_runs", "provider", "anthropic")
    _alter_default_if_present("deck_generation_runs", "generation_mode", "claude")
    _alter_default_if_present("generation_jobs", "provider", "provider_pending")


def downgrade() -> None:
    _alter_default_if_present("generation_jobs", "provider", "deterministic")
    _alter_default_if_present("deck_generation_runs", "generation_mode", "mock")
    _alter_default_if_present("deck_generation_runs", "provider", "mock")
    _alter_default_if_present("ai_runs", "provider", "mock")
