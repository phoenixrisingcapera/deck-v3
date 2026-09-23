from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
import secrets
from typing import Literal
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.core.config import settings
from app.core.security import generate_id
from app.db.models import GeneratedSlide, InstantDeckCompilation, InstantDeckHtmlArtifact, InstantDeckRenderCapability, User
from app.core.instant_html_crypto import get_instant_html_render_fernet
from app.services.admin.security_audit import record_security_event
from app.services.rendering.render_proof_service import RenderProofRequired, read_encrypted_render_document, require_complete_render_proofs
from app.services.storage.artifact_storage import get_upload_storage
from app.services.visualizer.deck_artifact_listing import list_deck_llm_artifacts
from app.schemas.smart_deck import InstantHtmlRenderCapabilityResponse

router = APIRouter(tags=["deck-artifacts"])
public_renderer_router = APIRouter(tags=["instant-html-renderer"])


class CapabilityArtifactFailure(HTTPException):
    def __init__(self, *, status_code: int, detail: str, telemetry_category: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.telemetry_category = telemetry_category


def _browser_utc_isoformat(value: datetime) -> str:
    """Serialize a capability deadline as an unambiguous browser UTC instant."""
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.isoformat().replace("+00:00", "Z")


_FULL_DECK_PRINT_STYLE = """<style id="instant-deck-export-contract">
/* Each generated canvas owns its positioned children, as in isolated rendering. */
section[data-da-slide-root] {
  position: relative !important;
  isolation: isolate;
  box-sizing: border-box !important;
  width: 1920px !important;
  height: 1080px !important;
  overflow: hidden !important;
}

@media screen and (max-width: 480px) {
  [data-da-slide-root] .content,
  [data-da-slide-root].content {
    min-width: 0 !important;
    grid-template-columns: minmax(0, 1fr) !important;
  }
  [data-da-slide-root] table {
    box-sizing: border-box !important;
    table-layout: fixed !important;
    width: 100% !important;
    max-width: 100% !important;
  }
  [data-da-slide-root] th,
  [data-da-slide-root] td {
    min-width: 0 !important;
    overflow-wrap: anywhere !important;
    word-break: normal !important;
  }
}
@media print {
  /* Match the 1920 x 1080 CSS-pixel canvas used by the isolated render proof. */
  @page { size: 20in 11.25in; margin: 0; }
  html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
  body { overflow: visible !important; }
  section[data-da-slide-root] {
    box-sizing: border-box !important;
    width: 1920px !important;
    height: 1080px !important;
    min-height: 1080px !important;
    max-height: 1080px !important;
    overflow: hidden !important;
    break-after: page;
    page-break-after: always;
  }
  section[data-da-slide-root]:last-of-type {
    break-after: auto;
    page-break-after: auto;
  }
}
</style>"""


def _with_full_deck_print_contract(document: str) -> str:
    """Add responsive screen and print pagination contracts after artifact verification."""
    title = "" if re.search(r"<title(?:\s[^>]*)?>.*?</title\s*>", document, flags=re.IGNORECASE | re.DOTALL) else "<title>Instant Deck</title>"
    addition = title + _FULL_DECK_PRINT_STYLE
    if re.search(r"</head\s*>", document, flags=re.IGNORECASE):
        return re.sub(r"</head\s*>", addition + "</head>", document, count=1, flags=re.IGNORECASE)
    if re.search(r"<html(?:\s[^>]*)?>", document, flags=re.IGNORECASE):
        return re.sub(r"(<html(?:\s[^>]*)?>)", r"\1<head>" + addition + "</head>", document, count=1, flags=re.IGNORECASE)
    return "<!doctype html><html><head>" + addition + "</head><body>" + document + "</body></html>"


def _renderer_origin(request: Request) -> str:
    configured = settings.instant_html_renderer_origin.rstrip("/")
    observed = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
    if not settings.instant_html_enabled or not configured or observed != configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Instant HTML renderer origin is unavailable.")
    return configured


def _read_encrypted_document(storage_key: str, expected_hash: str) -> str:
    try:
        return read_encrypted_render_document(storage_key, expected_hash)
    except RenderProofRequired as exc:
        raise CapabilityArtifactFailure(
            status_code=404,
            detail="Sanitized compiled slide content not found.",
            telemetry_category="render_document_retrieval_failed",
        ) from exc


def _read_verified_encrypted_artifact(artifact: InstantDeckHtmlArtifact) -> str:
    if not artifact.encrypted or not artifact.encryption_key_version or artifact.encryption_purpose != "instant-html-sanitized-deck":
        raise CapabilityArtifactFailure(
            status_code=409,
            detail="Sanitized artifact encryption identity is invalid.",
            telemetry_category="artifact_identity_invalid",
        )
    path = get_upload_storage().resolve_path(artifact.storage_key)
    if path is None or not path.exists():
        raise CapabilityArtifactFailure(
            status_code=404,
            detail="Sanitized compiled slide content not found.",
            telemetry_category="artifact_retrieval_failed",
        )
    try:
        plaintext = get_instant_html_render_fernet().decrypt(path.read_bytes())
    except Exception as exc:
        raise CapabilityArtifactFailure(
            status_code=409,
            detail="Sanitized artifact integrity check failed.",
            telemetry_category="artifact_decryption_failed",
        ) from exc
    if not secrets.compare_digest(sha256(plaintext).hexdigest(), artifact.content_hash):
        raise CapabilityArtifactFailure(
            status_code=409,
            detail="Sanitized artifact integrity check failed.",
            telemetry_category="artifact_integrity_failed",
        )
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CapabilityArtifactFailure(status_code=409, detail="Sanitized artifact encoding is invalid.", telemetry_category="artifact_integrity_failed") from exc


def _verify_encrypted_artifact(artifact: InstantDeckHtmlArtifact) -> None:
    _read_verified_encrypted_artifact(artifact)


def _deck_artifacts_response(
    *,
    deck_id: str,
    request: Request,
    artifact_type: str | None = None,
    limit: int = 100,
    current_user: User,
    db: Session,
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        return list_deck_llm_artifacts(
            db,
            deck_id,
            artifact_type=artifact_type,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Deck LLM artifacts are temporarily unavailable.",
                "failureCategory": "deck_llm_artifacts_load",
                "requestId": getattr(request.state, "request_id", None),
            },
        ) from exc


def product_deck_artifacts(
    deck_id: str,
    request: Request,
    artifact_type: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _deck_artifacts_response(
        deck_id=deck_id,
        artifact_type=artifact_type,
        limit=limit,
        request=request,
        current_user=current_user,
        db=db,
    )


@router.get("/decks/{deck_id}/artifacts")
def deck_artifacts(
    deck_id: str,
    request: Request,
    artifact_type: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _deck_artifacts_response(
        deck_id=deck_id,
        artifact_type=artifact_type,
        limit=limit,
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/products/deck-aistack-codes/decks/{deck_id}/html-artifacts/{artifact_id}/slides/{generated_slide_id}/capability",
    response_model=InstantHtmlRenderCapabilityResponse,
)
def mint_instant_html_capability(
    deck_id: str,
    artifact_id: str,
    generated_slide_id: str,
    scope: Literal["section", "full_deck"] = "section",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_user_deck_or_404(db, current_user, deck_id)
    if not settings.instant_html_enabled or not settings.instant_html_renderer_origin.strip():
        raise HTTPException(status_code=503, detail="Instant HTML rendering is disabled.")
    artifact = db.query(InstantDeckHtmlArtifact).filter(
        InstantDeckHtmlArtifact.id == artifact_id,
        InstantDeckHtmlArtifact.deck_id == deck_id,
        InstantDeckHtmlArtifact.artifact_kind == "sanitized",
        InstantDeckHtmlArtifact.quarantined.is_(False),
        InstantDeckHtmlArtifact.encrypted.is_(True),
    ).one_or_none()
    slide = db.query(GeneratedSlide).filter(
        GeneratedSlide.id == generated_slide_id,
        GeneratedSlide.deck_id == deck_id,
        GeneratedSlide.design_version_id == (artifact.design_version_id if artifact else None),
        GeneratedSlide.render_mode == "html_compiled.v1",
    ).one_or_none()
    if artifact is None or slide is None:
        raise HTTPException(status_code=404, detail="Sanitized compiled slide artifact not found.")
    if not artifact.encryption_key_version or artifact.encryption_purpose != "instant-html-sanitized-deck":
        raise HTTPException(status_code=409, detail="Sanitized artifact encryption identity is invalid.")
    try:
        compilation = require_complete_render_proofs(slide.design_version, db)
    except RenderProofRequired as exc:
        raise HTTPException(status_code=409, detail="Compiled slide is not render-proven.") from exc
    if compilation.sanitized_html_artifact_id != artifact.id:
        raise HTTPException(status_code=409, detail="Artifact identity does not match the render proof.")
    from app.services.rendering.instant_svg_text_layout import ensure_saved_offsets
    ensure_saved_offsets(db, compilation, artifact, _read_verified_encrypted_artifact)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(seconds=settings.instant_html_capability_ttl_seconds)
    manifest = compilation.manifest_json or {}
    manifest_slide = next(
        (item for item in manifest.get("slides", []) if item.get("generatedSlideId") == slide.id),
        None,
    )
    if scope == "full_deck":
        document_hash = artifact.content_hash
        if manifest.get("contentHash") != document_hash:
            raise HTTPException(status_code=409, detail="Compiled full-deck artifact identity is incomplete.")
    else:
        document_hash = str((manifest_slide or {}).get("renderDocumentHash") or "")
        if len(document_hash) != 64 or not (manifest_slide or {}).get("renderDocumentStorageKey"):
            raise HTTPException(status_code=409, detail="Compiled slide document identity is incomplete.")
    capability = InstantDeckRenderCapability(
        id=generate_id("rendercap"), artifact_id=artifact.id, generated_slide_id=slide.id,
        design_version_id=artifact.design_version_id, scope=scope,
        artifact_encryption_key_version=artifact.encryption_key_version,
        artifact_hash=artifact.content_hash, token_hash=sha256(token.encode()).hexdigest(),
        render_document_hash=document_hash, minted_by_user_id=current_user.id, expires_at=expires_at,
    )
    db.add(capability)
    expires_at_iso = _browser_utc_isoformat(expires_at)
    record_security_event(
        db, action="instant_html.capability.mint", result="success", actor=current_user,
        resource_type="instant_deck_render_capability", resource_id=capability.id,
        details={"artifactId": artifact.id, "generatedSlideId": slide.id, "scope": scope, "expiresAt": expires_at_iso},
    )
    db.commit()
    render_url = urljoin(settings.instant_html_renderer_origin.rstrip("/") + "/", f"api/instant-html-render/{token}")
    return {
        "artifactId": artifact.id,
        "artifactSha256": artifact.content_hash,
        "designVersionId": capability.design_version_id,
        "artifactEncryptionKeyVersion": capability.artifact_encryption_key_version,
        "generatedSlideId": slide.id,
        "sectionId": slide.section_id,
        "scope": capability.scope,
        "renderMode": "html_compiled.v1",
        "renderProofStatus": "ready",
        "renderUrl": render_url,
        "expiresAt": expires_at_iso,
    }


@public_renderer_router.get("/instant-html-render/{token}", response_class=HTMLResponse)
def render_instant_html_capability(token: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    _renderer_origin(request)
    if request.headers.get("authorization") or request.headers.get("cookie"):
        raise HTTPException(status_code=400, detail="The cookieless renderer does not accept credentials.")
    capability = db.query(InstantDeckRenderCapability).filter(
        InstantDeckRenderCapability.token_hash == sha256(token.encode()).hexdigest(),
    ).with_for_update().one_or_none()
    if capability is None:
        request.state.capability_status = "invalid"
        raise HTTPException(status_code=404, detail="Render capability is invalid or expired.")
    if int(capability.use_count or 0) > 0:
        request.state.capability_status = "replayed"
        raise HTTPException(status_code=404, detail="Render capability is invalid or expired.")
    if capability.expires_at <= datetime.utcnow():
        request.state.capability_status = "expired"
        raise HTTPException(status_code=404, detail="Render capability is invalid or expired.")
    if capability.revoked_at is not None:
        request.state.capability_status = "revoked"
        raise HTTPException(status_code=404, detail="Render capability is invalid or expired.")
    if capability.scope not in {"section", "full_deck"} or not capability.design_version_id or not capability.artifact_encryption_key_version:
        request.state.capability_status = "artifact_identity_invalid"
        raise HTTPException(status_code=404, detail="Render capability is invalid or expired.")
    artifact = db.query(InstantDeckHtmlArtifact).filter(
        InstantDeckHtmlArtifact.id == capability.artifact_id,
        InstantDeckHtmlArtifact.content_hash == capability.artifact_hash,
        InstantDeckHtmlArtifact.design_version_id == capability.design_version_id,
        InstantDeckHtmlArtifact.encryption_key_version == capability.artifact_encryption_key_version,
        InstantDeckHtmlArtifact.artifact_kind == "sanitized",
        InstantDeckHtmlArtifact.quarantined.is_(False),
    ).one_or_none()
    slide = db.query(GeneratedSlide).filter(
        GeneratedSlide.id == capability.generated_slide_id,
        GeneratedSlide.design_version_id == capability.design_version_id,
        GeneratedSlide.render_mode == "html_compiled.v1",
    ).one_or_none()
    compilation = db.query(InstantDeckCompilation).filter(
        InstantDeckCompilation.design_version_id == capability.design_version_id,
        InstantDeckCompilation.sanitized_html_artifact_id == (artifact.id if artifact else None),
        InstantDeckCompilation.render_proof_status == "ready",
    ).one_or_none()
    manifest = compilation.manifest_json if compilation else {}
    manifest_slide = next(
        (item for item in (compilation.manifest_json or {}).get("slides", []) if item.get("generatedSlideId") == capability.generated_slide_id),
        None,
    ) if compilation else None
    full_deck_scope = capability.scope == "full_deck"
    if (
        artifact is None or slide is None or compilation is None
        or (full_deck_scope and (manifest.get("contentHash") != capability.render_document_hash or not secrets.compare_digest(capability.render_document_hash, artifact.content_hash)))
        or (not full_deck_scope and (manifest_slide is None or manifest_slide.get("renderDocumentHash") != capability.render_document_hash))
    ):
        request.state.capability_status = "artifact_unavailable"
        raise HTTPException(status_code=404, detail="Sanitized compiled slide content not found.")
    try:
        if full_deck_scope:
            document = _read_verified_encrypted_artifact(artifact)
            document = _with_full_deck_print_contract(document)
        else:
            _verify_encrypted_artifact(artifact)
            document = _read_encrypted_document(str(manifest_slide.get("renderDocumentStorageKey") or ""), capability.render_document_hash)
        if manifest.get('evidencePolicy') == 'advisory-draft.v1':
            from app.services.rendering.html_deck_compiler import restore_advisory_document_root_css
            document = restore_advisory_document_root_css(document)
            from app.services.rendering.instant_svg_text_layout import restore_saved_offsets
            document = restore_saved_offsets(db, artifact, document)
    except CapabilityArtifactFailure as exc:
        request.state.capability_status = exc.telemetry_category
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        request.state.capability_status = "artifact_processing_failed"
        raise
    except Exception as exc:
        request.state.capability_status = "artifact_processing_failed"
        raise HTTPException(status_code=404, detail="Sanitized compiled slide content not found.") from exc
    capability.last_used_at = datetime.utcnow()
    capability.use_count = int(capability.use_count or 0) + 1
    capability.revoked_at = capability.last_used_at
    record_security_event(
        db, action="instant_html.capability.use", result="success", actor=None,
        resource_type="instant_deck_render_capability", resource_id=capability.id,
        details={"artifactId": artifact.id, "generatedSlideId": slide.id, "scope": capability.scope, "useCount": capability.use_count},
    )
    db.commit()
    request.state.capability_status = "consumed"
    parent_origin = settings.instant_html_render_parent_origin
    csp = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
        "script-src 'none'; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; "
        f"base-uri 'none'; form-action 'none'; frame-ancestors {parent_origin}; sandbox"
    )
    return HTMLResponse(document, headers={
        "Content-Security-Policy": csp,
        "Cache-Control": "private, no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    })


@router.delete(
    "/products/deck-aistack-codes/decks/{deck_id}/html-render-capabilities/{capability_id}",
    status_code=204,
    response_class=Response,
)
def revoke_instant_html_capability(
    deck_id: str,
    capability_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    get_user_deck_or_404(db, current_user, deck_id)
    capability = db.query(InstantDeckRenderCapability).join(InstantDeckHtmlArtifact).filter(
        InstantDeckRenderCapability.id == capability_id,
        InstantDeckHtmlArtifact.deck_id == deck_id,
    ).one_or_none()
    if capability is None:
        raise HTTPException(status_code=404, detail="Render capability not found.")
    if capability.revoked_at is None:
        capability.revoked_at = datetime.utcnow()
        record_security_event(
            db, action="instant_html.capability.revoke", result="success", actor=current_user,
            resource_type="instant_deck_render_capability", resource_id=capability.id,
            details={"artifactId": capability.artifact_id, "generatedSlideId": capability.generated_slide_id},
        )
        db.commit()
    return Response(status_code=204)
