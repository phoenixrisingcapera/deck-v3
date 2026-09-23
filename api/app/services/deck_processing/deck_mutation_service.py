"""Deck mutation service.

Owns: deck/slide/block/suggestion create, patch, analyse, and related helpers.
"""

from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.agents.adaptation_suggestion_agent import run as adaptation_suggestion_run
from app.agents.audience_alignment_agent import run as audience_alignment_run
from app.agents.block_classifier_agent import run as block_classifier_run
from app.agents.diligence_gap_agent import run as diligence_gap_run
from app.core.security import generate_id
from app.services.deck_processing.generation_workspace_service import ensure_generation_workspace
from app.db.models import (
    AdaptationSuggestion,
    AnalysisFinding,
    AnalysisRun,
    AdaptationRun,
    BlockClassification,
    Deck,
    DeckSlide,
    DeckSlideBlock,
    DeckSlideRevision,
    DeckGenerationRun,
    DeckGenerationWorkspace,
    DeckSlideVersion,
    DiligenceReport,
    SmartEditSuggestion,
    User,
    Workspace,
)
from app.services.deck_processing.state_machine import DeckState, canonical_deck_state
from app.services.deck_processing.save_confirmation import record_save_confirmation
from app.services.deck_processing.due_diligence_integrity import normalize_diligence_audience
from app.services.llm.generation_service import _resolve_claude_config
from app.services.platform.auth.user_service import ensure_workspace
from app.services.platform.shell.shell_service import record_accepted_deck_version
from app.services.visualizer.slide_read_model import _map_adaptation_suggestion, _map_block, _map_deck, _map_smart_edit_suggestion
from app.services.deck_processing.workspace_summary_service import resolve_workspace_for_user


def _resolve_workspace(db: Session, workspace_id: str) -> Workspace | None:
    return db.query(Workspace).filter(Workspace.id == workspace_id).one_or_none()


def _deck_agent_context(deck: Deck) -> dict:
    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    return {
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "status": canonical_deck_state(deck.status).value,
        },
        "slides": [
            {
                "id": slide.id,
                "slide_index": slide.slide_index,
                "slide_number": slide.slide_number or slide.source_page_number or slide.slide_index + 1,
                "title": slide.title,
                "role": slide.role,
                "semantic_slide_type": slide.semantic_slide_type,
                "summary": slide.summary,
                "raw_text": slide.raw_text,
                "blocks": [
                    {
                        "id": block.id,
                        "block_index": block.block_index,
                        "block_type": block.block_type,
                        "raw_text": block.raw_text,
                        "normalized_text": block.normalized_text,
                    }
                    for block in sorted(slide.blocks, key=lambda item: item.block_index)[:12]
                ],
            }
            for slide in slides[:20]
        ],
    }


def create_deck(db: Session, payload: dict, user_id: str | None = None) -> dict | None:
    requested_workspace_id = payload.get("workspace_id")
    workspace = _resolve_workspace(db, requested_workspace_id) if isinstance(requested_workspace_id, str) else None

    if workspace is None and user_id is not None:
        placeholder_workspace_ids = {"ws_01", "ws_demo", "ws_default"}
        if requested_workspace_id is None or requested_workspace_id in placeholder_workspace_ids:
            workspace = resolve_workspace_for_user(db, user_id)
        if workspace is None:
            user = db.query(User).filter(User.id == user_id).one_or_none()
            if user is not None:
                workspace = ensure_workspace(db, user)

    if workspace is None:
        return None
    if user_id is not None and workspace.user_id != user_id:
        return None

    deck = Deck(
        id=generate_id("deck"),
        workspace_id=workspace.id,
        user_id=user_id,
        title=payload["title"],
        audience=payload["audience"],
        purpose=payload["purpose"],
        status=DeckState.PENDING.value,
        summary="Deck record created. Upload is pending.",
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return _map_deck(deck)


def patch_block(
    db: Session,
    deck_id: str,
    block_id: str,
    text: str,
    reason: str = "Manual block edit",
    *,
    commit: bool = True,
) -> dict | None:
    block = (
        db.query(DeckSlideBlock)
        .join(DeckSlide, DeckSlide.id == DeckSlideBlock.slide_id)
        .filter(DeckSlide.deck_id == deck_id, DeckSlideBlock.id == block_id)
        .one_or_none()
    )
    if block is None:
        return None

    previous = block.raw_text
    block.raw_text = text
    block.normalized_text = text.strip()
    db.add(
        DeckSlideRevision(
            id=generate_id("rev"),
            deck_id=deck_id,
            slide_id=block.slide_id,
            block_id=block.id,
            previous_text=previous,
            next_text=text,
            reason=reason,
        )
    )
    if commit:
        db.commit()
        db.refresh(block)
    else:
        db.flush()
    return _map_block(block)


def patch_suggestion(db: Session, deck_id: str, suggestion_id: str, status: str, edited_text: str | None = None) -> dict | None:
    return patch_suggestion_with_audit(
        db,
        deck_id,
        suggestion_id,
        status,
        edited_text,
        audit_metadata=None,
    )


def patch_suggestion_with_audit(
    db: Session,
    deck_id: str,
    suggestion_id: str,
    status: str,
    edited_text: str | None = None,
    audit_metadata: dict | None = None,
) -> dict | None:
    suggestion = (
        db.query(AdaptationSuggestion)
        .filter(AdaptationSuggestion.deck_id == deck_id, AdaptationSuggestion.id == suggestion_id)
        .one_or_none()
    )
    if suggestion is not None:
        suggestion.status = status
        if edited_text:
            suggestion.suggested_text = edited_text
        _record_suggestion_audit(
            db,
            deck_id=deck_id,
            suggestion_id=suggestion.id,
            suggestion_kind="adaptation",
            decision=status,
            applied=False,
            audit_metadata=audit_metadata,
        )
        db.commit()
        db.refresh(suggestion)
        return _map_adaptation_suggestion(suggestion)

    smart_suggestion = (
        db.query(SmartEditSuggestion)
        .filter(SmartEditSuggestion.deck_id == deck_id, SmartEditSuggestion.id == suggestion_id)
        .one_or_none()
    )
    if smart_suggestion is None:
        return None

    if smart_suggestion.status != "pending":
        return _map_smart_edit_suggestion(smart_suggestion)

    smart_suggestion.status = status
    if edited_text:
        smart_suggestion.suggested_text = edited_text
    applied = False
    slide_version = None
    if status in {"accepted", "applied", "edited"}:
        patch_block(
            db,
            deck_id,
            smart_suggestion.block_id,
            smart_suggestion.suggested_text,
            reason="Smart Edit accepted" if status == "accepted" else "Smart Edit edited",
            commit=False,
        )
        slide_version = _create_smart_edit_slide_version(db, smart_suggestion)
        if slide_version is not None:
            record_accepted_deck_version(
                db,
                deck_id,
                source_surface="smart_edit",
                source_artifact_id=smart_suggestion.id,
                changed_slide_ids=[smart_suggestion.slide_id],
                change_summary=smart_suggestion.reason or "Accepted Smart Edit change.",
            )
        smart_suggestion.status = "applied" if status == "accepted" else status
        applied = True
    _record_suggestion_audit(
        db,
        deck_id=deck_id,
        suggestion_id=smart_suggestion.id,
        suggestion_kind="smart_edit",
        decision=status,
        applied=applied,
        audit_metadata=audit_metadata,
    )
    db.commit()
    db.refresh(smart_suggestion)
    mapped = _map_smart_edit_suggestion(smart_suggestion)
    if applied and slide_version is not None:
        mapped["slideVersionId"] = slide_version.id
    return mapped


def _create_smart_edit_slide_version(db: Session, suggestion: SmartEditSuggestion) -> DeckSlideVersion | None:
    """Persist an accepted Smart Edit as a DeckSlideVersion.

    The existing mutation path still creates `DeckSlideRevision` through
    `patch_block`; this additional version record gives the Smart Deck shell a
    versioned artifact to select or inspect after accept.
    """
    slide = db.query(DeckSlide).filter(DeckSlide.id == suggestion.slide_id, DeckSlide.deck_id == suggestion.deck_id).one_or_none()
    if slide is None:
        return None
    # REPLACED: The former query-then-insert path could race with source-context
    # and legacy generation workspace creation.
    # workspace = db.query(DeckGenerationWorkspace).filter(DeckGenerationWorkspace.deck_id == suggestion.deck_id).one_or_none()
    # if workspace is None:
    #     workspace = DeckGenerationWorkspace(id=generate_id("dgw"), deck_id=suggestion.deck_id, generation_status="source_ready")
    #     db.add(workspace)
    #     db.flush()
    workspace = ensure_generation_workspace(
        db,
        deck_id=suggestion.deck_id,
        generation_status="source_ready",
    )
    generation_run = DeckGenerationRun(
        id=generate_id("dgr"),
        deck_generation_workspace_id=workspace.id,
        deck_id=suggestion.deck_id,
        status="completed",
        provider="smart_edit",
        model="reviewed_suggestion",
        generation_mode="smart_edit_accept",
        scope_type="single_slide",
        request_payload_json=json.dumps({"suggestionId": suggestion.id, "runId": suggestion.run_id}),
        generated_deck_json=json.dumps({"slideId": slide.id, "blockId": suggestion.block_id, "suggestedText": suggestion.suggested_text}),
    )
    db.add(generation_run)
    version_number = int(
        db.query(func.count(DeckSlideVersion.id))
        .filter(DeckSlideVersion.deck_generation_workspace_id == workspace.id, DeckSlideVersion.source_slide_id == slide.id)
        .scalar()
        or 0
    ) + 1
    slide_version = DeckSlideVersion(
        id=generate_id("dsv"),
        deck_generation_workspace_id=workspace.id,
        generation_run_id=generation_run.id,
        source_slide_id=slide.id,
        slide_index=slide.slide_index,
        source_slide_title=slide.title,
        version_number=version_number,
        title=slide.title or f"Slide {slide.slide_index + 1}",
        status="accepted",
        generated_slide_json=json.dumps(
            {
                "source": "smart_edit_accept",
                "suggestionId": suggestion.id,
                "runId": suggestion.run_id,
                "slideId": slide.id,
                "blockId": suggestion.block_id,
                "originalText": suggestion.original_text,
                "suggestedText": suggestion.suggested_text,
                "reason": suggestion.reason,
            }
        ),
    )
    db.add(slide_version)
    db.flush()
    return slide_version


def _record_suggestion_audit(
    db: Session,
    *,
    deck_id: str,
    suggestion_id: str,
    suggestion_kind: str,
    decision: str,
    applied: bool,
    audit_metadata: dict | None,
) -> None:
    deck = db.query(Deck).filter(Deck.id == deck_id).one_or_none()
    metadata = {
        "suggestionKind": suggestion_kind,
        "decision": decision,
        "applied": applied,
        **(audit_metadata or {}),
    }
    record_save_confirmation(
        db,
        deck_id=deck_id,
        workspace_id=deck.workspace_id if deck is not None else None,
        user_id=(audit_metadata or {}).get("userId") if audit_metadata else None,
        event_type=f"smart_edit_{decision}",
        entity_type="smart_edit_suggestion",
        entity_id=suggestion_id,
        title="Smart Edit decision saved",
        message=f"Smart Edit suggestion marked {decision}.",
        source_surface="due_diligence_smart_edit",
        source_route=f"/decks/{deck_id}/due-diligence",
        dedupe_key=f"smart_edit:{deck_id}:{suggestion_id}:{decision}:{len(str(metadata))}",
        metadata=metadata,
    )


def _add_diligence_report(
    db: Session,
    *,
    deck_id: str,
    run_id: str,
    report_id: str,
    audience: str,
    status: str,
    provider_config: dict | None,
    report_json: dict | None,
    validation_verdict: str,
    workflow_job_id: str | None,
) -> None:
    db.add(
        AnalysisRun(
            id=run_id,
            deck_id=deck_id,
            status=status,
            audience=audience,
            workflow_job_id=workflow_job_id,
        )
    )
    db.add(
        DiligenceReport(
            id=report_id,
            deck_id=deck_id,
            analysis_run_id=run_id,
            workflow_job_id=workflow_job_id,
            audience=audience,
            status=status,
            degraded=status != "completed",
            provider=str((provider_config or {}).get("provider") or "") or None,
            model=str((provider_config or {}).get("model") or "") or None,
            prompt_version="diligence-gap-agent.v1",
            retrieval_trace_json={"status": "not_used", "source": "canonical_agent_context"},
            evidence_summary_json={"grounding": "deck_objects", "externalEvidenceCount": 0},
            validation_verdict=validation_verdict,
            report_json=report_json,
        )
    )


def analyse_deck(
    db: Session,
    deck_id: str,
    *,
    audience: str | None = None,
    workflow_job_id: str | None = None,
    deadline=None,
    usage_sink: dict | None = None,
) -> dict | None:
    deck = (
        db.query(Deck)
        .options(selectinload(Deck.slides).selectinload(DeckSlide.blocks))
        .filter(Deck.id == deck_id)
        .one_or_none()
    )
    if deck is None:
        return None

    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    slide_ids = {slide.id for slide in slides}
    block_ids = {block.id for slide in slides for block in slide.blocks}
    block_slide_lookup = {
        block.id: slide.id
        for slide in slides
        for block in slide.blocks
    }
    first_slide = slides[0] if slides else None
    first_block = sorted(first_slide.blocks, key=lambda item: item.block_index)[0] if first_slide and first_slide.blocks else None

    # DISABLED: replacing findings destroyed prior report history. Findings are
    # now immutable children of one report/run and reruns append new snapshots.
    # db.query(AnalysisFinding).filter(AnalysisFinding.deck_id == deck.id).delete(synchronize_session=False)
    db.query(AdaptationSuggestion).filter(AdaptationSuggestion.deck_id == deck.id).delete(synchronize_session=False)
    db.query(AdaptationRun).filter(AdaptationRun.deck_id == deck.id).delete(synchronize_session=False)
    if block_ids:
        db.query(BlockClassification).filter(BlockClassification.block_id.in_(block_ids)).delete(synchronize_session=False)

    requested_audience = normalize_diligence_audience(audience or deck.audience)
    run_id = generate_id("analysis")
    report_id = generate_id("dd_report")
    alignment = audience_alignment_run(requested_audience, deck.purpose)
    deck_context = _deck_agent_context(deck)
    # The selected audience is analysis input, not a presentation-only label.
    deck_context["deck"]["audience"] = requested_audience
    for payload in block_classifier_run(deck.id, deck_context=deck_context):
        payload_block_id = str(payload.get("block_id") or "")
        if payload_block_id not in block_ids:
            continue
        db.add(
            BlockClassification(
                id=generate_id("block_cls"),
                # BlockClassification ownership is derived through block_id;
                # the current Core model has no duplicate deck_id/slide_id fields.
                # deck_id=deck.id,
                # slide_id=block_slide_lookup[payload_block_id],
                block_id=payload_block_id,
                semantic_tag=str(payload.get("semantic_tag") or "supporting_text")[:120],
                diligence_category=str(payload.get("diligence_category") or "narrative")[:120],
                confidence=float(payload.get("confidence") if payload.get("confidence") is not None else 0.55),
            )
        )

    db.add(
        AdaptationRun(
            id=generate_id("adapt_run"),
            deck_id=deck.id,
            audience=str(alignment.get("audience_type") or requested_audience),
            purpose=str(alignment.get("purpose") or deck.purpose),
            status="completed",
        )
    )
    provider_config = _resolve_claude_config(db, deck, use_case="analysis")

    if first_slide is not None:
        diligence_payloads = diligence_gap_run(deck.id, deck_context=deck_context, provider_config=provider_config, deadline=deadline, usage_sink=usage_sink)
        if diligence_payloads is None:
            # Roll back the staged delete/replace work so the last successful
            # findings remain visible while this run is explicitly degraded.
            db.rollback()
            _add_diligence_report(
                db,
                deck_id=deck.id,
                run_id=run_id,
                report_id=report_id,
                audience=requested_audience,
                status="degraded",
                provider_config=provider_config,
                report_json={"findingIds": [], "reason": "provider_or_output_unavailable"},
                validation_verdict="degraded_no_output",
                workflow_job_id=workflow_job_id,
            )
            db.add(
                AdaptationRun(
                    id=generate_id("adapt_run"),
                    deck_id=deck.id,
                    audience=str(alignment.get("audience_type") or requested_audience),
                    purpose=str(alignment.get("purpose") or deck.purpose),
                    status="degraded",
                )
            )
            db.commit()
            from app.services.visualizer.slide_read_model import get_deck as get_deck_read

            return get_deck_read(db, deck.id)
        finding_ids: list[str] = []
        for payload in diligence_payloads:
            # DISABLED: independently falling back slide_id and block_id could
            # pair a block with the wrong slide and falsely mark it grounded.
            # payload_slide_id = payload.get("slide_id") if payload.get("slide_id") in slide_ids else first_slide.id
            # payload_block_id = payload.get("block_id") if payload.get("block_id") in block_ids else (first_block.id if first_block is not None else None)
            requested_slide_id = str(payload.get("slide_id") or "")
            requested_block_id = str(payload.get("block_id") or "")
            slide_target_is_exact = requested_slide_id in slide_ids
            payload_slide_id = requested_slide_id if slide_target_is_exact else first_slide.id
            chosen_slide = next(slide for slide in slides if slide.id == payload_slide_id)
            block_target_is_exact = (
                requested_block_id in block_ids
                and block_slide_lookup.get(requested_block_id) == payload_slide_id
            )
            chosen_slide_blocks = sorted(chosen_slide.blocks, key=lambda item: item.block_index)
            payload_block_id = (
                requested_block_id
                if block_target_is_exact
                else (chosen_slide_blocks[0].id if chosen_slide_blocks else None)
            )
            target_is_exact = slide_target_is_exact and block_target_is_exact
            target_block = next(
                (block for slide in slides for block in slide.blocks if block.id == payload_block_id),
                None,
            )
            finding_id = generate_id("finding")
            finding_ids.append(finding_id)
            db.add(
                AnalysisFinding(
                    id=finding_id,
                    deck_id=deck.id,
                    report_id=report_id,
                    analysis_run_id=run_id,
                    audience=requested_audience,
                    slide_id=payload_slide_id,
                    block_id=payload_block_id,
                    field_key=f"block:{payload_block_id}.raw_text" if payload_block_id else None,
                    target_snapshot_json={
                        "slideId": payload_slide_id,
                        "blockId": payload_block_id,
                        "fieldKey": f"block:{payload_block_id}.raw_text" if payload_block_id else None,
                        "beforeText": target_block.raw_text if target_block is not None else None,
                    },
                    evidence_json={
                        "sourceReferences": [
                            {"type": "deck_block", "slideId": payload_slide_id, "blockId": payload_block_id}
                        ] if target_is_exact and payload_block_id else [],
                        "status": "deck_context_grounded" if target_is_exact else "target_fallback_unverified",
                        "requestedTarget": {
                            "slideId": requested_slide_id or None,
                            "blockId": requested_block_id or None,
                        },
                    },
                    validation_verdict="deck_context_grounded" if target_is_exact else "target_fallback_unverified",
                    title=payload["title"],
                    detail=payload["detail"],
                    severity=payload["severity"],
                    category=payload["category"],
                )
            )
        adaptation_payloads = adaptation_suggestion_run(
            deck.id,
            requested_audience,
            deck_context=deck_context,
            provider_config=provider_config,
            deadline=deadline,
            usage_sink=usage_sink,
        )
        if adaptation_payloads is None:
            db.rollback()
            _add_diligence_report(
                db,
                deck_id=deck.id,
                run_id=run_id,
                report_id=report_id,
                audience=requested_audience,
                status="degraded",
                provider_config=provider_config,
                report_json={"findingIds": [], "reason": "adaptation_output_unavailable"},
                validation_verdict="degraded_no_output",
                workflow_job_id=workflow_job_id,
            )
            db.add(
                AdaptationRun(
                    id=generate_id("adapt_run"),
                    deck_id=deck.id,
                    audience=str(alignment.get("audience_type") or requested_audience),
                    purpose=str(alignment.get("purpose") or deck.purpose),
                    status="degraded",
                )
            )
            db.commit()
            from app.services.visualizer.slide_read_model import get_deck as get_deck_read

            return get_deck_read(db, deck.id)
        for payload in adaptation_payloads:
            payload_slide_id = payload.get("slide_id") if payload.get("slide_id") in slide_ids else first_slide.id
            payload_block_id = payload.get("block_id") if payload.get("block_id") in block_ids else (first_block.id if first_block is not None else None)
            db.add(
                AdaptationSuggestion(
                    id=generate_id("adpt"),
                    deck_id=deck.id,
                    slide_id=payload_slide_id,
                    block_id=payload_block_id,
                    title=payload["title"],
                    reason=payload["reason"],
                    suggested_text=payload["suggested_text"],
                    status="pending",
                    audience=requested_audience,
                )
            )

    else:
        db.rollback()
        _add_diligence_report(
            db,
            deck_id=deck.id,
            run_id=run_id,
            report_id=report_id,
            audience=requested_audience,
            status="degraded",
            provider_config=None,
            report_json={"findingIds": [], "reason": "deck_has_no_slides"},
            validation_verdict="degraded_no_source",
            workflow_job_id=workflow_job_id,
        )
        db.commit()
        from app.services.visualizer.slide_read_model import get_deck as get_deck_read

        return get_deck_read(db, deck.id)

    _add_diligence_report(
        db,
        deck_id=deck.id,
        run_id=run_id,
        report_id=report_id,
        audience=requested_audience,
        status="completed",
        provider_config=provider_config,
        report_json={"findingIds": finding_ids, "findingCount": len(finding_ids)},
        validation_verdict="completed_with_deck_context",
        workflow_job_id=workflow_job_id,
    )
    db.commit()
    from app.services.visualizer.slide_read_model import get_deck as get_deck_read

    return get_deck_read(db, deck.id)
