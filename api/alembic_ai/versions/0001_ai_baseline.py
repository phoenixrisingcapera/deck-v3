"""Create the independent AI database baseline.

This lineage is intentionally independent from the core product lineage. It
does not create users, auth, billing, deck source-of-truth, or workflow tables.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0001_ai_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vector_chunks (
            id VARCHAR PRIMARY KEY,
            deck_id VARCHAR NOT NULL,
            slide_id VARCHAR,
            block_id VARCHAR,
            artifact_id VARCHAR,
            chunk_type VARCHAR NOT NULL,
            source_key VARCHAR NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            content_text TEXT NOT NULL,
            embedding_provider VARCHAR,
            embedding_model VARCHAR,
            embedding_dimensions INTEGER,
            embedding_fallback_level INTEGER NOT NULL DEFAULT 0,
            embedding_error_category VARCHAR,
            embedding_status VARCHAR NOT NULL DEFAULT 'pending',
            embedding vector(1024),
            metadata_json JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_vector_chunks_source_hash UNIQUE (source_key, content_hash)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_vector_chunks_deck_id ON vector_chunks (deck_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vector_chunks_workspace_scope ON vector_chunks (deck_id, source_key)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vector_chunks_embedding_cosine "
        "ON vector_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_telemetry_events (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            deck_id VARCHAR,
            user_id VARCHAR,
            run_id VARCHAR,
            run_type VARCHAR NOT NULL,
            step_id VARCHAR,
            step_name VARCHAR,
            event_name VARCHAR NOT NULL,
            event_level VARCHAR,
            provider VARCHAR,
            model VARCHAR,
            status VARCHAR,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost_cents DOUBLE PRECISION,
            latency_ms INTEGER,
            error_category VARCHAR,
            error_message TEXT,
            error_message_redacted TEXT,
            trace_id VARCHAR,
            span_id VARCHAR,
            request_id VARCHAR,
            metadata_json JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_regression_cases (
            id VARCHAR PRIMARY KEY,
            source_event_id VARCHAR,
            workspace_id VARCHAR,
            deck_id VARCHAR,
            user_id VARCHAR,
            run_id VARCHAR,
            run_type VARCHAR,
            event_name VARCHAR NOT NULL,
            case_name VARCHAR NOT NULL,
            case_type VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'active',
            failure_category VARCHAR,
            title VARCHAR,
            fixture_json JSON,
            notes TEXT,
            input_json JSON,
            expected_output_json JSON,
            actual_output_json JSON,
            last_run_at TIMESTAMP WITHOUT TIME ZONE,
            created_by_user_id VARCHAR,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_learning_memories (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            deck_id VARCHAR,
            memory_type VARCHAR NOT NULL,
            content TEXT NOT NULL,
            confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            source_run_id VARCHAR,
            metadata_json JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_runs (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            deck_id VARCHAR NOT NULL,
            user_id VARCHAR,
            intent VARCHAR NOT NULL,
            mode VARCHAR NOT NULL,
            user_instruction TEXT NOT NULL,
            selected_slide_ids_json JSON NOT NULL,
            audience VARCHAR,
            provider VARCHAR NOT NULL DEFAULT 'provider_pending',
            model VARCHAR,
            status VARCHAR NOT NULL DEFAULT 'pending',
            error_message TEXT,
            metrics_json JSON,
            result_json JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_run_steps (
            id VARCHAR PRIMARY KEY,
            ai_run_id VARCHAR NOT NULL REFERENCES ai_runs(id) ON DELETE CASCADE,
            step_name VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            input_json JSON,
            output_json JSON,
            error_message TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage_buckets (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            quota_key VARCHAR NOT NULL,
            window_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embedding_model_registry (
            id VARCHAR PRIMARY KEY,
            provider VARCHAR NOT NULL,
            model VARCHAR NOT NULL,
            dimensions INTEGER NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'active',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_embedding_model_registry_provider_model UNIQUE (provider, model)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS embedding_ingestion_runs (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR,
            deck_id VARCHAR,
            content_hash VARCHAR(64) NOT NULL,
            provider VARCHAR NOT NULL,
            model VARCHAR NOT NULL,
            dimensions INTEGER NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'queued',
            error_message TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITHOUT TIME ZONE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS retrieval_traces (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            deck_id VARCHAR NOT NULL,
            query_hash VARCHAR(64) NOT NULL,
            result_count INTEGER NOT NULL DEFAULT 0,
            metadata_json JSON,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_dead_letters (
            id VARCHAR PRIMARY KEY,
            job_id VARCHAR,
            workspace_id VARCHAR,
            deck_id VARCHAR,
            operation VARCHAR NOT NULL,
            payload_json JSON,
            error_message TEXT NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    # Preserve production data during rollback. Operators may explicitly drop
    # these tables after a verified backup and migration reconciliation.
    pass
