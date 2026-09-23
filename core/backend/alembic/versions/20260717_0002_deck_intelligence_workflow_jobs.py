"""Allow durable Deck Map analysis and Market Research workflow jobs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0002_deck_intelligence_workflow_jobs"
down_revision = "20260717_0001_workspace_ai_model_categories"
branch_labels = None
depends_on = None


def _job_type_check(job_types: set[str]) -> str:
    values = ",".join(f"'{value.replace(chr(39), chr(39) * 2)}'" for value in sorted(job_types))
    return f"job_type in ({values})"


def _deployed_job_types() -> set[str]:
    rows = op.get_bind().execute(sa.text("SELECT DISTINCT job_type FROM workflow_jobs"))
    return {str(row[0]) for row in rows if row[0]}


def _replace(job_types: set[str]) -> None:
    constraints = sa.inspect(op.get_bind()).get_check_constraints("workflow_jobs")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("workflow_jobs") as batch_op:
            if any(item.get("name") == "ck_workflow_jobs_job_type" for item in constraints):
                batch_op.drop_constraint("ck_workflow_jobs_job_type", type_="check")
            batch_op.create_check_constraint("ck_workflow_jobs_job_type", _job_type_check(job_types))
        return
    if any(item.get("name") == "ck_workflow_jobs_job_type" for item in constraints):
        op.drop_constraint("ck_workflow_jobs_job_type", "workflow_jobs", type_="check")
    op.create_check_constraint("ck_workflow_jobs_job_type", "workflow_jobs", _job_type_check(job_types))


def upgrade() -> None:
    _replace(_deployed_job_types() | {"deck_map_analysis", "market_research"})


def downgrade() -> None:
    # Preserve historical job identities; removing accepted values would make
    # existing audit rows violate the database contract.
    _replace(_deployed_job_types())
