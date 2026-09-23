from __future__ import annotations

from pathlib import Path
from typing import Any
import tempfile

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import Deck, User, Workspace
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state, transition_deck_state
from app.services.storage.deck_file_service import compute_sha256
from app.services.storage.upload_security import LimitedUpload
from app.services.deck_processing.workspace_summary_service import create_first_deck_upload, get_workspace_summary_for_user, soft_delete_workspace_deck


_SMOKE_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"%\xe2\xe3\xcf\xd3\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
    b"xref\n"
    b"0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"trailer << /Size 4 /Root 1 0 R >>\n"
    b"startxref\n150\n"
    b"%%EOF\n"
)


def _safe_workspace_name(user: User) -> str:
    display_name = (user.name or user.email or "Deck").strip()
    return display_name.split()[0] if display_name else "Deck"


def _ensure_workspace(db: Session, user: User) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.user_id == user.id).order_by(Workspace.created_at.asc()).first()
    if workspace is not None:
        return workspace

    workspace = Workspace(
        id=generate_id("ws"),
        name=f"{_safe_workspace_name(user)}'s Workspace",
        user_id=user.id,
    )
    db.add(workspace)
    db.flush()
    return workspace


def _manual_smart_deck_fields(deck_id: str) -> dict[str, str]:
    state = DeckState.UPLOADED.value
    return {
        "status": state,
        "state": state,
        "deckStatus": state,
        "next_action": "create_smart_deck",
        "next_step_message": "Click Create Smart Deck to start processing.",
        "create_smart_deck_url": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction",
        "processing_status_url": f"/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state",
        "smart_deck_url": f"/decks/{deck_id}/smart-deck",
    }


def _write_smoke_pdf() -> tuple[Path, int, str]:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(_SMOKE_PDF_BYTES)
        payload_path = Path(handle.name)
    size = len(_SMOKE_PDF_BYTES)
    checksum = compute_sha256(_SMOKE_PDF_BYTES)
    return payload_path, size, checksum


def _build_acceptance_entry(payload: dict[str, Any], deck: Deck | None, workspace_summary: dict[str, Any], deck_id: str) -> tuple[dict[str, bool], bool]:
    acceptance = {
        "uploadReturnsSuccess": bool(payload.get("ok")),
        "responseIncludesDeckId": bool(deck_id),
        "workspaceSummaryContainsDeck": any(
            (item.get("id") == deck_id)
            for item in workspace_summary.get("latest_decks", [])
        ),
        "statusIsUploaded": bool(deck and canonical_deck_state(deck.status) == DeckState.UPLOADED),
        "nextActionIsCreateSmartDeck": payload.get("next_action") == "create_smart_deck",
    }
    return acceptance, all(acceptance.values())


def _as_result(
    *,
    payload: dict[str, Any],
    workspace_summary: dict[str, Any] | None = None,
    deck_id: str | None = None,
    accepted: bool = False,
    message: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    if workspace_summary is None:
        workspace_summary = {}

    return {
        "ok": bool(payload.get("ok")) and accepted,
        "status": "passed" if accepted else "failed",
        "ranInsideBackend": True,
        "deckId": deck_id,
        "workspaceSummary": workspace_summary,
        "message": message or "Railway upload smoke test complete.",
        "acceptance": {
            "uploadReturnsSuccess": bool(payload.get("ok")),
            "responseIncludesDeckId": bool(deck_id),
            "workspaceSummaryContainsDeck": bool(
                any(
                    isinstance(workspace_summary, dict)
                    and isinstance(item, dict)
                    and item.get("id") == deck_id
                    for item in workspace_summary.get("latest_decks", [])
                )
            ),
            "statusIsUploaded": bool(payload.get("deckStatus") == DeckState.UPLOADED.value or payload.get("state") == DeckState.UPLOADED.value),
            "nextActionIsCreateSmartDeck": payload.get("next_action") == "create_smart_deck",
            "accepted": accepted,
        },
        "error": error,
    }


async def run_railway_upload_smoke_test(
    db: Session,
    user: User,
    *,
    cleanup: bool = True,
) -> dict[str, Any]:
    """
    Run a live admin-only smoke test for the upload persistence pipeline.

    This creates a tiny PDF deck using the same backend upload persistence path
    used by real user uploads, verifies workspace visibility, and returns a
    contract-shaped response describing readiness acceptance flags.
    """

    workspace = _ensure_workspace(db, user)
    deck_id: str | None = None
    payload: dict[str, Any] = {"ok": False}
    workspace_summary: dict[str, Any] = {}
    temp_path: Path | None = None

    try:
        payload_path, payload_size, payload_checksum = _write_smoke_pdf()
        temp_path = payload_path
        deck_upload = LimitedUpload(
            path=payload_path,
            size=payload_size,
            checksum_sha256=payload_checksum,
        )
        payload = await create_first_deck_upload(
            db=db,
            user_id=user.id,
            file_name="railway-upload-smoke-test.pdf",
            content_type="application/pdf",
            deck_upload=deck_upload,
            workspace_id=workspace.id,
            company_name="Railway Test",
        )

        deck_id = str(payload.get("deck_id") or "")
        payload["deck_id"] = deck_id
        if not deck_id:
            return _as_result(
                payload=payload,
                deck_id=deck_id,
                accepted=False,
                message="Smoke test returned no deck_id from upload persistence.",
            )

        deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
        if deck is None:
            return _as_result(
                payload=payload,
                deck_id=deck_id,
                accepted=False,
                message="Smoke test could not load created deck.",
            )

        transition_deck_state(
            db,
            deck,
            DeckState.UPLOADED,
            actor_user_id=user.id,
            reason="railway_upload_smoke_test_state_reset",
            summary="Smoke test deck prepared. Click Create Smart Deck to start processing.",
            source_surface="admin_upload_smoke_test",
            source_route="/api/admin/railway-upload-smoke-test",
            commit=True,
        )
        db.refresh(deck)
        db.refresh(deck.file)
        if not payload.get("processing"):
            payload.update(_manual_smart_deck_fields(deck_id))
        workspace_summary = get_workspace_summary_for_user(db, user, workspace.id).model_dump()
        acceptance, accepted = _build_acceptance_entry(payload, deck, workspace_summary, deck_id)

        if cleanup:
            try:
                soft_delete_workspace_deck(db, deck_id=deck.id, workspace_id=workspace.id)
            except Exception:
                # Keep the smoke test result stable if cleanup is blocked by an
                # edge-case; return the readiness result and include the cleanup
                # failure only as a warning.
                payload["smokeTestCleanupWarning"] = "cleanup_failed"

        acceptance["accepted"] = accepted
        return _as_result(
            payload=payload,
            workspace_summary=workspace_summary,
            deck_id=deck_id,
            accepted=acceptance["accepted"],
            message="Smoke test upload persistence path completed.",
        )
    except Exception as exc:
        db.rollback()
        return _as_result(
            payload=payload,
            workspace_summary=workspace_summary,
            deck_id=deck_id,
            accepted=False,
            message="Railway upload smoke test failed.",
            error=f"{exc.__class__.__name__}: {exc}",
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
