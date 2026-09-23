"""Add idempotent Instant HTML operation and compiled artifact lineage."""

from alembic import op
import sqlalchemy as sa


revision = "20260805_0001_html"
down_revision = "20260731_0001_unified_deck_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("design_versions", sa.Column("artifact_type", sa.String(), nullable=False, server_default="render_schema.v1"))
    op.add_column("design_versions", sa.Column("render_mode", sa.String(), nullable=False, server_default="scene_graph.v1"))
    op.create_index("ix_design_versions_artifact_type", "design_versions", ["artifact_type"])
    op.create_index("ix_design_versions_render_mode", "design_versions", ["render_mode"])
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("generated_slides") as batch_op:
            batch_op.alter_column("render_schema_json", existing_type=sa.JSON(), nullable=True)
    else:
        op.alter_column("generated_slides", "render_schema_json", existing_type=sa.JSON(), nullable=True)
    op.add_column("generated_slides", sa.Column("render_mode", sa.String(), nullable=False, server_default="scene_graph.v1"))
    op.add_column("generated_slides", sa.Column("section_id", sa.String(), nullable=True))
    op.add_column("generated_slides", sa.Column("section_sha256", sa.String(length=64), nullable=True))
    op.add_column("generated_slides", sa.Column("compilation_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_generated_slides_render_mode", "generated_slides", ["render_mode"])
    op.create_index("ix_generated_slides_section_id", "generated_slides", ["section_id"])
    op.create_index("ix_generated_slides_compilation_hash", "generated_slides", ["compilation_hash"])
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("generated_slide_code_versions") as batch_op:
            batch_op.alter_column("render_schema_json", existing_type=sa.JSON(), nullable=True)
    else:
        op.alter_column("generated_slide_code_versions", "render_schema_json", existing_type=sa.JSON(), nullable=True)

    op.create_table(
        "instant_deck_operations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_job_id", sa.String(), sa.ForeignKey("workflow_jobs.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("output_contract", sa.String(), nullable=False, server_default="full_html_deck.v1"),
        sa.Column("checkpoint_stage", sa.String(), nullable=False, server_default="created"),
        sa.Column("provider_request_starts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_provider_request_starts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False, server_default="160000"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="32000"),
        sa.Column("max_cost_cents", sa.Float(), nullable=False, server_default="1000"),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_provider_cost_cents", sa.Float(), nullable=False, server_default="0"),
        sa.Column("product_credit_transaction_id", sa.String(), nullable=True, unique=True),
        sa.Column("charge_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("terminal_reason", sa.String(), nullable=True),
        sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("deck_id", "user_id", "idempotency_key", name="uq_instant_deck_operation_command"),
    )
    for name, columns in (
        ("ix_instant_deck_operations_deck_id", ["deck_id"]),
        ("ix_instant_deck_operations_user_id", ["user_id"]),
        ("ix_instant_deck_operations_status", ["status"]),
        ("ix_instant_deck_operations_checkpoint_stage", ["checkpoint_stage"]),
        ("ix_instant_deck_operations_charge_status", ["charge_status"]),
    ):
        op.create_index(name, "instant_deck_operations", columns)

    op.create_table(
        "instant_deck_provider_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("operation_id", sa.String(), sa.ForeignKey("instant_deck_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("request_kind", sa.String(), nullable=False, server_default="generation"),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("provider_request_id", sa.String(), nullable=True),
        sa.Column("request_started_at", sa.DateTime(), nullable=False),
        sa.Column("response_received_at", sa.DateTime(), nullable=True),
        sa.Column("outcome_known", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("response_state", sa.String(), nullable=False, server_default="started"),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_cost_cents", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cost_source", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("provider_idempotency_key", sa.String(), nullable=True, unique=True),
        sa.Column("raw_artifact_id", sa.String(), nullable=True),
        sa.Column("validation_summary_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("operation_id", "attempt_number", name="uq_instant_deck_attempt_number"),
    )
    op.create_index("ix_instant_deck_provider_attempts_operation_id", "instant_deck_provider_attempts", ["operation_id"])
    op.create_index("ix_instant_deck_provider_attempts_provider_request_id", "instant_deck_provider_attempts", ["provider_request_id"])
    op.create_index("ix_instant_deck_provider_attempts_response_state", "instant_deck_provider_attempts", ["response_state"])

    op.create_table(
        "instant_deck_html_artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation_id", sa.String(), sa.ForeignKey("instant_deck_operations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_attempt_id", sa.String(), sa.ForeignKey("instant_deck_provider_attempts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("artifact_kind", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False, unique=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False, server_default="text/html; charset=utf-8"),
        sa.Column("quarantined", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("encryption_key_version", sa.String(), nullable=True),
        sa.Column("encryption_purpose", sa.String(), nullable=True),
        sa.Column("compiler_version", sa.String(), nullable=True),
        sa.Column("sanitizer_policy_version", sa.String(), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(), nullable=True),
        sa.Column("purge_status", sa.String(), nullable=True),
        sa.Column("purge_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purge_error_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for name, columns in (
        ("ix_instant_deck_html_artifacts_deck_id", ["deck_id"]),
        ("ix_instant_deck_html_artifacts_operation_id", ["operation_id"]),
        ("ix_instant_deck_html_artifacts_provider_attempt_id", ["provider_attempt_id"]),
        ("ix_instant_deck_html_artifacts_design_version_id", ["design_version_id"]),
        ("ix_instant_deck_html_artifacts_artifact_kind", ["artifact_kind"]),
        ("ix_instant_deck_html_artifacts_content_hash", ["content_hash"]),
        ("ix_instant_deck_html_artifacts_retention_expires_at", ["retention_expires_at"]),
        ("ix_instant_deck_html_artifacts_purge_status", ["purge_status"]),
    ):
        op.create_index(name, "instant_deck_html_artifacts", columns)
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("instant_deck_provider_attempts") as batch_op:
            batch_op.create_foreign_key(
                "fk_instant_attempt_raw_artifact",
                "instant_deck_html_artifacts",
                ["raw_artifact_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        op.create_foreign_key(
            "fk_instant_attempt_raw_artifact",
            "instant_deck_provider_attempts",
            "instant_deck_html_artifacts",
            ["raw_artifact_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "instant_deck_compilations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("design_version_id", sa.String(), sa.ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("provider_attempt_id", sa.String(), sa.ForeignKey("instant_deck_provider_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sanitized_html_artifact_id", sa.String(), sa.ForeignKey("instant_deck_html_artifacts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default="compiled"),
        sa.Column("stage", sa.String(), nullable=False, server_default="validating"),
        sa.Column("compiler_version", sa.String(), nullable=False),
        sa.Column("sanitizer_policy_version", sa.String(), nullable=False),
        sa.Column("renderer_version", sa.String(), nullable=False),
        sa.Column("grounding_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("issue_manifest_json", sa.JSON(), nullable=False),
        sa.Column("render_proof_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for name, columns in (
        ("ix_instant_deck_compilations_deck_id", ["deck_id"]),
        ("ix_instant_deck_compilations_design_version_id", ["design_version_id"]),
        ("ix_instant_deck_compilations_provider_attempt_id", ["provider_attempt_id"]),
        ("ix_instant_deck_compilations_status", ["status"]),
        ("ix_instant_deck_compilations_stage", ["stage"]),
        ("ix_instant_deck_compilations_content_hash", ["content_hash"]),
        ("ix_instant_deck_compilations_render_proof_status", ["render_proof_status"]),
    ):
        op.create_index(name, "instant_deck_compilations", columns)

    op.create_table(
        "generated_slide_source_lineage",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lineage_order", sa.Integer(), nullable=False),
        sa.Column("lineage_role", sa.String(), nullable=False, server_default="evidence"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("generated_slide_id", "source_slide_id", name="uq_generated_slide_source_lineage"),
        sa.UniqueConstraint("generated_slide_id", "lineage_order", name="uq_generated_slide_source_order"),
    )
    op.create_index("ix_generated_slide_source_lineage_generated_slide_id", "generated_slide_source_lineage", ["generated_slide_id"])
    op.create_index("ix_generated_slide_source_lineage_source_slide_id", "generated_slide_source_lineage", ["source_slide_id"])

    op.create_table(
        "instant_deck_render_proofs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("compilation_id", sa.String(), sa.ForeignKey("instant_deck_compilations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("render_document_hash", sa.String(length=64), nullable=False),
        sa.Column("screenshot_hash", sa.String(length=64), nullable=False),
        sa.Column("compilation_hash", sa.String(length=64), nullable=False),
        sa.Column("sanitizer_policy_version", sa.String(), nullable=False),
        sa.Column("renderer_version", sa.String(), nullable=False),
        sa.Column("browser_version", sa.String(), nullable=False),
        sa.Column("viewport_hash", sa.String(length=64), nullable=False),
        sa.Column("proof_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(), nullable=False, server_default="passed"),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("compilation_id", "generated_slide_id", name="uq_instant_deck_render_proof_slide"),
    )
    op.create_index("ix_instant_deck_render_proofs_compilation_id", "instant_deck_render_proofs", ["compilation_id"])
    op.create_index("ix_instant_deck_render_proofs_generated_slide_id", "instant_deck_render_proofs", ["generated_slide_id"])
    op.create_index("ix_instant_deck_render_proofs_status", "instant_deck_render_proofs", ["status"])

    op.create_table(
        "instant_deck_render_capabilities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("artifact_id", sa.String(), sa.ForeignKey("instant_deck_html_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_slide_id", sa.String(), sa.ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("render_document_hash", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("minted_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_instant_deck_render_capabilities_artifact_id", "instant_deck_render_capabilities", ["artifact_id"])
    op.create_index("ix_instant_deck_render_capabilities_generated_slide_id", "instant_deck_render_capabilities", ["generated_slide_id"])
    op.create_index("ix_instant_deck_render_capabilities_artifact_hash", "instant_deck_render_capabilities", ["artifact_hash"])
    op.create_index("ix_instant_deck_render_capabilities_minted_by_user_id", "instant_deck_render_capabilities", ["minted_by_user_id"])
    op.create_index("ix_instant_deck_render_capabilities_expires_at", "instant_deck_render_capabilities", ["expires_at"])
    op.create_index("ix_instant_deck_render_capabilities_render_document_hash", "instant_deck_render_capabilities", ["render_document_hash"])
    op.create_index("ix_instant_deck_render_capabilities_revoked_at", "instant_deck_render_capabilities", ["revoked_at"])


def downgrade() -> None:
    connection = op.get_bind()
    html_count = connection.execute(sa.text(
        "SELECT COUNT(*) FROM generated_slides WHERE render_mode = 'html_compiled.v1' OR render_schema_json IS NULL"
    )).scalar()
    code_count = connection.execute(sa.text(
        "SELECT COUNT(*) FROM generated_slide_code_versions WHERE render_schema_json IS NULL"
    )).scalar()
    if int(html_count or 0) or int(code_count or 0):
        raise RuntimeError(
            "Downgrade blocked: Instant HTML or nullable render-schema data exists. Export/preserve and migrate it before downgrade."
        )
    op.drop_table("instant_deck_render_capabilities")
    op.drop_table("instant_deck_render_proofs")
    op.drop_table("generated_slide_source_lineage")
    op.drop_table("instant_deck_compilations")
    op.drop_constraint("fk_instant_attempt_raw_artifact", "instant_deck_provider_attempts", type_="foreignkey")
    op.drop_table("instant_deck_html_artifacts")
    op.drop_table("instant_deck_provider_attempts")
    op.drop_table("instant_deck_operations")
    op.drop_index("ix_generated_slides_compilation_hash", table_name="generated_slides")
    op.drop_index("ix_generated_slides_section_id", table_name="generated_slides")
    op.drop_index("ix_generated_slides_render_mode", table_name="generated_slides")
    op.drop_column("generated_slides", "compilation_hash")
    op.drop_column("generated_slides", "section_sha256")
    op.drop_column("generated_slides", "section_id")
    op.drop_column("generated_slides", "render_mode")
    op.alter_column("generated_slide_code_versions", "render_schema_json", existing_type=sa.JSON(), nullable=False)
    op.alter_column("generated_slides", "render_schema_json", existing_type=sa.JSON(), nullable=False)
    op.drop_index("ix_design_versions_render_mode", table_name="design_versions")
    op.drop_index("ix_design_versions_artifact_type", table_name="design_versions")
    op.drop_column("design_versions", "render_mode")
    op.drop_column("design_versions", "artifact_type")
