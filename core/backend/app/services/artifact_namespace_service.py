from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from re import sub
from typing import Iterable

from app.core.config import settings


class ArtifactProductArea(StrEnum):
    SOURCE = "source"
    SMART_DECK = "smart-deck"
    SMART_EDIT = "smart-edit"
    DUE_DILIGENCE = "due-diligence"
    EXPORTS = "exports"


class ArtifactKind(StrEnum):
    ORIGINAL = "original"
    STRUCTURE = "structure"
    SLIDE_PREVIEW = "slide-preview"
    ASSET = "asset"
    WORKFLOW = "workflow"
    DESIGN_VERSION = "design-version"
    GENERATED_SLIDE = "generated-slide"
    RENDER_SCHEMA = "render-schema"
    THUMBNAIL = "thumbnail"
    EDIT_SESSION = "edit-session"
    ELEMENT_VERSION = "element-version"
    DIFF = "diff"
    RESEARCH = "research"
    EVIDENCE = "evidence"
    CITATION = "citation"
    REPORT = "report"
    EXPORT = "export"
    MANIFEST = "manifest"


_ALLOWED_SUFFIXES = {
    ".json",
    ".jsonl",
    ".txt",
    ".md",
    ".pdf",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".csv",
    ".parquet",
    ".html",
}


@dataclass(frozen=True)
class ArtifactNamespace:
    bucket_name: str
    key: str
    product_area: ArtifactProductArea
    artifact_kind: ArtifactKind

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket_name}/{self.key}" if self.bucket_name else self.key


def _slug(value: str, *, fallback: str) -> str:
    normalized = sub(r"[^A-Za-z0-9_.=-]+", "-", (value or "").strip()).strip("-._")
    return normalized or fallback


def _safe_suffix(filename: str | None, default_suffix: str) -> str:
    suffix = PurePosixPath(filename or "").suffix.lower() or default_suffix
    return suffix if suffix in _ALLOWED_SUFFIXES else default_suffix


def _join_key(parts: Iterable[str]) -> str:
    return "/".join(part.strip("/") for part in parts if part and part.strip("/"))


def artifact_bucket_name() -> str:
    return settings.upload_storage_s3_bucket or settings.supabase_storage_bucket


def artifact_root_prefix() -> str:
    return _join_key([settings.upload_storage_s3_prefix or "deck-aistack-codes/artifacts"])


def build_artifact_key(
    *,
    user_id: str,
    deck_id: str,
    product_area: ArtifactProductArea,
    artifact_kind: ArtifactKind,
    filename: str | None = None,
    workflow_id: str | None = None,
    design_version_id: str | None = None,
    generated_slide_id: str | None = None,
    smart_edit_session_id: str | None = None,
    due_diligence_run_id: str | None = None,
    export_id: str | None = None,
    slide_number: int | None = None,
    suffix: str = ".json",
) -> ArtifactNamespace:
    user = _slug(user_id, fallback="anonymous-user")
    deck = _slug(deck_id, fallback="unknown-deck")
    safe_filename = _slug(filename or artifact_kind.value, fallback=artifact_kind.value)
    extension = _safe_suffix(filename, suffix)
    common = [artifact_root_prefix(), "users", user, "decks", deck]

    if product_area == ArtifactProductArea.SOURCE:
        area_parts = [product_area.value]
        if artifact_kind == ArtifactKind.ORIGINAL:
            area_parts += ["original", safe_filename]
        elif artifact_kind == ArtifactKind.SLIDE_PREVIEW:
            area_parts += ["slides", str(slide_number or 0).zfill(3), f"preview{extension}"]
        elif artifact_kind == ArtifactKind.ASSET:
            area_parts += ["assets", safe_filename]
        else:
            area_parts += [artifact_kind.value, safe_filename]
    elif product_area == ArtifactProductArea.SMART_DECK:
        area_parts = [product_area.value]
        if workflow_id:
            area_parts += ["workflows", _slug(workflow_id, fallback="workflow")]
        if design_version_id:
            area_parts += ["design-versions", _slug(design_version_id, fallback="version")]
        if generated_slide_id:
            area_parts += ["generated-slides", _slug(generated_slide_id, fallback="slide")]
        area_parts += [artifact_kind.value, safe_filename]
    elif product_area == ArtifactProductArea.SMART_EDIT:
        area_parts = [product_area.value]
        if smart_edit_session_id:
            area_parts += ["edit-sessions", _slug(smart_edit_session_id, fallback="session")]
        if generated_slide_id:
            area_parts += ["generated-slides", _slug(generated_slide_id, fallback="slide")]
        area_parts += [artifact_kind.value, safe_filename]
    elif product_area == ArtifactProductArea.DUE_DILIGENCE:
        area_parts = [product_area.value]
        if due_diligence_run_id:
            area_parts += ["runs", _slug(due_diligence_run_id, fallback="run")]
        area_parts += [artifact_kind.value, safe_filename]
    elif product_area == ArtifactProductArea.EXPORTS:
        area_parts = [product_area.value]
        if export_id:
            area_parts += [_slug(export_id, fallback="export")]
        area_parts += [artifact_kind.value, safe_filename]
    else:
        area_parts = [product_area.value, artifact_kind.value, safe_filename]

    return ArtifactNamespace(
        bucket_name=artifact_bucket_name(),
        key=_join_key([*common, *area_parts]),
        product_area=product_area,
        artifact_kind=artifact_kind,
    )


def smart_deck_render_schema_key(
    *,
    user_id: str,
    deck_id: str,
    workflow_id: str,
    design_version_id: str,
    generated_slide_id: str,
) -> ArtifactNamespace:
    return build_artifact_key(
        user_id=user_id,
        deck_id=deck_id,
        product_area=ArtifactProductArea.SMART_DECK,
        artifact_kind=ArtifactKind.RENDER_SCHEMA,
        workflow_id=workflow_id,
        design_version_id=design_version_id,
        generated_slide_id=generated_slide_id,
        filename="render_schema.json",
    )


def smart_edit_diff_key(
    *,
    user_id: str,
    deck_id: str,
    smart_edit_session_id: str,
    generated_slide_id: str,
) -> ArtifactNamespace:
    return build_artifact_key(
        user_id=user_id,
        deck_id=deck_id,
        product_area=ArtifactProductArea.SMART_EDIT,
        artifact_kind=ArtifactKind.DIFF,
        smart_edit_session_id=smart_edit_session_id,
        generated_slide_id=generated_slide_id,
        filename="diff.json",
    )


def due_diligence_evidence_key(
    *,
    user_id: str,
    deck_id: str,
    due_diligence_run_id: str,
    filename: str = "evidence.json",
) -> ArtifactNamespace:
    return build_artifact_key(
        user_id=user_id,
        deck_id=deck_id,
        product_area=ArtifactProductArea.DUE_DILIGENCE,
        artifact_kind=ArtifactKind.EVIDENCE,
        due_diligence_run_id=due_diligence_run_id,
        filename=filename,
    )
