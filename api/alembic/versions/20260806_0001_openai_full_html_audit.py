"""Add audited OpenAI attempt metadata and set the new-operation $5 default."""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0001_openai_audit"
down_revision = "20260805_0001_html"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize the historical $10 default before enforcing the audited $5
    # ceiling. Existing operations at or below the new consumed/reserved budget
    # remain resumable; runtime guards terminalize any already-over-budget row.
    op.execute(
        sa.text(
            "UPDATE instant_deck_operations SET max_cost_cents = 500 "
            "WHERE max_cost_cents > 500"
        )
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("instant_deck_operations") as batch_op:
            batch_op.alter_column(
                "max_cost_cents",
                existing_type=sa.Float(),
                server_default="500",
                existing_nullable=False,
            )
            batch_op.add_column(
                sa.Column("reserved_provider_cost_cents", sa.Float(), nullable=False, server_default="0")
            )
            batch_op.create_check_constraint(
                "ck_instant_deck_operation_max_cost",
                "max_cost_cents >= 0 AND max_cost_cents <= 500",
            )
    else:
        op.alter_column(
            "instant_deck_operations",
            "max_cost_cents",
            existing_type=sa.Float(),
            server_default="500",
            existing_nullable=False,
        )
        op.add_column(
            "instant_deck_operations",
            sa.Column("reserved_provider_cost_cents", sa.Float(), nullable=False, server_default="0"),
        )
        op.create_check_constraint(
            "ck_instant_deck_operation_max_cost",
            "instant_deck_operations",
            "max_cost_cents >= 0 AND max_cost_cents <= 500",
        )
    op.add_column("instant_deck_provider_attempts", sa.Column("client_request_id", sa.String(), nullable=True))
    op.add_column("instant_deck_provider_attempts", sa.Column("provider_response_id", sa.String(), nullable=True))
    op.add_column("instant_deck_provider_attempts", sa.Column("http_status", sa.Integer(), nullable=True))
    op.add_column("instant_deck_provider_attempts", sa.Column("provider_error_code", sa.String(), nullable=True))
    op.add_column("instant_deck_provider_attempts", sa.Column("retry_after_seconds", sa.Float(), nullable=True))
    op.add_column("instant_deck_provider_attempts", sa.Column("rate_limit_metadata_json", sa.JSON(), nullable=True))
    op.add_column("instant_deck_provider_attempts", sa.Column("outcome_metadata_json", sa.JSON(), nullable=True))
    op.add_column(
        "instant_deck_provider_attempts",
        sa.Column("reserved_cost_cents", sa.Float(), nullable=False, server_default="0"),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("instant_deck_provider_attempts") as batch_op:
            batch_op.create_unique_constraint(
                "uq_instant_deck_attempt_client_request_id",
                ["client_request_id"],
            )
    else:
        op.create_unique_constraint(
            "uq_instant_deck_attempt_client_request_id",
            "instant_deck_provider_attempts",
            ["client_request_id"],
        )
    op.create_index(
        "ix_instant_deck_provider_attempts_provider_response_id",
        "instant_deck_provider_attempts",
        ["provider_response_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_instant_deck_provider_attempts_provider_response_id",
        table_name="instant_deck_provider_attempts",
    )
    op.drop_constraint(
        "uq_instant_deck_attempt_client_request_id",
        "instant_deck_provider_attempts",
        type_="unique",
    )
    op.drop_constraint(
        "ck_instant_deck_operation_max_cost",
        "instant_deck_operations",
        type_="check",
    )
    for column in (
        "reserved_cost_cents",
        "outcome_metadata_json",
        "rate_limit_metadata_json",
        "retry_after_seconds",
        "provider_error_code",
        "http_status",
        "client_request_id",
        "provider_response_id",
    ):
        op.drop_column("instant_deck_provider_attempts", column)
    op.drop_column("instant_deck_operations", "reserved_provider_cost_cents")
    # Do not restore a higher server default during downgrade.
    op.alter_column(
        "instant_deck_operations",
        "max_cost_cents",
        existing_type=sa.Float(),
        server_default=None,
        existing_nullable=False,
    )
