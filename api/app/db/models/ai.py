"""AI-specific database models.

These models are designed to be stored in the AI database (AI_DATABASE_URL)
with pgvector support. They reference Core IDs as plain strings, not
cross-database foreign keys.

When AI_DATABASE_URL is not configured, these tables remain in the core
database for backward compatibility.
"""
from __future__ import annotations

from datetime import datetime

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AiBase


class VectorChunk(AiBase):
    """Vector embeddings for semantic search and retrieval.

    Stores chunked content with pgvector embeddings for similarity search.
    References Core IDs (deck_id, slide_id, block_id) as plain strings.
    """
    __tablename__ = "vector_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    deck_id: Mapped[str] = mapped_column(String, index=True)
    slide_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    block_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    artifact_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    chunk_type: Mapped[str] = mapped_column(String, index=True)
    source_key: Mapped[str] = mapped_column(String, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    content_text: Mapped[str] = mapped_column(Text)
    embedding_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_fallback_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_error_category: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_status: Mapped[str] = mapped_column(String, default="pending", index=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024) if PGVECTOR_AVAILABLE else JSON,
        nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmbeddingModelRegistry(AiBase):
    """Provider/model dimension contract used by worker readiness checks."""

    __tablename__ = "embedding_model_registry"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_embedding_model_registry_provider_model"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, index=True)
    dimensions: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmbeddingIngestionRun(AiBase):
    __tablename__ = "embedding_ingestion_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    dimensions: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RetrievalTrace(AiBase):
    __tablename__ = "retrieval_traces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    deck_id: Mapped[str] = mapped_column(String, index=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AiDeadLetter(AiBase):
    __tablename__ = "ai_dead_letters"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    operation: Mapped[str] = mapped_column(String, index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AgentTelemetryEvent(AiBase):
    """LLM execution telemetry and tracking.

    Records every LLM call with provider, model, tokens, latency, and status.
    References Core IDs as plain strings.
    """
    __tablename__ = "agent_telemetry_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(String, index=True)
    step_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    step_name: Mapped[str | None] = mapped_column(String, nullable=True)
    event_name: Mapped[str] = mapped_column(String, index=True)
    event_level: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String, default="provider_pending", index=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True, default=None, index=True)
    status: Mapped[str] = mapped_column(String, default="started", index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_cents: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    span_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentRegressionCase(AiBase):
    """Regression test cases for AI quality tracking.

    Stores test cases with input/output pairs for regression testing.
    References Core IDs as plain strings.
    """
    __tablename__ = "agent_regression_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String, index=True)
    case_name: Mapped[str] = mapped_column(String, index=True)
    case_type: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    failure_category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    fixture_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actual_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentLearningMemory(AiBase):
    """Learning memories for AI improvement.

    Stores insights and patterns learned from user interactions.
    References Core IDs as plain strings.
    """
    __tablename__ = "agent_learning_memories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    deck_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    memory_type: Mapped[str] = mapped_column(String, index=True)
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_run_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    feedback_label: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    tags_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AiRun(AiBase):
    """AI orchestration runs.

    Tracks complete AI operations with steps and results.
    References Core IDs as plain strings.
    """
    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    deck_id: Mapped[str] = mapped_column(String, index=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    intent: Mapped[str] = mapped_column(String, index=True)
    mode: Mapped[str] = mapped_column(String, index=True)
    user_instruction: Mapped[str] = mapped_column(Text)
    selected_slide_ids_json: Mapped[list[str]] = mapped_column(JSON)
    audience: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str] = mapped_column(String, default="provider_pending")
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    steps: Mapped[list["AiRunStep"]] = relationship(back_populates="ai_run", cascade="all, delete-orphan")


class AiRunStep(AiBase):
    """Steps within an AI orchestration run.

    Tracks individual steps within an AI run.
    References Core IDs as plain strings.
    """
    __tablename__ = "ai_run_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    ai_run_id: Mapped[str] = mapped_column(String, ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
    step_name: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_run: Mapped["AiRun"] = relationship(back_populates="steps")


class AiUsageBucket(AiBase):
    """AI usage quota tracking.

    Tracks usage counts per user/workspace per quota key.
    References Core IDs as plain strings.
    """
    __tablename__ = "ai_usage_buckets"
    __table_args__ = (
        UniqueConstraint("user_id", "quota_key", name="uq_ai_usage_buckets_user_quota"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    quota_key: Mapped[str] = mapped_column(String, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class AiBudgetReservation(AiBase):
    """One idempotent provider-operation reservation linked to its aggregate bucket."""

    __tablename__ = "ai_budget_reservations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    reservation_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    bucket_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="reserved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
