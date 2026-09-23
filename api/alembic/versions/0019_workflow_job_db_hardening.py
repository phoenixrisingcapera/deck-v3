"""harden workflow job lifecycle constraints

Revision ID: 0019_workflow_job_db_hardening
Revises: 0018_workflow_jobs
Create Date: 2026-06-26 21:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_workflow_job_db_hardening"
down_revision = "0018_workflow_jobs"
branch_labels = None
depends_on = None

WORKFLOW_JOB_TYPE_CHECK = (
    "job_type in ("
    "'source_ingestion',"
    "'source_extraction',"
    "'miniatures',"
    "'brand_extraction',"
    "'smart_deck_context',"
    "'db_publisher',"
    "'llm_generation',"
    "'schema_validation',"
    "'preview_render',"
    "'apply_version',"
    "'compile_final_deck',"
    "'export'"
    ")"
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in _inspector().get_indexes(table_name))


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    try:
        constraints = _inspector().get_check_constraints(table_name)
    except NotImplementedError:
        return False
    return any(constraint.get("name") == constraint_name for constraint in constraints)


def _create_check_constraint(table_name: str, constraint_name: str, expression: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_check_constraint(constraint_name, expression)
    else:
        op.create_check_constraint(constraint_name, table_name, expression)


def upgrade() -> None:
    if _has_table("workflow_jobs"):
        if not _has_check_constraint("workflow_jobs", "ck_workflow_jobs_job_type"):
            _create_check_constraint("workflow_jobs", "ck_workflow_jobs_job_type", WORKFLOW_JOB_TYPE_CHECK)
        if not _has_check_constraint("workflow_jobs", "ck_workflow_jobs_attempt_values"):
            _create_check_constraint(
                "workflow_jobs", "ck_workflow_jobs_attempt_values", "attempt_count >= 0 and max_attempts >= 1"
            )
        if not _has_index("workflow_jobs", "ix_workflow_jobs_recovery_scan"):
            op.create_index(
                "ix_workflow_jobs_recovery_scan",
                "workflow_jobs",
                ["status", "heartbeat_at", "locked_until"],
            )

    if _has_table("workflow_job_dependencies") and not _has_check_constraint(
        "workflow_job_dependencies",
        "ck_workflow_job_dependencies_type",
    ):
        _create_check_constraint(
            "workflow_job_dependencies",
            "ck_workflow_job_dependencies_type",
            "dependency_type in ('requires_completion')",
        )


def downgrade() -> None:
    if _has_table("workflow_job_dependencies") and _has_check_constraint(
        "workflow_job_dependencies",
        "ck_workflow_job_dependencies_type",
    ):
        op.drop_constraint(
            "ck_workflow_job_dependencies_type",
            "workflow_job_dependencies",
            type_="check",
        )

    if _has_table("workflow_jobs"):
        if _has_index("workflow_jobs", "ix_workflow_jobs_recovery_scan"):
            op.drop_index("ix_workflow_jobs_recovery_scan", table_name="workflow_jobs")
        if _has_check_constraint("workflow_jobs", "ck_workflow_jobs_attempt_values"):
            op.drop_constraint(
                "ck_workflow_jobs_attempt_values",
                "workflow_jobs",
                type_="check",
            )
        if _has_check_constraint("workflow_jobs", "ck_workflow_jobs_job_type"):
            op.drop_constraint(
                "ck_workflow_jobs_job_type",
                "workflow_jobs",
                type_="check",
            )
