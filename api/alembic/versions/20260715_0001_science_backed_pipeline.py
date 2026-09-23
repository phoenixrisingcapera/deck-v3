"""add science-backed pipeline tables

Revision ID: 20260715_0001_science_backed_pipeline
Revises: 20260714_0002_embedding_fallback_metadata
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260715_0001_science_backed_pipeline"
down_revision = "20260714_0002_embedding_fallback_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing deployments may already contain these tables from the legacy
    # bootstrap. Mark the forward migration applied without attempting to
    # recreate objects that contain production data.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if {
        "artifact_objects",
        "materialized_deck_state",
        "source_extraction_jobs",
        "llm_runs",
        "change_requests",
        "audit_log",
    }.issubset(existing):
        return

    # artifact_objects: tracks files in object storage (structured deck JSON, reports, etc.)
    op.create_table(
        "artifact_objects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "deck_id",
            sa.String(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(),
            sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("artifact_type", sa.String(), nullable=False, index=True),
        sa.Column("storage_key", sa.String(), nullable=False, index=True),
        sa.Column("storage_provider", sa.String(), nullable=False, server_default="local"),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # materialized_deck_state: single source of truth for deck processing stage
    op.create_table(
        "materialized_deck_state",
        sa.Column(
            "deck_id",
            sa.String(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(),
            sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="pending", index=True),
        sa.Column("extraction_status", sa.String(), nullable=False, server_default="pending", index=True),
        sa.Column("current_stage", sa.String(), nullable=False, server_default="uploaded", index=True),
        sa.Column("slide_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("block_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("asset_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_thumbnails", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_structured_json", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_embeddings", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_open_smart_deck", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_open_smart_edit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_open_due_diligence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("next_action", sa.String(), nullable=True),
        sa.Column("warnings_json", sa.JSON(), nullable=True),
        sa.Column("errors_json", sa.JSON(), nullable=True),
        sa.Column(
            "extraction_report_artifact_id",
            sa.String(),
            sa.ForeignKey("artifact_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "structured_json_artifact_id",
            sa.String(),
            sa.ForeignKey("artifact_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_extraction_at", sa.DateTime(), nullable=True),
        sa.Column("last_generation_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("deck_id", name="uq_materialized_deck_state_deck_id"),
    )

    # source_extraction_jobs: explicit per-stage pipeline jobs
    op.create_table(
        "source_extraction_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "deck_id",
            sa.String(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(),
            sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("stage", sa.String(), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="queued", index=True),
        sa.Column("idempotency_key", sa.String(), nullable=True, index=True),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("locked_by", sa.String(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "deck_id", "stage", "idempotency_key",
            name="uq_source_extraction_jobs_deck_stage_key",
        ),
    )

    # llm_runs: tracks LLM execution for semantic enrichment
    op.create_table(
        "llm_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "deck_id",
            sa.String(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(),
            sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("run_type", sa.String(), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending", index=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column(
            "artifact_id",
            sa.String(),
            sa.ForeignKey("artifact_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # change_requests: LLM or user proposed changes (accept/reject before persist)
    op.create_table(
        "change_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "deck_id",
            sa.String(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(),
            sa.ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "llm_run_id",
            sa.String(),
            sa.ForeignKey("llm_runs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("change_type", sa.String(), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending", index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column(
            "accepted_by_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # audit_log: every mutation is traceable
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "deck_id",
            sa.String(),
            sa.ForeignKey("decks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(), nullable=False, index=True),
        sa.Column("resource_type", sa.String(), nullable=False, index=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("change_requests")
    op.drop_table("llm_runs")
    op.drop_table("source_extraction_jobs")
    op.drop_table("materialized_deck_state")
    op.drop_table("artifact_objects")
