"""Add owner-scoped upload request coordination without altering hot tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0004_upload_request_id"
down_revision = "20260806_0003_export_handoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A new empty table is rolling-safe for old API/worker processes: they keep
    # selecting deck_files without depending on a newly added mapped column.
    # The unique index is built as part of empty-table creation, avoiding a scan
    # or long write lock on existing uploads.
    op.create_table(
        "deck_upload_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("client_request_hash", sa.String(length=64), nullable=False),
        sa.Column("intent_hash", sa.String(length=64), nullable=False),
        sa.Column("deck_id", sa.String(), nullable=False),
        sa.Column("deck_file_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["deck_file_id"], ["deck_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deck_id", name="uq_deck_upload_requests_deck_id"),
        sa.UniqueConstraint("deck_file_id", name="uq_deck_upload_requests_deck_file_id"),
        sa.UniqueConstraint(
            "user_id",
            "workspace_id",
            "client_request_hash",
            name="uq_deck_upload_request_owner_workspace_client",
        ),
    )
    op.create_index("ix_deck_upload_requests_user_id", "deck_upload_requests", ["user_id"])
    op.create_index("ix_deck_upload_requests_workspace_id", "deck_upload_requests", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_deck_upload_requests_workspace_id", table_name="deck_upload_requests")
    op.drop_index("ix_deck_upload_requests_user_id", table_name="deck_upload_requests")
    op.drop_table("deck_upload_requests")
