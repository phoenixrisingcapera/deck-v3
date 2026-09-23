"""add workflow job lifecycle columns

Revision ID: 0020_workflow_job_lifecycle_columns
Revises: 0019_workflow_job_db_hardening
Create Date: 2026-06-27 10:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_workflow_job_lifecycle_columns"
down_revision = "0019_workflow_job_db_hardening"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column.get("name") == column_name for column in _inspector().get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in _inspector().get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("workflow_jobs"):
        return

    if not _has_column("workflow_jobs", "recovery_count"):
        op.add_column(
            "workflow_jobs",
            sa.Column("recovery_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column("workflow_jobs", "last_recovered_at"):
        op.add_column(
            "workflow_jobs",
            sa.Column("last_recovered_at", sa.DateTime(), nullable=True),
        )
    if not _has_column("workflow_jobs", "last_recovered_by"):
        op.add_column(
            "workflow_jobs",
            sa.Column("last_recovered_by", sa.String(), nullable=True),
        )
    if not _has_column("workflow_jobs", "terminal_reason"):
        op.add_column(
            "workflow_jobs",
            sa.Column("terminal_reason", sa.String(), nullable=True),
        )
    if not _has_column("workflow_jobs", "published_phase"):
        op.add_column(
            "workflow_jobs",
            sa.Column("published_phase", sa.String(), nullable=True),
        )
    if not _has_column("workflow_jobs", "published_at"):
        op.add_column(
            "workflow_jobs",
            sa.Column("published_at", sa.DateTime(), nullable=True),
        )

    if not _has_index("workflow_jobs", "ix_workflow_jobs_recovery_count"):
        op.create_index("ix_workflow_jobs_recovery_count", "workflow_jobs", ["recovery_count"])
    if not _has_index("workflow_jobs", "ix_workflow_jobs_last_recovered_at"):
        op.create_index("ix_workflow_jobs_last_recovered_at", "workflow_jobs", ["last_recovered_at"])
    if not _has_index("workflow_jobs", "ix_workflow_jobs_terminal_reason"):
        op.create_index("ix_workflow_jobs_terminal_reason", "workflow_jobs", ["terminal_reason"])
    if not _has_index("workflow_jobs", "ix_workflow_jobs_published_phase"):
        op.create_index("ix_workflow_jobs_published_phase", "workflow_jobs", ["published_phase"])


def downgrade() -> None:
    if not _has_table("workflow_jobs"):
        return

    for index_name in [
        "ix_workflow_jobs_published_phase",
        "ix_workflow_jobs_terminal_reason",
        "ix_workflow_jobs_last_recovered_at",
        "ix_workflow_jobs_recovery_count",
    ]:
        if _has_index("workflow_jobs", index_name):
            op.drop_index(index_name, table_name="workflow_jobs")

    for column_name in [
        "published_at",
        "published_phase",
        "terminal_reason",
        "last_recovered_by",
        "last_recovered_at",
        "recovery_count",
    ]:
        if _has_column("workflow_jobs", column_name):
            op.drop_column("workflow_jobs", column_name)
