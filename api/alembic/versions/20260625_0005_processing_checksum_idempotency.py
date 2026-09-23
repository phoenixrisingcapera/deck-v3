"""processing checksum idempotency safeguards

Revision ID: 20260625_0005_processing_checksum
Revises: 0020_workflow_job_lifecycle_columns
Create Date: 2026-06-25 11:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260625_0005_processing_checksum"
down_revision: Union[str, None] = "0020_workflow_job_lifecycle_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CORE_ARTIFACT_TYPES = (
    "deck_profile",
    "slide_catalog",
    "prompt_context",
    "smart_deck_generation_context",
    "smart_deck_design_version_manifest",
    "generated_slide_render_schema",
    "generated_slide_code_version",
)
CORE_ARTIFACT_TYPES_SQL = ", ".join(f"'{item}'" for item in CORE_ARTIFACT_TYPES)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _duplicate_ids_sql(table_name: str, partition_columns: str, where_clause: str) -> str:
    return f"""
        SELECT id
        FROM (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY {partition_columns}
                    ORDER BY created_at DESC, id DESC
                ) AS duplicate_rank
            FROM {table_name}
            WHERE {where_clause}
        ) ranked_duplicates
        WHERE duplicate_rank > 1
    """


def _delete_duplicates(table_name: str, partition_columns: str, where_clause: str) -> None:
    op.execute(
        sa.text(
            f"""
            DELETE FROM {table_name}
            WHERE id IN ({_duplicate_ids_sql(table_name, partition_columns, where_clause)})
            """
        )
    )


def _create_partial_unique_index(
    *,
    table_name: str,
    index_name: str,
    columns: list[str],
    where_clause: str,
) -> None:
    if table_name not in _tables() or _index_exists(table_name, index_name):
        return
    op.create_index(
        index_name,
        table_name,
        columns,
        unique=True,
        postgresql_where=sa.text(where_clause),
        sqlite_where=sa.text(where_clause),
    )


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    if table_name not in _tables() or not _index_exists(table_name, index_name):
        return
    op.drop_index(index_name, table_name=table_name)


def _dedupe_source_pages(existing_tables: set[str]) -> None:
    duplicate_slide_ids = _duplicate_ids_sql(
        "deck_slides",
        "deck_id, source_file_id, source_page_number",
        "source_file_id IS NOT NULL AND source_page_number IS NOT NULL",
    )
    if "deck_slide_blocks" in existing_tables and "block_classifications" in existing_tables:
        op.execute(
            sa.text(
                f"""
                DELETE FROM block_classifications
                WHERE block_id IN (
                    SELECT id FROM deck_slide_blocks WHERE slide_id IN ({duplicate_slide_ids})
                )
                """
            )
        )
    if "deck_slide_assets" in existing_tables:
        op.execute(sa.text(f"DELETE FROM deck_slide_assets WHERE slide_id IN ({duplicate_slide_ids})"))
    if "deck_slide_blocks" in existing_tables:
        op.execute(sa.text(f"DELETE FROM deck_slide_blocks WHERE slide_id IN ({duplicate_slide_ids})"))
    op.execute(sa.text(f"DELETE FROM deck_slides WHERE id IN ({duplicate_slide_ids})"))


def _dedupe_source_preview_assets(existing_tables: set[str]) -> None:
    duplicate_asset_ids = _duplicate_ids_sql(
        "deck_slide_assets",
        "deck_id, slide_id, asset_type",
        "asset_type = 'source_preview'",
    )
    if "deck_slide_blocks" in existing_tables:
        op.execute(sa.text(f"UPDATE deck_slide_blocks SET asset_id = NULL WHERE asset_id IN ({duplicate_asset_ids})"))
    op.execute(sa.text(f"DELETE FROM deck_slide_assets WHERE id IN ({duplicate_asset_ids})"))


def upgrade() -> None:
    existing_tables = _tables()

    if "deck_slides" in existing_tables:
        _dedupe_source_pages(existing_tables)
        _create_partial_unique_index(
            table_name="deck_slides",
            index_name="uq_deck_slides_source_page",
            columns=["deck_id", "source_file_id", "source_page_number"],
            where_clause="source_file_id IS NOT NULL AND source_page_number IS NOT NULL",
        )

    if "deck_slide_assets" in existing_tables:
        _dedupe_source_preview_assets(existing_tables)
        _create_partial_unique_index(
            table_name="deck_slide_assets",
            index_name="uq_deck_source_preview_asset_per_slide",
            columns=["deck_id", "slide_id", "asset_type"],
            where_clause="asset_type = 'source_preview'",
        )

    if "deck_llm_artifacts" in existing_tables:
        _delete_duplicates(
            "deck_llm_artifacts",
            "deck_id, artifact_type, artifact_key",
            f"artifact_key IS NOT NULL AND artifact_type IN ({CORE_ARTIFACT_TYPES_SQL})",
        )
        _create_partial_unique_index(
            table_name="deck_llm_artifacts",
            index_name="uq_deck_llm_artifacts_core_artifact_key",
            columns=["deck_id", "artifact_type", "artifact_key"],
            where_clause=f"artifact_key IS NOT NULL AND artifact_type IN ({CORE_ARTIFACT_TYPES_SQL})",
        )


def downgrade() -> None:
    _drop_index_if_present("deck_llm_artifacts", "uq_deck_llm_artifacts_core_artifact_key")
    _drop_index_if_present("deck_slide_assets", "uq_deck_source_preview_asset_per_slide")
    _drop_index_if_present("deck_slides", "uq_deck_slides_source_page")
