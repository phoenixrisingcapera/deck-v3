"""add failure tickets

Revision ID: 0035_failure_tickets
Revises: 0034_repair_security_audit_request_id
Create Date: 2026-06-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0035_failure_tickets"
down_revision = "0034_repair_security_audit_request_id"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if _table_exists("failure_tickets"):
        return

    op.create_table(
        "failure_tickets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("route", sa.String(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("api_path", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("deck_id", sa.String(), nullable=True),
        sa.Column("error_name", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_stack", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
        sa.Column("source", sa.String(), nullable=False, server_default="frontend"),
        sa.Column("status", sa.String(), nullable=False, server_default="new"),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("fixed_at", sa.DateTime(), nullable=True),
        sa.Column("ignored_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "route",
        "api_path",
        "status_code",
        "user_id",
        "user_email",
        "deck_id",
        "severity",
        "source",
        "status",
        "request_id",
        "created_at",
        "updated_at",
    ):
        op.create_index(op.f(f"ix_failure_tickets_{column}"), "failure_tickets", [column], unique=False)


def downgrade() -> None:
    if not _table_exists("failure_tickets"):
        return

    for column in (
        "updated_at",
        "created_at",
        "request_id",
        "status",
        "source",
        "severity",
        "deck_id",
        "user_email",
        "user_id",
        "status_code",
        "api_path",
        "route",
    ):
        op.drop_index(op.f(f"ix_failure_tickets_{column}"), table_name="failure_tickets")
    op.drop_table("failure_tickets")
