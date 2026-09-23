"""Repair the workflow job type constraint for fresh databases.

Revision ID: 20260819_0001_workflow_job_type_constraint
Revises: 20260817_0001_design_version_provenance
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260819_0001_workflow_job_type_constraint"
down_revision = "20260817_0001_design_version_provenance"
branch_labels = None
depends_on = None

CANONICAL_JOB_TYPES = {
    "source_ingestion",
    "source_extraction",
    "miniatures",
    "brand_extraction",
    "smart_deck_context",
    "db_publisher",
    "llm_generation",
    "instant_deck_generation",
    "selected_slide_generation",
    "schema_validation",
    "preview_render",
    "apply_version",
    "compile_final_deck",
    "export",
    "due_diligence",
    "deck_map_analysis",
    "market_research",
    "smart_edit",
    "media_processing",
}


def _deployed_job_types() -> set[str]:
    rows = op.get_bind().execute(sa.text("SELECT DISTINCT job_type FROM workflow_jobs"))
    return {str(row[0]) for row in rows if row[0]}


def _replace() -> None:
    job_types = CANONICAL_JOB_TYPES | _deployed_job_types()
    values = ",".join(
        f"'{value.replace(chr(39), chr(39) * 2)}'" for value in sorted(job_types)
    )
    constraints = sa.inspect(op.get_bind()).get_check_constraints("workflow_jobs")
    expression = f"job_type in ({values})"
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("workflow_jobs") as batch_op:
            if any(item.get("name") == "ck_workflow_jobs_job_type" for item in constraints):
                batch_op.drop_constraint("ck_workflow_jobs_job_type", type_="check")
            batch_op.create_check_constraint("ck_workflow_jobs_job_type", expression)
        return
    if any(item.get("name") == "ck_workflow_jobs_job_type" for item in constraints):
        op.drop_constraint("ck_workflow_jobs_job_type", "workflow_jobs", type_="check")
    op.create_check_constraint(
        "ck_workflow_jobs_job_type",
        "workflow_jobs",
        expression,
    )


def upgrade() -> None:
    _replace()


def downgrade() -> None:
    # Never tighten this constraint during rollback: historical job identities
    # must remain valid after they have been durably persisted.
    _replace()
