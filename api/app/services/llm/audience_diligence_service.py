from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.vc_finance_knowledge_context import build_vc_finance_verification_context
from app.core.security import generate_id
from app.db.models import AnalysisFinding, Deck, DeckLlmArtifact
from app.services.llm.finance_claim_extractor import extract_financial_claims_from_deck_map, extract_financial_claims_from_slides
from app.services.llm.generation_service import (
    _configured_qwen_fallback,
    _extract_json_payload,
    _load_deck,
    _resolve_claude_config,
)
from app.services.llm.prompt_package_loader import load_prompt_package
from app.services.llm.canonical_deck_intelligence_service import persist_canonical_deck_intelligence
from app.services.platform.shell.deck_map_service import get_deck_map
from app.services.brand.brand_design_tokens import build_brand_llm_context

AUDIENCE_DILIGENCE_ARTIFACT_TYPE = "audience_diligence_conversion_plan"
AUDIENCE_DILIGENCE_SCHEMA_VERSION = "audience-diligence-output.v1"
SUPPORTED_AUDIENCES = {
    "VC Partner",
    "VC Associate",
    "Investment Committee",
    "LP",
    "Strategic Corporate Buyer",
    "Accelerator Judge",
    "Board Member",
    "Fundraising Advisor Client",
    "Portfolio Founder",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_plain(value) -> dict:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {}


def _brand_context(deck: Deck) -> dict | None:
    brand = deck.brand_profile
    if not brand:
        return None
    return {
        **build_brand_llm_context(brand),
        "website": brand.company_website_url,
        "audienceLabel": brand.audience_label,
        "primaryGoal": brand.primary_goal,
        "warnings": brand.warnings_json,
    }


def _slides_context(deck: Deck) -> list[dict]:
    slides = []
    for slide in sorted(deck.slides, key=lambda item: item.slide_index):
        slides.append(
            {
                "id": slide.id,
                "slideNumber": slide.slide_number or slide.source_page_number or slide.slide_index + 1,
                "title": slide.title,
                "role": slide.role,
                "rawText": slide.raw_text,
                "summary": slide.summary,
                "narrativeNotes": slide.narrative_notes,
                "blocks": [
                    {
                        "id": block.id,
                        "blockIndex": block.block_index,
                        "type": block.block_type,
                        "text": block.raw_text,
                        "normalizedText": block.normalized_text,
                    }
                    for block in sorted(slide.blocks, key=lambda item: item.block_index)
                ],
            }
        )
    return slides


def _latest_artifact_payload(db: Session, deck_id: str, artifact_type: str) -> dict | None:
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == artifact_type,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    return artifact.payload_json if artifact and isinstance(artifact.payload_json, dict) else None


def _llm_report_insights_context(db: Session, deck_id: str) -> list[dict]:
    findings = (
        db.query(AnalysisFinding)
        .filter(AnalysisFinding.deck_id == deck_id)
        .order_by(AnalysisFinding.created_at.desc())
        .limit(12)
        .all()
    )
    return [
        {
            "id": finding.id,
            "title": finding.title,
            "detail": finding.detail,
            "severity": finding.severity,
            "category": finding.category,
            "slideId": finding.slide_id,
            "blockId": finding.block_id,
        }
        for finding in findings
    ]


def _market_research_financial_fallback(market_research: dict | None) -> dict | None:
    if not isinstance(market_research, dict) or not market_research:
        return None
    company = market_research.get("company") if isinstance(market_research.get("company"), dict) else {}
    market_sizing = market_research.get("marketSizing") if isinstance(market_research.get("marketSizing"), dict) else {}
    investment_thesis = market_research.get("investmentThesis") if isinstance(market_research.get("investmentThesis"), dict) else {}
    vc_assessment = market_research.get("vcAssessment") if isinstance(market_research.get("vcAssessment"), dict) else {}
    return {
        "company": {
            "name": company.get("name"),
            "businessModel": company.get("businessModel"),
            "fundingStage": company.get("fundingStage"),
            "totalRaised": company.get("totalRaised"),
        },
        "marketSizing": {
            "tam": market_sizing.get("tam"),
            "sam": market_sizing.get("sam"),
            "som": market_sizing.get("som"),
            "growthRate": market_sizing.get("growthRate"),
            "sourceConfidence": market_sizing.get("sourceConfidence"),
            "note": market_sizing.get("note"),
        },
        "investmentThesis": {
            "summary": investment_thesis.get("summary"),
            "strengths": investment_thesis.get("strengths") or [],
            "weaknesses": investment_thesis.get("weaknesses") or [],
        },
        "vcAssessment": {
            "score": vc_assessment.get("score"),
            "stageFit": vc_assessment.get("stageFit"),
            "concerns": vc_assessment.get("concerns") or [],
            "diligenceQuestions": vc_assessment.get("diligenceQuestions") or [],
        },
    }


def _build_context(db: Session, deck: Deck, *, selected_audience: str, conversion_goal: str | None, user_instruction: str | None) -> dict:
    deck_map = _to_plain(get_deck_map(db, deck.id))
    slides = _slides_context(deck)
    financial_claims = extract_financial_claims_from_deck_map(deck_map) or extract_financial_claims_from_slides(slides)
    market_research = _latest_artifact_payload(db, deck.id, "smart_deck_market_research")
    llm_report_insights = _llm_report_insights_context(db, deck.id)
    return {
        "schemaVersion": "audience-diligence-context.v1",
        "adaptationMode": "adapt_existing_deck_only",
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "summary": deck.summary,
            "status": deck.status,
        },
        "selectedAudience": selected_audience,
        "conversionGoal": conversion_goal,
        "userInstruction": user_instruction,
        "deckMap": deck_map,
        "slides": slides,
        "brandProfile": _brand_context(deck),
        "marketResearch": market_research,
        "llmReportInsights": llm_report_insights,
        "financialClaimsExtracted": financial_claims,
        "financialGroundingHierarchy": {
            "instructionPriority": "user_instruction_first",
            "sourcePriority": [
                {"source": "loaded_deck", "status": "ready"},
                {"source": "deck_financial_claims", "status": "ready" if financial_claims else "missing"},
                {"source": "llm_report_insights", "status": "ready" if llm_report_insights else "missing"},
                {"source": "market_research", "status": "ready" if market_research else "missing"},
            ],
            "marketResearchFinancialFallback": _market_research_financial_fallback(market_research),
        },
        "vcFinanceContext": build_vc_finance_verification_context(claims=financial_claims, audience=selected_audience),
    }


def _normalize_selected_audience(selected_audience: str | None, deck: Deck) -> str:
    raw = str(selected_audience or deck.audience or "VC Partner").strip()
    audience_map = {
        "vc_partner": "VC Partner",
        "vc associate": "VC Associate",
        "vc_associate": "VC Associate",
        "investment_committee": "Investment Committee",
        "ic": "Investment Committee",
        "lp": "LP",
        "lp / fund investor": "LP",
        "fund_partner": "LP",
        "strategic corporate buyer": "Strategic Corporate Buyer",
        "corporate": "Strategic Corporate Buyer",
        "accelerator demo day judge": "Accelerator Judge",
        "accelerator_judge": "Accelerator Judge",
        "board_member": "Board Member",
        "fundraising advisor client": "Fundraising Advisor Client",
        "advisor_client": "Fundraising Advisor Client",
        "portfolio founder": "Portfolio Founder",
        "portfolio_founder": "Portfolio Founder",
    }
    normalized = audience_map.get(raw.lower().replace("-", " "), raw)
    return normalized if normalized in SUPPORTED_AUDIENCES else raw


def _build_prompt(context: dict) -> str:
    package = load_prompt_package("audience_diligence")
    return (
        package.combined_prompt()
        + "\n\nReturn JSON only. Validate against audience-diligence-output.v1."
        + "\n\nExecution constraints:"
        + "\n- The userInstruction is the highest-priority direction when it does not conflict with evidence."
        + "\n- Adapt the existing deck only in this mode. Do not propose net-new slides or net-new financial sections."
        + "\n- Prefer loaded deck evidence and extracted deck financial claims for numbers."
        + "\n- Use llmReportInsights and marketResearch only to improve coherence, risk framing, and evidence requests."
        + "\n- If user financials are absent or weak, fall back to grounded market research; never invent numbers."
        + "\n\nAudience diligence context:\n"
        + json.dumps(context, ensure_ascii=True)
    )


def _call_llm(provider: str, model: str, api_key: str, prompt: str) -> dict:
    if provider == "anthropic":
        from app.services.llm.anthropic_provider import call_anthropic_message, extract_anthropic_text

        payload = call_anthropic_message(
            api_key=api_key,
            model=model,
            max_tokens=5000,
            system="You output only valid JSON for backend-validated audience diligence.",
            user=prompt,
            timeout=120,
        )
        return _extract_json_payload(extract_anthropic_text(payload))
    if provider == "openai":
        from app.services.llm.openai_provider import call_openai_response, extract_openai_text

        payload = call_openai_response(
            api_key=api_key,
            model=model,
            system="You output only valid JSON for backend-validated audience diligence.",
            user=prompt,
            timeout=120,
            response_format={"type": "json_object"},
        )
        return _extract_json_payload(extract_openai_text(payload))
    if provider == "openrouter":
        from app.services.llm.openrouter_provider import call_openrouter_chat_completion, extract_openrouter_text

        payload = call_openrouter_chat_completion(
            api_key=api_key,
            model=model,
            system="You output only valid JSON for backend-validated audience diligence.",
            user=prompt,
            timeout=120,
            response_format={"type": "json_object"},
        )
        return _extract_json_payload(extract_openrouter_text(payload))
    if provider == "dashscope":
        from app.services.llm.dashscope_provider import call_dashscope_chat_completion, extract_dashscope_text

        payload = call_dashscope_chat_completion(
            api_key=api_key,
            model=model,
            system="You output only valid JSON for backend-validated audience diligence.",
            user=prompt,
            timeout=120,
            response_format={"type": "json_object"},
        )
        return _extract_json_payload(extract_dashscope_text(payload))
    raise ValueError("Audience diligence requires Anthropic, OpenAI, OpenRouter, or DashScope.")


def _empty_financial_insights(financial_claims: list[dict]) -> dict:
    return {
        "overallFinancialCredibility": {"score": 50, "label": "weak" if financial_claims else "adequate", "reason": "Financial claims require evidence review."},
        "financialClaims": [
            {
                "claimType": claim.get("claimType") if claim.get("claimType") in {"market_size", "revenue_projection", "roi_claim", "unit_economics", "fundraising_ask", "valuation_claim"} else "other",
                "claimText": str(claim.get("claimText") or ""),
                "slideId": claim.get("slideId"),
                "verificationStatus": "partially_supported",
                "issue": "Claim extracted for VC finance validation.",
                "assumptions": [],
                "evidenceNeeded": ["source", "calculation logic", "assumptions"],
                "confidence": 0.45,
            }
            for claim in financial_claims[:20]
        ],
        "financialConsistencyIssues": [],
        "overstatedClaims": [],
        "missingFinancialEvidence": [],
        "saferWording": [],
        "slideImplementationInstructions": [],
    }


def _normalise_result(raw: dict, context: dict) -> dict:
    if not isinstance(raw, dict):
        raw = {}
    financial_claims = context.get("financialClaimsExtracted") or []
    slides = context.get("slides") or []
    first_slide = slides[0] if slides else {}
    result = dict(raw)
    result.setdefault("schemaVersion", AUDIENCE_DILIGENCE_SCHEMA_VERSION)
    result.setdefault("selectedAudience", context.get("selectedAudience") or "VC Partner")
    result.setdefault("conversionGoal", context.get("conversionGoal"))
    result.setdefault("audiencePriorities", [])
    result.setdefault("audienceObjections", [])
    result.setdefault("audienceDecisionCriteria", [])
    current_deck_fit = result.get("currentDeckFit") if isinstance(result.get("currentDeckFit"), dict) else {}
    deck_fit_score = int(current_deck_fit.get("score") or result.get("currentDeckFitScore") or 50)
    deck_fit_label = str(current_deck_fit.get("label") or result.get("currentDeckFit") or "usable_with_rewrites")
    deck_fit_reason = str(current_deck_fit.get("mainReason") or result.get("currentDeckFitReason") or "Audience fit requires review.")
    result["currentDeckFit"] = deck_fit_label
    result["currentDeckFitScore"] = max(0, min(100, deck_fit_score))
    result["currentDeckFitReason"] = deck_fit_reason
    result.setdefault(
        "deckDiagnosis",
        {
            "currentDeckType": context.get("deck", {}).get("purpose"),
            "currentNarrativeArc": None,
            "mainAudienceProblem": "Deck requires audience-specific diligence conversion.",
            "narrativeGap": "Narrative requires validation against selected audience priorities.",
            "evidenceGap": "Evidence requires review, especially financial evidence.",
            "strongestSlides": [],
            "weakestSlides": [],
            "duplicatedSlides": [],
            "missingSlides": [],
            "highestImpactChanges": [],
        },
    )
    result.setdefault("financialInsights", _empty_financial_insights(financial_claims))
    result.setdefault("narrativeShift", "Convert the deck for the selected audience using evidence-safe VC judgment.")
    plan = result.get("deckImplementationPlan") if isinstance(result.get("deckImplementationPlan"), dict) else {}
    result["deckImplementationPlan"] = {
        "slidesToAdd": [],
        "slidesToRewrite": plan.get("slidesToRewrite") or plan.get("slidesToRedesign") or [],
        "slidesToReorder": plan.get("slidesToReorder") or [],
        "slidesToMerge": plan.get("slidesToMerge") or [],
        "slidesToDelete": plan.get("slidesToDelete") or [],
    }
    result.setdefault("slideLevelInstructions", [])
    result.setdefault("missingEvidence", [])
    smart_deck_instruction = result.get("smartDeckInstruction") if isinstance(result.get("smartDeckInstruction"), dict) else {}
    result.setdefault(
        "smartDeckInstruction",
        {
            "task": "Review an audience-specific deck version using the audience diligence plan; keep this analysis out of visible slide copy.",
            "targetAudience": result["selectedAudience"],
            "narrativeShift": result["narrativeShift"],
            "executionRules": ["Do not invent facts.", "Mark missing evidence in this report.", "Preserve deck-backed claims.", "Do not render analysis summaries or evidence requests as slide text."],
            "sourceSlideIds": [str(slide.get("id")) for slide in slides if slide.get("id")],
            "requiresEvidenceReview": True,
        },
    )
    if smart_deck_instruction:
        result["smartDeckInstruction"] = {
            "task": smart_deck_instruction.get("task") or "Review an audience-specific deck version using the audience diligence plan; keep this analysis out of visible slide copy.",
            "targetAudience": smart_deck_instruction.get("targetAudience") or result["selectedAudience"],
            "narrativeShift": smart_deck_instruction.get("narrativeShift") or result["narrativeShift"],
            "executionRules": smart_deck_instruction.get("executionRules") or ["Do not invent facts.", "Mark missing evidence in this report.", "Preserve deck-backed claims.", "Do not render analysis summaries or evidence requests as slide text."],
            "sourceSlideIds": smart_deck_instruction.get("sourceSlideIds") or [str(slide.get("id")) for slide in slides if slide.get("id")],
            "requiresEvidenceReview": bool(smart_deck_instruction.get("requiresEvidenceReview", True)),
            "generationPrompt": smart_deck_instruction.get("generationPrompt") or result.get("narrativeShift"),
        }
    user_instruction = str(context.get("userInstruction") or "").strip()
    generation_prompt_parts = []
    if user_instruction:
        generation_prompt_parts.append(f"Primary user instruction: {user_instruction}")
    generation_prompt_parts.extend(
        [
            f"Adapt the existing deck for {result['selectedAudience']}.",
            f"Narrative shift: {result['narrativeShift']}",
            "Use deck-backed facts and extracted deck financial claims first.",
            "Use LLM report insights and market research only as supporting grounding.",
            "Do not add net-new slides or net-new financial sections in this mode.",
            "Do not invent facts, metrics, or financial assumptions.",
        ]
    )
    execution_rules = list(result["smartDeckInstruction"].get("executionRules") or []) if isinstance(result.get("smartDeckInstruction"), dict) else []
    for rule in [
        "User instruction has highest priority when it remains evidence-safe.",
        "Prefer extracted deck financial claims over market-research fallback for numeric truth.",
        "Adapt existing slides only in this mode; do not add net-new slides or financial sections.",
    ]:
        if rule not in execution_rules:
            execution_rules.append(rule)
    result["smartDeckInstruction"] = {
        **(result.get("smartDeckInstruction") or {}),
        "executionRules": execution_rules,
        "generationPrompt": " ".join(part for part in generation_prompt_parts if part),
        "targetAudience": result["selectedAudience"],
        "narrativeShift": result["narrativeShift"],
        "requiresEvidenceReview": True,
    }
    normalized_slide_instructions = []
    for item in result.get("slideLevelInstructions") or []:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        action = str(normalized.get("action") or "rewrite")
        if action in {"add", "split"}:
            if not normalized.get("slideId"):
                continue
            normalized["action"] = "rewrite"
            normalized["implementationInstruction"] = str(normalized.get("implementationInstruction") or "Rewrite the existing slide using audience-specific evidence framing.")
        normalized_slide_instructions.append(normalized)
    result["slideLevelInstructions"] = normalized_slide_instructions
    if not result["slideLevelInstructions"] and first_slide:
        result["slideLevelInstructions"] = [
            {
                "slideId": first_slide.get("id"),
                "slideTitle": first_slide.get("title"),
                "currentRole": first_slide.get("role"),
                "targetRole": "audience_evidence_slide",
                "action": "rewrite",
                "audienceProblem": "Slide needs audience-specific evidence framing.",
                "audienceReason": "The selected audience needs clearer proof and assumptions.",
                "implementationInstruction": "Rewrite safely using deck-backed facts and mark missing evidence.",
                "headlineDirection": None,
                "bodyCopyDirection": None,
                "layoutDirection": None,
                "visualDirection": None,
                "evidenceNeeded": [],
                "factsToPreserve": [],
                "claimsToSoften": [],
                "priority": "medium",
                "confidence": 0.4,
                "requiresReview": True,
            }
        ]
    result.setdefault("smartEditInstructions", [])
    result.setdefault("riskControls", {"inventedClaims": False, "factsPreserved": True, "assumptionsMarked": True, "requiresHumanReview": True})
    result.setdefault("requiresReview", True)
    result.setdefault("confidence", 0.5)
    if result["audienceObjections"] and isinstance(result["audienceObjections"], list):
        normalized_objections = []
        for item in result["audienceObjections"]:
            if isinstance(item, dict):
                normalized_objections.append(
                    {
                        "objection": str(item.get("objection") or item.get("question") or ""),
                        "whyItMatters": str(item.get("whyItMatters") or item.get("why") or ""),
                        "deckArea": str(item.get("deckArea") or item.get("area") or "general"),
                        "priority": str(item.get("priority") or "medium"),
                    }
                )
            elif str(item).strip():
                normalized_objections.append(
                    {
                        "objection": str(item),
                        "whyItMatters": "This audience is likely to challenge the current deck on this point.",
                        "deckArea": "general",
                        "priority": "medium",
                    }
                )
        result["audienceObjections"] = normalized_objections
    if not result["slideLevelInstructions"] and first_slide:
        result["slideLevelInstructions"] = [
            {
                "slideId": first_slide.get("id"),
                "slideTitle": first_slide.get("title"),
                "currentRole": first_slide.get("role"),
                "targetRole": "audience_evidence_slide",
                "action": "rewrite",
                "audienceProblem": "Slide needs audience-specific evidence framing.",
                "audienceReason": "The selected audience needs clearer proof and assumptions.",
                "implementationInstruction": "Rewrite safely using deck-backed facts and mark missing evidence.",
                "headlineDirection": None,
                "bodyCopyDirection": None,
                "layoutDirection": None,
                "visualDirection": None,
                "evidenceNeeded": [],
                "factsToPreserve": [],
                "claimsToSoften": [],
                "priority": "medium",
                "confidence": 0.4,
                "requiresReview": True,
            }
        ]
    if not result["smartEditInstructions"]:
        result["smartEditInstructions"] = [
            {
                "slideId": str(item.get("slideId") or ""),
                "instruction": str(item.get("implementationInstruction") or "Rewrite the slide using audience-specific evidence framing."),
                "priority": str(item.get("priority") or "medium"),
                "requiresReview": bool(item.get("requiresReview", True)),
            }
            for item in result["slideLevelInstructions"][:12]
            if isinstance(item, dict) and item.get("slideId")
        ]
    result.setdefault(
        "recommendedDeckVersion",
        {
            "title": f"{result['selectedAudience']} version",
            "audience": result["selectedAudience"],
            "summary": result["narrativeShift"],
            "generationPrompt": result["smartDeckInstruction"].get("generationPrompt") if isinstance(result.get("smartDeckInstruction"), dict) else result["narrativeShift"],
        },
    )
    return result


def _persist_artifact(db: Session, deck_id: str, payload: dict, *, provider: str, model: str | None) -> DeckLlmArtifact:
    artifact_id = generate_id("adl")
    artifact = DeckLlmArtifact(
        id=artifact_id,
        deck_id=deck_id,
        artifact_type=AUDIENCE_DILIGENCE_ARTIFACT_TYPE,
        artifact_key=artifact_id,
        schema_version=AUDIENCE_DILIGENCE_SCHEMA_VERSION,
        status="ready",
        summary=str(payload.get("narrativeShift") or "Audience diligence conversion plan")[:1000],
        payload_json=payload,
        metrics_json={"generatedAt": _iso_now(), "provider": provider, "model": model},
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact


def run_audience_diligence(
    db: Session,
    deck_id: str,
    *,
    selected_audience: str,
    conversion_goal: str | None = None,
    user_instruction: str | None = None,
    preferred_model: str | None = None,
) -> dict:
    deck = _load_deck(db, deck_id)
    if deck is None:
        raise ValueError("Deck not found")
    normalized_audience = _normalize_selected_audience(selected_audience, deck)
    context = _build_context(db, deck, selected_audience=normalized_audience, conversion_goal=conversion_goal, user_instruction=user_instruction)
    provider_config = _resolve_claude_config(db, deck, preferred_model, use_case="analysis")
    provider = provider_config.get("provider")
    model = provider_config.get("model")
    api_key = provider_config.get("apiKey")
    if provider in {"anthropic", "openai", "openrouter", "dashscope"} and model and api_key:
        try:
            raw = _call_llm(provider, model, api_key, _build_prompt(context))
        except Exception as exc:
            from app.services.llm.provider_errors import is_provider_capacity_error

            fallback = _configured_qwen_fallback() if provider == "dashscope" and is_provider_capacity_error(exc) else None
            if fallback is None:
                raise
            provider = fallback["provider"]
            model = fallback["model"]
            raw = _call_llm(provider, model, fallback["apiKey"], _build_prompt(context))
    else:
        raw = {}
    payload = _normalise_result(raw, context)
    artifact = _persist_artifact(db, deck_id, payload, provider=str(provider or "deterministic"), model=model)
    persist_canonical_deck_intelligence(db, deck_id)
    return {"artifactId": artifact.id, "deckId": deck_id, "status": "ready", "result": payload}


def analyze_audience_diligence(
    db: Session,
    deck_id: str,
    *,
    selected_audience: str,
    conversion_goal: str | None = None,
    user_instruction: str | None = None,
    preferred_model: str | None = None,
) -> dict:
    return run_audience_diligence(
        db,
        deck_id,
        selected_audience=selected_audience,
        conversion_goal=conversion_goal,
        user_instruction=user_instruction,
        preferred_model=preferred_model,
    )


def plan_audience_diligence(
    db: Session,
    deck_id: str,
    *,
    selected_audience: str,
    conversion_goal: str | None = None,
    user_instruction: str | None = None,
    preferred_model: str | None = None,
) -> dict:
    return run_audience_diligence(
        db,
        deck_id,
        selected_audience=selected_audience,
        conversion_goal=conversion_goal,
        user_instruction=user_instruction,
        preferred_model=preferred_model,
    )


def generate_smart_deck_instructions(
    db: Session,
    deck_id: str,
    *,
    selected_audience: str,
    conversion_goal: str | None = None,
    user_instruction: str | None = None,
    preferred_model: str | None = None,
) -> dict:
    return run_audience_diligence(
        db,
        deck_id,
        selected_audience=selected_audience,
        conversion_goal=conversion_goal,
        user_instruction=user_instruction,
        preferred_model=preferred_model,
    )


def get_latest_audience_diligence(db: Session, deck_id: str) -> dict | None:
    artifact = (
        db.query(DeckLlmArtifact)
        .filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == AUDIENCE_DILIGENCE_ARTIFACT_TYPE,
            DeckLlmArtifact.status == "ready",
        )
        .order_by(DeckLlmArtifact.created_at.desc())
        .first()
    )
    if artifact is None:
        return None
    return {"artifactId": artifact.id, "deckId": deck_id, "status": artifact.status, "result": artifact.payload_json or {}, "createdAt": artifact.created_at.isoformat() if artifact.created_at else None}
