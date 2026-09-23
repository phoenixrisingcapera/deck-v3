from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.core.security import generate_id
from app.db.models import (
    AdaptationSuggestion,
    AnalysisFinding,
    AnalysisRun,
    BatchSlideDecision,
    BlockClassification,
    CompanyProfile,
    Deck,
    DeckBrandAsset,
    DeckBrandProfile,
    DeckInputSource,
    DeckLlmArtifact,
    DeckSlide,
    DeckSlideBlock,
    DeckSlideRevision,
    DesignBatch,
    DesignBatchSlide,
    DesignVersion,
    GeneratedSlide,
    GeneratedSlideCandidate,
    GenerationJob,
    SmartEditSuggestion,
    Workspace,
)
from app.services.brand.company_profile import infer_stage_from_deck
from app.services.rendering.final_deck_service import GENERATED_VERSION, ORIGINAL, save_batch_slide_decision
from app.services.deck_processing.save_confirmation import map_save_confirmation, record_save_confirmation
from app.services.brand.website_context import build_website_context
from app.services.platform.shell.iteration_retention_service import apply_iteration_retention, refresh_iteration_training_snapshot
from app.services.training.iteration_training_export_service import auto_export_pending_iteration_training_snapshots

GENERATED_SLIDE_ARTIFACT_TYPE = "smart_deck_generated_slide"

SHELL_TEMPLATE = [
    {
        "title": "Executive cover",
        "role": "cover",
        "raw_text": "{company_name} investor review",
        "narrative_notes": "Opening frame for the working session. This should immediately orient the reviewer to the company and current fundraising story.",
        "blocks": [
            {
                "block_type": "headline",
                "raw_text": "{company_name}",
                "semantic_tag": "deck_title",
                "diligence_category": "narrative",
            },
            {
                "block_type": "body",
                "raw_text": "{company_name} is preparing a tighter investor-ready version of the uploaded source deck.",
                "semantic_tag": "deck_purpose",
                "diligence_category": "positioning",
            },
        ],
    },
    {
        "title": "Problem",
        "role": "problem",
        "raw_text": "{company_name} is solving an operational bottleneck that still needs harder proof in the uploaded deck.",
        "narrative_notes": "The shell should surface proof gaps early so the team can tighten this slide before outward sharing.",
        "blocks": [
            {
                "block_type": "headline",
                "raw_text": "The problem is credible but under-sourced.",
                "semantic_tag": "problem_claim",
                "diligence_category": "market",
            },
            {
                "block_type": "body",
                "raw_text": "The current deck implies a meaningful pain point, but reviewers still need benchmark or customer evidence to trust the magnitude.",
                "semantic_tag": "unsupported_claim",
                "diligence_category": "evidence",
            },
        ],
        "finding": {
            "title": "Problem claim needs primary evidence",
            "detail": "The uploaded source deck describes the problem clearly but does not yet anchor it with primary evidence or a sourced benchmark.",
            "severity": "high",
            "category": "missing evidence",
            "block_index": 1,
        },
        "suggestion": {
            "title": "Reframe the problem for investor review",
            "reason": "Investor readers trust quantified operational framing more than broad founder language.",
            "suggested_text": "Quantify the bottleneck with one sourced benchmark and one direct customer signal before presenting the market impact.",
            "audience": "Investment Committee",
            "block_index": 0,
        },
    },
    {
        "title": "Solution",
        "role": "solution",
        "raw_text": "{company_name} offers a structured workflow improvement with a clearer value proposition than the source deck currently shows.",
        "narrative_notes": "Solution slides perform better when the product motion is explicit and the business outcome is tied to the audience.",
        "blocks": [
            {
                "block_type": "headline",
                "raw_text": "Show the product motion before the feature list.",
                "semantic_tag": "solution_claim",
                "diligence_category": "product",
            },
            {
                "block_type": "body",
                "raw_text": "Explain what changes in the customer workflow, why that change matters, and what operational result it produces.",
                "semantic_tag": "workflow_summary",
                "diligence_category": "product",
            },
        ],
    },
    {
        "title": "Traction",
        "role": "traction",
        "raw_text": "The uploaded deck signals momentum, but the shell should help restate traction with cleaner measurement windows and audience-specific proof.",
        "narrative_notes": "Traction language should survive diligence scrutiny without needing oral explanation in the meeting.",
        "blocks": [
            {
                "block_type": "metric",
                "raw_text": "Add one validated traction metric with period, cohort, and baseline.",
                "semantic_tag": "traction_metric",
                "diligence_category": "commercial_traction",
            },
            {
                "block_type": "body",
                "raw_text": "The best traction slide for this shell should make growth, retention, or workflow impact comparable at a glance.",
                "semantic_tag": "traction_context",
                "diligence_category": "evidence",
            },
        ],
        "finding": {
            "title": "Traction metric needs cohort context",
            "detail": "The narrative suggests momentum but does not yet state the sample set, timeframe, or comparison baseline.",
            "severity": "medium",
            "category": "weak traction",
            "block_index": 0,
        },
        "suggestion": {
            "title": "Tighten traction framing",
            "reason": "Reviewers need a metric that is bounded by time, sample, and business consequence.",
            "suggested_text": "Rewrite the traction claim with one metric, one timeframe, and one line on why the outcome matters to the next financing step.",
            "audience": "Investment Committee",
            "block_index": 0,
        },
    },
    {
        "title": "Team",
        "role": "team",
        "raw_text": "Team credibility should connect operator history to why this team can execute the proposed go-to-market and product motion.",
        "narrative_notes": "Team slides usually need less design work and more evidence of fit, ownership, and execution pattern.",
        "blocks": [
            {
                "block_type": "headline",
                "raw_text": "Connect founder credibility to the company problem.",
                "semantic_tag": "team_positioning",
                "diligence_category": "team",
            },
            {
                "block_type": "body",
                "raw_text": "Use one line per leader that ties prior operating context to the current company mission.",
                "semantic_tag": "team_context",
                "diligence_category": "team",
            },
        ],
    },
]


def _iso(value) -> str:
    return value.isoformat() if value is not None else ""


def _map_file(deck: Deck) -> dict | None:
    if deck.file is None:
        return None

    return {
        "id": deck.file.id,
        "filename": deck.file.filename,
        "mimeType": deck.file.mime_type,
        "size": deck.file.size,
        "uploadedAt": _iso(deck.file.uploaded_at),
    }


def _map_graph_deck(deck: Deck) -> dict:
    return {
        "id": deck.id,
        "workspaceId": deck.workspace_id,
        "title": deck.title,
        "audience": deck.audience,
        "purpose": deck.purpose,
        "status": deck.status,
        "summary": deck.summary or "",
        "createdAt": _iso(deck.created_at),
        "updatedAt": _iso(deck.updated_at),
        "file": _map_file(deck),
    }


def _map_slide(slide: DeckSlide) -> dict:
    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "slideIndex": slide.slide_index,
        "title": slide.title,
        "role": slide.role,
        "rawText": slide.raw_text,
        "narrativeNotes": slide.narrative_notes or "",
    }


def _map_block(block: DeckSlideBlock) -> dict:
    return {
        "id": block.id,
        "slideId": block.slide_id,
        "blockIndex": block.block_index,
        "rawText": block.raw_text,
        "normalizedText": block.normalized_text,
        "blockType": block.block_type,
        "position": block.position,
        "style": block.style,
    }


def _map_classification(classification: BlockClassification) -> dict:
    return {
        "id": classification.id,
        "blockId": classification.block_id,
        "semanticTag": classification.semantic_tag,
        "diligenceCategory": classification.diligence_category,
        "confidence": classification.confidence,
    }


def _map_finding(finding: AnalysisFinding) -> dict:
    return {
        "id": finding.id,
        "deckId": finding.deck_id,
        "slideId": finding.slide_id,
        "blockId": finding.block_id,
        "title": finding.title,
        "detail": finding.detail,
        "severity": finding.severity,
        "category": finding.category,
    }


def _map_suggestion(suggestion: AdaptationSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "deckId": suggestion.deck_id,
        "slideId": suggestion.slide_id,
        "blockId": suggestion.block_id,
        "title": suggestion.title,
        "reason": suggestion.reason,
        "suggestedText": suggestion.suggested_text,
        "status": suggestion.status,
        "audience": suggestion.audience,
    }


def _map_smart_edit_suggestion(suggestion: SmartEditSuggestion) -> dict:
    return {
        "id": suggestion.id,
        "runId": suggestion.run_id,
        "deckId": suggestion.deck_id,
        "slideId": suggestion.slide_id,
        "blockId": suggestion.block_id,
        "originalText": suggestion.original_text,
        "suggestedText": suggestion.suggested_text,
        "reason": suggestion.reason,
        "riskLevel": suggestion.risk_level,
        "status": suggestion.status,
    }


def _map_revision(revision: DeckSlideRevision) -> dict:
    return {
        "id": revision.id,
        "deckId": revision.deck_id,
        "slideId": revision.slide_id,
        "blockId": revision.block_id,
        "previousText": revision.previous_text,
        "nextText": revision.next_text,
        "reason": revision.reason,
        "createdAt": _iso(revision.created_at),
    }


def _load_deck_with_slides(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.workspace).selectinload(Workspace.company_profiles),
            selectinload(Deck.file),
            selectinload(Deck.brand_profile),
            selectinload(Deck.input_sources),
            selectinload(Deck.brand_assets),
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
        )
        .filter(Deck.id == deck_id)
        .first()
    )


def get_deck_graph(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None

    slides = sorted(deck.slides, key=lambda item: item.slide_index)
    blocks = [block for slide in slides for block in sorted(slide.blocks, key=lambda item: item.block_index)]
    block_ids = [block.id for block in blocks]

    classifications = []
    if block_ids:
        classifications = (
            db.query(BlockClassification)
            .filter(BlockClassification.block_id.in_(block_ids))
            .order_by(BlockClassification.block_id.asc(), BlockClassification.confidence.desc())
            .all()
        )

    return {
        "deck": _map_graph_deck(deck),
        "slides": [_map_slide(slide) for slide in slides],
        "blocks": [_map_block(block) for block in blocks],
        "classifications": [_map_classification(item) for item in classifications],
        "findings": [
            _map_finding(item)
            for item in db.query(AnalysisFinding).filter(AnalysisFinding.deck_id == deck_id).all()
        ],
        "suggestions": [
            _map_suggestion(item)
            for item in db.query(AdaptationSuggestion).filter(AdaptationSuggestion.deck_id == deck_id).all()
        ],
        "smartEditSuggestions": [
            _map_smart_edit_suggestion(item)
            for item in db.query(SmartEditSuggestion).filter(SmartEditSuggestion.deck_id == deck_id).all()
        ],
        "revisions": [
            _map_revision(item)
            for item in db.query(DeckSlideRevision)
            .filter(DeckSlideRevision.deck_id == deck_id)
            .order_by(DeckSlideRevision.created_at.desc())
            .all()
        ],
    }


def _derive_company_name(deck: Deck) -> str:
    raw_title = deck.title.strip()
    if " series " in raw_title.lower():
        return raw_title.lower().split(" series ", 1)[0].title()
    if " seed " in raw_title.lower():
        return raw_title.lower().split(" seed ", 1)[0].title()
    return raw_title


def _resolve_company_profile(deck: Deck, profile: DeckBrandProfile | None) -> CompanyProfile | None:
    if deck.workspace is None:
        return None

    target_name = profile.company_name if profile is not None and profile.company_name else _derive_company_name(deck)
    target_website = profile.company_website_url if profile is not None else None

    for company_profile in deck.workspace.company_profiles:
        if target_website and company_profile.website_url == target_website:
            return company_profile
        if target_name and company_profile.canonical_name == target_name:
            return company_profile

    return None


def _map_brand_profile(deck: Deck, profile: DeckBrandProfile | None) -> dict:
    sources_used = [source.label for source in deck.input_sources if source.label]
    brand_asset_labels = [asset.label for asset in deck.brand_assets if asset.label]
    company_profile = _resolve_company_profile(deck, profile)

    if profile is None:
        return {
            "deckId": deck.id,
            "companyName": _derive_company_name(deck),
            "companyWebsiteUrl": None,
            "contactEmail": None,
            "companyStage": infer_stage_from_deck(deck),
            "founderName": None,
            "teamSummary": None,
            "brandSummary": "Brand profile will become richer as website context and source material are connected.",
            "visualDirection": "Premium investor-facing layout with restrained colour use and strong information hierarchy.",
            "audienceLabel": deck.audience,
            "primaryGoal": deck.purpose,
            "processingStatus": "draft",
            "sourceFileName": deck.file.filename if deck.file is not None else None,
            "brandReady": False,
            "sourcesUsed": sources_used,
            "brandAssetLabels": brand_asset_labels,
            "updatedAt": _iso(deck.updated_at),
        }

    return {
        "deckId": deck.id,
        "companyName": profile.company_name,
        "companyWebsiteUrl": profile.company_website_url,
        "contactEmail": company_profile.contact_email if company_profile is not None else None,
        "companyStage": company_profile.inferred_stage if company_profile is not None else infer_stage_from_deck(deck),
        "founderName": profile.founder_name,
        "teamSummary": profile.team_summary,
        "brandSummary": profile.brand_summary,
        "visualDirection": profile.visual_direction,
        "audienceLabel": profile.audience_label or deck.audience,
        "primaryGoal": profile.primary_goal or deck.purpose,
        "processingStatus": profile.processing_status,
        "sourceFileName": deck.file.filename if deck.file is not None else None,
        "brandReady": bool(profile.company_name or profile.brand_summary or profile.visual_direction),
        "sourcesUsed": sources_used,
        "brandAssetLabels": brand_asset_labels,
        "updatedAt": _iso(profile.updated_at),
    }


def get_deck_shell_properties(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None

    return _map_brand_profile(deck, deck.brand_profile)


def update_deck_shell_properties(db: Session, deck_id: str, payload: dict) -> dict | None:
    from app.services.brand.brand_extraction import apply_manual_brand_profile_fields
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None

    profile = deck.brand_profile
    if profile is None:
        profile = DeckBrandProfile(
            id=generate_id("brand"),
            deck_id=deck.id,
            processing_status="ready",
        )
        db.add(profile)
        db.flush()

    # Persist only user-facing deck properties here so the shell stays editable without mutating slide content.
    apply_manual_brand_profile_fields(profile, payload)
    if "founderName" in payload:
        profile.founder_name = payload.get("founderName")
    if "teamSummary" in payload:
        profile.team_summary = payload.get("teamSummary")
    profile.processing_status = "ready"

    if payload.get("audienceLabel"):
        deck.audience = payload["audienceLabel"]
    if payload.get("primaryGoal"):
        deck.purpose = payload["primaryGoal"]

    company_profile = _resolve_company_profile(deck, profile)
    should_persist_company_profile = any(
        payload.get(key)
        for key in ("companyName", "companyWebsiteUrl", "founderName", "teamSummary")
    )
    if company_profile is None and should_persist_company_profile:
        company_profile = CompanyProfile(
            id=generate_id("company"),
            workspace_id=deck.workspace_id,
            canonical_name=payload.get("companyName") or _derive_company_name(deck),
        )
        db.add(company_profile)

    if company_profile is not None:
        if payload.get("companyName"):
            company_profile.canonical_name = payload["companyName"]
        if "companyWebsiteUrl" in payload:
            company_profile.website_url = payload.get("companyWebsiteUrl")
        if "founderName" in payload:
            company_profile.founder_name = payload.get("founderName")
        if "teamSummary" in payload:
            company_profile.team_summary = payload.get("teamSummary")

        if company_profile.website_url:
            website_context = build_website_context(company_profile.website_url)
            if website_context is not None and not company_profile.contact_email:
                company_profile.contact_email = website_context["contact_email_hint"]

        company_profile.inferred_stage = company_profile.inferred_stage or infer_stage_from_deck(deck)

    confirmation = record_save_confirmation(
        db,
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        user_id=deck.user_id,
        event_type="deck_properties_saved",
        entity_type="deck_properties",
        entity_id=profile.id,
        title="Deck saved successfully",
        message="Your deck properties are secure and ready for the next step.",
        source_surface="smart_deck_shell",
        source_route=f"/decks/{deck.id}/smart-deck",
        dedupe_key=f"deck_properties_saved:{deck.id}:{','.join(sorted(payload.keys()))}",
        metadata={"changedFields": sorted(payload.keys())},
    )
    db.commit()
    db.refresh(deck)
    return {
        "properties": _map_brand_profile(deck, profile),
        "confirmation": map_save_confirmation(confirmation),
    }


def _map_slide_with_blocks(slide: DeckSlide, classifications: list[BlockClassification]) -> dict:
    classification_lookup: dict[str, list[BlockClassification]] = {}
    for item in classifications:
        classification_lookup.setdefault(item.block_id, []).append(item)

    return {
        "id": slide.id,
        "deckId": slide.deck_id,
        "slideNumber": slide.slide_index,
        "title": slide.title,
        "rawText": slide.raw_text,
        "summary": slide.narrative_notes or None,
        "slideRole": slide.role or "unknown",
        "blocks": [
            {
                "id": block.id,
                "deckId": slide.deck_id,
                "slideId": slide.id,
                "blockIndex": block.block_index,
                "blockType": block.block_type,
                "rawText": block.raw_text,
                "currentText": block.raw_text,
                "normalizedText": block.normalized_text,
                "classification": (
                    {
                        "id": classification_lookup[block.id][0].id,
                        "blockId": classification_lookup[block.id][0].block_id,
                        "semanticTag": classification_lookup[block.id][0].semantic_tag,
                        "diligenceCategory": classification_lookup[block.id][0].diligence_category,
                        "confidence": classification_lookup[block.id][0].confidence,
                    }
                    if classification_lookup.get(block.id)
                    else None
                ),
            }
            for block in sorted(slide.blocks, key=lambda item: item.block_index)
        ],
    }


def create_shell_slide(db: Session, deck_id: str, payload: dict) -> dict | None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None

    next_index = max((slide.slide_index for slide in deck.slides), default=0) + 1
    slide = DeckSlide(
        id=generate_id("slide"),
        deck_id=deck.id,
        slide_index=next_index,
        title=(payload.get("title") or f"New slide {next_index}").strip(),
        role=(payload.get("role") or "appendix").strip(),
        raw_text=(payload.get("rawText") or "Add the core narrative for this slide.").strip(),
        narrative_notes="New slide created from the interactive shell. Review and refine the extracted blocks before generating a new version.",
    )
    db.add(slide)
    db.flush()

    headline_block = DeckSlideBlock(
        id=generate_id("block"),
        slide_id=slide.id,
        block_index=0,
        raw_text=slide.title,
        normalized_text=slide.title,
        block_type="headline",
    )
    body_block = DeckSlideBlock(
        id=generate_id("block"),
        slide_id=slide.id,
        block_index=1,
        raw_text=slide.raw_text,
        normalized_text=slide.raw_text,
        block_type="body",
    )
    db.add_all([headline_block, body_block])
    db.flush()

    db.add_all(
        [
            BlockClassification(
                id=generate_id("classification"),
                block_id=headline_block.id,
                semantic_tag="new_slide_title",
                diligence_category="narrative",
                confidence=0.61,
            ),
            BlockClassification(
                id=generate_id("classification"),
                block_id=body_block.id,
                semantic_tag="new_slide_body",
                diligence_category="draft_content",
                confidence=0.58,
            ),
        ]
    )

    db.commit()
    db.refresh(slide)

    classifications = (
        db.query(BlockClassification)
        .filter(BlockClassification.block_id.in_([headline_block.id, body_block.id]))
        .order_by(BlockClassification.confidence.desc())
        .all()
    )

    return _map_slide_with_blocks(slide, classifications)


def update_shell_block(db: Session, deck_id: str, block_id: str, text: str) -> dict | None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None

    block = (
        db.query(DeckSlideBlock)
        .join(DeckSlide, DeckSlideBlock.slide_id == DeckSlide.id)
        .filter(DeckSlide.deck_id == deck_id, DeckSlideBlock.id == block_id)
        .one_or_none()
    )

    if block is None:
        return None

    previous_text = block.raw_text
    normalized_text = text.strip()

    # Manual canvas edits must stay reviewable, so every saved change writes a revision row.
    block.raw_text = text
    block.normalized_text = normalized_text

    if block.block_type in {"headline", "title"}:
        block.slide.title = text

    revision = DeckSlideRevision(
        id=generate_id("rev"),
        deck_id=deck_id,
        slide_id=block.slide_id,
        block_id=block.id,
        previous_text=previous_text,
        next_text=text,
        reason="Manual shell edit",
    )

    db.add(revision)
    confirmation = record_save_confirmation(
        db,
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        user_id=deck.user_id,
        event_type="deck_block_saved",
        entity_type="deck_block",
        entity_id=block.id,
        title="Block saved successfully",
        message="Your latest content update is now part of this Smart Deck.",
        source_surface="smart_deck_shell",
        source_route=f"/decks/{deck.id}/smart-deck",
        dedupe_key=f"deck_block_saved:{deck.id}:{block.id}:{revision.id}",
        metadata={"slideId": block.slide_id, "revisionId": revision.id},
    )
    db.commit()
    db.refresh(block)
    return {
        "block": _map_block(block),
        "confirmation": map_save_confirmation(confirmation),
    }


def _map_batch_preview(batch: DesignBatch) -> dict:
    return {
        "id": batch.id,
        "versionId": batch.id,
        "deckId": batch.deck_id,
        "versionNumber": batch.version_number,
        "iterationNumber": batch.batch_number,
        "batchNumber": batch.batch_number,
        "versionName": f"Version {batch.version_number}" if batch.version_number is not None else None,
        "iterationName": batch.batch_name,
        "batchName": batch.batch_name,
        "scopeType": batch.scope_type,
        "selectedSlideCount": batch.selected_slide_count,
        "status": batch.status,
        "sourceSurface": batch.source_surface,
        "sourceArtifactId": batch.source_artifact_id,
        "sourceDesignVersionId": batch.source_design_version_id,
        "changeSummary": batch.change_summary,
        "acceptedByUserId": batch.accepted_by_user_id,
        "acceptedAt": _iso(batch.accepted_at),
        "createdAt": _iso(batch.created_at),
    }


def _map_candidate(candidate: GeneratedSlideCandidate) -> dict:
    return {
        "id": candidate.id,
        "iterationId": candidate.batch_id,
        "batchId": candidate.batch_id,
        "sourceSlideId": candidate.source_slide_id,
        "slideIndex": candidate.slide_index,
        "title": candidate.title,
        "headline": candidate.headline,
        "summary": candidate.summary,
        "status": candidate.status,
    }


def _next_batch_number(db: Session, deck_id: str) -> int:
    db.query(Deck.id).filter(Deck.id == deck_id).with_for_update().one()
    latest_batch = (
        db.query(DesignBatch)
        .filter(DesignBatch.deck_id == deck_id)
        .order_by(DesignBatch.batch_number.desc(), DesignBatch.created_at.desc())
        .first()
    )
    return int(latest_batch.batch_number if latest_batch else 0) + 1


def _next_version_number(db: Session, deck_id: str) -> int:
    latest_version = (
        db.query(DesignBatch)
        .filter(DesignBatch.deck_id == deck_id, DesignBatch.version_number.is_not(None))
        .order_by(DesignBatch.version_number.desc())
        .first()
    )
    return int(latest_version.version_number if latest_version and latest_version.version_number else 0) + 1


def _candidate_copy_from_generated_slide(generated_slide: GeneratedSlide) -> tuple[str, str]:
    render_schema = generated_slide.render_schema_json if isinstance(generated_slide.render_schema_json, dict) else {}
    elements = render_schema.get("elements") if isinstance(render_schema.get("elements"), list) else []
    text_values = [
        str(element.get("text") or "").strip()
        for element in elements
        if isinstance(element, dict) and element.get("type") == "text" and str(element.get("text") or "").strip()
    ]
    headline = text_values[0] if text_values else generated_slide.title
    summary = text_values[1] if len(text_values) > 1 else headline
    return headline[:4000], summary[:8000]


def _trim_design_batches(db: Session, deck_id: str, keep: int = 3) -> None:
    apply_iteration_retention(db, deck_id, visible_limit=keep)


def _deck_version_snapshot(db: Session, deck: Deck, version: DesignVersion | None) -> dict:
    generated_by_source = {
        slide.source_slide_id: slide
        for slide in (version.generated_slides if version is not None else [])
        if slide.source_slide_id
    }
    from app.services.rendering.export_service import build_accepted_snapshot_asset_manifests

    asset_manifests = build_accepted_snapshot_asset_manifests(
        db,
        deck.id,
        {
            slide.id: slide.render_schema_json
            for slide in generated_by_source.values()
            if isinstance(slide.render_schema_json, dict)
        },
    )
    return {
        "schemaVersion": "deck-version-snapshot.v1",
        "deckId": deck.id,
        "designVersionId": version.id if version is not None else None,
        "slides": [
            {
                "slideId": slide.id,
                "slideIndex": slide.slide_index,
                "title": slide.title,
                "rawText": slide.raw_text,
                "blocks": [
                    {
                        "blockId": block.id,
                        "blockIndex": block.block_index,
                        "blockType": block.block_type,
                        "text": block.raw_text,
                    }
                    for block in sorted(slide.blocks, key=lambda item: item.block_index)
                ],
                "generatedSlide": (
                    {
                        "generatedSlideId": generated_by_source[slide.id].id,
                        "title": generated_by_source[slide.id].title,
                        "renderSchema": generated_by_source[slide.id].render_schema_json,
                        "designTokens": (
                            None
                            if generated_by_source[slide.id].render_mode == "html_compiled.v1"
                            else generated_by_source[slide.id].design_tokens_json
                        ),
                        "assets": asset_manifests.get(generated_by_source[slide.id].id, []),
                        "previewImageUrl": generated_by_source[slide.id].preview_image_url,
                    }
                    if slide.id in generated_by_source
                    else None
                ),
            }
            for slide in sorted(deck.slides, key=lambda item: item.slide_index)
        ],
    }


def record_accepted_deck_version(
    db: Session,
    deck_id: str,
    *,
    source_surface: str,
    source_artifact_id: str,
    design_version_id: str | None = None,
    changed_slide_ids: list[str] | None = None,
    change_summary: str | None = None,
    accepted_by_user_id: str | None = None,
    keep: int = 50,
) -> dict | None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None
    # Serialize number allocation and idempotency checks on the owning deck.
    batch_number = _next_batch_number(db, deck_id)
    version_number = _next_version_number(db, deck_id)
    existing = (
        db.query(DesignBatch)
        .filter(
            DesignBatch.deck_id == deck_id,
            DesignBatch.source_surface == source_surface,
            DesignBatch.source_artifact_id == source_artifact_id,
        )
        .first()
    )
    if existing is not None:
        return _map_batch_preview(existing)
    version = None
    if design_version_id:
        version = (
            db.query(DesignVersion)
            .options(selectinload(DesignVersion.generated_slides), selectinload(DesignVersion.generation_job))
            .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == design_version_id)
            .first()
        )
        if version is None:
            return None
    elif deck.current_design_version_id:
        version = (
            db.query(DesignVersion)
            .options(selectinload(DesignVersion.generated_slides), selectinload(DesignVersion.generation_job))
            .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == deck.current_design_version_id)
            .first()
        )

    generated_slides = sorted(version.generated_slides, key=lambda item: item.slide_number) if version is not None else []
    generation_job: GenerationJob | None = version.generation_job if version is not None else None
    llm_context = generation_job.llm_context_json if generation_job and isinstance(generation_job.llm_context_json, dict) else {}
    subject_context = llm_context.get("subjectContext") if isinstance(llm_context.get("subjectContext"), dict) else {}
    batch = DesignBatch(
        id=generate_id("version"),
        deck_id=deck_id,
        batch_number=batch_number,
        version_number=version_number,
        batch_name=f"Version {version_number}",
        scope_type="whole_deck",
        prompt=(generation_job.prompt if generation_job else change_summary or source_surface).strip(),
        audience_label=(subject_context.get("audience") or deck.audience or None),
        selected_slide_count=len(deck.slides),
        status="saved",
        source_surface=source_surface,
        source_artifact_id=source_artifact_id,
        source_design_version_id=version.id if version is not None else None,
        change_summary=change_summary,
        snapshot_json=_deck_version_snapshot(db, deck, version),
        accepted_by_user_id=accepted_by_user_id,
        accepted_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()

    changed_ids = set(changed_slide_ids or [])
    for source_slide in sorted(deck.slides, key=lambda item: item.slide_index):
        db.add(
            DesignBatchSlide(
                id=generate_id("batchslide"),
                batch_id=batch.id,
                slide_id=source_slide.id,
                slide_index_snapshot=source_slide.slide_index,
                slide_title_snapshot=source_slide.title,
            )
        )
    decided_source_slide_ids: set[str] = set()
    for generated_slide in generated_slides:
        headline, summary = _candidate_copy_from_generated_slide(generated_slide)
        candidate = GeneratedSlideCandidate(
            id=generate_id("candidate"),
            batch_id=batch.id,
            source_slide_id=generated_slide.source_slide_id,
            slide_index=max(0, generated_slide.slide_number - 1),
            title=generated_slide.title,
            headline=headline,
            summary=summary,
            status="applied" if not changed_ids or generated_slide.source_slide_id in changed_ids else "unchanged",
        )
        db.add(candidate)
        db.flush()
        db.add(
            DeckLlmArtifact(
                id=generate_id("artifact"),
                deck_id=deck_id,
                artifact_type=GENERATED_SLIDE_ARTIFACT_TYPE,
                artifact_key=candidate.id,
                schema_version="generated_slide.v1",
                status="valid",
                summary=f"Persisted generated slide for deck version {version_number}.",
                payload_json={
                    "generatedSlideId": generated_slide.id,
                    "schemaJson": generated_slide.render_schema_json,
                    "renderSchema": generated_slide.render_schema_json,
                    "previewImageUrl": generated_slide.preview_image_url,
                    "batchId": batch.id,
                    "sourceSlideId": generated_slide.source_slide_id,
                },
                metrics_json={"candidateId": candidate.id, "designVersionId": version.id if version else None},
            )
        )
        # Whole-deck narrative reconstruction is intentionally not one output
        # slide per input slide. Several generated slides may therefore share
        # the same primary source slide. The accepted-history decision table is
        # a legacy source-slide index with a unique (deck, batch, slide)
        # contract, so persist one representative decision per source slide
        # while retaining every generated candidate and artifact above.
        if (
            generated_slide.source_slide_id
            and generated_slide.source_slide_id not in decided_source_slide_ids
        ):
            db.add(
                BatchSlideDecision(
                    id=generate_id("decision"),
                    deck_id=deck_id,
                    batch_id=batch.id,
                    slide_id=generated_slide.source_slide_id,
                    generated_slide_candidate_id=candidate.id,
                    choice=GENERATED_VERSION,
                    decided_by_user_id=accepted_by_user_id,
                )
            )
            decided_source_slide_ids.add(generated_slide.source_slide_id)
    db.flush()
    refresh_iteration_training_snapshot(db, batch.id, source_surface=source_surface)
    _trim_design_batches(db, deck_id, keep=keep)
    return _map_batch_preview(batch)


def sync_design_version_to_batch(db: Session, deck_id: str, design_version_id: str, *, keep: int = 50) -> dict | None:
    version = (
        db.query(DesignVersion)
        .options(selectinload(DesignVersion.generated_slides), selectinload(DesignVersion.generation_job))
        .filter(DesignVersion.deck_id == deck_id, DesignVersion.id == design_version_id)
        .first()
    )
    if version is None:
        return None

    return record_accepted_deck_version(
        db,
        deck_id,
        source_surface="smart_deck",
        source_artifact_id=version.id,
        design_version_id=version.id,
        change_summary=version.summary or version.name,
        keep=keep,
    )


def _candidate_slide_type(slide_index: int) -> str:
    slide_types = ["cover", "problem", "solution", "market", "product", "traction", "business_model", "ask"]
    return slide_types[slide_index % len(slide_types)] if slide_types else "generic"


def _build_candidate_code_payload(
    deck_id: str,
    batch: DesignBatch,
    candidate: GeneratedSlideCandidate,
) -> tuple[dict, dict, str, list[str]]:
    schema_json = {
        "schema": "generated_slide.v1",
        "generatedSlideId": candidate.id,
        "deckId": deck_id,
        "batchId": batch.id,
        "sourceSlideId": candidate.source_slide_id,
        "slideIndex": candidate.slide_index,
        "slideType": _candidate_slide_type(candidate.slide_index),
        "title": candidate.title,
        "blocks": [
            {
                "id": f"{candidate.id}_heading",
                "type": "heading",
                "text": candidate.headline,
                "role": "primary",
                "x": 72,
                "y": 72,
                "w": 780,
                "h": 84,
            },
            {
                "id": f"{candidate.id}_summary",
                "type": "body",
                "text": candidate.summary,
                "role": "secondary",
                "x": 72,
                "y": 188,
                "w": 640,
                "h": 160,
            },
        ],
    }
    render_schema = {
        "renderer": "schema_json",
        "generatedSlideId": candidate.id,
        "canvas": "16:9",
        "composition": "two_column" if candidate.slide_index % 2 == 0 else "three_cards",
        "safeMarginPx": 64,
        "executableCode": False,
    }

    validation_messages: list[str] = []
    if not schema_json.get("title"):
        validation_messages.append("title missing")
    if not schema_json.get("blocks"):
        validation_messages.append("blocks missing")
    if not render_schema.get("renderer"):
        validation_messages.append("renderer missing")

    validation_status = "valid" if len(validation_messages) == 0 else "invalid"
    if validation_status == "valid":
        validation_messages = [
            "schema_json present",
            "render_schema present",
            "no executable frontend provider code",
        ]

    return schema_json, render_schema, validation_status, validation_messages


def _upsert_candidate_code_artifact(
    db: Session,
    deck_id: str,
    batch: DesignBatch,
    candidate: GeneratedSlideCandidate,
) -> DeckLlmArtifact:
    existing = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == GENERATED_SLIDE_ARTIFACT_TYPE,
            DeckLlmArtifact.artifact_key == candidate.id,
        )
        .first()
    )

    schema_json, render_schema, validation_status, validation_messages = _build_candidate_code_payload(deck_id, batch, candidate)
    payload_json = {
        "generatedSlideId": candidate.id,
        "schemaJson": schema_json,
        "renderSchema": render_schema,
        "validationStatus": validation_status,
        "validationMessages": validation_messages,
        "batchId": batch.id,
        "sourceSlideId": candidate.source_slide_id,
        "prompt": batch.prompt,
    }

    if existing is None:
        existing = DeckLlmArtifact(
            id=generate_id("artifact"),
            deck_id=deck_id,
            artifact_type=GENERATED_SLIDE_ARTIFACT_TYPE,
            artifact_key=candidate.id,
            schema_version="generated_slide.v1",
            status=validation_status,
            summary=f"Generated Smart Deck code artifact for candidate {candidate.id}.",
            payload_json=payload_json,
            metrics_json={
                "candidateId": candidate.id,
                "batchId": batch.id,
                "sourceSlideId": candidate.source_slide_id,
            },
        )
        db.add(existing)
    else:
        existing.schema_version = "generated_slide.v1"
        existing.status = validation_status
        existing.summary = f"Generated Smart Deck code artifact for candidate {candidate.id}."
        existing.payload_json = payload_json
        existing.metrics_json = {
            "candidateId": candidate.id,
            "batchId": batch.id,
            "sourceSlideId": candidate.source_slide_id,
        }
        existing.updated_at = datetime.utcnow()

    return existing


def _map_batch_detail(batch: DesignBatch) -> dict:
    return {
        **_map_batch_preview(batch),
        "prompt": batch.prompt,
        "audienceLabel": batch.audience_label,
        "snapshot": batch.snapshot_json,
        "selectedSlideIds": [item.slide_id for item in sorted(batch.selected_slides, key=lambda slide: slide.slide_index_snapshot)],
        "candidateSlides": [_map_candidate(item) for item in sorted(batch.candidate_slides, key=lambda candidate: candidate.slide_index)],
    }


def _record_shell_revision(db: Session, deck_id: str, block: DeckSlideBlock, next_text: str, reason: str) -> None:
    if block.raw_text == next_text:
        return

    revision = DeckSlideRevision(
        id=generate_id("rev"),
        deck_id=deck_id,
        slide_id=block.slide_id,
        block_id=block.id,
        previous_text=block.raw_text,
        next_text=next_text,
        reason=reason,
    )
    db.add(revision)
    block.raw_text = next_text
    block.normalized_text = next_text.strip()


def _apply_candidate_to_source_slide(db: Session, deck_id: str, candidate: GeneratedSlideCandidate) -> None:
    if candidate.source_slide_id is None:
        return

    source_slide = (
        db.query(DeckSlide)
        .options(selectinload(DeckSlide.blocks))
        .filter(DeckSlide.id == candidate.source_slide_id, DeckSlide.deck_id == deck_id)
        .one_or_none()
    )
    if source_slide is None:
        return

    blocks = sorted(source_slide.blocks, key=lambda item: item.block_index)
    headline_block = next((block for block in blocks if block.block_type in {"headline", "title"}), None)
    body_block = next((block for block in blocks if block.block_type in {"body", "bullet", "quote"}), None)

    if headline_block is None:
        headline_block = DeckSlideBlock(
            id=generate_id("block"),
            slide_id=source_slide.id,
            block_index=len(blocks),
            raw_text=candidate.headline,
            normalized_text=candidate.headline.strip(),
            block_type="headline",
        )
        db.add(headline_block)
    else:
        _record_shell_revision(db, deck_id, headline_block, candidate.headline, "Applied generated slide version")

    if body_block is None:
        body_block = DeckSlideBlock(
            id=generate_id("block"),
            slide_id=source_slide.id,
            block_index=len(blocks) + 1,
            raw_text=candidate.summary,
            normalized_text=candidate.summary.strip(),
            block_type="body",
        )
        db.add(body_block)
    else:
        _record_shell_revision(db, deck_id, body_block, candidate.summary, "Applied generated slide version")

    # The original file remains preserved; this updates only the live review slot after explicit acceptance.
    source_slide.title = candidate.title
    source_slide.raw_text = candidate.summary
    source_slide.narrative_notes = candidate.summary


def review_generated_slide_candidate(
    db: Session,
    deck_id: str,
    batch_id: str,
    candidate_id: str,
    decision: str,
) -> dict | None:
    if decision not in {"keep_version", "keep_original"}:
        raise ValueError("Unsupported candidate review decision")

    batch = (
        db.query(DesignBatch)
        .options(
            selectinload(DesignBatch.selected_slides),
            selectinload(DesignBatch.candidate_slides),
        )
        .filter(DesignBatch.id == batch_id, DesignBatch.deck_id == deck_id)
        .first()
    )
    if batch is None:
        return None

    candidate = next((item for item in batch.candidate_slides if item.id == candidate_id), None)
    if candidate is None:
        return None
    if candidate.source_slide_id is None:
        raise ValueError("Generated slide candidate is not linked to a source slide")

    save_batch_slide_decision(
        db,
        deck_id,
        batch_id,
        candidate.source_slide_id,
        choice=GENERATED_VERSION if decision == "keep_version" else ORIGINAL,
        generated_slide_candidate_id=candidate.id if decision == "keep_version" else None,
        commit=False,
    )

    refresh_iteration_training_snapshot(db, batch_id, source_surface="iteration_review")
    db.commit()
    auto_export_pending_iteration_training_snapshots(db)

    refreshed_batch = (
        db.query(DesignBatch)
        .options(
            selectinload(DesignBatch.selected_slides),
            selectinload(DesignBatch.candidate_slides),
        )
        .filter(DesignBatch.id == batch_id, DesignBatch.deck_id == deck_id)
        .first()
    )
    if refreshed_batch is None:
        return None

    return _map_batch_detail(refreshed_batch)


def list_design_batches(db: Session, deck_id: str, limit: int = 3) -> list[dict]:
    batches = (
        db.query(DesignBatch)
        .filter(DesignBatch.deck_id == deck_id, DesignBatch.status != "archived")
        .order_by(DesignBatch.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_map_batch_preview(batch) for batch in batches]


def list_deck_versions(db: Session, deck_id: str, limit: int = 50) -> list[dict]:
    versions = (
        db.query(DesignBatch)
        .filter(DesignBatch.deck_id == deck_id, DesignBatch.version_number.is_not(None), DesignBatch.status != "archived")
        .order_by(DesignBatch.version_number.desc())
        .limit(limit)
        .all()
    )
    return [_map_batch_preview(version) for version in versions]


def get_design_batch(db: Session, deck_id: str, batch_id: str) -> dict | None:
    batch = (
        db.query(DesignBatch)
        .options(
            selectinload(DesignBatch.selected_slides),
            selectinload(DesignBatch.candidate_slides),
        )
        .filter(DesignBatch.id == batch_id, DesignBatch.deck_id == deck_id, DesignBatch.status != "archived")
        .first()
    )
    if batch is None:
        return None
    return _map_batch_detail(batch)


def get_deck_version(db: Session, deck_id: str, version_id: str) -> dict | None:
    batch = (
        db.query(DesignBatch)
        .options(selectinload(DesignBatch.selected_slides), selectinload(DesignBatch.candidate_slides))
        .filter(
            DesignBatch.id == version_id,
            DesignBatch.deck_id == deck_id,
            DesignBatch.version_number.is_not(None),
            DesignBatch.status != "archived",
        )
        .first()
    )
    return _map_batch_detail(batch) if batch is not None else None


def get_generated_slide_candidate_code(
    db: Session,
    deck_id: str,
    batch_id: str,
    candidate_id: str,
) -> dict | None:
    batch = (
        db.query(DesignBatch)
        .options(selectinload(DesignBatch.candidate_slides))
        .filter(DesignBatch.id == batch_id, DesignBatch.deck_id == deck_id, DesignBatch.status != "archived")
        .first()
    )
    if batch is None:
        return None

    candidate = next((item for item in batch.candidate_slides if item.id == candidate_id), None)
    if candidate is None:
        return None

    artifact = _upsert_candidate_code_artifact(db, deck_id, batch, candidate)
    db.commit()

    payload = artifact.payload_json or {}
    return {
        "generatedSlideId": candidate.id,
        "schemaJson": payload.get("schemaJson", {}),
        "renderSchema": payload.get("renderSchema", {}),
        "validationStatus": payload.get("validationStatus", "unknown"),
        "validationMessages": payload.get("validationMessages", []),
    }


def _generate_candidate_summary(slide: DeckSlide, prompt: str, finding_titles: list[str], suggestion_titles: list[str]) -> tuple[str, str]:
    prompt_sentence = prompt.strip().rstrip(".")
    issue_line = finding_titles[0] if finding_titles else "the source deck narrative"
    suggestion_line = suggestion_titles[0] if suggestion_titles else "a cleaner investor-ready framing"

    headline = f"{slide.title} · reviewable version"
    summary = (
        f"Use {prompt_sentence}. This candidate tightens {issue_line.lower()} and leans into {suggestion_line.lower()} "
        f"without overwriting the uploaded source slide."
    )
    return headline, summary


def create_design_batch(db: Session, deck_id: str, payload: dict) -> dict | None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return None

    all_slides = sorted(deck.slides, key=lambda item: item.slide_index)
    if payload["scopeType"] == "whole_deck":
        selected_slides = all_slides
    else:
        selected_ids = set(payload.get("selectedSlideIds", []))
        selected_slides = [slide for slide in all_slides if slide.id in selected_ids]

    if not selected_slides:
        return None

    batch_number = _next_batch_number(db, deck_id)

    batch = DesignBatch(
        id=generate_id("batch"),
        deck_id=deck.id,
        batch_number=batch_number,
        batch_name=(payload.get("iterationName") or payload.get("batchName") or f"Iteration {batch_number}").strip(),
        scope_type=payload["scopeType"],
        prompt=payload["prompt"].strip(),
        audience_label=payload.get("audienceLabel") or deck.audience,
        selected_slide_count=len(selected_slides),
        status="completed",
        use_brand_profile=payload.get("useBrandProfile", True),
        use_website_context=payload.get("useWebsiteContext", True),
        use_block_classifications=payload.get("useBlockClassifications", True),
    )
    db.add(batch)
    db.flush()

    findings = db.query(AnalysisFinding).filter(AnalysisFinding.deck_id == deck_id).all()
    suggestions = db.query(AdaptationSuggestion).filter(AdaptationSuggestion.deck_id == deck_id).all()

    for slide in selected_slides:
        db.add(
            DesignBatchSlide(
                id=generate_id("batchslide"),
                batch_id=batch.id,
                slide_id=slide.id,
                slide_index_snapshot=slide.slide_index,
                slide_title_snapshot=slide.title,
            )
        )

        slide_finding_titles = [item.title for item in findings if item.slide_id == slide.id]
        slide_suggestion_titles = [item.title for item in suggestions if item.slide_id == slide.id]
        headline, summary = _generate_candidate_summary(
            slide=slide,
            prompt=batch.prompt,
            finding_titles=slide_finding_titles,
            suggestion_titles=slide_suggestion_titles,
        )

        candidate = GeneratedSlideCandidate(
            id=generate_id("candidate"),
            batch_id=batch.id,
            source_slide_id=slide.id,
            slide_index=slide.slide_index,
            title=slide.title,
            headline=headline,
            summary=summary,
            status="reviewable",
        )
        db.add(candidate)
        db.flush()
        _upsert_candidate_code_artifact(db, deck.id, batch, candidate)

    refresh_iteration_training_snapshot(db, batch.id, source_surface="shell_create")
    apply_iteration_retention(db, deck_id)
    db.commit()
    auto_export_pending_iteration_training_snapshots(db)
    return get_design_batch(db, deck_id, batch.id)


def seed_shell_artifacts_for_deck(db: Session, deck_id: str) -> None:
    deck = _load_deck_with_slides(db, deck_id)
    if deck is None:
        return

    if deck.slides:
        if deck.brand_profile is None:
            db.add(
                DeckBrandProfile(
                    id=generate_id("brand"),
                    deck_id=deck.id,
                    company_name=_derive_company_name(deck),
                    audience_label=deck.audience,
                    primary_goal=deck.purpose,
                    brand_summary="Brand profile generated from the uploaded source deck and ready for review.",
                    visual_direction="Calm, structured, investor-grade presentation system.",
                    processing_status="ready",
                )
            )
            db.commit()
        return

    company_name = _derive_company_name(deck)
    brand_profile = DeckBrandProfile(
        id=generate_id("brand"),
        deck_id=deck.id,
        company_name=company_name,
        audience_label=deck.audience,
        primary_goal=deck.purpose,
        brand_summary="Brand profile generated from the uploaded source deck and ready for review.",
        visual_direction="Calm, structured, investor-grade presentation system.",
        processing_status="ready",
    )
    db.add(brand_profile)
    db.add(
        AnalysisRun(
            id=generate_id("analysis"),
            deck_id=deck.id,
            status="completed",
        )
    )

    for slide_index, template in enumerate(SHELL_TEMPLATE, start=1):
        slide = DeckSlide(
            id=generate_id("slide"),
            deck_id=deck.id,
            slide_index=slide_index,
            title=template["title"],
            role=template["role"],
            raw_text=template["raw_text"].format(company_name=company_name),
            narrative_notes=template["narrative_notes"],
        )
        db.add(slide)
        db.flush()
        created_blocks: list[DeckSlideBlock] = []

        for block_index, block_template in enumerate(template["blocks"]):
            block = DeckSlideBlock(
                id=generate_id("block"),
                slide_id=slide.id,
                block_index=block_index,
                raw_text=block_template["raw_text"].format(company_name=company_name),
                normalized_text=block_template["raw_text"].format(company_name=company_name),
                block_type=block_template["block_type"],
            )
            db.add(block)
            db.flush()
            created_blocks.append(block)

            db.add(
                BlockClassification(
                    id=generate_id("classification"),
                    block_id=block.id,
                    semantic_tag=block_template["semantic_tag"],
                    diligence_category=block_template["diligence_category"],
                    confidence=0.88 if block_template["block_type"] == "headline" else 0.79,
                )
            )

        if template.get("finding") is not None:
            finding_template = template["finding"]
            finding_block = created_blocks[finding_template["block_index"]]
            db.add(
                AnalysisFinding(
                    id=generate_id("finding"),
                    deck_id=deck.id,
                    slide_id=slide.id,
                    block_id=finding_block.id,
                    title=finding_template["title"],
                    detail=finding_template["detail"],
                    severity=finding_template["severity"],
                    category=finding_template["category"],
                )
            )

        if template.get("suggestion") is not None:
            suggestion_template = template["suggestion"]
            suggestion_block = created_blocks[suggestion_template["block_index"]]
            db.add(
                AdaptationSuggestion(
                    id=generate_id("suggestion"),
                    deck_id=deck.id,
                    slide_id=slide.id,
                    block_id=suggestion_block.id,
                    title=suggestion_template["title"],
                    reason=suggestion_template["reason"],
                    suggested_text=suggestion_template["suggested_text"],
                    status="pending",
                    audience=suggestion_template["audience"],
                )
            )

    deck.summary = "Uploaded deck converted into a reviewable Smart Deck shell with extracted slides, blocks, classifications, and recommendations."
    db.commit()
