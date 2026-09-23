"""batch decisions compiled decks

Revision ID: 0019_batch_compiled_decks
Revises: 0018_retrieval_variations
Create Date: 2026-06-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_batch_compiled_decks"
down_revision = "0018_retrieval_variations"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("batch_slide_decisions"):
        op.create_table(
            "batch_slide_decisions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.String(), sa.ForeignKey("design_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="CASCADE"), nullable=False),
            sa.Column("generated_slide_candidate_id", sa.String(), sa.ForeignKey("generated_slide_candidates.id", ondelete="SET NULL"), nullable=True),
            sa.Column("choice", sa.String(), nullable=False),
            sa.Column("decided_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("deck_id", "batch_id", "slide_id", name="uq_batch_slide_decisions_deck_batch_slide"),
        )
        op.create_index("ix_batch_slide_decisions_deck_id", "batch_slide_decisions", ["deck_id"])
        op.create_index("ix_batch_slide_decisions_batch_id", "batch_slide_decisions", ["batch_id"])
        op.create_index("ix_batch_slide_decisions_slide_id", "batch_slide_decisions", ["slide_id"])
        op.create_index("ix_batch_slide_decisions_generated_slide_candidate_id", "batch_slide_decisions", ["generated_slide_candidate_id"])
        op.create_index("ix_batch_slide_decisions_choice", "batch_slide_decisions", ["choice"])
        op.create_index("ix_batch_slide_decisions_decided_by_user_id", "batch_slide_decisions", ["decided_by_user_id"])
        op.create_index("ix_batch_slide_decisions_decided_at", "batch_slide_decisions", ["decided_at"])

    if not _has_table("compiled_decks"):
        op.create_table(
            "compiled_decks",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("source_deck_id", sa.String(), sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_id", sa.String(), sa.ForeignKey("design_batches.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="ready"),
            sa.Column("latest_slide_version_id", sa.String(), nullable=True),
            sa.Column("slide_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("manifest_json", sa.JSON(), nullable=False),
            sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("finalized_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_compiled_decks_source_deck_id", "compiled_decks", ["source_deck_id"])
        op.create_index("ix_compiled_decks_batch_id", "compiled_decks", ["batch_id"])
        op.create_index("ix_compiled_decks_status", "compiled_decks", ["status"])
        op.create_index("ix_compiled_decks_created_by_user_id", "compiled_decks", ["created_by_user_id"])
        op.create_index("ix_compiled_decks_finalized_at", "compiled_decks", ["finalized_at"])

    if not _has_table("compiled_deck_slides"):
        op.create_table(
            "compiled_deck_slides",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("compiled_deck_id", sa.String(), sa.ForeignKey("compiled_decks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_slide_id", sa.String(), sa.ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True),
            sa.Column("generated_slide_candidate_id", sa.String(), sa.ForeignKey("generated_slide_candidates.id", ondelete="SET NULL"), nullable=True),
            sa.Column("slide_index", sa.Integer(), nullable=False),
            sa.Column("choice", sa.String(), nullable=False),
            sa.Column("title_snapshot", sa.String(), nullable=False),
            sa.Column("manifest_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("compiled_deck_id", "slide_index", name="uq_compiled_deck_slides_deck_index"),
        )
        op.create_index("ix_compiled_deck_slides_compiled_deck_id", "compiled_deck_slides", ["compiled_deck_id"])
        op.create_index("ix_compiled_deck_slides_source_slide_id", "compiled_deck_slides", ["source_slide_id"])
        op.create_index("ix_compiled_deck_slides_generated_slide_candidate_id", "compiled_deck_slides", ["generated_slide_candidate_id"])
        op.create_index("ix_compiled_deck_slides_slide_index", "compiled_deck_slides", ["slide_index"])
        op.create_index("ix_compiled_deck_slides_choice", "compiled_deck_slides", ["choice"])


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_compiled_deck_slides_choice", "compiled_deck_slides"),
        ("ix_compiled_deck_slides_slide_index", "compiled_deck_slides"),
        ("ix_compiled_deck_slides_generated_slide_candidate_id", "compiled_deck_slides"),
        ("ix_compiled_deck_slides_source_slide_id", "compiled_deck_slides"),
        ("ix_compiled_deck_slides_compiled_deck_id", "compiled_deck_slides"),
        ("ix_compiled_decks_finalized_at", "compiled_decks"),
        ("ix_compiled_decks_created_by_user_id", "compiled_decks"),
        ("ix_compiled_decks_status", "compiled_decks"),
        ("ix_compiled_decks_batch_id", "compiled_decks"),
        ("ix_compiled_decks_source_deck_id", "compiled_decks"),
        ("ix_batch_slide_decisions_decided_at", "batch_slide_decisions"),
        ("ix_batch_slide_decisions_decided_by_user_id", "batch_slide_decisions"),
        ("ix_batch_slide_decisions_choice", "batch_slide_decisions"),
        ("ix_batch_slide_decisions_generated_slide_candidate_id", "batch_slide_decisions"),
        ("ix_batch_slide_decisions_slide_id", "batch_slide_decisions"),
        ("ix_batch_slide_decisions_batch_id", "batch_slide_decisions"),
        ("ix_batch_slide_decisions_deck_id", "batch_slide_decisions"),
    ]:
        if _has_table(table_name):
            op.drop_index(index_name, table_name=table_name)

    for table_name in ["compiled_deck_slides", "compiled_decks", "batch_slide_decisions"]:
        if _has_table(table_name):
            op.drop_table(table_name)
