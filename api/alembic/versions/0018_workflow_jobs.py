"""add workflow job durability tables

Revision ID: 0018_workflow_jobs
Revises: 0039_iteration_training_exports
Create Date: 2026-06-26 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_workflow_jobs"
down_revision = "0039_iteration_training_exports"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("workflow_jobs"):
        op.create_table(
            "workflow_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("extraction_run_id", sa.String(), sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("job_type", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("idempotency_key", sa.String(), nullable=True),
            sa.Column("input_json", sa.JSON(), nullable=True),
            sa.Column("output_json", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by", sa.String(), nullable=True),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.Column("queued_at", sa.DateTime(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("deck_id", "job_type", "idempotency_key", name="uq_workflow_jobs_deck_job_type_idempotency"),
            sa.CheckConstraint(
                "status in ('queued','running','completed','failed_retryable','failed_final','blocked','timed_out')",
                name="ck_workflow_jobs_status",
            ),
        )
        op.create_index("ix_workflow_jobs_deck_id", "workflow_jobs", ["deck_id"])
        op.create_index("ix_workflow_jobs_deck_created_at", "workflow_jobs", ["deck_id", "created_at"])
        op.create_index("ix_workflow_jobs_workspace_id", "workflow_jobs", ["workspace_id"])
        op.create_index("ix_workflow_jobs_user_id", "workflow_jobs", ["user_id"])
        op.create_index("ix_workflow_jobs_extraction_run_id", "workflow_jobs", ["extraction_run_id"])
        op.create_index("ix_workflow_jobs_job_type", "workflow_jobs", ["job_type"])
        op.create_index("ix_workflow_jobs_status", "workflow_jobs", ["status"])
        op.create_index("ix_workflow_jobs_idempotency_key", "workflow_jobs", ["idempotency_key"])
        op.create_index("ix_workflow_jobs_heartbeat_at", "workflow_jobs", ["heartbeat_at"])
        op.create_index("ix_workflow_jobs_claim", "workflow_jobs", ["status", "job_type", "priority", "created_at"])

    if not _has_table("workflow_job_events"):
        op.create_table(
            "workflow_job_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("job_id", sa.String(), sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("from_status", sa.String(), nullable=True),
            sa.Column("to_status", sa.String(), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_workflow_job_events_job_id", "workflow_job_events", ["job_id"])
        op.create_index("ix_workflow_job_events_event_type", "workflow_job_events", ["event_type"])

    if not _has_table("workflow_job_artifacts"):
        op.create_table(
            "workflow_job_artifacts",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("job_id", sa.String(), sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("artifact_type", sa.String(), nullable=False),
            sa.Column("storage_key", sa.String(), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("job_id", "artifact_type", "storage_key", name="uq_workflow_job_artifacts_job_type_storage"),
        )
        op.create_index("ix_workflow_job_artifacts_job_id", "workflow_job_artifacts", ["job_id"])
        op.create_index("ix_workflow_job_artifacts_deck_id", "workflow_job_artifacts", ["deck_id"])
        op.create_index("ix_workflow_job_artifacts_artifact_type", "workflow_job_artifacts", ["artifact_type"])
        op.create_index("ix_workflow_job_artifacts_storage_key", "workflow_job_artifacts", ["storage_key"])

    if not _has_table("workflow_job_dependencies"):
        op.create_table(
            "workflow_job_dependencies",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("job_id", sa.String(), sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("depends_on_job_id", sa.String(), sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("dependency_type", sa.String(), nullable=False, server_default="requires_completion"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("job_id", "depends_on_job_id", "dependency_type", name="uq_workflow_job_dependencies_edge"),
        )
        op.create_index("ix_workflow_job_dependencies_job_id", "workflow_job_dependencies", ["job_id"])
        op.create_index("ix_workflow_job_dependencies_depends_on_job_id", "workflow_job_dependencies", ["depends_on_job_id"])


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_workflow_job_dependencies_depends_on_job_id", "workflow_job_dependencies"),
        ("ix_workflow_job_dependencies_job_id", "workflow_job_dependencies"),
        ("ix_workflow_job_artifacts_storage_key", "workflow_job_artifacts"),
        ("ix_workflow_job_artifacts_artifact_type", "workflow_job_artifacts"),
        ("ix_workflow_job_artifacts_deck_id", "workflow_job_artifacts"),
        ("ix_workflow_job_artifacts_job_id", "workflow_job_artifacts"),
        ("ix_workflow_job_events_event_type", "workflow_job_events"),
        ("ix_workflow_job_events_job_id", "workflow_job_events"),
        ("ix_workflow_jobs_heartbeat_at", "workflow_jobs"),
        ("ix_workflow_jobs_claim", "workflow_jobs"),
        ("ix_workflow_jobs_idempotency_key", "workflow_jobs"),
        ("ix_workflow_jobs_status", "workflow_jobs"),
        ("ix_workflow_jobs_job_type", "workflow_jobs"),
        ("ix_workflow_jobs_extraction_run_id", "workflow_jobs"),
        ("ix_workflow_jobs_user_id", "workflow_jobs"),
        ("ix_workflow_jobs_workspace_id", "workflow_jobs"),
        ("ix_workflow_jobs_deck_created_at", "workflow_jobs"),
        ("ix_workflow_jobs_deck_id", "workflow_jobs"),
    ]:
        if _has_table(table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in [
        "workflow_job_dependencies",
        "workflow_job_artifacts",
        "workflow_job_events",
        "workflow_jobs",
    ]:
        if _has_table(table_name):
            op.drop_table(table_name)
