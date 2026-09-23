from __future__ import annotations

from datetime import datetime

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CoreBase
from app.core.instant_deck_request_policy import MAX_PROVIDER_REQUEST_STARTS

Base = CoreBase


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="general", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="user")
    permissions: Mapped[list["Permission"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    deck_workspace_preferences: Mapped[list["DeckWorkspacePreference"]] = relationship(back_populates="user")
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user")
    connected_accounts: Mapped[list["ConnectedAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    save_confirmations: Mapped[list["DeckSaveConfirmation"]] = relationship(back_populates="user")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resource: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="permissions")


class SecurityAuditEvent(Base):
    __tablename__ = "security_audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, index=True)
    resource_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    result: Mapped[str] = mapped_column(String, index=True)
    source_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor: Mapped["User | None"] = relationship()


class DeveloperToolEvent(Base):
    """Redacted, page-scoped developer visibility events in the core DB.

    This is deliberately a CoreBase model. It records product workflow
    visibility and correlation, not provider prompts, vectors, or AI traces.
    """

    __tablename__ = "developer_tool_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    surface: Mapped[str] = mapped_column(String, index=True)
    event_name: Mapped[str] = mapped_column(String, index=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workflow_job_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    artifact_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class FailureTicket(Base):
    __tablename__ = "failure_tickets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    route: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_path: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
    error_name: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(String, default="medium", index=True)
    source: Mapped[str] = mapped_column(String, default="frontend", index=True)
    status: Mapped[str] = mapped_column(String, default="new", index=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user: Mapped["User | None"] = relationship()
    deck: Mapped["Deck | None"] = relationship()


class InterestLead(Base):
    __tablename__ = "interest_leads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    company_website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    role_label: Mapped[str | None] = mapped_column(String, nullable=True)
    use_case: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="new", index=True)
    source_page: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_jti: Mapped[str] = mapped_column(String, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped["User"] = relationship()


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    actor_key: Mapped[str] = mapped_column(String, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


# DISABLED: These models have been moved to app/db/models/ai.py for 2-database architecture
# They are now imported from ai.py in __init__.py
# class AiUsageBucket(Base):
#     __tablename__ = "ai_usage_buckets"
#     __table_args__ = (UniqueConstraint("user_id", "quota_key", name="uq_ai_usage_buckets_user_quota"),)
#
#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
#     quota_key: Mapped[str] = mapped_column(String, index=True)
#     window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
#     usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
#     updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
#
#
# class AiRun(Base):
#     __tablename__ = "ai_runs"
#
#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
#     deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
#     user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
#     intent: Mapped[str] = mapped_column(String, index=True)
#     mode: Mapped[str] = mapped_column(String, index=True)
#     user_instruction: Mapped[str] = mapped_column(Text)
#     selected_slide_ids_json: Mapped[list[str]] = mapped_column(JSON)
#     audience: Mapped[str | None] = mapped_column(String, nullable=True)
#     provider: Mapped[str] = mapped_column(String, default="provider_pending")
#     model: Mapped[str | None] = mapped_column(String, nullable=True)
#     status: Mapped[str] = mapped_column(String, default="pending", index=True)
#     error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
#     metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#     result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
#     updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
#     completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
#     steps: Mapped[list["AiRunStep"]] = relationship(back_populates="ai_run", cascade="all, delete-orphan")
#     deck: Mapped["Deck"] = relationship()
#     workspace: Mapped["Workspace"] = relationship()
#     user: Mapped["User | None"] = relationship()
#
#
# class AiRunStep(Base):
#     __tablename__ = "ai_run_steps"
#
#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     ai_run_id: Mapped[str] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
#     step_name: Mapped[str] = mapped_column(String, index=True)
#     status: Mapped[str] = mapped_column(String, default="pending", index=True)
#     input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#     output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#     error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
#     completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
#     ai_run: Mapped["AiRun"] = relationship(back_populates="steps")
#
#
# class AgentTelemetryEvent(Base):
#     __tablename__ = "agent_telemetry_events"
#
#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     deck_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     run_type: Mapped[str] = mapped_column(String, index=True)
#     step_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     event_name: Mapped[str] = mapped_column(String, index=True)
#     event_level: Mapped[str] = mapped_column(String, default="info", index=True)
#     status: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     provider: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     model: Mapped[str | None] = mapped_column(String, nullable=True)
#     latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
#     estimated_cost_cents: Mapped[float | None] = mapped_column(Float, nullable=True)
#     error_category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     error_message_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
#     trace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     span_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
#
#
# class AgentRegressionCase(Base):
#     __tablename__ = "agent_regression_cases"
#     __table_args__ = (
#         UniqueConstraint("source_event_id", name="uq_agent_regression_case_source_event"),
#     )
#
#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     source_event_id: Mapped[str] = mapped_column(ForeignKey("agent_telemetry_events.id", ondelete="CASCADE"), index=True)
#     workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
#     deck_id: Mapped[str | None] = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
#     user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
#     run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     run_type: Mapped[str] = mapped_column(String, index=True)
#     event_name: Mapped[str] = mapped_column(String, index=True)
#     status: Mapped[str] = mapped_column(String, default="active", index=True)
#     failure_category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     title: Mapped[str] = mapped_column(String)
#     fixture_json: Mapped[dict] = mapped_column(JSON)
#     notes: Mapped[str | None] = mapped_column(Text, nullable=True)
#     created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
#     updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    allow_model_training: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    model_training_policy: Mapped[str] = mapped_column(String, default="disabled", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="workspaces")
    decks: Mapped[list["Deck"]] = relationship(back_populates="workspace")
    company_profiles: Mapped[list["CompanyProfile"]] = relationship(back_populates="workspace")
    ai_credentials: Mapped[list["WorkspaceAiCredential"]] = relationship(back_populates="workspace")
    ai_provider_setting: Mapped["WorkspaceAiProviderSetting | None"] = relationship(back_populates="workspace")
    subscriptions: Mapped[list["WorkspaceSubscription"]] = relationship(back_populates="workspace")
    save_confirmations: Mapped[list["DeckSaveConfirmation"]] = relationship(back_populates="workspace")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    job_title: Mapped[str | None] = mapped_column(String, nullable=True)
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String, nullable=True)
    work_email: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_profile_url: Mapped[str | None] = mapped_column(String, nullable=True)
    skills_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    education_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    certifications_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    profile_source_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="profile")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="connected")
    external_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    external_email: Mapped[str | None] = mapped_column(String, nullable=True)
    external_display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    scopes_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    access_token_masked: Mapped[str | None] = mapped_column(String, nullable=True)
    refresh_token_stored: Mapped[bool] = mapped_column(Boolean, default=False)
    external_profile_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user: Mapped["User"] = relationship(back_populates="connected_accounts")


class BillingPlan(Base):
    __tablename__ = "billing_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cta_label: Mapped[str | None] = mapped_column(String, nullable=True)
    is_highlighted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enterprise: Mapped[bool] = mapped_column(Boolean, default=False)
    seat_label: Mapped[str | None] = mapped_column(String, nullable=True)
    feature_bullets_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subscriptions: Mapped[list["WorkspaceSubscription"]] = relationship(back_populates="billing_plan")


class WorkspaceSubscription(Base):
    __tablename__ = "workspace_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    billing_plan_id: Mapped[str] = mapped_column(ForeignKey("billing_plans.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String, default="active")
    interval: Mapped[str] = mapped_column(String, default="monthly")
    seat_count: Mapped[int] = mapped_column(Integer, default=1)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace: Mapped["Workspace"] = relationship(back_populates="subscriptions")
    billing_plan: Mapped["BillingPlan"] = relationship(back_populates="subscriptions")
    invoices: Mapped[list["BillingInvoice"]] = relationship(
        back_populates="workspace_subscription",
        cascade="all, delete-orphan",
    )


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_subscription_id: Mapped[str] = mapped_column(
        ForeignKey("workspace_subscriptions.id", ondelete="CASCADE"),
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String, default="USD")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace_subscription: Mapped["WorkspaceSubscription"] = relationship(back_populates="invoices")


class WorkspaceAiCredential(Base):
    __tablename__ = "workspace_ai_credentials"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    encrypted_api_key: Mapped[bytes] = mapped_column(LargeBinary)
    api_key_last4: Mapped[str] = mapped_column(String(4))
    key_version: Mapped[str] = mapped_column(String, default="local-dev", index=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace: Mapped["Workspace"] = relationship(back_populates="ai_credentials")


class WorkspaceAiProviderSetting(Base):
    __tablename__ = "workspace_ai_provider_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    preferred_model: Mapped[str | None] = mapped_column(String, nullable=True)
    reasoning_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    credential_id: Mapped[str | None] = mapped_column(ForeignKey("workspace_ai_credentials.id", ondelete="SET NULL"), nullable=True)
    use_for_smart_deck: Mapped[bool] = mapped_column(Boolean, default=True)
    use_for_smart_edit: Mapped[bool] = mapped_column(Boolean, default=True)
    use_for_analysis: Mapped[bool] = mapped_column(Boolean, default=True)
    configured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace: Mapped["Workspace"] = relationship(back_populates="ai_provider_setting")
    credential: Mapped["WorkspaceAiCredential | None"] = relationship()


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    audience: Mapped[str] = mapped_column(String)
    purpose: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    slide_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    current_design_version_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    workspace: Mapped["Workspace"] = relationship(back_populates="decks")
    file: Mapped["DeckFile"] = relationship(back_populates="deck")
    slides: Mapped[list["DeckSlide"]] = relationship(back_populates="deck")
    extraction_runs: Mapped[list["DeckExtractionRun"]] = relationship(back_populates="deck")
    brand_profile: Mapped["DeckBrandProfile | None"] = relationship(back_populates="deck")
    design_batches: Mapped[list["DesignBatch"]] = relationship(back_populates="deck")
    iteration_training_snapshots: Mapped[list["IterationTrainingSnapshot"]] = relationship(back_populates="deck")
    batch_slide_decisions: Mapped[list["BatchSlideDecision"]] = relationship(back_populates="deck")
    compiled_decks: Mapped[list["CompiledDeck"]] = relationship(back_populates="source_deck")
    input_sources: Mapped[list["DeckInputSource"]] = relationship(back_populates="deck")
    brand_assets: Mapped[list["DeckBrandAsset"]] = relationship(back_populates="deck")
    llm_artifacts: Mapped[list["DeckLlmArtifact"]] = relationship(back_populates="deck")
    workspace_preferences: Mapped[list["DeckWorkspacePreference"]] = relationship(back_populates="deck")
    deck_generation_workspace: Mapped["DeckGenerationWorkspace | None"] = relationship(back_populates="deck")
    save_confirmations: Mapped[list["DeckSaveConfirmation"]] = relationship(back_populates="deck")
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(back_populates="deck")
    design_versions: Mapped[list["DesignVersion"]] = relationship(back_populates="deck")
    generated_slides: Mapped[list["GeneratedSlide"]] = relationship(back_populates="deck")
    smart_deck_workspace: Mapped["SmartDeckWorkspace | None"] = relationship(back_populates="deck")
    smart_deck_preferences: Mapped[list["SmartDeckPreference"]] = relationship(back_populates="deck")
    smart_deck_messages: Mapped[list["SmartDeckMessage"]] = relationship(back_populates="deck")
    design_tokens: Mapped[list["DesignToken"]] = relationship(back_populates="deck")
    workflow_jobs: Mapped[list["WorkflowJob"]] = relationship(back_populates="deck")
    media_assets: Mapped[list["DeckMediaAsset"]] = relationship(back_populates="deck")


class DeckFile(Base):
    __tablename__ = "deck_files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"), unique=True)
    filename: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    file_role: Mapped[str] = mapped_column(String, default="original_upload", index=True)
    mime_type: Mapped[str] = mapped_column(String)
    file_extension: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_provider: Mapped[str] = mapped_column(String, default="local")
    size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="file")
    extraction_runs: Mapped[list["DeckExtractionRun"]] = relationship(back_populates="source_file")


class DeckUploadRequest(Base):
    """Owner-scoped coordination for one browser upload action.

    Only digests are retained: neither the raw client request ID nor semantic
    intake text belongs in durable coordination state.
    """

    __tablename__ = "deck_upload_requests"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            "client_request_hash",
            name="uq_deck_upload_request_owner_workspace_client",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_request_hash: Mapped[str] = mapped_column(String(64))
    intent_hash: Mapped[str] = mapped_column(String(64))
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), unique=True)
    deck_file_id: Mapped[str] = mapped_column(ForeignKey("deck_files.id", ondelete="CASCADE"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeckBrandProfile(Base):
    __tablename__ = "deck_brand_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    company_website_url: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String, nullable=True)
    founder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    team_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_style: Mapped[str | None] = mapped_column(String, nullable=True)
    audience_label: Mapped[str | None] = mapped_column(String, nullable=True)
    primary_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String, nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String, nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String, nullable=True)
    background_color: Mapped[str | None] = mapped_column(String, nullable=True)
    text_color: Mapped[str | None] = mapped_column(String, nullable=True)
    palette_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    font_candidates_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    warnings_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    raw_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    branding_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    processing_status: Mapped[str] = mapped_column(String, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="brand_profile")


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    canonical_name: Mapped[str] = mapped_column(String, index=True)
    website_url: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    inferred_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    founder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    team_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_urls_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_notes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace: Mapped["Workspace"] = relationship(back_populates="company_profiles")


class DeckInputSource(Base):
    __tablename__ = "deck_input_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="input_sources")
    brand_assets: Mapped[list["DeckBrandAsset"]] = relationship(back_populates="source_input")


class DeckBrandAsset(Base):
    __tablename__ = "deck_brand_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_input_id: Mapped[str | None] = mapped_column(ForeignKey("deck_input_sources.id", ondelete="SET NULL"), nullable=True)
    asset_type: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    public_url: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="brand_assets")
    source_input: Mapped["DeckInputSource | None"] = relationship(back_populates="brand_assets")


class DeckWorkspacePreference(Base):
    __tablename__ = "deck_workspace_preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active_tool: Mapped[str] = mapped_column(String, default="slides")
    left_panel_open: Mapped[bool] = mapped_column(Boolean, default=True)
    selected_slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_slides.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("design_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_slide_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_slide_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_element_type: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_data_view: Mapped[str | None] = mapped_column(String, nullable=True)
    chat_open: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="workspace_preferences")
    user: Mapped["User"] = relationship(back_populates="deck_workspace_preferences")


class DeckSlide(Base):
    __tablename__ = "deck_slides"
    __table_args__ = (
        Index(
            "uq_deck_slides_source_page",
            "deck_id",
            "source_file_id",
            "source_page_number",
            unique=True,
            postgresql_where=text("source_file_id IS NOT NULL AND source_page_number IS NOT NULL"),
            sqlite_where=text("source_file_id IS NOT NULL AND source_page_number IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    extraction_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    slide_index: Mapped[int] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    narrative_notes: Mapped[str] = mapped_column(Text, default="")
    source_file_id: Mapped[str | None] = mapped_column(ForeignKey("deck_files.id", ondelete="SET NULL"), nullable=True)
    source_page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail_mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    rendered_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    width_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_points: Mapped[float | None] = mapped_column(Float, nullable=True)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    semantic_slide_type: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="slides")
    extraction_run: Mapped["DeckExtractionRun | None"] = relationship(back_populates="slides")
    blocks: Mapped[list["DeckSlideBlock"]] = relationship(back_populates="slide")
    assets: Mapped[list["DeckSlideAsset"]] = relationship(back_populates="slide")


class DeckSlideBlock(Base):
    __tablename__ = "deck_slide_blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str | None] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), nullable=True, index=True)
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id"))
    extraction_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_block_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_slide_blocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    block_index: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    block_type: Mapped[str] = mapped_column(String)
    block_kind: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    extraction_stage: Mapped[str] = mapped_column(String, default="raw", index=True)
    extraction_source: Mapped[str] = mapped_column(String, default="pdf_text", index=True)
    semantic_role: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_slide_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bbox_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_top: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_top: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    z_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rotation: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    font_family: Mapped[str | None] = mapped_column(String, nullable=True)
    font_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    font_weight: Mapped[str | None] = mapped_column(String, nullable=True)
    font_style: Mapped[str | None] = mapped_column(String, nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String, nullable=True)
    source_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[str | None] = mapped_column(String, nullable=True)
    style: Mapped[str | None] = mapped_column(String, nullable=True)
    style_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_object_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page_object_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    slide: Mapped["DeckSlide"] = relationship(back_populates="blocks")
    extraction_run: Mapped["DeckExtractionRun | None"] = relationship(back_populates="blocks")
    asset: Mapped["DeckSlideAsset | None"] = relationship(back_populates="blocks", foreign_keys=[asset_id])
    parent_block: Mapped["DeckSlideBlock | None"] = relationship(remote_side=[id])


class DeckSlideAsset(Base):
    __tablename__ = "deck_slide_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id", ondelete="CASCADE"), index=True)
    extraction_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_type: Mapped[str] = mapped_column(String, index=True)
    asset_kind: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    storage_provider: Mapped[str] = mapped_column(String, default="local")
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    bbox_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_top: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_left: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_top: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_width: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_height: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_object_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page_object_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    slide: Mapped["DeckSlide"] = relationship(back_populates="assets")
    extraction_run: Mapped["DeckExtractionRun | None"] = relationship(back_populates="assets")
    blocks: Mapped[list["DeckSlideBlock"]] = relationship(back_populates="asset", foreign_keys="DeckSlideBlock.asset_id")


class DeckExtractionRun(Base):
    __tablename__ = "deck_extraction_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[str | None] = mapped_column(ForeignKey("deck_files.id", ondelete="SET NULL"), nullable=True)
    run_type: Mapped[str] = mapped_column(String, default="deterministic_pdf", index=True)
    extractor_name: Mapped[str] = mapped_column(String, default="deterministic_v1")
    extractor_version: Mapped[str] = mapped_column(String, default="v1")
    source_format: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    slide_count: Mapped[int] = mapped_column(Integer, default=0)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    current_stage_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    next_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempt_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    max_attempts: Mapped[int | None] = mapped_column(Integer, default=3, nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="extraction_runs")
    source_file: Mapped["DeckFile | None"] = relationship(back_populates="extraction_runs")
    slides: Mapped[list["DeckSlide"]] = relationship(back_populates="extraction_run")
    blocks: Mapped[list["DeckSlideBlock"]] = relationship(back_populates="extraction_run")
    assets: Mapped[list["DeckSlideAsset"]] = relationship(back_populates="extraction_run")
    llm_artifacts: Mapped[list["DeckLlmArtifact"]] = relationship(back_populates="extraction_run")
    workflow_jobs: Mapped[list["WorkflowJob"]] = relationship(back_populates="extraction_run")


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"
    __table_args__ = (
        UniqueConstraint("deck_id", "job_type", "idempotency_key", name="uq_workflow_jobs_deck_job_type_idempotency"),
        CheckConstraint(
            "status in ('queued','running','completed','failed_retryable','failed_final','blocked','timed_out')",
            name="ck_workflow_jobs_status",
        ),
        CheckConstraint(
            "job_type in ("
            "'source_ingestion',"
            "'source_extraction',"
            "'miniatures',"
            "'brand_extraction',"
            "'smart_deck_context',"
            "'db_publisher',"
            "'llm_generation',"
            "'instant_deck_generation',"
            "'selected_slide_generation',"
            "'schema_validation',"
            "'preview_render',"
            "'apply_version',"
            "'compile_final_deck',"
            "'export',"
            "'due_diligence',"
            "'deck_map_analysis',"
            "'market_research',"
            "'smart_edit',"
            "'media_processing'"
            ")",
            name="ck_workflow_jobs_job_type",
        ),
        CheckConstraint(
            "attempt_count >= 0 and max_attempts >= 1",
            name="ck_workflow_jobs_attempt_values",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    extraction_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recovery_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    last_recovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_recovered_by: Mapped[str | None] = mapped_column(String, nullable=True)
    terminal_reason: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    published_phase: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="workflow_jobs")
    extraction_run: Mapped["DeckExtractionRun | None"] = relationship(back_populates="workflow_jobs")
    events: Mapped[list["WorkflowJobEvent"]] = relationship(back_populates="job")
    artifacts: Mapped[list["WorkflowJobArtifact"]] = relationship(back_populates="job")
    dependencies: Mapped[list["WorkflowJobDependency"]] = relationship(
        back_populates="job",
        foreign_keys="WorkflowJobDependency.job_id",
    )
    upstream_dependencies: Mapped[list["WorkflowJobDependency"]] = relationship(
        back_populates="depends_on_job",
        foreign_keys="WorkflowJobDependency.depends_on_job_id",
    )


class WorkflowJobEvent(Base):
    __tablename__ = "workflow_job_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("workflow_jobs.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["WorkflowJob"] = relationship(back_populates="events")


class WorkflowJobArtifact(Base):
    __tablename__ = "workflow_job_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "artifact_type", "storage_key", name="uq_workflow_job_artifacts_job_type_storage"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("workflow_jobs.id", ondelete="CASCADE"), index=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    artifact_type: Mapped[str] = mapped_column(String, index=True)
    storage_key: Mapped[str] = mapped_column(String, index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["WorkflowJob"] = relationship(back_populates="artifacts")


class WorkflowJobDependency(Base):
    __tablename__ = "workflow_job_dependencies"
    __table_args__ = (
        UniqueConstraint("job_id", "depends_on_job_id", "dependency_type", name="uq_workflow_job_dependencies_edge"),
        CheckConstraint(
            "dependency_type in ('requires_completion')",
            name="ck_workflow_job_dependencies_type",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("workflow_jobs.id", ondelete="CASCADE"), index=True)
    depends_on_job_id: Mapped[str] = mapped_column(ForeignKey("workflow_jobs.id", ondelete="CASCADE"), index=True)
    dependency_type: Mapped[str] = mapped_column(String, default="requires_completion")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["WorkflowJob"] = relationship(
        back_populates="dependencies",
        foreign_keys=[job_id],
    )
    depends_on_job: Mapped["WorkflowJob"] = relationship(
        back_populates="upstream_dependencies",
        foreign_keys=[depends_on_job_id],
    )


class DeckLlmArtifact(Base):
    __tablename__ = "deck_llm_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "deck_id",
            "artifact_type",
            "identity_user_id",
            "identity_audience",
            "client_exchange_key",
            name="uq_deck_llm_artifacts_diligence_exchange",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    extraction_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String, index=True)
    artifact_key: Mapped[str] = mapped_column(String, index=True)
    # Exchange identity columns are nullable so all legacy artifact kinds and
    # pre-key Due Diligence clients remain compatible. PostgreSQL enforces the
    # complete identity only when a client exchange key is present.
    identity_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    identity_audience: Mapped[str | None] = mapped_column(String, nullable=True)
    client_exchange_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    schema_version: Mapped[str] = mapped_column(String, default="v1")
    status: Mapped[str] = mapped_column(String, default="ready", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bucket_payload_key: Mapped[str | None] = mapped_column(String, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="llm_artifacts")
    extraction_run: Mapped["DeckExtractionRun | None"] = relationship(back_populates="llm_artifacts")


# DISABLED: This model has been moved to app/db/models/ai.py for 2-database architecture
# if PGVECTOR_AVAILABLE:
#     class VectorChunk(Base):
#         __tablename__ = "vector_chunks"
#
#         id: Mapped[str] = mapped_column(String, primary_key=True)
#         deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
#         slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True, index=True)
#         block_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slide_blocks.id", ondelete="SET NULL"), nullable=True, index=True)
#         artifact_id: Mapped[str | None] = mapped_column(ForeignKey("deck_llm_artifacts.id", ondelete="SET NULL"), nullable=True, index=True)
#         chunk_type: Mapped[str] = mapped_column(String, index=True)
#         source_key: Mapped[str] = mapped_column(String, index=True)
#         content_text: Mapped[str] = mapped_column(Text)
#         embedding_provider: Mapped[str | None] = mapped_column(String, nullable=True)
#         embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
#         embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
#         embedding_fallback_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
#         embedding_error_category: Mapped[str | None] = mapped_column(String, nullable=True)
#         embedding_status: Mapped[str] = mapped_column(String, default="pending", index=True)
#         embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
#         metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#         created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
#         updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
# else:
#     class VectorChunk(Base):
#         __tablename__ = "vector_chunks"
#
#         id: Mapped[str] = mapped_column(String, primary_key=True)
#         deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
#         slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True, index=True)
#         block_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slide_blocks.id", ondelete="SET NULL"), nullable=True, index=True)
#         artifact_id: Mapped[str | None] = mapped_column(ForeignKey("deck_llm_artifacts.id", ondelete="SET NULL"), nullable=True, index=True)
#         chunk_type: Mapped[str] = mapped_column(String, index=True)
#         source_key: Mapped[str] = mapped_column(String, index=True)
#         content_text: Mapped[str] = mapped_column(Text)
#         embedding_provider: Mapped[str | None] = mapped_column(String, nullable=True)
#         embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
#         embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
#         embedding_fallback_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
#         embedding_error_category: Mapped[str | None] = mapped_column(String, nullable=True)
#         embedding_status: Mapped[str] = mapped_column(String, default="pending", index=True)
#         embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
#         metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#         created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
#         updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BlockClassification(Base):
    __tablename__ = "block_classifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    block_id: Mapped[str] = mapped_column(ForeignKey("deck_slide_blocks.id"))
    semantic_tag: Mapped[str] = mapped_column(String)
    diligence_category: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    status: Mapped[str] = mapped_column(String)
    audience: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workflow_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DiligenceReport(Base):
    """Immutable product-facing snapshot for one Due Diligence analysis run."""

    __tablename__ = "diligence_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    workflow_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    audience: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, default="diligence-gap-agent.v1")
    retrieval_trace_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_verdict: Mapped[str] = mapped_column(String, default="not_validated")
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AnalysisFinding(Base):
    __tablename__ = "analysis_findings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("diligence_reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    analysis_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    audience: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True)
    block_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slide_blocks.id", ondelete="SET NULL"), nullable=True)
    field_key: Mapped[str | None] = mapped_column(String, nullable=True)
    target_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_verdict: Mapped[str] = mapped_column(String, default="unverified")
    title: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)


class AudienceProfile(Base):
    __tablename__ = "audience_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, unique=True)
    focus: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(Text, default="")


class AdaptationRun(Base):
    __tablename__ = "adaptation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    audience: Mapped[str] = mapped_column(String)
    purpose: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AdaptationSuggestion(Base):
    __tablename__ = "adaptation_suggestions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id"))
    block_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slide_blocks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    suggested_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    audience: Mapped[str] = mapped_column(String)


class SmartEditRun(Base):
    __tablename__ = "smart_edit_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id"))
    block_id: Mapped[str] = mapped_column(ForeignKey("deck_slide_blocks.id"))
    instruction: Mapped[str] = mapped_column(Text)
    audience_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    workflow_job_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_jobs.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SmartEditSuggestion(Base):
    __tablename__ = "smart_edit_suggestions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("smart_edit_runs.id"))
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id"))
    block_id: Mapped[str] = mapped_column(ForeignKey("deck_slide_blocks.id"))
    original_text: Mapped[str] = mapped_column(Text)
    suggested_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class DeckSlideRevision(Base):
    __tablename__ = "deck_slide_revisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id"))
    block_id: Mapped[str] = mapped_column(ForeignKey("deck_slide_blocks.id"))
    previous_text: Mapped[str] = mapped_column(Text)
    next_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeckExport(Base):
    __tablename__ = "deck_exports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id"))
    type: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    handoff_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    handoff_attempts: Mapped[int] = mapped_column(Integer, default=0)
    handoff_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    handoff_attempted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    handoff_ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeckExportShare(Base):
    """Revocable public capability for one immutable, persisted deck export."""

    __tablename__ = "deck_export_shares"
    __table_args__ = (
        CheckConstraint("status in ('active','revoked')", name="ck_deck_export_shares_status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_export_id: Mapped[str] = mapped_column(
        ForeignKey("deck_exports.id", ondelete="CASCADE"),
        index=True,
    )
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, default="active", server_default="active", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class DeckSaveConfirmation(Base):
    __tablename__ = "deck_save_confirmations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String, default="success")
    cta_label: Mapped[str | None] = mapped_column(String, nullable=True)
    cta_href: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="confirmed", index=True)
    source_surface: Mapped[str | None] = mapped_column(String, nullable=True)
    source_route: Mapped[str | None] = mapped_column(String, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    deck: Mapped["Deck"] = relationship(back_populates="save_confirmations")
    workspace: Mapped["Workspace | None"] = relationship(back_populates="save_confirmations")
    user: Mapped["User | None"] = relationship(back_populates="save_confirmations")


class DesignBatch(Base):
    __tablename__ = "design_batches"
    __table_args__ = (
        UniqueConstraint("deck_id", "version_number", name="uq_design_batches_deck_version_number"),
        UniqueConstraint("deck_id", "source_surface", "source_artifact_id", name="uq_design_batches_source_artifact"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    batch_number: Mapped[int] = mapped_column(Integer)
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_name: Mapped[str | None] = mapped_column(String, nullable=True)
    scope_type: Mapped[str] = mapped_column(String, index=True)
    prompt: Mapped[str] = mapped_column(Text)
    audience_label: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_slide_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="completed", index=True)
    source_surface: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source_artifact_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    source_design_version_id: Mapped[str | None] = mapped_column(ForeignKey("design_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    use_brand_profile: Mapped[bool] = mapped_column(Boolean, default=True)
    use_website_context: Mapped[bool] = mapped_column(Boolean, default=True)
    use_block_classifications: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="design_batches")
    selected_slides: Mapped[list["DesignBatchSlide"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    candidate_slides: Mapped[list["GeneratedSlideCandidate"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    slide_decisions: Mapped[list["BatchSlideDecision"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )
    compiled_decks: Mapped[list["CompiledDeck"]] = relationship(back_populates="batch")
    training_snapshot: Mapped["IterationTrainingSnapshot | None"] = relationship(back_populates="batch", cascade="all, delete-orphan")


class IterationTrainingSnapshot(Base):
    __tablename__ = "iteration_training_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("design_batches.id", ondelete="CASCADE"), unique=True, index=True)
    source_surface: Mapped[str] = mapped_column(String, default="iteration_history", index=True)
    visibility_state: Mapped[str] = mapped_column(String, default="visible", index=True)
    export_state: Mapped[str] = mapped_column(String, default="pending", index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="iteration_training_snapshots")
    batch: Mapped["DesignBatch"] = relationship(back_populates="training_snapshot")


class DesignBatchSlide(Base):
    __tablename__ = "design_batch_slides"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("design_batches.id", ondelete="CASCADE"), index=True)
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id", ondelete="CASCADE"), index=True)
    slide_index_snapshot: Mapped[int] = mapped_column(Integer)
    slide_title_snapshot: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    batch: Mapped["DesignBatch"] = relationship(back_populates="selected_slides")


class GeneratedSlideCandidate(Base):
    __tablename__ = "generated_slide_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("design_batches.id", ondelete="CASCADE"), index=True)
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True)
    slide_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String)
    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="reviewable")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    batch: Mapped["DesignBatch"] = relationship(back_populates="candidate_slides")
    slide_decisions: Mapped[list["BatchSlideDecision"]] = relationship(back_populates="generated_candidate")


class BatchSlideDecision(Base):
    __tablename__ = "batch_slide_decisions"
    __table_args__ = (UniqueConstraint("deck_id", "batch_id", "slide_id", name="uq_batch_slide_decisions_deck_batch_slide"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("design_batches.id", ondelete="CASCADE"), index=True)
    slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id", ondelete="CASCADE"), index=True)
    generated_slide_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slide_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    choice: Mapped[str] = mapped_column(String, index=True)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="batch_slide_decisions")
    batch: Mapped["DesignBatch"] = relationship(back_populates="slide_decisions")
    generated_candidate: Mapped["GeneratedSlideCandidate | None"] = relationship(back_populates="slide_decisions")
    slide: Mapped["DeckSlide"] = relationship()
    decided_by_user: Mapped["User | None"] = relationship()


class CompiledDeck(Base):
    __tablename__ = "compiled_decks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("design_batches.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ready", index=True)
    latest_slide_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    slide_count: Mapped[int] = mapped_column(Integer, default=0)
    manifest_json: Mapped[dict] = mapped_column(JSON)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    finalized_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source_deck: Mapped["Deck"] = relationship(back_populates="compiled_decks")
    batch: Mapped["DesignBatch"] = relationship(back_populates="compiled_decks")
    slides: Mapped[list["CompiledDeckSlide"]] = relationship(
        back_populates="compiled_deck",
        cascade="all, delete-orphan",
    )
    created_by_user: Mapped["User | None"] = relationship()


class CompiledDeckSlide(Base):
    __tablename__ = "compiled_deck_slides"
    __table_args__ = (UniqueConstraint("compiled_deck_id", "slide_index", name="uq_compiled_deck_slides_deck_index"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    compiled_deck_id: Mapped[str] = mapped_column(ForeignKey("compiled_decks.id", ondelete="CASCADE"), index=True)
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_slide_candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slide_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    slide_index: Mapped[int] = mapped_column(Integer, index=True)
    choice: Mapped[str] = mapped_column(String, index=True)
    title_snapshot: Mapped[str] = mapped_column(String)
    manifest_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    compiled_deck: Mapped["CompiledDeck"] = relationship(back_populates="slides")
    source_slide: Mapped["DeckSlide | None"] = relationship()
    generated_candidate: Mapped["GeneratedSlideCandidate | None"] = relationship()


class DeckGenerationWorkspace(Base):
    __tablename__ = "deck_generation_workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), unique=True, index=True)
    generation_status: Mapped[str] = mapped_column(String, default="idle", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="deck_generation_workspace")
    generation_runs: Mapped[list["DeckGenerationRun"]] = relationship(
        back_populates="deck_generation_workspace",
        cascade="all, delete-orphan",
    )
    slide_versions: Mapped[list["DeckSlideVersion"]] = relationship(
        back_populates="deck_generation_workspace",
        cascade="all, delete-orphan",
    )
    feedback_events: Mapped[list["DeckFeedbackEvent"]] = relationship(
        back_populates="deck_generation_workspace",
        cascade="all, delete-orphan",
    )


class DeckGenerationRun(Base):
    __tablename__ = "deck_generation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_generation_workspace_id: Mapped[str] = mapped_column(ForeignKey("deck_generation_workspaces.id", ondelete="CASCADE"), index=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    provider: Mapped[str] = mapped_column(String, default="anthropic")
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_mode: Mapped[str] = mapped_column(String, default="claude")
    scope_type: Mapped[str] = mapped_column(String, default="whole_deck")
    request_payload_json: Mapped[str] = mapped_column(Text)
    generated_deck_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck_generation_workspace: Mapped["DeckGenerationWorkspace"] = relationship(back_populates="generation_runs")
    slide_versions: Mapped[list["DeckSlideVersion"]] = relationship(
        back_populates="generation_run",
        cascade="all, delete-orphan",
    )
    feedback_events: Mapped[list["DeckFeedbackEvent"]] = relationship(back_populates="generation_run")


class DeckSlideVersion(Base):
    __tablename__ = "deck_slide_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_generation_workspace_id: Mapped[str] = mapped_column(ForeignKey("deck_generation_workspaces.id", ondelete="CASCADE"), index=True)
    generation_run_id: Mapped[str] = mapped_column(
        ForeignKey("deck_generation_runs.id", ondelete="CASCADE"),
        index=True,
    )
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True)
    slide_index: Mapped[int] = mapped_column(Integer)
    source_slide_title: Mapped[str | None] = mapped_column(String, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="reviewable", index=True)
    generated_slide_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck_generation_workspace: Mapped["DeckGenerationWorkspace"] = relationship(back_populates="slide_versions")
    generation_run: Mapped["DeckGenerationRun"] = relationship(back_populates="slide_versions")


class DeckFeedbackEvent(Base):
    __tablename__ = "deck_feedback_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_generation_workspace_id: Mapped[str] = mapped_column(ForeignKey("deck_generation_workspaces.id", ondelete="CASCADE"), index=True)
    generation_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_generation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    slide_version_id: Mapped[str] = mapped_column(
        ForeignKey("deck_slide_versions.id", ondelete="CASCADE"),
        index=True,
    )
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deck_generation_workspace: Mapped["DeckGenerationWorkspace"] = relationship(back_populates="feedback_events")
    generation_run: Mapped["DeckGenerationRun | None"] = relationship(back_populates="feedback_events")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    provider: Mapped[str] = mapped_column(String, default="provider_pending")
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt: Mapped[str] = mapped_column(Text)
    selected_source_slide_ids_json: Mapped[list[str]] = mapped_column(JSON)
    style_id: Mapped[str | None] = mapped_column(String, nullable=True)
    brand_product_id: Mapped[str | None] = mapped_column(String, nullable=True)
    additional_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deck: Mapped["Deck"] = relationship(back_populates="generation_jobs")
    design_versions: Mapped[list["DesignVersion"]] = relationship(back_populates="generation_job")
    generated_slides: Mapped[list["GeneratedSlide"]] = relationship(back_populates="generation_job")
    smart_deck_messages: Mapped[list["SmartDeckMessage"]] = relationship(back_populates="generation_job")


# DISABLED: This model has been moved to app/db/models/ai.py for 2-database architecture
# class AgentLearningMemory(Base):
#     __tablename__ = "agent_learning_memories"
#     __table_args__ = (
#         UniqueConstraint("source_run_id", "memory_type", name="uq_agent_learning_memory_source_type"),
#     )
#
#     id: Mapped[str] = mapped_column(String, primary_key=True)
#     workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
#     deck_id: Mapped[str | None] = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
#     user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
#     source_run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     source_run_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     memory_type: Mapped[str] = mapped_column(String, index=True)
#     status: Mapped[str] = mapped_column(String, default="active", index=True)
#     feedback_label: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
#     score: Mapped[float] = mapped_column(Float, default=0)
#     title: Mapped[str] = mapped_column(String)
#     content: Mapped[str] = mapped_column(Text)
#     tags_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
#     evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
#     created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
#     created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
#     updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
#     last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DesignVersion(Base):
    __tablename__ = "design_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    generation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_type: Mapped[str] = mapped_column(String, default="render_schema.v1", index=True)
    render_mode: Mapped[str] = mapped_column(String, default="scene_graph.v1", index=True)
    bucket_manifest_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # Canonical product spine fields — durable generation provenance
    generation_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transformation_plan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    repair_history_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deck: Mapped["Deck"] = relationship(back_populates="design_versions")
    generation_job: Mapped["GenerationJob | None"] = relationship(back_populates="design_versions")
    generated_slides: Mapped[list["GeneratedSlide"]] = relationship(
        back_populates="design_version",
        cascade="all, delete-orphan",
    )
    design_tokens: Mapped[list["DesignToken"]] = relationship(back_populates="design_version")
    html_compilation: Mapped["InstantDeckCompilation | None"] = relationship(
        back_populates="design_version", uselist=False, cascade="all, delete-orphan"
    )


class GeneratedSlide(Base):
    __tablename__ = "generated_slides"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    design_version_id: Mapped[str] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), index=True)
    generation_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True, index=True)
    slide_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ready")
    current_version_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    render_schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    render_mode: Mapped[str] = mapped_column(String, default="scene_graph.v1", index=True)
    section_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    section_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compilation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    design_tokens_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preview_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    validation_status: Mapped[str] = mapped_column(String, default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="generated_slides")
    design_version: Mapped["DesignVersion"] = relationship(back_populates="generated_slides")
    generation_job: Mapped["GenerationJob | None"] = relationship(back_populates="generated_slides")
    source_slide: Mapped["DeckSlide | None"] = relationship()
    code_versions: Mapped[list["GeneratedSlideCodeVersion"]] = relationship(
        back_populates="generated_slide",
        cascade="all, delete-orphan",
    )
    elements: Mapped[list["GeneratedSlideElement"]] = relationship(
        back_populates="generated_slide",
        cascade="all, delete-orphan",
    )
    assets: Mapped[list["Asset"]] = relationship(back_populates="generated_slide")
    design_tokens: Mapped[list["DesignToken"]] = relationship(back_populates="generated_slide")
    source_lineage: Mapped[list["GeneratedSlideSourceLineage"]] = relationship(
        back_populates="generated_slide",
        cascade="all, delete-orphan",
        order_by="GeneratedSlideSourceLineage.lineage_order",
    )


class GeneratedSlideCodeVersion(Base):
    __tablename__ = "generated_slide_code_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    code_kind: Mapped[str] = mapped_column(String, default="render_schema")
    schema_version: Mapped[str] = mapped_column(String, default="smart-deck-render-schema.v1")
    render_schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    code_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    bucket_render_schema_key: Mapped[str | None] = mapped_column(String, nullable=True)
    bucket_code_key: Mapped[str | None] = mapped_column(String, nullable=True)
    bucket_thumbnail_key: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="valid")
    validation_errors_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generated_slide: Mapped["GeneratedSlide"] = relationship(back_populates="code_versions")


class GeneratedSlideElement(Base):
    __tablename__ = "generated_slide_elements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    design_version_id: Mapped[str] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), index=True)
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True, index=True)
    element_key: Mapped[str] = mapped_column(String, index=True)
    element_type: Mapped[str] = mapped_column(String, index=True)
    parent_element_id: Mapped[str | None] = mapped_column(ForeignKey("generated_slide_elements.id", ondelete="SET NULL"), nullable=True)
    z_index: Mapped[int] = mapped_column(Integer, default=0)
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=1)
    height: Mapped[int] = mapped_column(Integer, default=1)
    rotation: Mapped[float] = mapped_column(Float, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    style_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    generated_slide: Mapped["GeneratedSlide"] = relationship(back_populates="elements")
    versions: Mapped[list["GeneratedSlideElementVersion"]] = relationship(
        back_populates="element",
        cascade="all, delete-orphan",
    )


class GeneratedSlideElementVersion(Base):
    __tablename__ = "generated_slide_element_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    element_id: Mapped[str] = mapped_column(ForeignKey("generated_slide_elements.id", ondelete="CASCADE"), index=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    design_version_id: Mapped[str] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String, default="initial_generation")
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    style_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    element: Mapped["GeneratedSlideElement"] = relationship(back_populates="versions")


class InstantDeckOperation(Base):
    __tablename__ = "instant_deck_operations"
    __table_args__ = (
        UniqueConstraint("deck_id", "user_id", "idempotency_key", name="uq_instant_deck_operation_command"),
        CheckConstraint("max_cost_cents IS NULL OR max_cost_cents >= 0", name="ck_instant_deck_operation_max_cost"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workflow_job_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_jobs.id", ondelete="SET NULL"), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String, default="created", index=True)
    output_contract: Mapped[str] = mapped_column(String, default="full_html_deck.v1")
    checkpoint_stage: Mapped[str] = mapped_column(String, default="created", index=True)
    provider_request_starts: Mapped[int] = mapped_column(Integer, default=0)
    max_provider_request_starts: Mapped[int] = mapped_column(
        Integer, default=MAX_PROVIDER_REQUEST_STARTS, server_default=str(MAX_PROVIDER_REQUEST_STARTS)
    )
    max_input_tokens: Mapped[int] = mapped_column(Integer, default=160000)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=32000)
    max_cost_cents: Mapped[float | None] = mapped_column(Float, nullable=True)
    reserved_provider_cost_cents: Mapped[float] = mapped_column(Float, default=0.0)
    actual_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_provider_cost_cents: Mapped[float] = mapped_column(Float, default=0.0)
    product_credit_transaction_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    charge_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    terminal_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    design_version_id: Mapped[str | None] = mapped_column(ForeignKey("design_versions.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InstantDeckProviderAttempt(Base):
    __tablename__ = "instant_deck_provider_attempts"
    __table_args__ = (UniqueConstraint("operation_id", "attempt_number", name="uq_instant_deck_attempt_number"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("instant_deck_operations.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    request_kind: Mapped[str] = mapped_column(String, default="generation")
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    provider_response_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    client_request_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_after_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_limit_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outcome_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reserved_cost_cents: Mapped[float] = mapped_column(Float, default=0.0)
    request_started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    response_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    outcome_known: Mapped[bool] = mapped_column(Boolean, default=False)
    response_state: Mapped[str] = mapped_column(String, default="started", index=True)
    actual_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    actual_cost_cents: Mapped[float] = mapped_column(Float, default=0.0)
    cost_source: Mapped[str] = mapped_column(String, default="unknown")
    provider_idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    raw_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("instant_deck_html_artifacts.id", ondelete="SET NULL"), nullable=True
    )
    validation_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InstantDeckHtmlArtifact(Base):
    __tablename__ = "instant_deck_html_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("instant_deck_operations.id", ondelete="CASCADE"), index=True)
    provider_attempt_id: Mapped[str | None] = mapped_column(ForeignKey("instant_deck_provider_attempts.id", ondelete="SET NULL"), nullable=True, index=True)
    design_version_id: Mapped[str | None] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    artifact_kind: Mapped[str] = mapped_column(String, index=True)
    storage_key: Mapped[str] = mapped_column(String, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String, default="text/html; charset=utf-8")
    quarantined: Mapped[bool] = mapped_column(Boolean, default=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=True)
    encryption_key_version: Mapped[str | None] = mapped_column(String, nullable=True)
    encryption_purpose: Mapped[str | None] = mapped_column(String, nullable=True)
    compiler_version: Mapped[str | None] = mapped_column(String, nullable=True)
    sanitizer_policy_version: Mapped[str | None] = mapped_column(String, nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    purge_status: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    purge_attempts: Mapped[int] = mapped_column(Integer, default=0)
    purge_error_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InstantDeckArtifactCleanupTask(Base):
    __tablename__ = "instant_deck_artifact_cleanup_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    storage_key: Mapped[str] = mapped_column(String, unique=True)
    deck_id: Mapped[str | None] = mapped_column(
        ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation_id: Mapped[str | None] = mapped_column(
        ForeignKey("instant_deck_operations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("instant_deck_provider_attempts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class InstantDeckCompilation(Base):
    __tablename__ = "instant_deck_compilations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    design_version_id: Mapped[str] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), unique=True, index=True)
    provider_attempt_id: Mapped[str] = mapped_column(ForeignKey("instant_deck_provider_attempts.id", ondelete="RESTRICT"), index=True)
    sanitized_html_artifact_id: Mapped[str] = mapped_column(ForeignKey("instant_deck_html_artifacts.id", ondelete="RESTRICT"), unique=True)
    status: Mapped[str] = mapped_column(String, default="compiled", index=True)
    stage: Mapped[str] = mapped_column(String, default="validating", index=True)
    compiler_version: Mapped[str] = mapped_column(String)
    sanitizer_policy_version: Mapped[str] = mapped_column(String)
    renderer_version: Mapped[str] = mapped_column(String)
    grounding_snapshot_hash: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    manifest_json: Mapped[dict] = mapped_column(JSON)
    issue_manifest_json: Mapped[list] = mapped_column(JSON, default=list)
    render_proof_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    design_version: Mapped["DesignVersion"] = relationship(back_populates="html_compilation")


class GeneratedSlideSourceLineage(Base):
    __tablename__ = "generated_slide_source_lineage"
    __table_args__ = (
        UniqueConstraint("generated_slide_id", "source_slide_id", name="uq_generated_slide_source_lineage"),
        UniqueConstraint("generated_slide_id", "lineage_order", name="uq_generated_slide_source_order"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    source_slide_id: Mapped[str] = mapped_column(ForeignKey("deck_slides.id", ondelete="RESTRICT"), index=True)
    lineage_order: Mapped[int] = mapped_column(Integer)
    lineage_role: Mapped[str] = mapped_column(String, default="evidence")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generated_slide: Mapped["GeneratedSlide"] = relationship(back_populates="source_lineage")


class InstantDeckRenderProof(Base):
    __tablename__ = "instant_deck_render_proofs"
    __table_args__ = (UniqueConstraint("compilation_id", "generated_slide_id", name="uq_instant_deck_render_proof_slide"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    compilation_id: Mapped[str] = mapped_column(ForeignKey("instant_deck_compilations.id", ondelete="CASCADE"), index=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    artifact_hash: Mapped[str] = mapped_column(String(64))
    render_document_hash: Mapped[str] = mapped_column(String(64))
    screenshot_hash: Mapped[str] = mapped_column(String(64))
    compilation_hash: Mapped[str] = mapped_column(String(64))
    sanitizer_policy_version: Mapped[str] = mapped_column(String)
    renderer_version: Mapped[str] = mapped_column(String)
    browser_version: Mapped[str] = mapped_column(String)
    viewport_hash: Mapped[str] = mapped_column(String(64))
    proof_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String, default="passed", index=True)
    metrics_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InstantDeckRenderCapability(Base):
    __tablename__ = "instant_deck_render_capabilities"
    __table_args__ = (
        CheckConstraint("scope in ('section','full_deck')", name="ck_instant_deck_render_capability_scope"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("instant_deck_html_artifacts.id", ondelete="CASCADE"), index=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    design_version_id: Mapped[str | None] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String, default="section", server_default="section")
    artifact_encryption_key_version: Mapped[str | None] = mapped_column(String, nullable=True)
    artifact_hash: Mapped[str] = mapped_column(String(64), index=True)
    render_document_hash: Mapped[str] = mapped_column(String(64), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    minted_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True, index=True)
    generated_slide_id: Mapped[str | None] = mapped_column(ForeignKey("generated_slides.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String, index=True)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    public_url: Mapped[str | None] = mapped_column(String, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    generated_slide: Mapped["GeneratedSlide | None"] = relationship(back_populates="assets")


class SmartDeckWorkspace(Base):
    __tablename__ = "smart_deck_workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    active_design_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("design_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    active_source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True)
    active_generated_slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slides.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_element_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slide_elements.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, default="ready", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="smart_deck_workspace")
    preference: Mapped["SmartDeckPreference | None"] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    messages: Mapped[list["SmartDeckMessage"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class SmartDeckPreference(Base):
    __tablename__ = "smart_deck_preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("smart_deck_workspaces.id", ondelete="CASCADE"), unique=True, index=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    selected_source_slide_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    active_source_slide_id: Mapped[str | None] = mapped_column(ForeignKey("deck_slides.id", ondelete="SET NULL"), nullable=True)
    active_design_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("design_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    active_generated_slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slides.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_element_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slide_elements.id", ondelete="SET NULL"),
        nullable=True,
    )
    audience: Mapped[str | None] = mapped_column(String, nullable=True)
    deck_type: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_model: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_subject: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_action_id: Mapped[str | None] = mapped_column(String, nullable=True)
    zoom_level: Mapped[float] = mapped_column(Float, default=1.0)
    canvas_fit_mode: Mapped[str] = mapped_column(String, default="fit")
    right_panel_open: Mapped[bool] = mapped_column(Boolean, default=True)
    slide_rail_open: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace: Mapped["SmartDeckWorkspace"] = relationship(back_populates="preference")
    deck: Mapped["Deck"] = relationship(back_populates="smart_deck_preferences")


class SmartDeckMessage(Base):
    __tablename__ = "smart_deck_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("smart_deck_workspaces.id", ondelete="CASCADE"), index=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    generation_job_id: Mapped[str | None] = mapped_column(ForeignKey("generation_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    selected_source_slide_ids_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    workspace: Mapped["SmartDeckWorkspace"] = relationship(back_populates="messages")
    deck: Mapped["Deck"] = relationship(back_populates="smart_deck_messages")
    generation_job: Mapped["GenerationJob | None"] = relationship(back_populates="smart_deck_messages")


class DesignToken(Base):
    __tablename__ = "design_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    design_version_id: Mapped[str | None] = mapped_column(ForeignKey("design_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    generated_slide_id: Mapped[str | None] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), nullable=True, index=True)
    token_name: Mapped[str] = mapped_column(String)
    token_value: Mapped[str] = mapped_column(String)
    token_type: Mapped[str] = mapped_column(String, default="color")
    source: Mapped[str] = mapped_column(String, default="smart_deck_llm")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deck: Mapped["Deck"] = relationship(back_populates="design_tokens")
    design_version: Mapped["DesignVersion | None"] = relationship(back_populates="design_tokens")
    generated_slide: Mapped["GeneratedSlide | None"] = relationship(back_populates="design_tokens")


class ElementVariationJob(Base):
    __tablename__ = "element_variation_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("smart_deck_workspaces.id", ondelete="CASCADE"), index=True)
    generated_slide_id: Mapped[str] = mapped_column(ForeignKey("generated_slides.id", ondelete="CASCADE"), index=True)
    element_id: Mapped[str] = mapped_column(ForeignKey("generated_slide_elements.id", ondelete="CASCADE"), index=True)
    base_element_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slide_element_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    instruction: Mapped[str] = mapped_column(Text)
    variation_count: Mapped[int] = mapped_column(Integer, default=1)
    retrieval_context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    output_element_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("generated_slide_element_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ============================================================================
# SCIENCE-BACKED PIPELINE TABLES
# These tables support the deterministic deck ingestion pipeline.
# ============================================================================


class ArtifactObject(Base):
    """Tracks artifacts stored in object storage (S3/local).

    Each artifact is a file with metadata, checksum, and storage location.
    Used for structured deck JSON, extraction reports, thumbnails, etc.
    """
    __tablename__ = "artifact_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String, index=True)
    storage_key: Mapped[str] = mapped_column(String, index=True)
    storage_provider: Mapped[str] = mapped_column(String, default="local")
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaterializedDeckState(Base):
    """Single source of truth for deck processing state.

    This table provides the canonical answer to "what stage is this deck in?"
    It is updated by the pipeline after each stage completes.
    """
    __tablename__ = "materialized_deck_state"
    __table_args__ = (
        UniqueConstraint("deck_id", name="uq_materialized_deck_state_deck_id"),
    )

    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True)
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    extraction_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    current_stage: Mapped[str] = mapped_column(String, default="uploaded", index=True)
    slide_count: Mapped[int] = mapped_column(Integer, default=0)
    block_count: Mapped[int] = mapped_column(Integer, default=0)
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    has_thumbnails: Mapped[bool] = mapped_column(Boolean, default=False)
    has_structured_json: Mapped[bool] = mapped_column(Boolean, default=False)
    has_embeddings: Mapped[bool] = mapped_column(Boolean, default=False)
    can_open_smart_deck: Mapped[bool] = mapped_column(Boolean, default=False)
    can_open_smart_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    can_open_due_diligence: Mapped[bool] = mapped_column(Boolean, default=False)
    next_action: Mapped[str | None] = mapped_column(String, nullable=True)
    warnings_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    errors_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extraction_report_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    structured_json_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_extraction_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_generation_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SourceExtractionJob(Base):
    """Explicit jobs for each stage of source extraction.

    Replaces the generic "process deck" job with explicit stage tracking.
    Each job type represents a specific step in the pipeline.
    """
    __tablename__ = "source_extraction_jobs"
    __table_args__ = (
        UniqueConstraint("deck_id", "stage", "idempotency_key", name="uq_source_extraction_jobs_deck_stage_key"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_by: Mapped[str | None] = mapped_column(String, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmRun(Base):
    """Tracks LLM execution runs for semantic enrichment.

    LLM runs are separate from source extraction. They can only run
    after structured deck JSON exists.
    """
    __tablename__ = "llm_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_type: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ChangeRequest(Base):
    """Tracks changes proposed by LLM or user.

    Changes are proposals that must be accepted/rejected before persistence.
    This ensures LLM output is validated and auditable.
    """
    __tablename__ = "change_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    source_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("deck_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    llm_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("llm_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_finding_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_findings.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Audit trail for all mutations.

    Every accepted/rejected change, every generation, every export is traceable.
    """
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String, index=True)
    resource_type: Mapped[str] = mapped_column(String, index=True)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class DeckMediaAsset(Base):
    """Persistent deck-scoped media library for logos and board/deck pictures.

    Owns: user-uploaded images that are asynchronously processed and made
    available to Smart Deck generation and Smart Edit as bounded LLM context.
    Must not own: source-slide extraction assets, brand-only logos, or generic
    rendering assets. Uses the existing durable WorkflowJob for async processing.
    """
    __tablename__ = "deck_media_assets"
    __table_args__ = (
        CheckConstraint(
            "role in ('logo','board_picture','deck_picture')",
            name="ck_deck_media_assets_role",
        ),
        CheckConstraint(
            "status in ('queued','processing','ready','failed_retryable','failed_final','archived')",
            name="ck_deck_media_assets_status",
        ),
        CheckConstraint(
            "size_bytes >= 0",
            name="ck_deck_media_assets_size_bytes",
        ),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="ck_deck_media_assets_width",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="ck_deck_media_assets_height",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    original_filename: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str] = mapped_column(String)
    storage_provider: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_colors_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    processing_version: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deck: Mapped["Deck"] = relationship(back_populates="media_assets")
    workflow_job: Mapped["WorkflowJob | None"] = relationship()
