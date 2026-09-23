"""Transfer legacy cleanup audit retries into the durable cleanup outbox."""

from __future__ import annotations

from hashlib import sha256

from alembic import op
import sqlalchemy as sa


revision = "20260807_0002_cleanup_xfer"
down_revision = "20260807_0001_html_cleanup"
branch_labels = None
depends_on = None


LEGACY_CLEANUP_ACTION = "instant_html.recovery_artifact.cleanup"
LEGACY_UNRESOLVED_RESULT = "retry_pending"
TRANSFERRED_RESULT = "migrated"
TRANSFER_DISPOSITION = "transferred_to_cleanup_outbox"
TRANSFER_METADATA_KEY = "cleanupTaskMigration"
REVERSIBLE_CLEANUP_STATUS = "completed"
TERMINAL_CLEANUP_STATUSES = ("canceled", REVERSIBLE_CLEANUP_STATUS)


def _tables() -> tuple[sa.TableClause, sa.TableClause]:
    cleanup = sa.table(
        "instant_deck_artifact_cleanup_tasks",
        sa.column("id", sa.String()),
        sa.column("storage_key", sa.String()),
        sa.column("status", sa.String()),
    )
    audits = sa.table(
        "security_audit_events",
        sa.column("id", sa.String()),
        sa.column("action", sa.String()),
        sa.column("result", sa.String()),
        sa.column("details_json", sa.JSON()),
    )
    return cleanup, audits


def _successor_task_id(storage_key: str) -> str:
    return f"legacycln_{sha256(storage_key.encode('utf-8')).hexdigest()[:22]}"


def _validated_legacy_rows(bind: sa.Connection, audits: sa.TableClause) -> list[dict]:
    rows = bind.execute(
        sa.select(audits.c.id, audits.c.details_json).where(
            audits.c.action == LEGACY_CLEANUP_ACTION,
            audits.c.result == LEGACY_UNRESOLVED_RESULT,
        ).order_by(audits.c.id)
    ).mappings().all()
    validated: list[dict] = []
    for row in rows:
        event_id = row["id"]
        details = row["details_json"]
        if not isinstance(event_id, str) or not event_id or not isinstance(details, dict):
            raise RuntimeError(
                "Legacy Instant HTML cleanup retry record is malformed; upgrade blocked without changes."
            )
        storage_keys = details.get("storageKeys")
        if (
            not isinstance(storage_keys, list)
            or not storage_keys
            or any(
                not isinstance(value, str) or not value.strip()
                for value in storage_keys
            )
            or TRANSFER_METADATA_KEY in details
        ):
            raise RuntimeError(
                "Legacy Instant HTML cleanup retry record is malformed; upgrade blocked without changes."
            )
        validated.append({
            "id": event_id,
            "details": details,
            "storage_keys": list(storage_keys),
        })
    return validated


def _transfer_legacy_cleanup_events() -> None:
    """Validate every source row before atomically transferring any of them."""
    bind = op.get_bind()
    cleanup, audits = _tables()
    rows = _validated_legacy_rows(bind, audits)
    if not rows:
        return

    existing_rows = bind.execute(
        sa.select(cleanup.c.id, cleanup.c.storage_key)
    ).mappings().all()
    tasks_by_key: dict[str, str] = {}
    keys_by_id: dict[str, str] = {}
    for row in existing_rows:
        task_id, storage_key = row["id"], row["storage_key"]
        if not isinstance(task_id, str) or not task_id or not isinstance(storage_key, str):
            raise RuntimeError("Cleanup outbox contains malformed identity data; upgrade blocked.")
        tasks_by_key[storage_key] = task_id
        keys_by_id[task_id] = storage_key

    planned: list[dict] = []
    planned_new: dict[str, str] = {}
    for row in rows:
        task_ids: list[str] = []
        created_task_ids: list[str] = []
        for storage_key in row["storage_keys"]:
            task_id = tasks_by_key.get(storage_key) or planned_new.get(storage_key)
            if task_id is None:
                task_id = _successor_task_id(storage_key)
                collision_key = keys_by_id.get(task_id)
                if collision_key is not None and collision_key != storage_key:
                    raise RuntimeError("Cleanup task identity collision; upgrade blocked without changes.")
                planned_new[storage_key] = task_id
                keys_by_id[task_id] = storage_key
                created_task_ids.append(task_id)
            task_ids.append(task_id)
        planned.append({**row, "task_ids": task_ids, "created_task_ids": created_task_ids})

    for storage_key, task_id in sorted(planned_new.items()):
        bind.execute(cleanup.insert().values(
            id=task_id,
            storage_key=storage_key,
            status="retry_pending",
        ))
    for row in planned:
        redacted = dict(row["details"])
        redacted.pop("storageKeys")
        redacted[TRANSFER_METADATA_KEY] = {
            "revision": revision,
            "disposition": TRANSFER_DISPOSITION,
            "sourceAuditEventId": row["id"],
            "cleanupTaskIds": row["task_ids"],
            "createdCleanupTaskIds": row["created_task_ids"],
            "cleanupTaskCount": len(row["task_ids"]),
            "storageKeysRedacted": True,
        }
        bind.execute(
            audits.update().where(
                audits.c.id == row["id"],
                audits.c.action == LEGACY_CLEANUP_ACTION,
                audits.c.result == LEGACY_UNRESOLVED_RESULT,
            ).values(result=TRANSFERRED_RESULT, details_json=redacted)
        )


def upgrade() -> None:
    _transfer_legacy_cleanup_events()


def _reverse_transferred_cleanup_events() -> None:
    bind = op.get_bind()
    cleanup, audits = _tables()
    nonterminal_count = bind.execute(
        sa.select(sa.func.count()).select_from(cleanup).where(
            sa.or_(
                cleanup.c.status.is_(None),
                cleanup.c.status.not_in(TERMINAL_CLEANUP_STATUSES),
            )
        )
    ).scalar_one()
    if nonterminal_count:
        raise RuntimeError(
            "Downgrade blocked: cleanup tasks are actionable or have an unknown status; reconcile them first."
        )

    rows = bind.execute(
        sa.select(audits.c.id, audits.c.details_json).where(
            audits.c.action == LEGACY_CLEANUP_ACTION,
            audits.c.result == TRANSFERRED_RESULT,
        ).order_by(audits.c.id)
    ).mappings().all()
    task_rows = bind.execute(
        sa.select(cleanup.c.id, cleanup.c.storage_key, cleanup.c.status)
    ).mappings().all()
    keys_by_id = {row["id"]: row["storage_key"] for row in task_rows}
    statuses_by_id = {row["id"]: row["status"] for row in task_rows}
    reversals: list[dict] = []
    created_task_ids: set[str] = set()
    for row in rows:
        details = row["details_json"]
        metadata = details.get(TRANSFER_METADATA_KEY) if isinstance(details, dict) else None
        task_ids = metadata.get("cleanupTaskIds") if isinstance(metadata, dict) else None
        created_ids = metadata.get("createdCleanupTaskIds") if isinstance(metadata, dict) else None
        if (
            metadata is None
            or metadata.get("revision") != revision
            or metadata.get("disposition") != TRANSFER_DISPOSITION
            or metadata.get("sourceAuditEventId") != row["id"]
            or not isinstance(task_ids, list)
            or not task_ids
            or any(not isinstance(task_id, str) or task_id not in keys_by_id for task_id in task_ids)
            or not isinstance(created_ids, list)
            or any(not isinstance(task_id, str) for task_id in created_ids)
            or any(task_id not in task_ids for task_id in created_ids)
            or metadata.get("cleanupTaskCount") != len(task_ids)
            or metadata.get("storageKeysRedacted") is not True
        ):
            raise RuntimeError(
                "Downgrade blocked: transferred cleanup audit traceability is incomplete; reconcile explicitly."
            )
        restored = dict(details)
        restored.pop(TRANSFER_METADATA_KEY)
        restored["storageKeys"] = [keys_by_id[task_id] for task_id in task_ids]
        reversals.append({"id": row["id"], "details": restored})
        created_task_ids.update(created_ids)

    transferred_task_ids = {
        task_id
        for row in rows
        for task_id in row["details_json"][TRANSFER_METADATA_KEY]["cleanupTaskIds"]
    }
    if any(
        statuses_by_id[task_id] != REVERSIBLE_CLEANUP_STATUS
        for task_id in transferred_task_ids
    ):
        raise RuntimeError(
            "Downgrade blocked: transferred cleanup tasks are not all completed; "
            "published artifacts and their provenance must be retained."
        )

    for row in reversals:
        bind.execute(
            audits.update().where(
                audits.c.id == row["id"],
                audits.c.action == LEGACY_CLEANUP_ACTION,
                audits.c.result == TRANSFERRED_RESULT,
            ).values(result=LEGACY_UNRESOLVED_RESULT, details_json=row["details"])
        )
    if created_task_ids:
        bind.execute(cleanup.delete().where(cleanup.c.id.in_(sorted(created_task_ids))))


def downgrade() -> None:
    _reverse_transferred_cleanup_events()
