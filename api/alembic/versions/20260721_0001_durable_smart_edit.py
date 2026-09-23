"""Add durable Smart Edit workflow lifecycle.

Revision ID: 20260721_0001_durable_smart_edit
Revises: 20260717_0003_deck_media_library
"""

from alembic import op
import sqlalchemy as sa

revision = "20260721_0001_durable_smart_edit"
down_revision = "20260717_0003_deck_media_library"
branch_labels = None
depends_on = None


def _job_type_check() -> str:
    values = (
        "source_ingestion", "source_extraction", "miniatures", "brand_extraction",
        "smart_deck_context", "db_publisher", "llm_generation", "selected_slide_generation",
        "schema_validation", "preview_render", "apply_version", "compile_final_deck", "export",
        "due_diligence", "deck_map_analysis", "market_research", "media_processing", "smart_edit",
    )
    return "job_type in (" + ",".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    # Smart Edit is an independent PostgreSQL workflow. Its historical
    # migration alters foreign-key constraints in place, an operation SQLite
    # cannot perform without recreating several unrelated tables. The local
    # Instant Deck runtime deliberately does not enable that workflow.
    if op.get_bind().dialect.name == "sqlite":
        return

    op.add_column("smart_edit_runs", sa.Column("status", sa.String(), nullable=False, server_default="queued"))
    op.add_column("smart_edit_runs", sa.Column("workflow_job_id", sa.String(), nullable=True))
    op.add_column("smart_edit_runs", sa.Column("error_code", sa.String(), nullable=True))
    op.add_column("smart_edit_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("smart_edit_runs", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_foreign_key("fk_smart_edit_runs_workflow_job", "smart_edit_runs", "workflow_jobs", ["workflow_job_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_smart_edit_runs_status", "smart_edit_runs", ["status"])
    op.create_index("ix_smart_edit_runs_workflow_job_id", "smart_edit_runs", ["workflow_job_id"], unique=True)
    op.drop_constraint("ck_workflow_jobs_job_type", "workflow_jobs", type_="check")
    op.create_check_constraint("ck_workflow_jobs_job_type", "workflow_jobs", _job_type_check())


def downgrade() -> None:
    op.drop_constraint("ck_workflow_jobs_job_type", "workflow_jobs", type_="check")
    op.drop_index("ix_smart_edit_runs_workflow_job_id", table_name="smart_edit_runs")
    op.drop_index("ix_smart_edit_runs_status", table_name="smart_edit_runs")
    op.drop_constraint("fk_smart_edit_runs_workflow_job", "smart_edit_runs", type_="foreignkey")
    op.drop_column("smart_edit_runs", "updated_at")
    op.drop_column("smart_edit_runs", "error_message")
    op.drop_column("smart_edit_runs", "error_code")
    op.drop_column("smart_edit_runs", "workflow_job_id")
    op.drop_column("smart_edit_runs", "status")
