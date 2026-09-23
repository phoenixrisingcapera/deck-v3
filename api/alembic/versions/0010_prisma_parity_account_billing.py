"""Add account and billing tables absorbed into canonical Alembic ownership.

Historical note: this revision imported requirements from an earlier
frontend-local schema design. It is now solely an Alembic/SQLAlchemy migration;
no Prisma runtime, client, schema, or deployment dependency remains.

Revision ID: 0010_account_billing_parity
Revises: 0009_brand_profile_fields
Create Date: 2026-06-11 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_account_billing_parity"
down_revision = "0009_brand_profile_fields"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    existing = _existing_tables()

    if "user_profiles" not in existing:
        op.create_table(
            "user_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=True),
            sa.Column("headline", sa.Text(), nullable=True),
            sa.Column("company_name", sa.String(), nullable=True),
            sa.Column("job_title", sa.String(), nullable=True),
            sa.Column("department", sa.String(), nullable=True),
            sa.Column("city", sa.String(), nullable=True),
            sa.Column("country", sa.String(), nullable=True),
            sa.Column("timezone", sa.String(), nullable=True),
            sa.Column("preferred_language", sa.String(), nullable=True),
            sa.Column("work_email", sa.String(), nullable=True),
            sa.Column("linkedin_profile_url", sa.String(), nullable=True),
            sa.Column("skills_json", sa.JSON(), nullable=True),
            sa.Column("education_json", sa.JSON(), nullable=True),
            sa.Column("certifications_json", sa.JSON(), nullable=True),
            sa.Column("profile_source_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        op.create_index(op.f("ix_user_profiles_user_id"), "user_profiles", ["user_id"], unique=True)

    if "connected_accounts" not in existing:
        op.create_table(
            "connected_accounts",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="connected"),
            sa.Column("external_account_id", sa.String(), nullable=True),
            sa.Column("external_email", sa.String(), nullable=True),
            sa.Column("external_display_name", sa.String(), nullable=True),
            sa.Column("scopes_json", sa.JSON(), nullable=True),
            sa.Column("access_token_masked", sa.String(), nullable=True),
            sa.Column("refresh_token_stored", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("external_profile_url", sa.String(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("sync_metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_connected_accounts_provider"), "connected_accounts", ["provider"], unique=False)
        op.create_index(op.f("ix_connected_accounts_user_id"), "connected_accounts", ["user_id"], unique=False)

    if "billing_plans" not in existing:
        op.create_table(
            "billing_plans",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("monthly_price_cents", sa.Integer(), nullable=True),
            sa.Column("annual_price_cents", sa.Integer(), nullable=True),
            sa.Column("cta_label", sa.String(), nullable=True),
            sa.Column("is_highlighted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_enterprise", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("seat_label", sa.String(), nullable=True),
            sa.Column("feature_bullets_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
        op.create_index(op.f("ix_billing_plans_code"), "billing_plans", ["code"], unique=True)

    if "workspace_subscriptions" not in existing:
        op.create_table(
            "workspace_subscriptions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("billing_plan_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("interval", sa.String(), nullable=False, server_default="monthly"),
            sa.Column("seat_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("current_period_start", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["billing_plan_id"], ["billing_plans.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_workspace_subscriptions_billing_plan_id"), "workspace_subscriptions", ["billing_plan_id"], unique=False)
        op.create_index(op.f("ix_workspace_subscriptions_workspace_id"), "workspace_subscriptions", ["workspace_id"], unique=False)

    if "billing_invoices" not in existing:
        op.create_table(
            "billing_invoices",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("workspace_subscription_id", sa.String(), nullable=False),
            sa.Column("invoice_number", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
            sa.Column("issued_at", sa.DateTime(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["workspace_subscription_id"], ["workspace_subscriptions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("invoice_number"),
        )
        op.create_index(
            op.f("ix_billing_invoices_workspace_subscription_id"),
            "billing_invoices",
            ["workspace_subscription_id"],
            unique=False,
        )

    if "adaptation_runs" in existing:
        adaptation_run_columns = _existing_columns("adaptation_runs")
        with op.batch_alter_table("adaptation_runs") as batch_op:
            if "status" not in adaptation_run_columns:
                batch_op.add_column(sa.Column("status", sa.String(), nullable=False, server_default="completed"))


def downgrade() -> None:
    existing = _existing_tables()

    if "adaptation_runs" in existing:
        adaptation_run_columns = _existing_columns("adaptation_runs")
        with op.batch_alter_table("adaptation_runs") as batch_op:
            if "status" in adaptation_run_columns:
                batch_op.drop_column("status")

    if "billing_invoices" in existing:
        op.drop_index(op.f("ix_billing_invoices_workspace_subscription_id"), table_name="billing_invoices")
        op.drop_table("billing_invoices")

    if "workspace_subscriptions" in existing:
        op.drop_index(op.f("ix_workspace_subscriptions_workspace_id"), table_name="workspace_subscriptions")
        op.drop_index(op.f("ix_workspace_subscriptions_billing_plan_id"), table_name="workspace_subscriptions")
        op.drop_table("workspace_subscriptions")

    if "billing_plans" in existing:
        op.drop_index(op.f("ix_billing_plans_code"), table_name="billing_plans")
        op.drop_table("billing_plans")

    if "connected_accounts" in existing:
        op.drop_index(op.f("ix_connected_accounts_user_id"), table_name="connected_accounts")
        op.drop_index(op.f("ix_connected_accounts_provider"), table_name="connected_accounts")
        op.drop_table("connected_accounts")

    if "user_profiles" in existing:
        op.drop_index(op.f("ix_user_profiles_user_id"), table_name="user_profiles")
        op.drop_table("user_profiles")
