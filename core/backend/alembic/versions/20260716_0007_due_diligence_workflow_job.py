"""Allow the dedicated durable Due Diligence workflow job type."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0007_due_diligence_workflow_job"
down_revision = "20260716_0006_due_diligence_report_integrity"
branch_labels = None
depends_on = None

# DISABLED: The original static expressions rejected legacy job types already
# persisted in production. They remain here as migration history while the
# dynamic expression below preserves deployed audit records.
# OLD_JOB_TYPE_CHECK = "job_type in (...,'export')"
# NEW_JOB_TYPE_CHECK = OLD_JOB_TYPE_CHECK[:-1] + ",'due_diligence')"


BASE_JOB_TYPES = {
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "brand_extraction",
    "smart_deck_context",
    "db_publisher",
    "llm_generation",
    "selected_slide_generation",
    "schema_validation",
    "preview_render",
    "apply_version",
    "compile_final_deck",
    "export",
}


def _job_type_check(job_types: set[str]) -> str:
    values = ",".join(f"'{value.replace(chr(39), chr(39) * 2)}'" for value in sorted(job_types))
    return f"job_type in ({values})"


def _deployed_job_types() -> set[str]:
    rows = op.get_bind().execute(sa.text("SELECT DISTINCT job_type FROM workflow_jobs"))
    return {str(row[0]) for row in rows if row[0]}


def _has_job_type_constraint() -> bool:
    return any(
        constraint.get("name") == "ck_workflow_jobs_job_type"
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("workflow_jobs")
    )


def _replace(expression: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite can only replace a table-level CHECK through Alembic's
        # copy-and-move batch operation. This preserves durable rows while
        # keeping the historical repair idempotent in local development.
        with op.batch_alter_table("workflow_jobs") as batch_op:
            if _has_job_type_constraint():
                batch_op.drop_constraint("ck_workflow_jobs_job_type", type_="check")
            batch_op.create_check_constraint("ck_workflow_jobs_job_type", expression)
        return

    if _has_job_type_constraint():
        op.drop_constraint("ck_workflow_jobs_job_type", "workflow_jobs", type_="check")
    op.create_check_constraint("ck_workflow_jobs_job_type", "workflow_jobs", expression)


def upgrade() -> None:
    # Preserve legacy job identities already persisted by earlier production
    # releases while extending the active contract. Rewriting historical jobs
    # would break auditability and caused the first Railway migration attempt
    # to fail safely with a check violation.
    _replace(_job_type_check(BASE_JOB_TYPES | _deployed_job_types() | {"due_diligence"}))


def downgrade() -> None:
    # Preserve any deployed legacy values during downgrade as well. Existing
    # due_diligence rows intentionally keep the extended constraint valid.
    _replace(_job_type_check(BASE_JOB_TYPES | _deployed_job_types()))
