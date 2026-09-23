from __future__ import annotations

import base64
import binascii
import copy
from dataclasses import dataclass
import hashlib
import html
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import (
    AnalysisFinding,
    CompiledDeck,
    Deck,
    DeckExport,
    DeckMediaAsset,
    DeckSlide,
    DesignBatch,
    DesignVersion,
    InstantDeckHtmlArtifact,
)
from app.schemas.smart_deck import RenderSchema
from app.services.brand.brand_design_tokens import DEFAULT_DESIGN_TOKENS
from app.services.storage.artifact_storage import get_upload_storage


HTML_EXPORT_FORMAT = "html"
FINAL_DECK_EXPORT_TYPE = "final_deck"
PROVISIONAL_HTML_EXPORT_TYPE = "provisional_html"
_MAX_INLINE_ASSET_BYTES = 10 * 1024 * 1024
_MAX_TOTAL_DECODED_ASSET_BYTES = 18 * 1024 * 1024
_MAX_TOTAL_ENCODED_ASSET_BYTES = 24 * 1024 * 1024
_MAX_HTML_EXPORT_BYTES = 25 * 1024 * 1024
_HTML_EXPORT_SIGNATURE = "deck-aistack-html-export.v1"
_COMPILED_HTML_EXPORT_VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
_COMPILED_HTML_EXPORT_DOCUMENT_RESET = (
    '<style id="deck-aistack-export-document-reset">'
    'html,body{margin:0;padding:0}'
    '@media print{.deck-section{box-sizing:border-box!important;'
    'width:1920px!important;height:1080px!important;min-height:1080px!important;'
    'max-height:1080px!important;overflow:hidden!important;'
    'page-break-after:auto!important;break-after:auto!important}}'
    '@media(max-width:640px){'
    '[data-da-slide-root] .grid-3,[data-da-slide-root].grid-3{grid-template-columns:1fr!important}'
    '[data-da-slide-root] .card,[data-da-slide-root].card{min-width:0!important;overflow-wrap:anywhere!important}'
    '}'
    '</style>'
)
_STRUCTURED_METADATA_PATTERN = re.compile(
    r'\A<!doctype html>\n<!-- deck-aistack-html-export\.v1 -->[\s\S]{0,3500}?'
    r'<meta name="deck-export-metadata" content="([A-Za-z0-9_-]+)">'
)
_LEGACY_METADATA_PATTERN = re.compile(
    r'\A<!doctype html>\n<html lang="en">\n<head>\n'
    r'  <meta charset="utf-8">\n'
    r'  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
    r'  <meta http-equiv="Content-Security-Policy" content="[^"]+">\n'
    r'  <meta name="design-version-id" content="([A-Za-z0-9._-]{1,120})">\n'
    r'  <meta name="deck-export-format" content="(html)">\n'
)
_MEDIA_ASSET_PATH_PATTERN = re.compile(
    r"^/api/products/deck-aistack-codes/decks/([^/]+)/media/([^/]+)/(?:content|thumbnail)$"
)


def _canonical_download_url(deck_id: str, export_id: str) -> str:
    return f"/api/products/deck-aistack-codes/decks/{deck_id}/exports/{export_id}/download"


def _detail_url(deck_id: str, export_id: str) -> str:
    return f"/api/decks/{deck_id}/exports/{export_id}"


def _metadata_from_content(deck_export: DeckExport) -> tuple[str | None, str | None]:
    return _metadata_from_values(deck_export.type, deck_export.deck_id, deck_export.content)


def _structured_metadata(content_prefix: str) -> dict[str, Any] | None:
    structured_match = _STRUCTURED_METADATA_PATTERN.match(content_prefix)
    if not structured_match:
        return None
    try:
        encoded = structured_match.group(1)
        padded = encoded + ("=" * (-len(encoded) % 4))
        metadata = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
        return None
    return metadata if isinstance(metadata, dict) else None


def _metadata_from_values(export_type: str, deck_id: str, content_prefix: str) -> tuple[str | None, str | None]:
    if export_type not in {FINAL_DECK_EXPORT_TYPE, PROVISIONAL_HTML_EXPORT_TYPE}:
        return None, None
    metadata = _structured_metadata(content_prefix)
    if metadata is not None:
        required_keys = {"deckId", "designVersionId", "exportType", "format", "signature"}
        allowed_keys = required_keys | {"classification", "versionStatus", "artifactHash"}
        if not required_keys <= set(metadata) or not set(metadata) <= allowed_keys:
            return None, None
        design_version_id = metadata.get("designVersionId")
        if (
            metadata.get("signature") != _HTML_EXPORT_SIGNATURE
            or metadata.get("deckId") != deck_id
            or metadata.get("exportType") != export_type
            or metadata.get("format") != HTML_EXPORT_FORMAT
            or not isinstance(design_version_id, str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", design_version_id)
        ):
            return None, None
        return design_version_id, HTML_EXPORT_FORMAT

    legacy_match = _LEGACY_METADATA_PATTERN.match(content_prefix) if export_type == FINAL_DECK_EXPORT_TYPE else None
    if legacy_match:
        return html.unescape(legacy_match.group(1)), legacy_match.group(2)
    return None, None


def _map_export(deck_export: DeckExport, *, include_content: bool = True) -> dict[str, Any]:
    design_version_id, export_format = _metadata_from_content(deck_export)
    mapped: dict[str, Any] = {
        "id": deck_export.id,
        "deck_id": deck_export.deck_id,
        "deckId": deck_export.deck_id,
        "type": deck_export.type,
        "created_at": deck_export.created_at.isoformat() if deck_export.created_at else "",
        "createdAt": deck_export.created_at.isoformat() if deck_export.created_at else "",
        "download_url": _canonical_download_url(deck_export.deck_id, deck_export.id),
        "downloadUrl": _canonical_download_url(deck_export.deck_id, deck_export.id),
        "detailUrl": _detail_url(deck_export.deck_id, deck_export.id),
    }
    if design_version_id is not None:
        mapped["designVersionId"] = design_version_id
    if export_format is not None:
        mapped["format"] = export_format
        metadata = _structured_metadata(deck_export.content)
        if metadata is not None:
            mapped["classification"] = metadata.get("classification")
            mapped["versionStatus"] = metadata.get("versionStatus")
            mapped["artifactHash"] = hashlib.sha256(deck_export.content.encode("utf-8")).hexdigest()
    if include_content:
        mapped["content"] = deck_export.content
    return mapped


def _export_file_contract(
    deck_id: str,
    export_id: str,
    export_type: str,
    *,
    export_format: str | None = None,
    design_version_id: str | None = None,
) -> tuple[str, str, str]:
    if export_type in {FINAL_DECK_EXPORT_TYPE, PROVISIONAL_HTML_EXPORT_TYPE} and export_format == HTML_EXPORT_FORMAT:
        media_type = "text/html; charset=utf-8"
        extension = "html"
    elif export_type == FINAL_DECK_EXPORT_TYPE:
        media_type = "application/json"
        extension = "json"
    else:
        media_type = "text/plain; charset=utf-8"
        extension = "txt"
    safe_deck_id = re.sub(r"[^A-Za-z0-9._-]+", "-", deck_id).strip("-") or "deck"
    safe_export_id = re.sub(r"[^A-Za-z0-9._-]+", "-", export_id).strip("-") or "export"
    safe_version_id = re.sub(r"[^A-Za-z0-9._-]+", "-", design_version_id or "").strip("-")
    version_segment = f"-{safe_version_id}" if safe_version_id else ""
    filename = f"deck-aistack-codes-{safe_deck_id}{version_segment}-{export_type}-{safe_export_id}.{extension}"
    return media_type, extension, filename


def _admin_release_directory(deck_export: DeckExport) -> Path:
    handoff_root = Path(settings.admin_export_handoff_dir).expanduser().resolve()
    return handoff_root / deck_export.deck_id / deck_export.id


def _admin_release_package_values(deck_export: DeckExport) -> tuple[str, str]:
    design_version_id, export_format = _metadata_from_content(deck_export)
    authenticated_download_ready = export_format == HTML_EXPORT_FORMAT and design_version_id is not None
    _media_type, _extension, filename = _export_file_contract(
        deck_export.deck_id,
        deck_export.id,
        deck_export.type,
        export_format=export_format,
        design_version_id=design_version_id,
    )
    metadata = json.dumps({
        "deckId": deck_export.deck_id,
        "exportId": deck_export.id,
        "exportType": deck_export.type,
        "createdAt": deck_export.created_at.isoformat() if deck_export.created_at else None,
        "releaseStatus": "authenticated_download_ready" if authenticated_download_ready else "admin_review_required",
        "contentFilename": filename,
        "designVersionId": design_version_id,
        "format": export_format,
        "downloadPath": _canonical_download_url(deck_export.deck_id, deck_export.id),
        "message": (
            "Export is ready for authenticated owner download; an admin handoff copy was also generated."
            if authenticated_download_ready
            else "Export generated and queued for admin release."
        ),
    }, indent=2, sort_keys=True)
    return filename, metadata


def _admin_release_package_matches(deck_export: DeckExport, export_dir: Path) -> bool:
    filename, metadata = _admin_release_package_values(deck_export)
    expected_names = {filename, "release-request.json"}
    try:
        if not export_dir.is_dir() or {path.name for path in export_dir.iterdir()} != expected_names:
            return False
        return (
            (export_dir / filename).read_text(encoding="utf-8") == deck_export.content
            and (export_dir / "release-request.json").read_text(encoding="utf-8") == metadata
        )
    except OSError:
        return False


def _write_admin_release_package(deck_export: DeckExport) -> bool:
    export_dir = _admin_release_directory(deck_export)
    if export_dir.exists():
        if _admin_release_package_matches(deck_export, export_dir):
            return False
        shutil.rmtree(export_dir, ignore_errors=True)
        if export_dir.exists():
            raise OSError("Stale admin handoff directory could not be removed before retry.")

    parent = export_dir.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent.chmod(0o700)
    for stale_staging_dir in parent.glob(f".{deck_export.id}.staging-*"):
        if stale_staging_dir.is_dir():
            shutil.rmtree(stale_staging_dir, ignore_errors=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{deck_export.id}.staging-", dir=parent))
    staging_dir.chmod(0o700)
    filename, metadata = _admin_release_package_values(deck_export)
    published = False
    try:
        for target, value in ((staging_dir / filename, deck_export.content), (staging_dir / "release-request.json", metadata)):
            with target.open("x", encoding="utf-8") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
        directory_descriptor = os.open(staging_dir, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        os.replace(staging_dir, export_dir)
        published = True
        parent_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
        return True
    except Exception:
        if published:
            shutil.rmtree(export_dir, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def publish_export_handoff(db: Session, export_id: str) -> bool:
    deck_export = (
        db.query(DeckExport)
        .filter(DeckExport.id == export_id)
        .with_for_update(skip_locked=True)
        .one_or_none()
    )
    if deck_export is None:
        return False
    if deck_export.handoff_status == "ready":
        return True
    export_dir = _admin_release_directory(deck_export)
    deck_export.handoff_attempts = int(deck_export.handoff_attempts or 0) + 1
    deck_export.handoff_attempted_at = datetime.utcnow()
    published_now = False
    try:
        published_now = _write_admin_release_package(deck_export)
        deck_export.handoff_status = "ready"
        deck_export.handoff_error = None
        deck_export.handoff_ready_at = datetime.utcnow()
    except Exception as exc:
        design_version_id, export_format = _metadata_from_content(deck_export)
        authenticated_download_ready = (
            deck_export.type in {FINAL_DECK_EXPORT_TYPE, PROVISIONAL_HTML_EXPORT_TYPE}
            and export_format == HTML_EXPORT_FORMAT
            and bool(design_version_id)
            and deck_export.content.lower().startswith("<!doctype html>")
        )
        # The database artifact is the canonical authenticated handoff.  The
        # filesystem admin package is an operational mirror; its failure must
        # remain visible without leaving a valid customer download "pending".
        deck_export.handoff_status = "ready" if authenticated_download_ready else "pending"
        deck_export.handoff_error = (
            "Optional admin release mirror failed; authenticated export remains ready. "
            + str(exc)
        )[:2000] if authenticated_download_ready else str(exc)[:2000]
        deck_export.handoff_ready_at = datetime.utcnow() if authenticated_download_ready else None
    try:
        db.commit()
    except Exception:
        db.rollback()
        if published_now:
            shutil.rmtree(export_dir, ignore_errors=True)
        return False
    return deck_export.handoff_status == "ready"


def reconcile_pending_export_handoffs(db: Session, *, limit: int = 10) -> dict[str, int]:
    bounded_limit = max(1, min(int(limit), 100))
    export_ids = [
        row[0]
        for row in (
            db.query(DeckExport.id)
            .filter(DeckExport.handoff_status == "pending")
            .order_by(DeckExport.created_at.asc(), DeckExport.id.asc())
            .limit(bounded_limit)
            .all()
        )
    ]
    ready = sum(1 for export_id in export_ids if publish_export_handoff(db, export_id))
    return {"processed": len(export_ids), "ready": ready, "pending": len(export_ids) - ready}


def _latest_compiled_deck(db: Session, deck_id: str) -> CompiledDeck | None:
    return (
        db.query(CompiledDeck)
        .filter(CompiledDeck.source_deck_id == deck_id, CompiledDeck.status == "ready")
        .order_by(CompiledDeck.finalized_at.desc())
        .first()
    )


def _build_compiled_deck_export_content(compiled_deck: CompiledDeck, export_type: str) -> str:
    manifest = compiled_deck.manifest_json or {}
    slides = manifest.get("slides", [])
    if export_type == "adapted_outline" and isinstance(slides, list):
        return "\n".join(
            (
                f"{slide.get('slideIndex', index)}. "
                f"{slide.get('title', 'Untitled slide')} "
                f"({slide.get('choice', 'original')})"
            )
            for index, slide in enumerate(slides, start=1)
            if isinstance(slide, dict)
        )

    return json.dumps(
        {
            "exportType": export_type,
            "deckId": compiled_deck.source_deck_id,
            "compiledDeckId": compiled_deck.id,
            "title": compiled_deck.title,
            "status": compiled_deck.status,
            "finalizedAt": compiled_deck.finalized_at.isoformat() if compiled_deck.finalized_at else None,
            "manifest": manifest,
        },
        sort_keys=True,
    )


def _build_legacy_export_content(db: Session, deck_id: str, export_type: str) -> str:
    slides = (
        db.query(DeckSlide)
        .filter(DeckSlide.deck_id == deck_id)
        .order_by(DeckSlide.slide_index.asc())
        .all()
    )
    findings = (
        db.query(AnalysisFinding)
        .filter(AnalysisFinding.deck_id == deck_id)
        .order_by(AnalysisFinding.severity.desc(), AnalysisFinding.title.asc())
        .all()
    )

    if export_type == "adapted_outline":
        return "\n".join(f"{slide.slide_index}. {slide.title} ({slide.role})" for slide in slides)

    return "\n".join(f"- {finding.title}: {finding.detail}" for finding in findings)


def _build_export_content(db: Session, deck_id: str, export_type: str) -> str:
    if export_type != "findings":
        compiled_deck = _latest_compiled_deck(db, deck_id)
        if compiled_deck is not None:
            return _build_compiled_deck_export_content(compiled_deck, export_type)

    return _build_legacy_export_content(db, deck_id, export_type)


@dataclass(frozen=True)
class _AcceptedExportSlide:
    id: str
    source_slide_id: str
    slide_number: int
    title: str
    render_schema: dict[str, Any]
    design_tokens: dict[str, Any]
    assets: dict[str, dict[str, Any]]


def _validated_export_slides(
    accepted_slides: list[_AcceptedExportSlide],
) -> list[_AcceptedExportSlide]:
    if not accepted_slides:
        raise ValueError("Accepted design version has no generated slides to export.")
    if len({slide.slide_number for slide in accepted_slides}) != len(accepted_slides):
        raise ValueError("Accepted design version has duplicate generated slide numbers.")

    accepted_source_ids = [slide.source_slide_id for slide in accepted_slides]
    if len(set(accepted_source_ids)) != len(accepted_source_ids):
        raise ValueError("Accepted deck history contains duplicate source slide identities.")
    if len({slide.id for slide in accepted_slides}) != len(accepted_slides):
        raise ValueError("Accepted deck history contains duplicate generated slide identities.")
    return accepted_slides


def _accepted_history(db: Session, deck_id: str, design_version_id: str) -> DesignBatch | None:
    return (
        db.query(DesignBatch)
        .options(selectinload(DesignBatch.selected_slides))
        .filter(
            DesignBatch.deck_id == deck_id,
            DesignBatch.source_design_version_id == design_version_id,
            DesignBatch.status == "saved",
            DesignBatch.accepted_at.is_not(None),
        )
        .order_by(DesignBatch.accepted_at.desc(), DesignBatch.created_at.desc())
        .first()
    )


def _accepted_snapshot_slides(history: DesignBatch, design_version_id: str) -> list[_AcceptedExportSlide]:
    snapshot = history.snapshot_json if isinstance(history.snapshot_json, dict) else {}
    snapshot_slides = snapshot.get("slides") if isinstance(snapshot.get("slides"), list) else []
    if snapshot.get("schemaVersion") != "deck-version-snapshot.v1" or snapshot.get("designVersionId") != design_version_id:
        raise ValueError("Accepted deck history is missing an immutable design-version snapshot.")

    accepted_slides: list[_AcceptedExportSlide] = []
    for position, source_snapshot in enumerate(snapshot_slides, start=1):
        if not isinstance(source_snapshot, dict) or not isinstance(source_snapshot.get("generatedSlide"), dict):
            raise ValueError("Accepted deck history is missing immutable generated slide content.")
        generated_snapshot = source_snapshot["generatedSlide"]
        source_slide_id = str(source_snapshot.get("slideId") or "").strip()
        generated_slide_id = str(generated_snapshot.get("generatedSlideId") or "").strip()
        render_schema = generated_snapshot.get("renderSchema")
        design_tokens = generated_snapshot.get("designTokens")
        if not source_slide_id or not generated_slide_id or not isinstance(render_schema, dict):
            raise ValueError("Accepted deck history is missing an immutable render schema.")
        if design_tokens is None:
            design_tokens = {}
        elif not isinstance(design_tokens, dict):
            raise ValueError("Accepted deck history contains invalid immutable design tokens.")
        try:
            validated_schema = RenderSchema.model_validate(render_schema).model_dump(mode="json")
        except Exception as exc:
            raise ValueError("Accepted deck history contains a non-renderable generated slide schema.") from exc
        export_metadata = validated_schema.get("exportMetadata") or {}
        if export_metadata.get("exportReady") is not True or export_metadata.get("renderer") != "smart_deck_scene_graph":
            raise ValueError("Accepted deck history contains a generated slide that is not export-ready.")
        referenced_tokens = set(validated_schema.get("brandTokensUsed") or [])
        missing_tokens = sorted(
            token for token in referenced_tokens if token not in {**DEFAULT_DESIGN_TOKENS, **design_tokens}
        )
        if missing_tokens:
            raise ValueError("Accepted deck history is missing required immutable design tokens.")
        asset_urls = set(_schema_asset_urls(validated_schema))
        raw_assets = generated_snapshot.get("assets")
        if raw_assets is None:
            if asset_urls:
                raise ValueError("Accepted deck history is missing immutable asset integrity metadata.")
            raw_assets = []
        if not isinstance(raw_assets, list):
            raise ValueError("Accepted deck history contains invalid asset integrity metadata.")
        assets: dict[str, dict[str, Any]] = {}
        for raw_asset in raw_assets:
            if not isinstance(raw_asset, dict):
                raise ValueError("Accepted deck history contains invalid asset integrity metadata.")
            asset_url = str(raw_asset.get("assetUrl") or "").strip()
            digest = str(raw_asset.get("sha256") or "").strip().lower()
            size = raw_asset.get("size")
            mime_type = str(raw_asset.get("mimeType") or "").strip().lower()
            if (
                not asset_url
                or asset_url in assets
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or not isinstance(size, int)
                or size <= 0
                or not mime_type.startswith("image/")
            ):
                raise ValueError("Accepted deck history contains invalid asset integrity metadata.")
            assets[asset_url] = {
                "assetUrl": asset_url,
                "sha256": digest,
                "size": size,
                "mimeType": mime_type,
            }
        if set(assets) != asset_urls:
            raise ValueError("Accepted deck history asset integrity metadata does not match its render schema.")
        slide_index = source_snapshot.get("slideIndex")
        slide_number = int(slide_index) + 1 if isinstance(slide_index, int) and slide_index >= 0 else position
        accepted_slides.append(
            _AcceptedExportSlide(
                id=generated_slide_id,
                source_slide_id=source_slide_id,
                slide_number=slide_number,
                title=str(generated_snapshot.get("title") or source_snapshot.get("title") or f"Slide {slide_number}"),
                render_schema=validated_schema,
                design_tokens=copy.deepcopy(design_tokens),
                assets=assets,
            )
        )
    return accepted_slides


def _validated_accepted_export_slides(
    db: Session,
    version: DesignVersion,
) -> list[_AcceptedExportSlide]:
    history = _accepted_history(db, version.deck_id, version.id)
    if history is None:
        raise ValueError("Design version has no accepted deck-history lineage.")
    return _validated_export_slides(_accepted_snapshot_slides(history, version.id))


def resolve_accepted_export_design_version(
    db: Session,
    deck: Deck,
    design_version_id: str,
    *,
    validate_assets: bool = False,
) -> DesignVersion:
    version = (
        db.query(DesignVersion)
        .filter(DesignVersion.deck_id == deck.id, DesignVersion.id == design_version_id)
        .one_or_none()
    )
    if version is None:
        raise ValueError("Design version not found for this deck.")
    history = _accepted_history(db, deck.id, version.id)
    if version.status == "discarded" or version.applied_at is None or history is None:
        raise ValueError("Design version has no accepted deck-history lineage.")
    validated = _validated_export_slides(_accepted_snapshot_slides(history, version.id))
    if validate_assets:
        _validate_render_assets(db, deck.id, validated)
    return version


def _compiled_html_export_artifact(
    db: Session,
    version: DesignVersion,
    *,
    read_content: bool,
) -> tuple[InstantDeckHtmlArtifact, str | None]:
    from app.services.rendering.render_proof_service import require_complete_render_proofs, read_encrypted_render_document
    from app.services.rendering.schema_validation import validate_design_version_slides

    if version.status == "discarded" or version.discarded_at is not None:
        raise ValueError("Compiled HTML design version has been discarded.")
    if version.render_mode != "html_compiled.v1" or version.artifact_type != "full_html_deck.v1":
        raise ValueError("Design version is not a compiled Instant HTML artifact.")
    validate_design_version_slides(db, version.deck_id, version.id)
    compilation = require_complete_render_proofs(version, db)
    if compilation.status != "compiled":
        raise ValueError("Compiled HTML design version is not ready for export.")
    artifact = (
        db.query(InstantDeckHtmlArtifact)
        .filter(
            InstantDeckHtmlArtifact.id == compilation.sanitized_html_artifact_id,
            InstantDeckHtmlArtifact.deck_id == version.deck_id,
            InstantDeckHtmlArtifact.design_version_id == version.id,
            InstantDeckHtmlArtifact.artifact_kind == "sanitized",
            InstantDeckHtmlArtifact.quarantined.is_(False),
            InstantDeckHtmlArtifact.encrypted.is_(True),
        )
        .one_or_none()
    )
    if artifact is None:
        raise ValueError("Sanitized compiled HTML artifact is unavailable for export.")
    if (
        artifact.encryption_purpose != "instant-html-sanitized-deck"
        or not artifact.encryption_key_version
        or artifact.encryption_key_version != settings.instant_html_render_key_version
    ):
        raise ValueError("Sanitized compiled HTML artifact encryption identity is invalid.")
    manifest_hash = str((compilation.manifest_json or {}).get("contentHash") or "")
    manifest_compilation_hash = str((compilation.manifest_json or {}).get("compilationHash") or "")
    if (
        manifest_hash != artifact.content_hash
        or manifest_compilation_hash != compilation.content_hash
        or artifact.byte_size <= 0
        or artifact.byte_size > min(_MAX_HTML_EXPORT_BYTES, settings.instant_html_whole_deck_max_bytes)
    ):
        raise ValueError("Sanitized compiled HTML artifact identity or size is invalid.")
    if not read_content:
        return artifact, None
    content = read_encrypted_render_document(artifact.storage_key, artifact.content_hash)
    if len(content.encode("utf-8")) != artifact.byte_size:
        raise ValueError("Sanitized compiled HTML artifact size changed before export.")
    return artifact, content


def resolve_html_export_design_version(
    db: Session,
    deck: Deck,
    design_version_id: str,
    *,
    export_type: str = FINAL_DECK_EXPORT_TYPE,
    validate_assets: bool = False,
) -> DesignVersion:
    version = db.query(DesignVersion).filter(DesignVersion.deck_id == deck.id, DesignVersion.id == design_version_id).one_or_none()
    if version is None:
        raise ValueError("Design version not found for this deck.")
    if export_type == PROVISIONAL_HTML_EXPORT_TYPE:
        if version.render_mode != "html_compiled.v1":
            raise ValueError("provisional_html export requires a compiled Instant HTML design version.")
        if version.status == "discarded" or version.discarded_at is not None or version.applied_at is not None or _accepted_history(db, deck.id, version.id) is not None:
            raise ValueError("provisional_html export requires a non-discarded, unaccepted provisional design version.")
        _compiled_html_export_artifact(db, version, read_content=validate_assets)
        return version
    if export_type != FINAL_DECK_EXPORT_TYPE:
        raise ValueError("Unsupported HTML export classification.")
    if version.render_mode != "html_compiled.v1":
        return resolve_accepted_export_design_version(db, deck, design_version_id, validate_assets=validate_assets)
    history = _accepted_history(db, deck.id, version.id)
    if version.status == "discarded" or version.discarded_at is not None or version.applied_at is None or history is None:
        raise ValueError("Design version has no accepted deck-history lineage.")
    _compiled_html_export_artifact(db, version, read_content=validate_assets)
    return version


def _build_compiled_html_export(db: Session, deck: Deck, version: DesignVersion, *, export_type: str) -> str:
    artifact, sanitized_html = _compiled_html_export_artifact(db, version, read_content=True)
    if sanitized_html is None:
        raise ValueError("Sanitized compiled HTML artifact is unavailable for export.")
    metadata = {
        "deckId": deck.id,
        "designVersionId": version.id,
        "exportType": export_type,
        "format": HTML_EXPORT_FORMAT,
        "signature": _HTML_EXPORT_SIGNATURE,
        "classification": "provisional" if export_type == PROVISIONAL_HTML_EXPORT_TYPE else "final",
        "versionStatus": version.status,
        "artifactHash": artifact.content_hash,
    }
    encoded_metadata = base64.urlsafe_b64encode(_json_for_html_script(metadata).encode("utf-8")).decode("ascii").rstrip("=")
    if not sanitized_html.lower().startswith("<!doctype html>"):
        raise ValueError("Sanitized compiled HTML artifact is not a complete HTML document.")
    marked = sanitized_html.replace("<!doctype html>", f"<!doctype html>\n<!-- {_HTML_EXPORT_SIGNATURE} -->", 1)
    content, count = re.subn(
        r"(<head(?:\s[^>]*)?>)",
        rf"\1\n{_COMPILED_HTML_EXPORT_VIEWPORT}"
        rf'\n<meta name="deck-export-metadata" content="{encoded_metadata}">'
        f"\n{_COMPILED_HTML_EXPORT_DOCUMENT_RESET}",
        marked,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise ValueError("Sanitized compiled HTML artifact is missing its document head.")
    if len(content.encode("utf-8")) > _MAX_HTML_EXPORT_BYTES:
        raise ValueError("Compiled HTML design version is too large to export.")
    return content


def _asset_storage_path(db: Session, deck_id: str, asset_url: str) -> tuple[str, str | None]:
    if asset_url.startswith("/uploads/"):
        storage_path = asset_url.removeprefix("/uploads/")
        return _owned_raw_storage_path(db, deck_id, storage_path)
    if asset_url.startswith("/api/uploads/local/"):
        storage_path = asset_url.removeprefix("/api/uploads/local/")
        return _owned_raw_storage_path(db, deck_id, storage_path)
    media_match = _MEDIA_ASSET_PATH_PATTERN.fullmatch(asset_url)
    if media_match:
        asset_deck_id, media_id = media_match.groups()
        if asset_deck_id != deck_id:
            raise ValueError("Accepted design version references media from another deck.")
        media = (
            db.query(DeckMediaAsset)
            .filter(DeckMediaAsset.deck_id == deck_id, DeckMediaAsset.id == media_id, DeckMediaAsset.status == "ready")
            .one_or_none()
        )
        if media is None:
            raise ValueError("Accepted design version references unavailable media.")
        return media.storage_path, media.mime_type
    raise ValueError("Accepted design version contains an asset that cannot be embedded.")


def _owned_raw_storage_path(db: Session, deck_id: str, storage_path: str) -> tuple[str, str | None]:
    relative_path = PurePosixPath(storage_path)
    if relative_path.is_absolute() or not relative_path.parts or ".." in relative_path.parts:
        raise ValueError("Accepted design version contains an invalid raw asset path.")
    normalized_path = relative_path.as_posix()

    owned_media = (
        db.query(DeckMediaAsset)
        .filter(
            DeckMediaAsset.deck_id == deck_id,
            DeckMediaAsset.storage_path == normalized_path,
            DeckMediaAsset.status == "ready",
        )
        .one_or_none()
    )
    if owned_media is not None:
        return normalized_path, owned_media.mime_type

    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        raise ValueError("Accepted design version asset owner is unavailable.")
    allowed_namespaces = []
    if deck.user_id:
        allowed_namespaces.append(PurePosixPath("users") / deck.user_id / "decks" / deck.id)
    if deck.workspace_id:
        allowed_namespaces.append(PurePosixPath("workspaces") / deck.workspace_id / "decks" / deck.id)
    if not any(relative_path.is_relative_to(namespace) for namespace in allowed_namespaces):
        raise ValueError("Accepted design version references a raw asset outside the owning deck namespace.")
    return normalized_path, None


@dataclass(frozen=True)
class _AssetDescriptor:
    mime_type: str
    decoded_bytes: int
    encoded_bytes: int
    storage_path: str | None = None


@dataclass
class _AssetBudget:
    decoded_bytes: int = 0
    encoded_bytes: int = 0

    def reserve(self, descriptor: _AssetDescriptor, *, include_decoded: bool) -> None:
        next_decoded = self.decoded_bytes + (descriptor.decoded_bytes if include_decoded else 0)
        next_encoded = self.encoded_bytes + descriptor.encoded_bytes
        if next_decoded > _MAX_TOTAL_DECODED_ASSET_BYTES:
            raise ValueError("Accepted design version exceeds the cumulative decoded asset budget.")
        if next_encoded > _MAX_TOTAL_ENCODED_ASSET_BYTES:
            raise ValueError("Accepted design version exceeds the cumulative encoded asset budget.")
        self.decoded_bytes = next_decoded
        self.encoded_bytes = next_encoded


_DATA_IMAGE_PATTERN = re.compile(r"\Adata:(image/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/]*={0,2})\Z")


def _asset_descriptor(db: Session, deck_id: str, asset_url: str) -> _AssetDescriptor:
    data_match = _DATA_IMAGE_PATTERN.fullmatch(asset_url)
    if data_match:
        mime_type, encoded_payload = data_match.groups()
        if len(encoded_payload) % 4 != 0:
            raise ValueError("Accepted design version contains an invalid embedded image.")
        padding = len(encoded_payload) - len(encoded_payload.rstrip("="))
        decoded_bytes = (len(encoded_payload) // 4) * 3 - padding
        if decoded_bytes <= 0:
            raise ValueError("Accepted design version contains an empty embedded image.")
        if decoded_bytes > _MAX_INLINE_ASSET_BYTES:
            raise ValueError("Accepted design version contains an asset that is too large to embed.")
        return _AssetDescriptor(mime_type=mime_type, decoded_bytes=decoded_bytes, encoded_bytes=len(asset_url.encode("ascii")))

    storage_path, persisted_mime_type = _asset_storage_path(db, deck_id, asset_url)
    storage = get_upload_storage()
    try:
        metadata = storage.object_metadata(storage_path)
        decoded_bytes = int(metadata.get("contentLength") or 0)
    except Exception as exc:
        raise ValueError("Accepted design version references an unavailable asset.") from exc
    if decoded_bytes <= 0:
        raise ValueError("Accepted design version references an empty asset.")
    if decoded_bytes > _MAX_INLINE_ASSET_BYTES:
        raise ValueError("Accepted design version contains an asset that is too large to embed.")
    mime_type = persisted_mime_type or mimetypes.guess_type(storage_path)[0]
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError("Accepted design version contains an unsupported asset type.")
    encoded_bytes = len(f"data:{mime_type};base64,".encode("ascii")) + (4 * ((decoded_bytes + 2) // 3))
    return _AssetDescriptor(
        mime_type=mime_type,
        decoded_bytes=decoded_bytes,
        encoded_bytes=encoded_bytes,
        storage_path=storage_path,
    )


def _schema_asset_urls(schema: dict[str, Any]):
    background = schema.get("background") or {}
    if background.get("type") == "image" and background.get("value"):
        yield str(background["value"])
    for layer in background.get("layers") or []:
        if layer.get("type") == "image" and layer.get("assetUrl"):
            yield str(layer["assetUrl"])
    for element in schema.get("elements") or []:
        if element.get("type") == "image" and element.get("assetUrl"):
            yield str(element["assetUrl"])


def _validate_render_assets(
    db: Session,
    deck_id: str,
    slides: list[_AcceptedExportSlide],
) -> None:
    descriptors: dict[str, _AssetDescriptor] = {}
    budget = _AssetBudget()
    expected_by_url: dict[str, dict[str, Any]] = {}
    for slide in slides:
        for asset_url in _schema_asset_urls(slide.render_schema):
            expected = slide.assets[asset_url]
            prior_expected = expected_by_url.get(asset_url)
            if prior_expected is not None and prior_expected != expected:
                raise ValueError("Accepted deck history contains conflicting integrity metadata for one asset.")
            expected_by_url[asset_url] = expected
            descriptor = descriptors.get(asset_url)
            is_new = descriptor is None
            if descriptor is None:
                descriptor = _asset_descriptor(db, deck_id, asset_url)
                descriptors[asset_url] = descriptor
            if descriptor.decoded_bytes != expected["size"] or descriptor.mime_type.lower() != expected["mimeType"]:
                raise ValueError("Accepted design version asset size or type no longer matches accepted history.")
            budget.reserve(descriptor, include_decoded=is_new)


def _inline_asset(asset_url: str, descriptor: _AssetDescriptor, expected: dict[str, Any]) -> str:
    if descriptor.storage_path is None:
        data_match = _DATA_IMAGE_PATTERN.fullmatch(asset_url)
        if data_match is None:
            raise ValueError("Accepted design version contains an invalid embedded image.")
        try:
            payload = base64.b64decode(data_match.group(2), validate=True)
        except binascii.Error as exc:
            raise ValueError("Accepted design version contains an invalid embedded image.") from exc
        embedded = asset_url
    else:
        resolved = get_upload_storage().resolve_path(descriptor.storage_path)
        if resolved is None or not resolved.is_file():
            raise ValueError("Accepted design version references an unavailable asset.")
        payload = resolved.read_bytes()
        if len(payload) != descriptor.decoded_bytes:
            raise ValueError("Accepted design version asset changed while the export was being generated.")
        embedded = f"data:{descriptor.mime_type};base64,{base64.b64encode(payload).decode('ascii')}"
    if len(payload) != expected["size"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
        raise ValueError("Accepted design version asset content no longer matches accepted history.")
    return embedded


def build_accepted_snapshot_asset_manifests(
    db: Session,
    deck_id: str,
    render_schemas: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    descriptors: dict[str, _AssetDescriptor] = {}
    integrity_by_url: dict[str, dict[str, Any]] = {}
    budget = _AssetBudget()
    manifests: dict[str, list[dict[str, Any]]] = {}

    for generated_slide_id, render_schema in render_schemas.items():
        slide_manifest: dict[str, dict[str, Any]] = {}
        for asset_url in _schema_asset_urls(render_schema):
            descriptor = descriptors.get(asset_url)
            is_new = descriptor is None
            if descriptor is None:
                descriptor = _asset_descriptor(db, deck_id, asset_url)
                descriptors[asset_url] = descriptor
            budget.reserve(descriptor, include_decoded=is_new)
            integrity = integrity_by_url.get(asset_url)
            if integrity is None:
                if descriptor.storage_path is None:
                    data_match = _DATA_IMAGE_PATTERN.fullmatch(asset_url)
                    if data_match is None:
                        raise ValueError("Accepted design version contains an invalid embedded image.")
                    try:
                        payload = base64.b64decode(data_match.group(2), validate=True)
                    except binascii.Error as exc:
                        raise ValueError("Accepted design version contains an invalid embedded image.") from exc
                else:
                    resolved = get_upload_storage().resolve_path(descriptor.storage_path)
                    if resolved is None or not resolved.is_file():
                        raise ValueError("Accepted design version references an unavailable asset.")
                    payload = resolved.read_bytes()
                if len(payload) != descriptor.decoded_bytes:
                    raise ValueError("Accepted design version asset changed while acceptance was being recorded.")
                integrity = {
                    "assetUrl": asset_url,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                    "mimeType": descriptor.mime_type.lower(),
                }
                integrity_by_url[asset_url] = integrity
            slide_manifest[asset_url] = integrity
        manifests[generated_slide_id] = [slide_manifest[url] for url in sorted(slide_manifest)]
    return manifests


def _inline_render_assets(
    db: Session,
    deck_id: str,
    slides: list[_AcceptedExportSlide],
) -> list[_AcceptedExportSlide]:
    cache: dict[str, str] = {}
    descriptors: dict[str, _AssetDescriptor] = {}
    expected_by_url: dict[str, dict[str, Any]] = {}
    budget = _AssetBudget()

    def inline(value: str, expected: dict[str, Any]) -> str:
        prior_expected = expected_by_url.get(value)
        if prior_expected is not None and prior_expected != expected:
            raise ValueError("Accepted deck history contains conflicting integrity metadata for one asset.")
        expected_by_url[value] = expected
        descriptor = descriptors.get(value)
        is_new = descriptor is None
        if descriptor is None:
            descriptor = _asset_descriptor(db, deck_id, value)
            descriptors[value] = descriptor
        if descriptor.decoded_bytes != expected["size"] or descriptor.mime_type.lower() != expected["mimeType"]:
            raise ValueError("Accepted design version asset size or type no longer matches accepted history.")
        budget.reserve(descriptor, include_decoded=is_new)
        if value not in cache:
            cache[value] = _inline_asset(value, descriptor, expected)
        return cache[value]

    result: list[_AcceptedExportSlide] = []
    for slide in slides:
        schema = copy.deepcopy(slide.render_schema)
        background = schema.get("background") or {}
        if background.get("type") == "image" and background.get("value"):
            asset_url = str(background["value"])
            background["value"] = inline(asset_url, slide.assets[asset_url])
        for layer in background.get("layers") or []:
            if layer.get("type") == "image" and layer.get("assetUrl"):
                asset_url = str(layer["assetUrl"])
                layer["assetUrl"] = inline(asset_url, slide.assets[asset_url])
        for element in schema.get("elements") or []:
            if element.get("type") == "image" and element.get("assetUrl"):
                asset_url = str(element["assetUrl"])
                element["assetUrl"] = inline(asset_url, slide.assets[asset_url])
        result.append(
            _AcceptedExportSlide(
                id=slide.id,
                source_slide_id=slide.source_slide_id,
                slide_number=slide.slide_number,
                title=slide.title,
                render_schema=schema,
                design_tokens=slide.design_tokens,
                assets=slide.assets,
            )
        )
    return result


def _json_for_html_script(value: Any) -> str:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _build_design_version_html(
    db: Session,
    deck: Deck,
    version: DesignVersion,
    slides: list[_AcceptedExportSlide],
) -> str:
    inlined_slides = _inline_render_assets(db, deck.id, slides)
    payload = {
        "deckId": deck.id,
        "designVersionId": version.id,
        "exportType": FINAL_DECK_EXPORT_TYPE,
        "format": HTML_EXPORT_FORMAT,
        "title": deck.title,
        "slides": [
            {
                "id": slide.id,
                "slideNumber": slide.slide_number,
                "title": slide.title,
                "renderSchema": slide.render_schema,
                "designTokens": {**DEFAULT_DESIGN_TOKENS, **slide.design_tokens},
            }
            for slide in inlined_slides
        ],
    }
    title = html.escape(deck.title or "Deck")
    metadata = {
        "deckId": deck.id,
        "designVersionId": version.id,
        "exportType": FINAL_DECK_EXPORT_TYPE,
        "format": HTML_EXPORT_FORMAT,
        "signature": _HTML_EXPORT_SIGNATURE,
    }
    encoded_metadata = base64.urlsafe_b64encode(_json_for_html_script(metadata).encode("utf-8")).decode("ascii").rstrip("=")
    deck_data = _json_for_html_script(payload)
    return f'''<!doctype html>
<!-- deck-aistack-html-export.v1 -->
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
  <meta name="deck-export-metadata" content="{encoded_metadata}">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; min-height: 100%; background: #020617; color: #f8fafc; font-family: Arial, sans-serif; }}
    body {{ display: grid; grid-template-rows: 1fr auto; height: 100vh; overflow: hidden; }}
    #stage {{ display: grid; place-items: center; min-height: 0; padding: 20px; }}
    .slide {{ position: relative; overflow: hidden; box-shadow: 0 20px 60px #0009; transform-origin: center; }}
    .item {{ position: absolute; white-space: pre-wrap; overflow: hidden; }}
    .item.image {{ object-fit: cover; }}
    #controls {{ display: flex; justify-content: center; align-items: center; gap: 12px; padding: 10px; background: #020617; }}
    button {{ border: 1px solid #475569; border-radius: 8px; background: #0f172a; color: #f8fafc; padding: 8px 14px; cursor: pointer; }}
    button:disabled {{ opacity: .4; cursor: default; }}
    @media print {{ body {{ display: block; height: auto; overflow: visible; background: white; }} #controls {{ display: none; }} #stage {{ padding: 0; }} .slide {{ box-shadow: none; transform: none !important; }} }}
  </style>
</head>
<body>
  <main id="stage" aria-label="{title}"></main>
  <nav id="controls" aria-label="Deck navigation"><button id="previous">Previous</button><span id="counter"></span><button id="next">Next</button></nav>
  <script id="deck-data" type="application/json">{deck_data}</script>
  <script>
    (() => {{
      const deck = JSON.parse(document.getElementById('deck-data').textContent);
      const stage = document.getElementById('stage');
      const previous = document.getElementById('previous');
      const next = document.getElementById('next');
      const counter = document.getElementById('counter');
      let index = 0;
      const token = (value, tokens, fallback = 'brand.body') => {{
        const resolved = value || fallback;
        if (tokens[resolved]) return tokens[resolved];
        return typeof resolved === 'string' ? resolved.replace(/brand\\.[A-Za-z0-9]+/g, name => tokens[name] || tokens[fallback]) : tokens[fallback];
      }};
      function position(node, item) {{
        Object.assign(node.style, {{ left: item.x + 'px', top: item.y + 'px', width: item.width + 'px', height: item.height + 'px', zIndex: item.zIndex ?? 0 }});
      }}
      function shape(item, tokens) {{
        const node = document.createElement('div'); position(node, item); node.className = 'item';
        node.style.background = token(item.style?.fill || item.fillToken, tokens); node.style.opacity = item.style?.opacity ?? 1;
        node.style.borderRadius = (item.style?.radius ?? 0) + 'px'; if (item.shape === 'circle') node.style.borderRadius = '50%';
        return node;
      }}
      function image(item) {{
        const node = document.createElement('img'); position(node, item); node.className = 'item image';
        node.src = item.assetUrl; node.alt = ''; node.style.opacity = item.style?.opacity ?? 1;
        node.style.borderRadius = (item.style?.radius ?? 0) + 'px'; return node;
      }}
      function render() {{
        const current = deck.slides[index]; const schema = current.renderSchema; const tokens = current.designTokens;
        const width = schema.width; const height = schema.height; stage.replaceChildren();
        const slide = document.createElement('section'); slide.className = 'slide'; slide.style.width = width + 'px'; slide.style.height = height + 'px';
        slide.setAttribute('aria-label', current.title || ('Slide ' + current.slideNumber)); const bg = schema.background;
        slide.style.background = bg.type === 'image' ? `center / cover no-repeat url("${{bg.value}}")` : token(bg.value || bg.fill, tokens);
        for (const layer of bg.layers || []) slide.append(layer.type === 'image' ? image(layer) : shape(layer, tokens));
        for (const item of schema.elements) {{
          let node;
          if (item.type === 'image') node = image(item);
          else if (item.type === 'shape') node = shape(item, tokens);
          else {{ node = document.createElement('div'); position(node, item); node.className = 'item'; node.textContent = item.text || (item.type === 'chart_placeholder' ? 'Chart placeholder' : '');
            node.style.color = token(item.colorToken, tokens); node.style.background = 'transparent';
            node.style.fontSize = (item.fontSize || 28) + 'px'; node.style.fontWeight = item.fontWeight || '400';
            node.style.fontFamily = tokens[item.fontWeight === 'bold' || Number(item.fontWeight) >= 600 ? 'brand.headingFont' : 'brand.bodyFont'] || 'Inter, sans-serif';
          }}
          slide.append(node);
        }}
        stage.append(slide); const scale = Math.min((stage.clientWidth - 40) / width, (stage.clientHeight - 40) / height, 1);
        slide.style.transform = `scale(${{Math.max(scale, .1)}})`; counter.textContent = `${{index + 1}} / ${{deck.slides.length}}`;
        previous.disabled = index === 0; next.disabled = index === deck.slides.length - 1;
      }}
      previous.addEventListener('click', () => {{ if (index > 0) {{ index--; render(); }} }});
      next.addEventListener('click', () => {{ if (index < deck.slides.length - 1) {{ index++; render(); }} }});
      addEventListener('keydown', event => {{ if (event.key === 'ArrowLeft') previous.click(); if (event.key === 'ArrowRight') next.click(); }});
      addEventListener('resize', render); render();
    }})();
  </script>
</body>
</html>
'''


def create_export(
    db: Session,
    deck_id: str,
    export_type: str,
    *,
    export_format: str | None = None,
    design_version_id: str | None = None,
    idempotency_key: str | None = None,
    commit: bool = True,
) -> dict[str, Any] | None:
    if export_type == PROVISIONAL_HTML_EXPORT_TYPE and (export_format != HTML_EXPORT_FORMAT or not design_version_id):
        raise ValueError("provisional_html export requires format=html and designVersionId.")
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    if deck is None:
        return None

    export_id = (
        f"export_{hashlib.sha256(f'{deck_id}:{idempotency_key}'.encode('utf-8')).hexdigest()[:24]}"
        if idempotency_key
        else generate_id("export")
    )
    existing = db.query(DeckExport).filter(DeckExport.id == export_id, DeckExport.deck_id == deck.id).one_or_none()
    if existing is not None:
        if existing.type != export_type:
            raise ValueError("Export idempotency key is already bound to another export classification.")
        existing_design_version_id, existing_format = _metadata_from_content(existing)
        if export_format != existing_format or design_version_id != existing_design_version_id:
            raise ValueError("Export idempotency key is already bound to another export request.")
        if commit:
            db.commit()
            publish_export_handoff(db, existing.id)
        return _map_export(existing)

    if export_format is not None:
        if export_type not in {FINAL_DECK_EXPORT_TYPE, PROVISIONAL_HTML_EXPORT_TYPE} or export_format != HTML_EXPORT_FORMAT or not design_version_id:
            raise ValueError("Only classified final_deck or provisional_html HTML export with designVersionId is supported.")
        version = resolve_html_export_design_version(db, deck, design_version_id, export_type=export_type)
        content = (
            _build_compiled_html_export(db, deck, version, export_type=export_type)
            if version.render_mode == "html_compiled.v1"
            else _build_design_version_html(db, deck, version, _validated_accepted_export_slides(db, version))
        )
        if len(content.encode("utf-8")) > _MAX_HTML_EXPORT_BYTES:
            raise ValueError("Accepted design version is too large for a self-contained HTML export.")
    else:
        content = _build_export_content(db, deck.id, export_type)

    deck_export = DeckExport(
        id=export_id,
        deck_id=deck.id,
        type=export_type,
        content=content,
        handoff_status="pending",
        handoff_attempts=0,
    )
    db.add(deck_export)
    db.flush()
    if commit:
        db.commit()
        db.refresh(deck_export)
        publish_export_handoff(db, deck_export.id)
    mapped = _map_export(deck_export)
    if export_format == HTML_EXPORT_FORMAT and design_version_id:
        mapped["classification"] = "provisional" if export_type == PROVISIONAL_HTML_EXPORT_TYPE else "final"
        mapped["versionStatus"] = version.status
        mapped["artifactHash"] = hashlib.sha256(deck_export.content.encode("utf-8")).hexdigest()
    return mapped


def list_exports(
    db: Session,
    deck_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 100))
    bounded_offset = max(0, int(offset))
    total = db.query(func.count(DeckExport.id)).filter(DeckExport.deck_id == deck_id).scalar() or 0
    rows = (
        db.query(
            DeckExport.id,
            DeckExport.deck_id,
            DeckExport.type,
            DeckExport.created_at,
            func.substr(DeckExport.content, 1, 4096).label("content_prefix"),
        )
        .filter(DeckExport.deck_id == deck_id)
        .order_by(DeckExport.created_at.desc(), DeckExport.id.desc())
        .offset(bounded_offset)
        .limit(bounded_limit)
        .all()
    )
    exports: list[dict[str, Any]] = []
    for row in rows:
        design_version_id, export_format = _metadata_from_values(row.type, row.deck_id, row.content_prefix or "")
        mapped: dict[str, Any] = {
            "id": row.id,
            "deck_id": row.deck_id,
            "deckId": row.deck_id,
            "type": row.type,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "createdAt": row.created_at.isoformat() if row.created_at else "",
            "download_url": _canonical_download_url(row.deck_id, row.id),
            "downloadUrl": _canonical_download_url(row.deck_id, row.id),
            "detailUrl": _detail_url(row.deck_id, row.id),
        }
        if design_version_id is not None:
            mapped["designVersionId"] = design_version_id
        if export_format is not None:
            mapped["format"] = export_format
        exports.append(mapped)
    return {
        "exports": exports,
        "total": total,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "hasMore": bounded_offset + len(exports) < total,
    }


def get_export(db: Session, deck_id: str, export_id: str) -> dict[str, Any] | None:
    deck_export = (
        db.query(DeckExport)
        .filter(DeckExport.deck_id == deck_id, DeckExport.id == export_id)
        .one_or_none()
    )
    return _map_export(deck_export) if deck_export is not None else None


def shareable_html_export_payload(db: Session, deck_id: str, export_id: str) -> tuple[DeckExport, str]:
    """Resolve the immutable HTML artifact that a public share may expose.

    Public sharing deliberately starts after the canonical export boundary. It
    must never rebuild provider output or weaken the compiler/version checks
    encoded in the persisted export metadata.
    """
    deck_export = (
        db.query(DeckExport)
        .filter(DeckExport.deck_id == deck_id, DeckExport.id == export_id)
        .one_or_none()
    )
    if deck_export is None:
        raise ValueError("Export not found.")
    if deck_export.handoff_status != "ready":
        raise ValueError("Export is not ready to share.")
    if deck_export.type not in {FINAL_DECK_EXPORT_TYPE, PROVISIONAL_HTML_EXPORT_TYPE}:
        raise ValueError("Only classified HTML deck exports can be shared.")
    design_version_id, export_format = _metadata_from_content(deck_export)
    if export_format != HTML_EXPORT_FORMAT or not design_version_id:
        raise ValueError("Export does not contain a verified HTML DesignVersion identity.")
    if not deck_export.content.lower().startswith("<!doctype html>"):
        raise ValueError("Export is not a complete HTML document.")
    return deck_export, design_version_id


def export_download_payload(db: Session, deck_id: str, export_id: str) -> tuple[str, str, str] | None:
    deck_export = (
        db.query(DeckExport)
        .filter(DeckExport.deck_id == deck_id, DeckExport.id == export_id)
        .one_or_none()
    )
    if deck_export is None:
        return None

    design_version_id, export_format = _metadata_from_content(deck_export)
    media_type, _extension, filename = _export_file_contract(
        deck_id,
        deck_export.id,
        deck_export.type,
        export_format=export_format,
        design_version_id=design_version_id,
    )
    return deck_export.content, media_type, filename
