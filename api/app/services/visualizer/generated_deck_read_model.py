from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.ai.diligence_knowledge_context import build_diligence_workspace_context
from app.core.security import generate_id
from app.db.models import AnalysisFinding, AnalysisRun, AudienceProfile, Deck, DeckSlide, DeckSlideBlock, DeckSlideRevision, DiligenceReport
from app.services.llm.audience_diligence_service import get_latest_audience_diligence
from app.services.deck_processing.deck_mutation_service import patch_block
from app.services.deck_processing.due_diligence_integrity import normalize_diligence_audience
from app.services.visualizer.slide_read_model import get_deck


def _severity_weight(severity: str) -> int:
    if severity == "high":
        return 4
    if severity == "medium":
        return 2
    return 1


def _normalize_audience(audience: str | None) -> str:
    return normalize_diligence_audience(audience)


def _evidence_status_from_severity(severity: str) -> str:
    if severity == "low":
        return "present"
    if severity == "medium":
        return "weak"
    return "missing"


def _risk_from_severity(severity: str) -> str:
    if severity == "high":
        return "high"
    if severity == "medium":
        return "medium"
    return "low"


def _domain_label(domain: str) -> str:
    labels = {
        "market": "Market",
        "competition": "Competition",
        "team": "Team",
        "traction": "Traction",
        "financials": "Financials",
        "product": "Product",
        "legal": "Legal",
        "risk": "Risk",
        "unknown": "General",
    }
    return labels.get((domain or "").lower(), str(domain).title() or "General")


def _load_deck_model(db: Session, deck_id: str) -> Deck | None:
    return (
        db.query(Deck)
        .options(
            selectinload(Deck.slides).selectinload(DeckSlide.blocks),
            selectinload(Deck.slides).selectinload(DeckSlide.assets),
        )
        .filter(Deck.id == deck_id)
        .one_or_none()
    )


def _load_audience_profile(db: Session, audience: str | None) -> dict | None:
    if not audience:
        return None
    profile = db.query(AudienceProfile).filter(AudienceProfile.label == audience).first()
    if profile is None:
        profile = db.query(AudienceProfile).filter(AudienceProfile.label.ilike(f"%{audience}%")).first()
    if profile is None:
        return None
    return {"label": profile.label, "focus": profile.focus, "tone": profile.tone}


def _parse_field_key(field_key: str) -> tuple[str, str | None]:
    if field_key.startswith("deck."):
        return "deck", field_key.split(".", 1)[1]
    if field_key.startswith("slide:") and ".title" in field_key:
        return "slide", "title"
    if field_key.startswith("slide:") and ".summary" in field_key:
        return "slide", "summary"
    if field_key.startswith("block:") and field_key.endswith(".raw_text"):
        return "block", "raw_text"
    return "unknown", None


def _find_slide(deck: Deck, slide_id: str | None) -> DeckSlide | None:
    if not slide_id:
        return None
    return next((slide for slide in deck.slides if slide.id == slide_id), None)


def _find_block(deck: Deck, block_id: str | None) -> DeckSlideBlock | None:
    if not block_id:
        return None
    for slide in deck.slides:
        for block in slide.blocks:
            if block.id == block_id:
                return block
    return None


def get_diligence_workspace(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck_model(db, deck_id)
    if deck is None:
        return None
    deck_payload = get_deck(db, deck_id)
    if deck_payload is None:
        return None
    audience_profile = _load_audience_profile(db, deck.audience)
    return build_diligence_workspace_context(
        deck=deck_payload.get("deck") or {},
        findings=deck_payload.get("findings") or [],
        suggestions=deck_payload.get("suggestions") or [],
        smart_edit_suggestions=deck_payload.get("smart_edit_suggestions") or [],
        slides=deck_payload.get("slides") or [],
        audience_profile=audience_profile,
    )


def build_due_diligence_workspace_payload(
    db: Session,
    deck_id: str,
    *,
    audience: str | None = None,
    selected_only: bool = True,
) -> dict | None:
    deck = _load_deck_model(db, deck_id)
    if deck is None:
        return None

    deck_payload = get_deck(db, deck_id)
    if deck_payload is None:
        return None

    # DISABLED HISTORICAL READ MODEL (Phase 2 integrity replacement):
    # Reason: this deck-wide implementation mixed findings from every rerun and
    # relabelled them with whichever audience was currently selected. It also
    # treated AnalysisRun as the report instead of reading immutable reports.
    #
    # payload = build_diligence_workspace_context(
    #     deck=deck_payload.get("deck") or {},
    #     findings=deck_payload.get("findings") or [],
    #     suggestions=deck_payload.get("suggestions") or [],
    #     smart_edit_suggestions=deck_payload.get("smart_edit_suggestions") or [],
    #     slides=deck_payload.get("slides") or [],
    #     audience_profile=_load_audience_profile(db, audience or deck.audience),
    # )
    # findings = deck_payload.get("findings") or []
    # latest_run = (
    #     db.query(AnalysisRun.id, AnalysisRun.status, AnalysisRun.created_at)
    #     .filter(AnalysisRun.deck_id == deck_id)
    #     .order_by(AnalysisRun.created_at.desc())
    #     .first()
    # )
    # recent_runs = (
    #     db.query(AnalysisRun.id, AnalysisRun.status, AnalysisRun.created_at)
    #     .filter(AnalysisRun.deck_id == deck_id)
    #     .order_by(AnalysisRun.created_at.desc())
    #     .limit(5)
    #     .all()
    # )
    # run_id = latest_run[0] if latest_run else None
    # latest_run_status = str(latest_run[1]) if latest_run else "not_run"
    # latest_run_at = latest_run[2].isoformat() if latest_run and latest_run[2] is not None else None
    # analysis_run_count = db.query(AnalysisRun).filter(AnalysisRun.deck_id == deck_id).count()

    selected_audience = _normalize_audience(audience or deck.audience)
    latest_report = (
        db.query(DiligenceReport)
        .filter(DiligenceReport.deck_id == deck_id, DiligenceReport.audience == selected_audience)
        .order_by(DiligenceReport.created_at.desc(), DiligenceReport.id.desc())
        .first()
    )
    display_report = (
        db.query(DiligenceReport)
        .filter(
            DiligenceReport.deck_id == deck_id,
            DiligenceReport.audience == selected_audience,
            DiligenceReport.status == "completed",
        )
        .order_by(DiligenceReport.created_at.desc(), DiligenceReport.id.desc())
        .first()
    )
    report_count = db.query(DiligenceReport).filter(DiligenceReport.deck_id == deck_id).count()
    report_findings = []
    if display_report is not None:
        report_findings = [
            {
                "id": finding.id,
                "deck_id": finding.deck_id,
                "report_id": finding.report_id,
                "analysis_run_id": finding.analysis_run_id,
                "audience": finding.audience,
                "slide_id": finding.slide_id,
                "block_id": finding.block_id,
                "field_key": finding.field_key,
                "target_snapshot": finding.target_snapshot_json,
                "evidence": finding.evidence_json,
                "validation_verdict": finding.validation_verdict,
                "title": finding.title,
                "detail": finding.detail,
                "severity": finding.severity,
                "category": finding.category,
            }
            for finding in db.query(AnalysisFinding)
            .filter(AnalysisFinding.report_id == display_report.id)
            .order_by(AnalysisFinding.severity.desc(), AnalysisFinding.title.asc())
            .all()
        ]

    # Legacy unlinked findings remain readable until the migration backfill has
    # run, but they are never relabelled as another audience's report.
    findings_for_report = report_findings if report_count else (deck_payload.get("findings") or [])
    payload = build_diligence_workspace_context(
        deck=deck_payload.get("deck") or {},
        findings=findings_for_report,
        suggestions=deck_payload.get("suggestions") or [],
        smart_edit_suggestions=deck_payload.get("smart_edit_suggestions") or [],
        slides=deck_payload.get("slides") or [],
        # DISABLED: querying with the raw human-readable value could miss the
        # normalized AudienceProfile used by persisted reports.
        # audience_profile=_load_audience_profile(db, audience or deck.audience),
        audience_profile=_load_audience_profile(db, selected_audience),
    )
    latest_audience_diligence = get_latest_audience_diligence(db, deck_id)

    findings = findings_for_report
    suggestions = deck_payload.get("suggestions") or []
    if selected_audience in {"lp", "investment_committee", "family_office", "fund_partner", "institutional"}:
        show_lp_view = True
    elif selected_audience in {"growth_equity", "series_a_vc", "seed_vc", "corporate", "angel"}:
        show_lp_view = False
    else:
        show_lp_view = False

    recent_reports = (
        db.query(DiligenceReport)
        .filter(DiligenceReport.deck_id == deck_id)
        .order_by(DiligenceReport.created_at.desc(), DiligenceReport.id.desc())
        .limit(5)
        .all()
    )
    if recent_reports:
        recent_run_payloads = [
            {
                "id": item.analysis_run_id,
                "status": item.status,
                "reportId": item.id,
                "audience": item.audience,
                "degraded": item.degraded,
                "provider": item.provider,
                "model": item.model,
                "promptVersion": item.prompt_version,
                "validationVerdict": item.validation_verdict,
                "created_at": item.created_at.isoformat() if item.created_at is not None else "",
            }
            for item in recent_reports
        ]
        run_id = latest_report.analysis_run_id if latest_report is not None else None
        latest_run_status = latest_report.status if latest_report is not None else "not_run"
        latest_run_at = latest_report.created_at.isoformat() if latest_report is not None else None
        analysis_run_count = report_count
    else:
        # Compatibility for databases before the report backfill migration.
        legacy_runs = (
            db.query(AnalysisRun)
            .filter(AnalysisRun.deck_id == deck_id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .limit(5)
            .all()
        )
        recent_run_payloads = [
            {
                "id": item.id,
                "status": item.status,
                "audience": item.audience,
                "degraded": item.status != "completed",
                "created_at": item.created_at.isoformat() if item.created_at is not None else "",
            }
            for item in legacy_runs
        ]
        run_id = legacy_runs[0].id if legacy_runs else None
        latest_run_status = legacy_runs[0].status if legacy_runs else "not_run"
        latest_run_at = legacy_runs[0].created_at.isoformat() if legacy_runs else None
        analysis_run_count = db.query(AnalysisRun).filter(AnalysisRun.deck_id == deck_id).count()

    claims = []
    domains: dict[str, dict[str, object]] = {}
    high_count = 0
    medium_count = 0
    low_count = 0
    category_counts: dict[str, int] = {}

    for finding in findings:
        finding_category = str(finding.get("category") or "general").lower()
        category_counts[finding_category] = category_counts.get(finding_category, 0) + 1
        severity = str(finding.get("severity") or "medium").lower()
        severity = "high" if severity not in {"high", "medium", "low"} else severity
        if severity == "high":
            high_count += 1
        elif severity == "medium":
            medium_count += 1
        else:
            low_count += 1

        risk = _risk_from_severity(severity)
        recommended_action = "request_source" if severity in {"high", "medium"} else "verify"
        if finding.get("title"):
            claims.append(
                {
                    "id": finding["id"],
                    "claim_text": finding["title"],
                    "claim_type": "evidence_gap",
                    "slide_id": finding.get("slide_id"),
                    "slide_title": next(
                        (
                            item.get("title")
                            for item in deck_payload.get("slides", [])
                            if item.get("id") == finding.get("slide_id")
                        ),
                        None,
                    ),
                    "blockId": finding.get("block_id"),
                    "fieldKey": finding.get("field_key"),
                    "findingDetail": finding.get("detail"),
                    "evidence": finding.get("evidence"),
                    "validationVerdict": finding.get("validation_verdict"),
                    "evidence_status": _evidence_status_from_severity(severity),
                    "risk_level": risk,
                    "confidence": 0.45 + (3 - _severity_weight(severity)) * 0.08,
                    "recommended_action": recommended_action,
                }
            )

        normalized = finding_category if finding_category in {"market", "competition", "team", "traction", "financials", "product", "legal", "risk"} else "unknown"
        domain = domains.setdefault(
            normalized,
            {
                "key": normalized,
                "label": _domain_label(normalized),
                "score": 70.0,
                "status": "review_needed",
                "findings": [],
                "count": 0,
                "severity": "low",
            },
        )
        domain["count"] = int(domain["count"]) + 1  # type: ignore[assignment]
        domain["findings"].append((finding.get("title") or finding.get("detail") or "Evidence issue"))

        if severity == "high":
            domain["status"] = "needs_source"
            domain["severity"] = "high"
            domain["score"] = max(20.0, float(domain["score"]) - 16)  # type: ignore[union-attr]
        elif severity == "medium":
            domain["status"] = "weak_evidence"
            domain["severity"] = "medium" if domain["severity"] != "high" else "high"
            domain["score"] = max(40.0, float(domain["score"]) - 10)  # type: ignore[union-attr]
        else:
            domain["score"] = min(92.0, float(domain["score"]) + 2)  # type: ignore[union-attr]

    domain_items = []
    for domain_key in ("market", "team", "traction", "financials", "product", "competition", "legal", "risk", "unknown"):
        if domain_key not in domains:
            continue
        domain = domains[domain_key]
        domain_score = float(round(float(domain["score"]), 1))
        domain_status = "ready" if int(category_counts.get(domain_key, 0)) == 0 else "pending_review"
        if domain["status"] != "review_needed":
            domain_status = str(domain["status"])
        domain_items.append(
            {
                "key": str(domain["key"]),
                "label": str(domain["label"]),
                "score": domain_score,
                "status": domain_status,
                "findings": list(domain["findings"]),
            }
        )

    evidence_score = 100 - (high_count * 12 + medium_count * 6 + low_count * 2)
    readiness_score = max(35, min(100, evidence_score))
    if not findings:
        readiness_score = 0
    evidence_quality = "high" if evidence_score > 90 else "medium" if evidence_score > 75 else "low"
    market_risk = "high" if high_count > 2 else "medium" if high_count else "low"
    ic_readiness = "needs_partner_review" if high_count or medium_count else "ready_for_memo_draft"

    strong_points = [suggestion.get("title") for suggestion in suggestions[:4] if suggestion.get("title")]
    if not strong_points:
        strong_points = [f"Potential found in {item.get('label', 'deck context')}" for item in payload.get("slideClassification", [])[:4]]

    weak_points = [item.get("detail") for item in findings[:4] if item.get("detail")]
    likely_questions = []
    for idx, finding in enumerate(findings[:5], start=1):
        if finding.get("title"):
            likely_questions.append(f"What supports {finding['title']}?")
        if idx >= 4:
            break

    risk_items = []
    for finding in findings[:6]:
        if not finding.get("title"):
            continue
        risk_items.append(
            {
                "risk": finding.get("title"),
                "category": str(finding.get("category") or "general"),
                "severity": _risk_from_severity(str(finding.get("severity") or "medium").lower()),
                "evidence": finding.get("detail") or "",
                "mitigation": "Request evidence source, refresh the relevant deck slide, and add methodology notes.",
            }
        )

    lp_view = {
        "fund_return_potential": "high" if evidence_score > 84 else "medium" if evidence_score > 60 else "low",
        "portfolio_fit": "strong" if readiness_score >= 70 else "medium",
        "follow_on_reserve_pressure": "low" if readiness_score >= 72 else "high" if readiness_score < 50 else "medium",
        "exit_pathway_clarity": "medium" if readiness_score > 55 else "low",
        "concern": "No legal disclosure or exit path update was detected." if evidence_score < 90 else None,
    }
    if not show_lp_view:
        lp_view = {
            "fund_return_potential": "medium",
            "portfolio_fit": "medium",
            "follow_on_reserve_pressure": "medium",
            "exit_pathway_clarity": "low",
            "concern": "LP view is visible for LP, IC, Fund Partner and Institutional audiences.",
        }

    if selected_only:
        domain_items = [item for item in domain_items if item["findings"]]
        if not domain_items:
            domain_items = []

    return {
        "deck_id": deck.id,
        "run_id": run_id,
        "analysis_run_count": analysis_run_count,
        "latest_analysis_run_at": latest_run_at,
        "recent_analysis_runs": recent_run_payloads,
        "status": latest_run_status,
        "selected_audience": selected_audience,
        "summary": {
            "investment_readiness_score": readiness_score,
            "evidence_quality": evidence_quality,
            "market_claim_risk": market_risk,
            "ic_readiness": ic_readiness,
            "lp_suitability": lp_view["portfolio_fit"],
        },
        "domains": domain_items,
        "claims": claims,
        "audience_fit": {
            "audience": selected_audience,
            "fit_score": min(100, max(24, readiness_score - high_count * 4)),
            "strengths": strong_points[:5],
            "weaknesses": weak_points[:6],
            "likely_questions": likely_questions,
        },
        "ic_memo": {
            "thesis": (
                f"{deck.title or 'This deck'} may be investable if evidence and methodology for market claims are validated."
            ),
            "reasons_to_believe": strong_points[:3],
            "main_risks": [item.get("title") for item in findings[:4] if item.get("title")],
            "recommendation": (
                "proceed_to_deeper_diligence" if evidence_score < 80 else "ready_for_partner_review"
            ),
        },
        "lp_view": lp_view,
        "risk_register": risk_items,
        "diligence_workspace": payload,
        "audience_diligence": (latest_audience_diligence or {}).get("result") if isinstance(latest_audience_diligence, dict) else None,
        "deck_implementation_plan": (((latest_audience_diligence or {}).get("result") or {}).get("deckImplementationPlan")) if isinstance(latest_audience_diligence, dict) else None,
        "slide_level_instructions": (((latest_audience_diligence or {}).get("result") or {}).get("slideLevelInstructions")) if isinstance(latest_audience_diligence, dict) else None,
        "smart_deck_instruction": (((latest_audience_diligence or {}).get("result") or {}).get("smartDeckInstruction")) if isinstance(latest_audience_diligence, dict) else None,
        "smart_edit_instructions": (((latest_audience_diligence or {}).get("result") or {}).get("smartEditInstructions")) if isinstance(latest_audience_diligence, dict) else None,
        "knowledgeMetadata": payload.get("knowledgeMetadata"),
        "slide_classification": payload.get("slideClassification"),
    }


def list_editable_fields(db: Session, deck_id: str) -> dict | None:
    deck = _load_deck_model(db, deck_id)
    if deck is None:
        return None
    fields = [
        {
            "fieldKey": "deck.title",
            "label": "Deck title",
            "value": deck.title,
            "scope": "deck",
            "sourceType": "deck",
            "usageCount": 1,
            "usageSummary": "Used in the deck header and workspace title.",
        },
        {
            "fieldKey": "deck.audience",
            "label": "Audience",
            "value": deck.audience,
            "scope": "deck",
            "sourceType": "deck",
            "usageCount": 1,
            "usageSummary": "Used for due diligence guidance and prompt context.",
        },
        {
            "fieldKey": "deck.purpose",
            "label": "Purpose",
            "value": deck.purpose,
            "scope": "deck",
            "sourceType": "deck",
            "usageCount": 1,
            "usageSummary": "Used across Smart Deck and due diligence surfaces.",
        },
        {
            "fieldKey": "deck.summary",
            "label": "Summary",
            "value": deck.summary,
            "scope": "deck",
            "sourceType": "deck",
            "usageCount": 1,
            "usageSummary": "Used as short context in workspace cards.",
        },
    ]
    for slide in sorted(deck.slides, key=lambda item: item.slide_index):
        fields.append(
            {
                "fieldKey": f"slide:{slide.id}.title",
                "label": f"Slide {slide.slide_index + 1} title",
                "value": slide.title,
                "scope": "slide",
                "sourceType": "slide",
                "slideId": slide.id,
                "usageCount": 1,
                "usageSummary": slide.role or "Slide title used in navigation and review surfaces.",
            }
        )
        fields.append(
            {
                "fieldKey": f"slide:{slide.id}.summary",
                "label": f"Slide {slide.slide_index + 1} summary",
                "value": slide.summary,
                "scope": "slide",
                "sourceType": "slide",
                "slideId": slide.id,
                "usageCount": 1,
                "usageSummary": "Used in slide preview and diligence context.",
            }
        )
        for block in sorted(slide.blocks, key=lambda item: item.block_index):
            fields.append(
                {
                    "fieldKey": f"block:{block.id}.raw_text",
                    "label": f"Slide {slide.slide_index + 1} block {block.block_index + 1}",
                    "value": block.raw_text,
                    "scope": "block",
                    "sourceType": "block",
                    "slideId": slide.id,
                    "blockId": block.id,
                    "usageCount": 1,
                    "usageSummary": "Used as the primary editable text payload for Smart Edit.",
                }
            )
    return {"deckId": deck_id, "fields": fields}


def get_editable_field(db: Session, deck_id: str, field_key: str) -> dict | None:
    payload = list_editable_fields(db, deck_id)
    if payload is None:
        return None
    return next((field for field in payload["fields"] if field["fieldKey"] == field_key), None)


def preview_field_change(db: Session, deck_id: str, field_key: str, value: str) -> dict | None:
    deck = _load_deck_model(db, deck_id)
    if deck is None:
        return None
    field_type, _ = _parse_field_key(field_key)
    affected_slides = []
    affected_blocks = []
    if field_type == "deck":
        affected_slides = [{"id": slide.id, "title": slide.title} for slide in sorted(deck.slides, key=lambda item: item.slide_index)[:5]]
    elif field_type == "slide":
        slide_id = field_key.split(":", 1)[1].split(".", 1)[0]
        slide = _find_slide(deck, slide_id)
        if slide is not None:
            affected_slides = [{"id": slide.id, "title": slide.title}]
            affected_blocks = [{"id": block.id, "text": block.raw_text} for block in sorted(slide.blocks, key=lambda item: item.block_index)]
    elif field_type == "block":
        block_id = field_key.split(":", 1)[1].split(".", 1)[0]
        block = _find_block(deck, block_id)
        if block is not None:
            affected_blocks = [{"id": block.id, "text": block.raw_text}]
            affected_slides = [{"id": block.slide_id, "title": block.slide.title if block.slide else None}]
    return {
        "schemaVersion": "change-request-preview.v1",
        "deckId": deck_id,
        "fieldKey": field_key,
        "nextValue": value,
        "affectedSlides": affected_slides,
        "affectedBlocks": affected_blocks,
        "rebuildNeeded": field_type in {"deck", "slide", "block"},
        "changeRequest": {
            "id": generate_id("change"),
            "fieldKey": field_key,
            "value": value,
            "status": "preview",
        },
    }


def apply_field_change(db: Session, deck_id: str, field_key: str, value: str) -> dict | None:
    deck = _load_deck_model(db, deck_id)
    if deck is None:
        return None
    field_type, field_name = _parse_field_key(field_key)
    if field_type == "deck" and field_name:
        setattr(deck, field_name, value)
        db.commit()
        db.refresh(deck)
        return {
            "schemaVersion": "change-request-apply.v1",
            "applied": True,
            "deckId": deck_id,
            "fieldKey": field_key,
            "value": value,
            "rebuildJob": {
                "id": generate_id("rebuild"),
                "status": "completed",
                "summary": f"Applied {field_key} to deck metadata.",
            },
        }
    if field_type == "slide":
        slide_id = field_key.split(":", 1)[1].split(".", 1)[0]
        slide = _find_slide(deck, slide_id)
        if slide is None or field_name is None:
            return None
        setattr(slide, field_name, value)
        db.commit()
        db.refresh(slide)
        return {
            "schemaVersion": "change-request-apply.v1",
            "applied": True,
            "deckId": deck_id,
            "fieldKey": field_key,
            "value": value,
            "rebuildJob": {
                "id": generate_id("rebuild"),
                "status": "completed",
                "summary": f"Applied {field_key} to slide metadata.",
            },
        }
    if field_type == "block":
        block_id = field_key.split(":", 1)[1].split(".", 1)[0]
        block = _find_block(deck, block_id)
        if block is None:
            return None
        patched = patch_block(db, deck_id, block.id, value, reason=f"Applied change request for {field_key}")
        return {
            "schemaVersion": "change-request-apply.v1",
            "applied": True,
            "deckId": deck_id,
            "fieldKey": field_key,
            "value": value,
            "patchedBlock": patched,
            "rebuildJob": {
                "id": generate_id("rebuild"),
                "status": "completed",
                "summary": f"Applied {field_key} to block text.",
            },
        }
    return None
