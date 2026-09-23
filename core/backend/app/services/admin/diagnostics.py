from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Asset,
    Deck,
    DeckFile,
    DeckInputSource,
    DeckLlmArtifact,
    DeckSlideAsset,
    DesignVersion,
    GeneratedSlideCodeVersion,
    InstantDeckHtmlArtifact,
)
from app.services.deck_processing.upload_service import deck_storage_prefix
from app.services.storage.artifact_storage import get_upload_storage


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _add_key(keys: set[str], value: object) -> None:
    if isinstance(value, str) and value.strip():
        keys.add(value.strip())


def _referenced_storage_keys(db: Session) -> set[str]:
    keys: set[str] = set()
    for value, in db.query(DeckFile.storage_path).filter(DeckFile.storage_path.isnot(None)).all():
        _add_key(keys, value)
    for value, in db.query(DeckInputSource.storage_path).filter(DeckInputSource.storage_path.isnot(None)).all():
        _add_key(keys, value)
    for value, in db.query(DeckSlideAsset.storage_path).filter(DeckSlideAsset.storage_path.isnot(None)).all():
        _add_key(keys, value)
    for value, in db.query(Asset.storage_path).filter(Asset.storage_path.isnot(None)).all():
        _add_key(keys, value)
    for value, in db.query(DeckLlmArtifact.bucket_payload_key).filter(DeckLlmArtifact.bucket_payload_key.isnot(None)).all():
        _add_key(keys, value)
    for value, in db.query(DesignVersion.bucket_manifest_key).filter(DesignVersion.bucket_manifest_key.isnot(None)).all():
        _add_key(keys, value)
    for value, in db.query(InstantDeckHtmlArtifact.storage_key).all():
        _add_key(keys, value)
    for render_key, code_key, thumbnail_key in db.query(
        GeneratedSlideCodeVersion.bucket_render_schema_key,
        GeneratedSlideCodeVersion.bucket_code_key,
        GeneratedSlideCodeVersion.bucket_thumbnail_key,
    ).all():
        _add_key(keys, render_key)
        _add_key(keys, code_key)
        _add_key(keys, thumbnail_key)

    for payload, in db.query(DeckLlmArtifact.payload_json).filter(DeckLlmArtifact.payload_json.isnot(None)).all():
        if not isinstance(payload, dict):
            continue
        _add_key(keys, payload.get("storagePath"))
        _add_key(keys, payload.get("canonicalStoragePath"))
    return keys


def build_storage_inventory(db: Session, *, prefix: str = "") -> dict[str, Any]:
    storage = get_upload_storage()
    objects = storage.list_objects(prefix)
    referenced_keys = _referenced_storage_keys(db)
    object_paths = {str(item.get("storagePath")) for item in objects if item.get("storagePath")}
    total_bytes = sum(int(item.get("contentLength") or 0) for item in objects)
    referenced_objects = [item for item in objects if str(item.get("storagePath")) in referenced_keys]
    orphan_objects = [item for item in objects if str(item.get("storagePath")) not in referenced_keys]
    missing_references = sorted(
        key
        for key in referenced_keys
        if key not in object_paths and (not prefix or key.startswith(prefix))
    )
    by_top_level: dict[str, dict[str, int]] = {}
    for item in objects:
        storage_path = str(item.get("storagePath") or "")
        top_level = storage_path.split("/", 1)[0] if storage_path else "(unknown)"
        bucket = by_top_level.setdefault(top_level, {"objectCount": 0, "bytes": 0})
        bucket["objectCount"] += 1
        bucket["bytes"] += int(item.get("contentLength") or 0)

    return {
        "prefix": prefix,
        "provider": storage.provider,
        "objectCount": len(objects),
        "totalBytes": total_bytes,
        "referencedObjectCount": len(referenced_objects),
        "orphanObjectCount": len(orphan_objects),
        "missingReferenceCount": len(missing_references),
        "bytesByTopLevel": by_top_level,
        "orphanObjects": orphan_objects[:250],
        "missingReferences": missing_references[:250],
    }


def cleanup_orphan_storage_objects(
    db: Session,
    *,
    prefix: str = "",
    older_than_days: int = 7,
    execute: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    storage = get_upload_storage()
    inventory = build_storage_inventory(db, prefix=prefix)
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    candidates: list[dict] = []
    for item in inventory["orphanObjects"]:
        last_modified = _parse_datetime(item.get("lastModified"))
        if last_modified is not None and last_modified > cutoff:
            continue
        candidates.append(item)
        if len(candidates) >= limit:
            break

    deleted: list[dict] = []
    failures: list[dict] = []
    if execute:
        for item in candidates:
            storage_path = str(item.get("storagePath") or "")
            if not storage_path:
                continue
            object_key = item.get("objectKey")
            clean_upload_prefix = settings.upload_storage_s3_prefix.strip("/")
            if isinstance(object_key, str) and clean_upload_prefix and not object_key.startswith(f"{clean_upload_prefix}/"):
                failures.append(
                    {
                        "storagePath": storage_path,
                        "objectKey": object_key,
                        "errorType": "DirectArtifactKeySkipped",
                        "error": "Direct bucket artifact keys are not deleted through upload storage cleanup.",
                    }
                )
                continue
            try:
                storage.delete(storage_path)
                deleted.append(item)
            except Exception as exc:
                failures.append({"storagePath": storage_path, "errorType": exc.__class__.__name__, "error": str(exc)[:300]})

    return {
        "execute": execute,
        "prefix": prefix,
        "olderThanDays": older_than_days,
        "candidateCount": len(candidates),
        "deletedCount": len(deleted),
        "failureCount": len(failures),
        "candidates": candidates,
        "deleted": deleted,
        "failures": failures,
    }


def cleanup_stale_pending_decks(
    db: Session,
    *,
    older_than_days: int = 7,
    execute: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    storage = get_upload_storage()
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    stale_decks = (
        db.query(Deck)
        .filter(Deck.status == "pending", Deck.created_at <= cutoff, ~Deck.file.has())
        .order_by(Deck.created_at.asc())
        .limit(limit)
        .all()
    )

    candidates: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for deck in stale_decks:
        prefix = deck_storage_prefix(deck.user_id, deck.id)
        candidates.append(
            {
                "deckId": deck.id,
                "workspaceId": deck.workspace_id,
                "userId": deck.user_id,
                "storagePrefix": prefix,
                "createdAt": deck.created_at.isoformat() if deck.created_at else None,
            }
        )
        if not execute:
            continue

        try:
            for item in storage.list_objects(prefix=prefix):
                storage_path = str(item.get("storagePath") or "")
                if storage_path:
                    storage.delete(storage_path)
            db.delete(deck)
            deleted.append(candidates[-1])
        except Exception as exc:
            failures.append(
                {
                    "deckId": deck.id,
                    "storagePrefix": prefix,
                    "errorType": exc.__class__.__name__,
                    "error": str(exc)[:300],
                }
            )

    if execute and deleted:
        db.commit()

    return {
        "execute": execute,
        "olderThanDays": older_than_days,
        "candidateCount": len(candidates),
        "deletedCount": len(deleted),
        "failureCount": len(failures),
        "candidates": candidates,
        "deleted": deleted,
        "failures": failures,
    }
