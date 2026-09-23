"""Add deck media library and media_processing workflow job type."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0003_deck_media_library"
down_revision = "20260717_0002_deck_intelligence_workflow_jobs"
branch_labels = None
depends_on = None


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
    "due_diligence",
    "deck_map_analysis",
    "market_research",
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
        with op.batch_alter_table("workflow_jobs") as batch_op:
            if _has_job_type_constraint():
                batch_op.drop_constraint("ck_workflow_jobs_job_type", type_="check")
            batch_op.create_check_constraint("ck_workflow_jobs_job_type", expression)
        return
    if _has_job_type_constraint():
        op.drop_constraint("ck_workflow_jobs_job_type", "workflow_jobs", type_="check")
    op.create_check_constraint("ck_workflow_jobs_job_type", "workflow_jobs", expression)


def upgrade() -> None:
    # Create deck_media_assets table
    op.create_table(
        "deck_media_assets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("uploaded_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("role", sa.String(), nullable=False, index=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, default="queued", index=True),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("storage_provider", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True, index=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("dominant_colors_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("llm_enabled", sa.Boolean(), nullable=False, default=True, index=True),
        sa.Column("processing_version", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("workflow_job_id", sa.String(), sa.ForeignKey("workflow_jobs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("role in ('logo','board_picture','deck_picture')", name="ck_deck_media_assets_role"),
        sa.CheckConstraint("status in ('queued','processing','ready','failed_retryable','failed_final','archived')", name="ck_deck_media_assets_status"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_deck_media_assets_size_bytes"),
        sa.CheckConstraint("width IS NULL OR width > 0", name="ck_deck_media_assets_width"),
        sa.CheckConstraint("height IS NULL OR height > 0", name="ck_deck_media_assets_height"),
    )

    # Expand workflow job type constraint to include media_processing
    _replace(_job_type_check(BASE_JOB_TYPES | _deployed_job_types() | {"media_processing"}))


def downgrade() -> None:
    # Drop deck_media_assets table
    op.drop_table("deck_media_assets")

    # Restore previous job type constraint
    _replace(_job_type_check(BASE_JOB_TYPES | _deployed_job_types()))
