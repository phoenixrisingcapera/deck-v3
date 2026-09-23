from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.db.models import Deck, DeckLlmArtifact, DesignVersion, GeneratedSlide, GeneratedSlideCodeVersion, SmartDeckWorkspace
from app.services.storage.signed_urls import get_bucket_artifact_service


def _code_version_lifecycle(code_version: GeneratedSlideCodeVersion) -> str | None:
    code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
    lifecycle = code_json.get("lifecycle") or code_json.get("state")
    return lifecycle if isinstance(lifecycle, str) else None


def _archive_code_version_artifacts(code_version: GeneratedSlideCodeVersion) -> dict[str, str]:
    bucket_service = get_bucket_artifact_service()
    archived: dict[str, str] = {}
    keys = {
        "render_schema_key": code_version.bucket_render_schema_key,
        "code_key": code_version.bucket_code_key,
        "thumbnail_key": code_version.bucket_thumbnail_key,
    }
    for name, key in keys.items():
        if not key:
            continue
        archive_key = bucket_service.archive_object_sync(key=key)
        if archive_key:
            archived[name] = archive_key
    return archived


def _archive_design_version_manifest(version: DesignVersion) -> str | None:
    if not version.bucket_manifest_key:
        return None
    return get_bucket_artifact_service().archive_object_sync(key=version.bucket_manifest_key)


def _retire_llm_artifact(artifact: DeckLlmArtifact) -> dict[str, str] | None:
    artifact_key = artifact.bucket_payload_key
    if not artifact_key and isinstance(artifact.payload_json, dict):
        storage_path = artifact.payload_json.get("storagePath")
        artifact_key = storage_path if isinstance(storage_path, str) else None
    if not artifact_key:
        return None
    bucket_service = get_bucket_artifact_service()
    if bucket_service.object_exists_sync(key=artifact_key):
        bucket_service.delete_object_sync(key=artifact_key)
    return {"deletedArtifactKey": artifact_key}


def apply_retention(
    db: Session,
    deck_id: str,
    saved_limit: int = 3,
    unused_limit_per_slide: int = 3,
    llm_artifact_limit: int = 20,
) -> None:
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    workspace = db.query(SmartDeckWorkspace).filter(SmartDeckWorkspace.deck_id == deck_id).first()
    versions = (
        db.query(DesignVersion)
        .options(selectinload(DesignVersion.generated_slides).selectinload(GeneratedSlide.code_versions))
        .filter(DesignVersion.deck_id == deck_id)
        .order_by(DesignVersion.created_at.desc())
        .all()
    )
    slides = (
        db.query(GeneratedSlide)
        .options(selectinload(GeneratedSlide.code_versions))
        .filter(GeneratedSlide.deck_id == deck_id)
        .all()
    )
    llm_artifacts = (
        db.query(DeckLlmArtifact)
        .filter(DeckLlmArtifact.deck_id == deck_id)
        .order_by(DeckLlmArtifact.created_at.desc())
        .all()
    )

    saved_versions = [version for version in versions if version.is_active or version.status in {"applied", "saved", "restored"}]
    protected_design_version_ids = {version.id for version in saved_versions[:saved_limit]}
    if deck and deck.current_design_version_id:
        protected_design_version_ids.add(deck.current_design_version_id)
    if workspace and workspace.active_design_version_id:
        protected_design_version_ids.add(workspace.active_design_version_id)
    protected_design_version_ids.update(version.id for version in versions if version.is_active)

    protected_code_version_ids: set[str] = set()
    latest_unused_code_version_ids: set[str] = set()
    latest_unused_design_version_ids: set[str] = set()
    for slide in slides:
        unused_versions = [
            code_version
            for code_version in sorted(slide.code_versions, key=lambda item: item.created_at, reverse=True)
            if _code_version_lifecycle(code_version) == "unused"
        ]
        for code_version in unused_versions[:unused_limit_per_slide]:
            latest_unused_code_version_ids.add(code_version.id)
            latest_unused_design_version_ids.add(slide.design_version_id)

    protected_design_version_ids.update(latest_unused_design_version_ids)

    for version in versions:
        if version.id not in protected_design_version_ids:
            continue
        for slide in version.generated_slides:
            protected_code_version_ids.update(code_version.id for code_version in slide.code_versions)

    protected_code_version_ids.update(slide.current_version_id for slide in slides if slide.current_version_id)
    protected_code_version_ids.update(latest_unused_code_version_ids)

    for version in versions:
        if version.id in protected_design_version_ids or version.status in {"archived", "discarded"}:
            continue
        archived_manifest_key = _archive_design_version_manifest(version)
        version.status = "archived"
        version.is_active = False
        version.discarded_at = version.discarded_at or datetime.utcnow()
        if archived_manifest_key:
            version.bucket_manifest_key = archived_manifest_key

    for slide in slides:
        unused_versions = [
            code_version
            for code_version in sorted(slide.code_versions, key=lambda item: item.created_at, reverse=True)
            if _code_version_lifecycle(code_version) == "unused"
        ]
        protected_for_slide = set(protected_code_version_ids)
        protected_for_slide.update(code_version.id for code_version in unused_versions[:unused_limit_per_slide])

        for code_version in slide.code_versions:
            if code_version.id in protected_for_slide or _code_version_lifecycle(code_version) == "archived":
                continue
            if _code_version_lifecycle(code_version) != "unused":
                continue
            archived = _archive_code_version_artifacts(code_version)
            code_json = code_version.code_json if isinstance(code_version.code_json, dict) else {}
            code_version.code_json = {
                **code_json,
                "lifecycle": "archived",
                "retentionState": "archived",
                "archivedArtifactKeys": archived,
                "archivedAt": datetime.utcnow().isoformat() + "Z",
            }

    for artifact in llm_artifacts[llm_artifact_limit:]:
        retired = _retire_llm_artifact(artifact)
        artifact.status = "archived"
        artifact.bucket_payload_key = None
        artifact.metrics_json = {
            **(artifact.metrics_json or {}),
            "retentionState": "archived",
            "archivedAt": datetime.utcnow().isoformat() + "Z",
            **(retired or {}),
        }
