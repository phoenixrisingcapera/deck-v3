from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Deck, IterationTrainingSnapshot, Workspace


def training_export_is_enabled() -> bool:
    return settings.training_export_enabled and bool(str(settings.ai_database_url or "").strip())


def auto_export_pending_iteration_training_snapshots(db: Session) -> dict:
    try:
        return export_pending_iteration_training_snapshots(db)
    except Exception:
        db.rollback()
        return {
            "enabled": training_export_is_enabled(),
            "selected": 0,
            "exported": 0,
            "blocked": 0,
            "skipped": 0,
            "error": "auto_export_failed",
        }


def list_iteration_training_snapshots(
    db: Session,
    *,
    limit: int = 100,
    export_state: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    query = (
        db.query(IterationTrainingSnapshot, Deck.workspace_id, Workspace.name, Workspace.allow_model_training, Workspace.model_training_policy)
        .join(Deck, Deck.id == IterationTrainingSnapshot.deck_id)
        .join(Workspace, Workspace.id == Deck.workspace_id)
        .order_by(IterationTrainingSnapshot.created_at.desc())
    )
    if export_state:
        query = query.filter(IterationTrainingSnapshot.export_state == export_state)
    if workspace_id:
        query = query.filter(Deck.workspace_id == workspace_id)

    rows = query.limit(limit).all()
    return {
        "summary": {
            "returned": len(rows),
            "exportEnabled": training_export_is_enabled(),
        },
        "snapshots": [
            {
                "id": snapshot.id,
                "deckId": snapshot.deck_id,
                "workspaceId": resolved_workspace_id,
                "workspaceName": workspace_name,
                "batchId": snapshot.batch_id,
                "sourceSurface": snapshot.source_surface,
                "visibilityState": snapshot.visibility_state,
                "exportState": snapshot.export_state,
                "archivedAt": snapshot.archived_at.isoformat() if snapshot.archived_at else None,
                "exportedAt": snapshot.exported_at.isoformat() if snapshot.exported_at else None,
                "createdAt": snapshot.created_at.isoformat(),
                "updatedAt": snapshot.updated_at.isoformat(),
                "allowModelTraining": allow_model_training,
                "modelTrainingPolicy": model_training_policy,
                "snapshot": snapshot.snapshot_json,
            }
            for snapshot, resolved_workspace_id, workspace_name, allow_model_training, model_training_policy in rows
        ],
    }


@contextmanager
def _training_connection() -> Iterator:
    engine = create_engine(settings.ai_database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            _ensure_training_export_schema(connection)
            yield connection
    finally:
        engine.dispose()


def _ensure_training_export_schema(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS training_iteration_examples (
                id VARCHAR(64) PRIMARY KEY,
                snapshot_id VARCHAR(64) UNIQUE NOT NULL,
                deck_id VARCHAR(64) NOT NULL,
                workspace_id VARCHAR(64) NOT NULL,
                batch_id VARCHAR(64) NOT NULL,
                source_surface VARCHAR(80) NOT NULL,
                visibility_state VARCHAR(40) NOT NULL,
                export_state VARCHAR(40) NOT NULL,
                model_training_policy VARCHAR(80) NOT NULL,
                snapshot_json JSON NOT NULL,
                archived_at TIMESTAMP NULL,
                exported_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
            """
        )
    )


def export_pending_iteration_training_snapshots(db: Session, *, limit: int | None = None) -> dict:
    batch_size = max(1, int(limit or settings.training_export_batch_size))
    pending = (
        db.query(IterationTrainingSnapshot, Deck.workspace_id, Workspace.allow_model_training, Workspace.model_training_policy)
        .join(Deck, Deck.id == IterationTrainingSnapshot.deck_id)
        .join(Workspace, Workspace.id == Deck.workspace_id)
        .filter(IterationTrainingSnapshot.export_state == "pending")
        .order_by(IterationTrainingSnapshot.created_at.asc())
        .limit(batch_size)
        .all()
    )
    if not pending:
        return {
            "enabled": training_export_is_enabled(),
            "selected": 0,
            "exported": 0,
            "blocked": 0,
            "skipped": 0,
        }

    exported = 0
    blocked = 0
    skipped = 0
    now = datetime.utcnow()

    if not training_export_is_enabled():
        return {
            "enabled": False,
            "selected": len(pending),
            "exported": 0,
            "blocked": 0,
            "skipped": len(pending),
        }

    with _training_connection() as connection:
        for snapshot, workspace_id, allow_model_training, model_training_policy in pending:
            if (not allow_model_training) or str(model_training_policy or "").strip().lower() == "disabled":
                snapshot.export_state = "blocked"
                snapshot.updated_at = now
                blocked += 1
                continue

            connection.execute(
                text(
                    """
                    INSERT INTO training_iteration_examples (
                        id,
                        snapshot_id,
                        deck_id,
                        workspace_id,
                        batch_id,
                        source_surface,
                        visibility_state,
                        export_state,
                        model_training_policy,
                        snapshot_json,
                        archived_at,
                        exported_at,
                        created_at,
                        updated_at
                    ) VALUES (
                        :id,
                        :snapshot_id,
                        :deck_id,
                        :workspace_id,
                        :batch_id,
                        :source_surface,
                        :visibility_state,
                        :export_state,
                        :model_training_policy,
                        :snapshot_json,
                        :archived_at,
                        :exported_at,
                        :created_at,
                        :updated_at
                    )
                    ON CONFLICT(snapshot_id) DO UPDATE SET
                        visibility_state = excluded.visibility_state,
                        export_state = excluded.export_state,
                        model_training_policy = excluded.model_training_policy,
                        snapshot_json = excluded.snapshot_json,
                        archived_at = excluded.archived_at,
                        exported_at = excluded.exported_at,
                        updated_at = excluded.updated_at
                    """
                ),
                {
                    "id": f"train_{snapshot.id}",
                    "snapshot_id": snapshot.id,
                    "deck_id": snapshot.deck_id,
                    "workspace_id": workspace_id,
                    "batch_id": snapshot.batch_id,
                    "source_surface": snapshot.source_surface,
                    "visibility_state": snapshot.visibility_state,
                    "export_state": "exported",
                    "model_training_policy": model_training_policy,
                    "snapshot_json": json.dumps(snapshot.snapshot_json, ensure_ascii=True),
                    "archived_at": snapshot.archived_at,
                    "exported_at": now,
                    "created_at": snapshot.created_at,
                    "updated_at": now,
                },
            )
            snapshot.export_state = "exported"
            snapshot.exported_at = now
            snapshot.updated_at = now
            exported += 1

    db.commit()
    return {
        "enabled": True,
        "selected": len(pending),
        "exported": exported,
        "blocked": blocked,
        "skipped": skipped,
    }
