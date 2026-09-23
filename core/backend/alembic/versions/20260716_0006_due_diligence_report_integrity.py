"""Add immutable, run-linked Due Diligence reports and finding provenance.

This migration is additive. Existing findings are attached to the latest
available analysis run for their deck so they remain visible after rollout.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0006_due_diligence_report_integrity"
down_revision = "20260715_0005_core_data_contract_reconciliation"
branch_labels = None
depends_on = None


def _replace_finding_fk_with_set_null(*, column_name: str, referred_table: str) -> None:
    """Replace the live PostgreSQL FK using its inspected deployed name."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # The production migration contract is PostgreSQL. SQLite test schemas
        # are built from ORM metadata and do not execute Alembic FK alterations.
        return
    matches = [
        foreign_key
        for foreign_key in sa.inspect(bind).get_foreign_keys("analysis_findings")
        if foreign_key.get("constrained_columns") == [column_name]
        and foreign_key.get("referred_table") == referred_table
    ]
    if len(matches) != 1 or not matches[0].get("name"):
        raise RuntimeError(
            f"Expected exactly one named analysis_findings.{column_name} foreign key; found {len(matches)}."
        )
    op.drop_constraint(str(matches[0]["name"]), "analysis_findings", type_="foreignkey")
    op.create_foreign_key(
        f"fk_analysis_findings_{column_name}_set_null",
        "analysis_findings",
        referred_table,
        [column_name],
        ["id"],
        ondelete="SET NULL",
    )


def _backfill_legacy_finding_targets_and_evidence() -> None:
    """Snapshot current source objects before future reprocessing detaches FKs."""
    op.execute(
        sa.text(
            """
            UPDATE analysis_findings AS af
            SET field_key = CASE
                    WHEN b.id IS NOT NULL AND b.slide_id = af.slide_id
                    THEN 'block:' || b.id || '.raw_text'
                    ELSE NULL
                END,
                target_snapshot_json = json_build_object(
                    'slideId', af.slide_id,
                    'slideTitle', s.title,
                    'blockId', CASE WHEN b.slide_id = af.slide_id THEN b.id ELSE NULL END,
                    'fieldKey', CASE
                        WHEN b.id IS NOT NULL AND b.slide_id = af.slide_id
                        THEN 'block:' || b.id || '.raw_text'
                        ELSE NULL
                    END,
                    'beforeText', CASE WHEN b.slide_id = af.slide_id THEN b.raw_text ELSE NULL END
                ),
                evidence_json = CASE
                    WHEN b.id IS NOT NULL AND b.slide_id = af.slide_id THEN json_build_object(
                        'sourceReferences', json_build_array(json_build_object(
                            'type', 'deck_block',
                            'slideId', af.slide_id,
                            'blockId', b.id
                        )),
                        'status', 'legacy_deck_context_snapshot'
                    )
                    ELSE json_build_object(
                        'sourceReferences', json_build_array(),
                        'status', 'legacy_target_unverified'
                    )
                END,
                validation_verdict = CASE
                    WHEN b.id IS NOT NULL AND b.slide_id = af.slide_id
                    THEN 'legacy_deck_context_snapshot'
                    ELSE 'legacy_target_unverified'
                END
            FROM deck_slides AS s, deck_slide_blocks AS b
            WHERE s.id = af.slide_id
              AND b.id = af.block_id
              AND b.slide_id = s.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE analysis_findings AS af
            SET field_key = NULL,
                target_snapshot_json = json_build_object(
                    'slideId', af.slide_id,
                    'slideTitle', s.title,
                    'blockId', NULL,
                    'fieldKey', NULL,
                    'beforeText', NULL
                ),
                evidence_json = json_build_object(
                    'sourceReferences', json_build_array(),
                    'status', 'legacy_target_unverified'
                ),
                validation_verdict = 'legacy_target_unverified'
            FROM deck_slides AS s
            WHERE s.id = af.slide_id
              AND af.target_snapshot_json IS NULL
            """
        )
    )


def upgrade() -> None:
    # This is a PostgreSQL-only integrity/backfill migration: it changes
    # foreign-key constraints in place and uses PostgreSQL JSON/regex SQL.
    # Local SQLite is supported for the Instant Deck development pipeline, not
    # the independent Due Diligence historical workflow.  Keep its migration
    # graph traversable without pretending those PostgreSQL operations are
    # portable; production continues through the full path below.
    if op.get_bind().dialect.name == "sqlite":
        return

    op.add_column("analysis_runs", sa.Column("audience", sa.String(), nullable=True))
    op.add_column("analysis_runs", sa.Column("workflow_job_id", sa.String(), nullable=True))
    op.create_index("ix_analysis_runs_audience", "analysis_runs", ["audience"])
    op.create_index("ix_analysis_runs_workflow_job_id", "analysis_runs", ["workflow_job_id"])
    op.create_foreign_key(
        "fk_analysis_runs_workflow_job_id",
        "analysis_runs",
        "workflow_jobs",
        ["workflow_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            """
            UPDATE analysis_runs AS ar
            SET audience = COALESCE(
                NULLIF(btrim(regexp_replace(lower(btrim(COALESCE(d.audience, ''))), '[^a-z0-9]+', '_', 'g'), '_'), ''),
                'seed_vc'
            )
            FROM decks AS d
            WHERE d.id = ar.deck_id
            """
        )
    )

    op.create_table(
        "diligence_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("deck_id", sa.String(), nullable=False),
        sa.Column("analysis_run_id", sa.String(), nullable=False),
        sa.Column("workflow_job_id", sa.String(), nullable=True),
        sa.Column("audience", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=False, server_default="diligence-gap-agent.v1"),
        sa.Column("retrieval_trace_json", sa.JSON(), nullable=True),
        sa.Column("evidence_summary_json", sa.JSON(), nullable=True),
        sa.Column("validation_verdict", sa.String(), nullable=False, server_default="not_validated"),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_job_id"], ["workflow_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id"),
    )
    op.create_index("ix_diligence_reports_deck_id", "diligence_reports", ["deck_id"])
    op.create_index("ix_diligence_reports_analysis_run_id", "diligence_reports", ["analysis_run_id"])
    op.create_index("ix_diligence_reports_workflow_job_id", "diligence_reports", ["workflow_job_id"])
    op.create_index("ix_diligence_reports_audience", "diligence_reports", ["audience"])
    op.create_index("ix_diligence_reports_status", "diligence_reports", ["status"])
    op.create_index("ix_diligence_reports_created_at", "diligence_reports", ["created_at"])

    op.add_column("analysis_findings", sa.Column("report_id", sa.String(), nullable=True))
    op.add_column("analysis_findings", sa.Column("analysis_run_id", sa.String(), nullable=True))
    op.add_column("analysis_findings", sa.Column("audience", sa.String(), nullable=True))
    op.add_column("analysis_findings", sa.Column("field_key", sa.String(), nullable=True))
    op.add_column("analysis_findings", sa.Column("target_snapshot_json", sa.JSON(), nullable=True))
    op.add_column("analysis_findings", sa.Column("evidence_json", sa.JSON(), nullable=True))
    op.add_column(
        "analysis_findings",
        sa.Column("validation_verdict", sa.String(), nullable=False, server_default="unverified"),
    )
    op.alter_column("analysis_findings", "slide_id", existing_type=sa.String(), nullable=True)
    op.create_index("ix_analysis_findings_report_id", "analysis_findings", ["report_id"])
    op.create_index("ix_analysis_findings_analysis_run_id", "analysis_findings", ["analysis_run_id"])
    op.create_index("ix_analysis_findings_audience", "analysis_findings", ["audience"])
    op.create_foreign_key(
        "fk_analysis_findings_report_id",
        "analysis_findings",
        "diligence_reports",
        ["report_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("change_requests", sa.Column("source_finding_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_change_requests_source_finding_id",
        "change_requests",
        "analysis_findings",
        ["source_finding_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_change_requests_source_finding_id",
        "change_requests",
        ["source_finding_id"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_analysis_findings_analysis_run_id",
        "analysis_findings",
        "analysis_runs",
        ["analysis_run_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Preserve old output under one explicitly legacy report per deck. New runs
    # always create one report per run and never update these snapshots.
    op.execute(
        sa.text(
            """
            INSERT INTO diligence_reports (
                id, deck_id, analysis_run_id, audience, status, degraded,
                prompt_version, validation_verdict, created_at
            )
            SELECT 'legacy_report_' || ar.id, ar.deck_id, ar.id,
                   COALESCE(
                       NULLIF(btrim(regexp_replace(lower(btrim(COALESCE(d.audience, ''))), '[^a-z0-9]+', '_', 'g'), '_'), ''),
                       'seed_vc'
                   ), ar.status,
                   CASE WHEN ar.status = 'completed' THEN false ELSE true END,
                   'legacy-unversioned', 'legacy_unverified', ar.created_at
            FROM analysis_runs ar
            JOIN decks d ON d.id = ar.deck_id
            WHERE ar.id = (
                SELECT ar2.id FROM analysis_runs ar2
                WHERE ar2.deck_id = ar.deck_id
                ORDER BY ar2.created_at DESC, ar2.id DESC LIMIT 1
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE analysis_runs AS ar
            SET audience = dr.audience
            FROM diligence_reports AS dr
            WHERE dr.analysis_run_id = ar.id
              AND dr.prompt_version = 'legacy-unversioned'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE analysis_findings
            SET analysis_run_id = dr.analysis_run_id,
                report_id = dr.id,
                audience = dr.audience,
                validation_verdict = 'legacy_unverified'
            FROM diligence_reports dr
            WHERE dr.deck_id = analysis_findings.deck_id
              AND dr.prompt_version = 'legacy-unversioned'
            """
        )
    )
    _backfill_legacy_finding_targets_and_evidence()

    # Snapshots must exist before source object deletion can null these links.
    _replace_finding_fk_with_set_null(column_name="slide_id", referred_table="deck_slides")
    _replace_finding_fk_with_set_null(column_name="block_id", referred_table="deck_slide_blocks")


def downgrade() -> None:
    # Refuse to stamp the database backwards while retaining forward-only
    # columns: doing so would make a later upgrade attempt duplicate DDL. Root
    # preservation policy also prohibits dropping report/evidence history.
    raise RuntimeError(
        "20260716_0006_due_diligence_report_integrity is intentionally irreversible; restore a pre-upgrade snapshot."
    )
