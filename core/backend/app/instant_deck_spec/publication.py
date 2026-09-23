"""Pure fail-closed publication planning for the disabled offline slice."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from .compiler import CompiledDeck


class OfflinePublicationRejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OfflinePublicationState:
    current_design_version_id: str | None
    published_design_version_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OfflinePublicationCandidate:
    design_version_id: str
    compilation_hash: str
    slide_count: int


def build_publication_candidate(
    *,
    design_version_id: str,
    compiled: CompiledDeck | None,
    chromium_report: Mapping[str, Any] | None,
) -> OfflinePublicationCandidate:
    if compiled is None:
        raise OfflinePublicationRejected("compiled_deck_required")
    if not chromium_report or chromium_report.get("passed") is not True:
        raise OfflinePublicationRejected("complete_chromium_proof_required")
    if chromium_report.get("deckContentSha256") != compiled.content_sha256:
        raise OfflinePublicationRejected("chromium_compilation_identity_mismatch")
    passed_ids = {row.get("slideId") for row in chromium_report.get("slides") or [] if row.get("passed") is True}
    if passed_ids != {slide.slide_id for slide in compiled.slides}:
        raise OfflinePublicationRejected("chromium_slide_proof_incomplete")
    if not design_version_id.strip():
        raise OfflinePublicationRejected("design_version_identity_required")
    return OfflinePublicationCandidate(
        design_version_id=design_version_id.strip(),
        compilation_hash=compiled.content_sha256,
        slide_count=len(compiled.slides),
    )


def apply_publication_candidate(
    state: OfflinePublicationState,
    candidate: OfflinePublicationCandidate,
) -> OfflinePublicationState:
    if candidate.design_version_id in state.published_design_version_ids:
        raise OfflinePublicationRejected("immutable_design_version_already_published")
    return replace(
        state,
        current_design_version_id=candidate.design_version_id,
        published_design_version_ids=(*state.published_design_version_ids, candidate.design_version_id),
    )
