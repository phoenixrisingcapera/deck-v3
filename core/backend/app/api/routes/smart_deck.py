import hashlib
import json

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from typing import Any
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_user_deck_or_404
from app.db.models import DeckBrandProfile, User
from app.schemas.deck_workflow import WorkflowApplyRequest, WorkflowGenerationRequest
from app.schemas.smart_deck import (
    CreateSmartDeckMessageInput,
    ApplyElementVersionResponse,
    CreateManualEditJobInput,
    CreateManualEditJobResponse,
    CreateSmartDeckAssistantRunInput,
    CreateElementVariationJobInput,
    CreateElementVariationJobResponse,
    CreateSmartDeckGenerationJobInput,
    CreateSmartDeckGenerationJobResponse,
    DesignTokenResponse,
    DesignTokensRouteResponse,
    DesignVersionsRouteResponse,
    GeneratedSlideCodeArtifactsResponse,
    GeneratedSlideCodeRouteResponse,
    GeneratedSlideThumbnailResponse,
    GeneratedSlideSceneGraphResponse,
    GenerationJobResponse,
    SmartDeckMessageResponse,
    SmartDeckAssistantRunResponse,
    SmartDeckMessagesRouteResponse,
    SmartDeckPreferenceResponse,
    SmartDeckWorkspaceResponse,
    UpdateSmartDeckSessionStateInput,
    UpdateSmartDeckSelectionInput,
    UpdateSmartDeckPreferenceInput,
    UpdateGeneratedSlideTypographyInput,
)
from app.schemas.smart_deck_agent import SmartDeckAgentGenerateInput
from app.services.platform.billing.ai_usage_quota_service import enforce_ai_generation_quota
from app.services.platform.billing.rate_limit_service import enforce_rate_limit
from app.services.admin.security_audit import record_security_event
from app.services.admin.failure_tickets import create_failure_ticket
from app.services.deck_processing.workflow_orchestration import WorkflowConflictError, queue_apply_design_version, queue_smart_deck_generation
from app.services.deck_processing.workflow_state_read_model import get_workflow_job as get_workflow_job_contract
from app.services.deck_processing.source_structure_read_model import get_deck_structure
from app.services.admin.guardrail_client import evaluate_deck_guardrail
from app.services.llm.generation_service import (
    ManualEditConflictError,
    SmartDeckProviderUnavailableError,
    apply_element_version,
    apply_design_version,
    create_smart_deck_assistant_run,
    create_element_variation_job,
    create_manual_edit_job,
    create_smart_deck_message,
    discard_design_version,
    get_generated_slide_code,
    get_generated_slide_scene_graph,
    get_generated_slide_code_artifact_urls,
    get_generation_provider_config,
    get_smart_deck_workspace,
    list_design_versions,
    list_smart_deck_messages,
    restore_design_version,
    save_generated_slide_code_thumbnail,
    update_smart_deck_preferences,
    update_smart_deck_selection,
    update_generated_slide_typography,
)
from app.services.visualizer.slide_read_model import list_design_tokens
from app.services.brand.brand_design_tokens import build_brand_llm_context

# Canonical backend owner for Smart Deck product APIs. In production this router
# is mounted under `/api/products/deck-aistack-codes`, while the frontend uses
# `/api/decks/*` server routes as authenticated proxies into this contract.
router = APIRouter(prefix="/decks", tags=["smart-deck"])


def _record_smart_deck_failure(
    *,
    db: Session,
    request: Request,
    actor: User,
    deck_id: str,
    stage: str,
    action: str,
    error: BaseException,
    status_code: int,
    workspace_id: str | None = None,
) -> None:
    try:
        create_failure_ticket(
            db,
            {
                "route": str(request.url.path),
                "apiPath": str(request.url.path),
                "statusCode": status_code,
                "errorName": error.__class__.__name__,
                "errorMessage": str(error),
                "severity": "high" if status_code >= 500 else "medium",
                "source": "backend",
                "deckId": deck_id,
                "userId": actor.id,
                "userEmail": actor.email,
                "context": {
                    "stage": stage,
                    "action": action,
                    "workspaceId": workspace_id,
                    "requestId": getattr(getattr(request, "state", None), "request_id", None),
                    "deckId": deck_id,
                },
            },
            request=request,
            current_user=actor,
            commit=True,
        )
    except Exception:
        pass


def _deck_workspace_id(deck: Any | None) -> str | None:
    return getattr(getattr(deck, "smart_deck_workspace", None), "id", None)


def _agent_generation_payload(payload: SmartDeckAgentGenerateInput, *, selected_slide_ids: list[str] | None = None) -> CreateSmartDeckGenerationJobInput:
    return CreateSmartDeckGenerationJobInput(
        prompt=payload.userPrompt,
        selectedSourceSlideIds=selected_slide_ids if selected_slide_ids is not None else payload.selectedSlideIds,
        deckType=payload.deckType,
        audience=payload.audience,
        preferredModel=payload.preferredModel,
        selectedElementId=payload.selectedElementId,
        selectedSubject=payload.selectedSubject,
        detectedSubjects=[item.model_dump() for item in payload.detectedSubjects],
        actionId=payload.actionId,
        actionPrompt=payload.actionPrompt,
        userPrompt=payload.userPrompt,
        latestBatchId=payload.latestBatchId,
    )


def _selected_slide_ids_for_agent(db: Session, deck_id: str, requested_ids: list[str]) -> list[str]:
    """Use requested slide ids, or default to the first extracted source slide."""
    if requested_ids:
        return list(requested_ids)
    structure = get_deck_structure(db, deck_id)
    slides = [slide for slide in structure.get("slides") or [] if isinstance(slide, dict) and slide.get("id")]
    return [str(slides[0]["id"])] if slides else []


def _workflow_generation_idempotency_key(deck_id: str, payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{deck_id}:workflow-generation:{digest}"


def create_generation_job(db: Session, deck_id: str, *, current_user_id: str, payload: WorkflowGenerationRequest) -> dict[str, Any]:
    """Compatibility seam for tests and older integrations.

    The implementation remains the durable workflow queue; the name exists so
    failure masking tests can patch the generation seam directly.
    """
    # DISABLED: route-local Smart Deck context readiness duplicated the durable
    # workflow queue guard and could block generation before the canonical
    # workflow-state conflict response. The queue remains the owner of readiness.
    # _require_smart_deck_context_ready(db, deck_id)
    return queue_smart_deck_generation(db, deck_id, current_user_id=current_user_id, payload=payload)


def generate_smart_deck_agent(db: Session, deck_id: str, *, current_user_id: str, payload: SmartDeckAgentGenerateInput) -> dict[str, Any]:
    """Compatibility seam for Smart Agent generation enqueueing."""
    # DISABLED: route-local Smart Deck context readiness duplicated the durable
    # workflow queue guard and could block generation before the canonical
    # workflow-state conflict response. The queue remains the owner of readiness.
    # _require_smart_deck_context_ready(db, deck_id)
    generation_payload = _agent_generation_payload(payload, selected_slide_ids=_selected_slide_ids_for_agent(db, deck_id, payload.selectedSlideIds))
    workflow_request = WorkflowGenerationRequest(
        prompt=generation_payload.prompt,
        selectedSourceSlideIds=list(generation_payload.selectedSourceSlideIds),
        idempotencyKey=_workflow_generation_idempotency_key(
            deck_id,
            {
                "prompt": generation_payload.prompt,
                "selectedSourceSlideIds": generation_payload.selectedSourceSlideIds,
                "deckType": generation_payload.deckType,
                "audience": generation_payload.audience,
                "preferredModel": generation_payload.preferredModel,
                "selectedElementId": generation_payload.selectedElementId,
                "selectedSubject": generation_payload.selectedSubject,
                "actionId": generation_payload.actionId,
                "actionPrompt": generation_payload.actionPrompt,
                "userPrompt": generation_payload.userPrompt,
                "latestBatchId": generation_payload.latestBatchId,
                "detectedSubjects": generation_payload.detectedSubjects,
            },
        ),
        deckType=generation_payload.deckType,
        audience=generation_payload.audience,
        preferredModel=generation_payload.preferredModel,
        selectedElementId=generation_payload.selectedElementId,
        selectedSubject=generation_payload.selectedSubject,
        actionId=generation_payload.actionId,
        actionPrompt=generation_payload.actionPrompt,
        userPrompt=generation_payload.userPrompt,
        latestBatchId=generation_payload.latestBatchId,
        detectedSubjects=generation_payload.detectedSubjects,
    )
    return queue_smart_deck_generation(db, deck_id, current_user_id=current_user_id, payload=workflow_request)


def _brand_profile_payload(profile: DeckBrandProfile | None) -> dict[str, Any] | None:
    """Return the brand context shape the Smart Deck UI/LLM can consume."""
    if profile is None:
        return None
    llm_context = build_brand_llm_context(profile)
    return {
        "id": profile.id,
        "companyName": profile.company_name,
        "companyWebsiteUrl": profile.company_website_url,
        "logoUrl": profile.logo_url,
        "visualStyle": profile.visual_style,
        "visualDirection": profile.visual_direction,
        "palette": profile.palette_json or [],
        "colors": llm_context.get("colors") or {},
        "tokens": llm_context.get("tokens") or {},
        "fontCandidates": profile.font_candidates_json or [],
        "confidenceScore": profile.confidence_score,
        "processingStatus": profile.processing_status,
        "sourceMode": profile.source_mode,
    }


def _source_facts_from_slides(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build stable evidence facts from extracted source slide text.

    This is the minimum viable source-fact package for context readiness. Later
    research workers can add market/team/competitor facts, but LLM generation can
    already cite these deck-backed facts safely.
    """
    facts: list[dict[str, Any]] = []
    for slide in slides:
        slide_id = str(slide.get("id") or "")
        slide_index = int(slide.get("slideIndex") or 0)
        raw_text = str(slide.get("rawText") or "").strip()
        if not slide_id or not raw_text:
            continue
        parts = [part.strip(" -:\t") for part in raw_text.replace("\n", " ").split(".") if part.strip(" -:\t")]
        for fact_index, text in enumerate(parts[:6], start=1):
            facts.append(
                {
                    "fact_id": f"fact_slide_{slide_index + 1:03d}_{fact_index:02d}",
                    "type": "deck_text",
                    "source": slide_id,
                    "slideIndex": slide_index,
                    "value": text[:500],
                }
            )
    return facts


def _deck_map_from_slides(slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify the current deck narrative from persisted slide labels."""
    archetypes: dict[str, str] = {}
    missing_sections: list[str] = []
    required = {"problem", "solution", "market", "business_model", "traction", "team", "competition", "ask"}
    seen: set[str] = set()
    narrative_flow: list[dict[str, Any]] = []
    for slide in slides:
        slide_id = str(slide.get("id") or "")
        role = str(slide.get("role") or slide.get("semanticSlideType") or "unknown").lower()
        title = str(slide.get("title") or "")
        normalized_role = _normalize_slide_archetype(role, title)
        if slide_id:
            archetypes[slide_id] = normalized_role
        seen.add(normalized_role)
        narrative_flow.append({"slideId": slide_id, "slideIndex": slide.get("slideIndex"), "title": title, "archetype": normalized_role})
    for section in sorted(required - seen):
        missing_sections.append(section)
    return {
        "sections": narrative_flow,
        "slide_archetypes": archetypes,
        "narrative_flow": narrative_flow,
        "missing_sections": missing_sections,
        "weak_sections": [],
    }


def _normalize_slide_archetype(role: str, title: str) -> str:
    haystack = f"{role} {title}".lower()
    mappings = {
        "problem": ["problem", "pain", "challenge"],
        "solution": ["solution", "product", "platform"],
        "market": ["market", "tam", "sam", "som", "opportunity"],
        "business_model": ["business model", "pricing", "revenue model"],
        "traction": ["traction", "growth", "customers", "revenue", "metrics"],
        "team": ["team", "founder", "leadership", "advisor"],
        "competition": ["competition", "competitor", "landscape"],
        "ask": ["ask", "funding", "raise", "use of funds"],
    }
    for archetype, tokens in mappings.items():
        if any(token in haystack for token in tokens):
            return archetype
    return role or "unknown"


def _smart_deck_context_readiness(db: Session, deck_id: str) -> dict[str, bool]:
    """Check the minimum deterministic context needed before LLM generation."""
    structure = get_deck_structure(db, deck_id)
    slides = list(structure.get("slides") or [])
    source_workspace = structure.get("sourceWorkspace") if isinstance(structure.get("sourceWorkspace"), dict) else None
    source_facts = _source_facts_from_slides(slides)
    thumbnails_ready = bool(slides) and all(bool(slide.get("thumbnailPath") or slide.get("thumbnailUrl")) for slide in slides)
    extracted_text_ready = bool(slides) and any(bool(str(slide.get("rawText") or "").strip()) for slide in slides)
    return {
        "slidesExist": bool(slides),
        "thumbnailsExist": thumbnails_ready,
        "extractedTextExists": extracted_text_ready,
        "smartDeckContextExists": bool(source_workspace),
        "sourceFactsExist": bool(source_facts),
    }


def _require_smart_deck_context_ready(db: Session, deck_id: str) -> None:
    readiness = _smart_deck_context_readiness(db, deck_id)
    if all(readiness.values()):
        return
    missing = [key for key, ready in readiness.items() if not ready]
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "smart_deck_context_not_ready",
            "message": "Smart Deck context is still processing. Wait until slides, thumbnails, extracted text, and source facts are ready.",
            "recoverable": True,
            "nextAction": "view_processing",
            "readiness": readiness,
            "missing": missing,
        },
    )


def _workflow_generation_job_response(
    workflow_job: dict[str, Any],
    *,
    provider: str,
    model: str | None,
    prompt: str,
    selected_source_slide_ids: list[str],
    style_id: str | None,
    brand_product_id: str | None,
) -> GenerationJobResponse:
    error = workflow_job.get("error") if isinstance(workflow_job.get("error"), dict) else {}
    output = workflow_job.get("output") if isinstance(workflow_job.get("output"), dict) else {}
    generation_job = output.get("generationJob") if isinstance(output.get("generationJob"), dict) else {}
    coverage_complete = output.get("coverageComplete", generation_job.get("coverageComplete"))
    failed_slide_ids = list(output.get("failedSlideIds") or generation_job.get("failedSlideIds") or [])
    failed_slides = list(output.get("failedSlides") or generation_job.get("failedSlides") or [])
    status_value = str(workflow_job.get("status") or "queued")
    if status_value.startswith("failed") or status_value in {"blocked", "timed_out"}:
        status_value = "failed"
    return GenerationJobResponse(
        id=str(workflow_job.get("jobId") or ""),
        deckId=str(workflow_job.get("deckId") or ""),
        status=status_value,
        provider=provider,
        model=model,
        prompt=prompt,
        selectedSourceSlideIds=selected_source_slide_ids,
        styleId=style_id,
        brandProductId=brand_product_id,
        errorMessage=error.get("message") or (
            f"{len(failed_slide_ids)} slide(s) require retry." if coverage_complete is False else None
        ),
        coverageComplete=coverage_complete if isinstance(coverage_complete, bool) else None,
        partialSuccess=bool(output.get("partialSuccess", generation_job.get("partialSuccess", False))),
        failedSlideIds=failed_slide_ids,
        failedSlides=failed_slides,
        createdAt=str(workflow_job.get("queuedAt") or workflow_job.get("startedAt") or ""),
        updatedAt=str(workflow_job.get("heartbeatAt") or workflow_job.get("startedAt") or workflow_job.get("queuedAt") or ""),
        completedAt=workflow_job.get("completedAt"),
    )


def _require_safety_gate(
    *,
    db: Session,
    request: Request,
    actor: User,
    deck: Any,
    task_type: str,
    source: str,
    user_instruction: str,
    prompt_preview: str | None = None,
) -> None:
    decision = evaluate_deck_guardrail(
        db=db,
        request=request,
        actor=actor,
        task_type=task_type,
        source=source,
        deck_id=deck.id,
        workspace_id=deck.workspace_id,
        user_instruction=user_instruction,
        user_id=actor.id,
        prompt_preview=prompt_preview or user_instruction,
        commit_events=True,
    )
    if not decision.get("allowed", True):
        reason = str(
            decision.get("reason")
            or decision.get("decision")
            or "Request blocked by safety controls."
        )
        severity = "high" if str(decision.get("riskLevel", "medium")).lower() in {"high", "critical"} else "medium"
        try:
            create_failure_ticket(
                db,
                {
                    "route": str(request.url.path),
                    "apiPath": str(request.url.path),
                    "statusCode": 403,
                    "errorName": "GuardrailBlocked",
                    "errorMessage": reason,
                    "severity": severity,
                    "source": "backend",
                    "deckId": deck.id,
                    "userId": actor.id,
                    "userEmail": actor.email,
                    "context": {
                        "taskType": task_type,
                        "riskLevel": decision.get("riskLevel"),
                        "policy": decision.get("policy"),
                        "guardrailStatus": decision.get("status"),
                        "decision": decision,
                    },
                },
                request=request,
                current_user=actor,
                commit=True,
            )
        except Exception:
            pass
        record_security_event(
            db,
            action="smart_deck.guardrail_blocked",
            result="blocked",
            actor=actor,
            resource_type="generation_job",
            resource_id=deck.id,
            request=request,
            details={
                "taskType": task_type,
                "riskLevel": decision.get("riskLevel"),
                "policy": decision.get("policy"),
                "reason": decision.get("reason"),
            },
            commit=True,
        )
        raise HTTPException(
            status_code=403,
            detail="Request blocked by safety controls. Please revise your prompt and try again.",
        )


@router.get("/{deck_id}/smart-deck", response_model=SmartDeckWorkspaceResponse)
def smart_deck_workspace(
    deck_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckWorkspaceResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    try:
        workspace = get_smart_deck_workspace(db, deck_id)
    except Exception as exc:
        db.rollback()
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="smart_deck_workspace_load",
            action="workspace_load",
            error=exc,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Smart Deck workspace is temporarily unavailable.",
        ) from exc
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckWorkspaceResponse(**workspace)


@router.get("/{deck_id}/smart-deck/context")
def smart_deck_context(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the minimum canonical context required before LLM generation.

    This endpoint is intentionally read-only and deterministic. It lets the UI
    decide whether to show the Smart Deck editor or a processing state without
    calling the LLM prematurely.
    """
    deck = get_user_deck_or_404(db, current_user, deck_id)
    try:
        structure = get_deck_structure(db, deck_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    slides = list(structure.get("slides") or [])
    brand_profile = db.query(DeckBrandProfile).filter(DeckBrandProfile.deck_id == deck_id).one_or_none()
    source_facts = _source_facts_from_slides(slides)
    deck_map = _deck_map_from_slides(slides)
    thumbnails_ready = bool(slides) and all(bool(slide.get("thumbnailPath") or slide.get("thumbnailUrl")) for slide in slides)
    extracted_text_ready = bool(slides) and any(bool(str(slide.get("rawText") or "").strip()) for slide in slides)
    source_workspace = structure.get("sourceWorkspace") if isinstance(structure.get("sourceWorkspace"), dict) else None
    context_ready = bool(deck and slides and thumbnails_ready and extracted_text_ready and source_workspace and source_facts)

    return {
        "deck": {
            "id": deck.id,
            "title": deck.title,
            "audience": deck.audience,
            "purpose": deck.purpose,
            "status": structure.get("status"),
            "workflowPhase": structure.get("workflowPhase"),
            "workflowStatus": structure.get("workflowStatus"),
        },
        "slides": slides,
        "thumbnails": [
            {
                "slideId": slide.get("id"),
                "thumbnailPath": slide.get("thumbnailPath"),
                "thumbnailUrl": slide.get("thumbnailUrl") or slide.get("thumbnailPath"),
            }
            for slide in slides
        ],
        "brand_profile": _brand_profile_payload(brand_profile),
        "deck_map": deck_map,
        "source_facts": source_facts,
        "sourceWorkspace": source_workspace,
        "ready_for_llm": context_ready,
        "readiness": {
            "deckRecordExists": bool(deck),
            "slidesExist": bool(slides),
            "thumbnailsExist": thumbnails_ready,
            "extractedTextExists": extracted_text_ready,
            "smartDeckContextExists": bool(source_workspace),
            "sourceFactsExist": bool(source_facts),
        },
    }


@router.post("/{deck_id}/smart-deck/generation-jobs", response_model=CreateSmartDeckGenerationJobResponse)
def smart_deck_create_generation_job(
    deck_id: str,
    payload: CreateSmartDeckGenerationJobInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreateSmartDeckGenerationJobResponse:
    # Compatibility wrapper only. Durable generation starts at enqueue and the
    # caller should follow workflow-job / workflow-state afterwards.
    deck = get_user_deck_or_404(db, current_user, deck_id)
    _require_safety_gate(
        db=db,
        request=request,
        actor=current_user,
        deck=deck,
        task_type="smart_deck_generation",
        source="smart_deck_generation_jobs",
        user_instruction=payload.prompt,
        prompt_preview=payload.userPrompt or payload.actionPrompt or payload.additionalContext,
    )
    enforce_rate_limit(f"smart-deck-generation:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    workflow_request = WorkflowGenerationRequest(
        prompt=payload.prompt,
        selectedSourceSlideIds=list(payload.selectedSourceSlideIds),
        idempotencyKey=_workflow_generation_idempotency_key(
            deck_id,
            {
                "prompt": payload.prompt,
                "selectedSourceSlideIds": payload.selectedSourceSlideIds,
                "styleId": payload.styleId,
                "brandProductId": payload.brandProductId,
                "additionalContext": payload.additionalContext,
                "deckType": payload.deckType,
                "audience": payload.audience,
                "preferredModel": payload.preferredModel,
                "selectedElementId": payload.selectedElementId,
                "selectedSubject": payload.selectedSubject,
                "actionId": payload.actionId,
                "actionPrompt": payload.actionPrompt,
                "userPrompt": payload.userPrompt,
                "latestBatchId": payload.latestBatchId,
                "detectedSubjects": payload.detectedSubjects,
                "subjectConfidence": payload.subjectConfidence,
                "designContext": payload.designContext,
                "generationMode": payload.generationMode,
            },
        ),
        styleId=payload.styleId,
        brandProductId=payload.brandProductId,
        additionalContext=payload.additionalContext,
        deckType=payload.deckType,
        audience=payload.audience,
        preferredModel=payload.preferredModel,
        selectedElementId=payload.selectedElementId,
        selectedSubject=payload.selectedSubject,
        actionId=payload.actionId,
        actionPrompt=payload.actionPrompt,
        userPrompt=payload.userPrompt,
        latestBatchId=payload.latestBatchId,
        detectedSubjects=payload.detectedSubjects,
        subjectConfidence=payload.subjectConfidence,
        designContext=payload.designContext,
        generationMode=payload.generationMode,
    )
    try:
        accepted = create_generation_job(db, deck_id, current_user_id=current_user.id, payload=workflow_request)
    except WorkflowConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": exc.message,
                "recoverable": exc.recoverable,
                "nextAction": exc.next_action,
            },
        ) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.generation_job",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="llm_provider_call",
            action="generation_job",
            error=exc,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck generation failed") from exc
    try:
        workflow_job = get_workflow_job_contract(db, accepted["jobId"])
        if workflow_job is None:
            raise RuntimeError("Smart Deck generation workflow job was not created")
        provider_config = get_generation_provider_config(
            db,
            deck,
            payload.preferredModel,
            strict=False,
            use_case="smart_deck",
        )
    except ValueError as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.generation_job",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="llm_provider_call",
            action="generation_job",
            error=exc,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.generation_job",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="llm_provider_call",
            action="generation_job",
            error=exc,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck generation failed") from exc
    record_security_event(
        db,
        action="smart_deck.generation_job",
        result="success",
        actor=current_user,
        resource_type="workflow_job",
        resource_id=accepted["jobId"],
        request=request,
        details={"deckId": deck_id, "status": accepted["status"]},
        commit=True,
    )
    return CreateSmartDeckGenerationJobResponse(
        generationJob=_workflow_generation_job_response(
            workflow_job,
            provider=provider_config["provider"],
            model=provider_config["model"] if provider_config["provider"] in {"anthropic", "openai", "openrouter", "dashscope"} else None,
            prompt=payload.prompt,
            selected_source_slide_ids=list(payload.selectedSourceSlideIds),
            style_id=payload.styleId,
            brand_product_id=payload.brandProductId,
        ),
        designVersion=None,
        workspace=None,
    )


@router.post("/{deck_id}/smart-deck/generate", response_model=CreateSmartDeckGenerationJobResponse)
def smart_deck_generate(
    deck_id: str,
    payload: CreateSmartDeckGenerationJobInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreateSmartDeckGenerationJobResponse:
    """Compatibility endpoint for the canonical Smart Deck generate action.

    The implementation delegates to the durable generation-job path so provider
    checks, SmartDeckContext readiness, guardrails, quota, idempotency, and audit
    behavior stay in one place.
    """
    return smart_deck_create_generation_job(
        deck_id=deck_id,
        payload=payload,
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post("/{deck_id}/smart-agent/generate", response_model=CreateSmartDeckGenerationJobResponse)
def smart_deck_agent_generate(
    deck_id: str,
    payload: SmartDeckAgentGenerateInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreateSmartDeckGenerationJobResponse:
    # Compatibility wrapper only. Durable generation starts at enqueue and the
    # caller should follow workflow-job / workflow-state afterwards.
    deck = get_user_deck_or_404(db, current_user, deck_id)
    _require_safety_gate(
        db=db,
        request=request,
        actor=current_user,
        deck=deck,
        task_type="smart_deck_agent_generation",
        source="smart_deck_agent_generate",
        user_instruction=payload.userPrompt,
        prompt_preview=payload.actionPrompt or payload.userPrompt,
    )
    enforce_rate_limit(f"smart-agent-generation:user:{current_user.id}", db=db, limit=10, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    try:
        accepted = generate_smart_deck_agent(db, deck_id, current_user_id=current_user.id, payload=payload)
    except WorkflowConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": exc.message,
                "recoverable": exc.recoverable,
                "nextAction": exc.next_action,
            },
        ) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.agent_generation",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck agent generation failed") from exc
    try:
        workflow_job = get_workflow_job_contract(db, accepted["jobId"])
        if workflow_job is None:
            raise RuntimeError("Smart Deck agent workflow job was not created")
        provider_config = get_generation_provider_config(
            db,
            deck,
            payload.preferredModel,
            strict=False,
            use_case="smart_deck",
        )
    except ValueError as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.agent_generation",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.agent_generation",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck agent generation failed") from exc
    record_security_event(
        db,
        action="smart_deck.agent_generation",
        result="success",
        actor=current_user,
        resource_type="workflow_job",
        resource_id=accepted["jobId"],
        request=request,
        details={"deckId": deck_id, "status": accepted["status"]},
        commit=True,
    )
    return CreateSmartDeckGenerationJobResponse(
        generationJob=_workflow_generation_job_response(
            workflow_job,
            provider=provider_config["provider"],
            model=provider_config["model"] if provider_config["provider"] in {"anthropic", "openai", "openrouter", "dashscope"} else None,
            prompt=payload.userPrompt,
            selected_source_slide_ids=list((workflow_job.get("input") or {}).get("selectedSourceSlideIds") or payload.selectedSlideIds),
            style_id=None,
            brand_product_id=None,
        ),
        designVersion=None,
        workspace=None,
    )


@router.get("/{deck_id}/smart-deck/generation-jobs/{job_id}", response_model=GenerationJobResponse)
def smart_deck_generation_job(
    deck_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GenerationJobResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    workflow_job = get_workflow_job_contract(db, job_id)
    if workflow_job is None or workflow_job.get("deckId") != deck_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found")
    input_payload = workflow_job.get("input") if isinstance(workflow_job.get("input"), dict) else {}
    return _workflow_generation_job_response(
        workflow_job,
        provider="workflow",
        model=None,
        prompt=str(input_payload.get("prompt") or ""),
        selected_source_slide_ids=list(input_payload.get("selectedSourceSlideIds") or []),
        style_id=input_payload.get("styleId"),
        brand_product_id=input_payload.get("brandProductId"),
    )


@router.patch("/{deck_id}/smart-deck/preferences", response_model=SmartDeckPreferenceResponse)
def smart_deck_update_preferences(
    deck_id: str,
    payload: UpdateSmartDeckPreferenceInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckPreferenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        preferences = update_smart_deck_preferences(db, deck_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if preferences is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckPreferenceResponse(**preferences)


@router.patch("/{deck_id}/smart-deck/selection", response_model=SmartDeckPreferenceResponse)
def smart_deck_update_selection(
    deck_id: str,
    payload: UpdateSmartDeckSelectionInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckPreferenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        preferences = update_smart_deck_selection(db, deck_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if preferences is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckPreferenceResponse(**preferences)


@router.patch("/{deck_id}/smart-deck/session-state", response_model=SmartDeckPreferenceResponse)
def smart_deck_update_session_state(
    deck_id: str,
    payload: UpdateSmartDeckSessionStateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckPreferenceResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        session_state = update_smart_deck_selection(db, deck_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if session_state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckPreferenceResponse(**session_state)


@router.get("/{deck_id}/smart-deck/messages", response_model=SmartDeckMessagesRouteResponse)
def smart_deck_messages(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckMessagesRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = list_smart_deck_messages(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckMessagesRouteResponse(
        messages=[SmartDeckMessageResponse(**message) for message in payload["messages"]],
    )


@router.post("/{deck_id}/smart-deck/messages", response_model=SmartDeckMessageResponse)
def smart_deck_create_message(
    deck_id: str,
    payload: CreateSmartDeckMessageInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckMessageResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        message = create_smart_deck_message(db, deck_id, payload)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return SmartDeckMessageResponse(**message)


@router.post("/{deck_id}/smart-deck/assistant-runs", response_model=SmartDeckAssistantRunResponse)
def smart_deck_create_assistant_run(
    deck_id: str,
    payload: CreateSmartDeckAssistantRunInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SmartDeckAssistantRunResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    _require_safety_gate(
        db=db,
        request=request,
        actor=current_user,
        deck=deck,
        task_type="smart_deck_assistant_run",
        source="smart_deck_assistant_runs",
        user_instruction=payload.instruction,
        prompt_preview=payload.instruction,
    )
    enforce_rate_limit(f"smart-deck-assistant:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    try:
        result = create_smart_deck_assistant_run(db, deck_id, payload)
    except ValueError as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.assistant_run",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.assistant_run",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck assistant run failed") from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    record_security_event(
        db,
        action="smart_deck.assistant_run",
        result="success",
        actor=current_user,
        resource_type="assistant_run",
        resource_id=result["runId"],
        request=request,
        details={"deckId": deck_id},
        commit=True,
    )
    return SmartDeckAssistantRunResponse(**result)


@router.get("/{deck_id}/design-versions", response_model=DesignVersionsRouteResponse)
def smart_deck_design_versions(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignVersionsRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = list_design_versions(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DesignVersionsRouteResponse(**payload)


@router.get("/{deck_id}/design-tokens", response_model=DesignTokensRouteResponse)
def smart_deck_design_tokens(
    deck_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignTokensRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = list_design_tokens(db, deck_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deck not found")
    return DesignTokensRouteResponse(
        designTokens=[DesignTokenResponse(**token) for token in payload["designTokens"]],
    )


@router.post(
    "/{deck_id}/design-versions/{version_id}/apply",
    response_model=DesignVersionsRouteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def smart_deck_apply_design_version(
    deck_id: str,
    version_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignVersionsRouteResponse:
    # Compatibility wrapper only. Canonical apply starts at durable enqueue and
    # the caller should follow workflow-job / workflow-state afterwards.
    deck = get_user_deck_or_404(db, current_user, deck_id)
    try:
        accepted = queue_apply_design_version(
            db,
            deck_id,
            current_user_id=current_user.id,
            payload=WorkflowApplyRequest(
                designVersionId=version_id,
                idempotencyKey=f"{deck_id}:apply:{version_id}",
            ),
        )
    except WorkflowConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.code,
                "message": exc.message,
                "recoverable": exc.recoverable,
                "nextAction": exc.next_action,
            },
        ) from exc
    except Exception as exc:
        db.rollback()
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="apply_design_version",
            action="apply",
            error=exc,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck apply failed.") from exc
    payload = list_design_versions(db, deck_id)
    payload.update(
        {
            "workflowId": accepted.get("workflowId"),
            "workflowPhase": accepted.get("phase"),
            "workflowStatus": accepted.get("status"),
            "workflowJobId": accepted.get("jobId"),
            "workflowJobType": accepted.get("jobType"),
            "workflowJobStatus": accepted.get("status"),
            "nextAction": accepted.get("nextAction"),
        }
    )
    return DesignVersionsRouteResponse(**payload)


@router.post("/{deck_id}/design-versions/{version_id}/discard", response_model=DesignVersionsRouteResponse)
def smart_deck_discard_design_version(
    deck_id: str,
    version_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignVersionsRouteResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    try:
        payload = discard_design_version(db, deck_id, version_id)
    except Exception as exc:
        db.rollback()
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="apply_design_version",
            action="discard",
            error=exc,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck discard failed.") from exc
    if payload is None:
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="apply_design_version",
            action="discard",
            error=LookupError("Design version not found"),
            status_code=status.HTTP_404_NOT_FOUND,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design version not found")
    return DesignVersionsRouteResponse(**payload)


@router.post("/{deck_id}/design-versions/{version_id}/restore", response_model=DesignVersionsRouteResponse)
def smart_deck_restore_design_version(
    deck_id: str,
    version_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DesignVersionsRouteResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    try:
        payload = restore_design_version(db, deck_id, version_id)
    except Exception as exc:
        db.rollback()
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="preview_persist",
            action="restore",
            error=exc,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Smart Deck restore failed.") from exc
    if payload is None:
        _record_smart_deck_failure(
            db=db,
            request=request,
            actor=current_user,
            deck_id=deck_id,
            workspace_id=_deck_workspace_id(deck),
            stage="preview_persist",
            action="restore",
            error=LookupError("Design version not found"),
            status_code=status.HTTP_404_NOT_FOUND,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design version not found")
    return DesignVersionsRouteResponse(**payload)


@router.get("/{deck_id}/generated-slides/{generated_slide_id}/code", response_model=GeneratedSlideCodeRouteResponse)
def smart_deck_generated_slide_code(
    deck_id: str,
    generated_slide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedSlideCodeRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = get_generated_slide_code(db, deck_id, generated_slide_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated slide code not found")

    generated_slide, code_version = result
    return GeneratedSlideCodeRouteResponse(generatedSlide=generated_slide, codeVersion=code_version)


@router.patch("/{deck_id}/generated-slides/{generated_slide_id}/design-tokens", response_model=GeneratedSlideCodeRouteResponse)
def smart_deck_generated_slide_typography(
    deck_id: str,
    generated_slide_id: str,
    payload: UpdateGeneratedSlideTypographyInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedSlideCodeRouteResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    result = update_generated_slide_typography(
        db,
        deck_id,
        generated_slide_id,
        heading_font=payload.headingFont,
        body_font=payload.bodyFont,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated slide code not found")
    generated_slide, code_version = result
    record_security_event(
        db,
        action="smart_deck.typography_update",
        result="success",
        actor=current_user,
        resource_type="generated_slide",
        resource_id=generated_slide_id,
        request=request,
        details={"deckId": deck_id},
        commit=True,
    )
    return GeneratedSlideCodeRouteResponse(generatedSlide=generated_slide, codeVersion=code_version)


@router.get(
    "/{deck_id}/generated-slides/{generated_slide_id}/code-versions/{code_version_id}/artifacts",
    response_model=GeneratedSlideCodeArtifactsResponse,
)
def smart_deck_generated_slide_code_artifacts(
    deck_id: str,
    generated_slide_id: str,
    code_version_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedSlideCodeArtifactsResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_generated_slide_code_artifact_urls(db, deck_id, generated_slide_id, code_version_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated slide code artifacts not found")
    return GeneratedSlideCodeArtifactsResponse(**payload)


@router.post(
    "/{deck_id}/generated-slides/{generated_slide_id}/code-versions/{code_version_id}/thumbnail",
    response_model=GeneratedSlideThumbnailResponse,
)
async def smart_deck_generated_slide_code_thumbnail(
    deck_id: str,
    generated_slide_id: str,
    code_version_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedSlideThumbnailResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = await file.read()
    try:
        result = save_generated_slide_code_thumbnail(
            db,
            deck_id=deck_id,
            generated_slide_id=generated_slide_id,
            code_version_id=code_version_id,
            payload=payload,
            content_type=file.content_type or "application/octet-stream",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated slide code version not found")
    return GeneratedSlideThumbnailResponse(**result)


@router.get("/{deck_id}/generated-slides/{generated_slide_id}/scene-graph", response_model=GeneratedSlideSceneGraphResponse)
def smart_deck_generated_slide_scene_graph(
    deck_id: str,
    generated_slide_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedSlideSceneGraphResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    payload = get_generated_slide_scene_graph(db, deck_id, generated_slide_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated slide scene graph not found")
    return GeneratedSlideSceneGraphResponse(**payload)


@router.post(
    "/{deck_id}/generated-slides/{generated_slide_id}/manual-edit-jobs",
    response_model=CreateManualEditJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def smart_deck_create_manual_edit_job(
    deck_id: str,
    generated_slide_id: str,
    payload: CreateManualEditJobInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreateManualEditJobResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        manual_edit_job, candidate_version, generated_slide = create_manual_edit_job(
            db,
            deck_id,
            generated_slide_id,
            payload,
        )
    except ManualEditConflictError as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.manual_edit",
            result="failure",
            actor=current_user,
            resource_type="generated_slide",
            resource_id=generated_slide_id,
            request=request,
            details={"reason": exc.code, "deckId": deck_id},
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message, "recoverable": True},
        ) from exc
    except ValueError as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.manual_edit",
            result="failure",
            actor=current_user,
            resource_type="generated_slide",
            resource_id=generated_slide_id,
            request=request,
            details={"reason": exc.__class__.__name__, "deckId": deck_id},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.manual_edit",
            result="failure",
            actor=current_user,
            resource_type="generated_slide",
            resource_id=generated_slide_id,
            request=request,
            details={"reason": exc.__class__.__name__, "deckId": deck_id},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Manual slide edit failed") from exc

    record_security_event(
        db,
        action="smart_deck.manual_edit",
        result="success",
        actor=current_user,
        resource_type="design_version",
        resource_id=candidate_version["id"],
        request=request,
        details={
            "deckId": deck_id,
            "baseDesignVersionId": payload.baseDesignVersionId,
            "baseGeneratedSlideId": generated_slide_id,
            "sourceSlideId": payload.sourceSlideId,
            "operationCount": len(payload.operations),
        },
        commit=True,
    )
    return CreateManualEditJobResponse(
        manualEditJob=manual_edit_job,
        candidateDesignVersion=candidate_version,
        generatedSlide=generated_slide,
        renderSchema=generated_slide["renderSchema"],
    )


@router.post(
    "/{deck_id}/generated-slides/{generated_slide_id}/elements/{element_id}/variation-jobs",
    response_model=CreateElementVariationJobResponse,
)
def smart_deck_create_element_variation_job(
    deck_id: str,
    generated_slide_id: str,
    element_id: str,
    payload: CreateElementVariationJobInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreateElementVariationJobResponse:
    deck = get_user_deck_or_404(db, current_user, deck_id)
    _require_safety_gate(
        db=db,
        request=request,
        actor=current_user,
        deck=deck,
        task_type="smart_deck_element_variation",
        source="smart_deck_element_variations",
        user_instruction=payload.instruction,
        prompt_preview=payload.instruction,
    )
    enforce_rate_limit(f"smart-deck-element-variation:user:{current_user.id}", db=db, limit=30, window_seconds=3600)
    enforce_ai_generation_quota(db, current_user)
    try:
        result = create_element_variation_job(db, deck_id, generated_slide_id, element_id, payload)
    except ValueError as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.element_variation",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__, "generatedSlideId": generated_slide_id, "elementId": element_id},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        record_security_event(
            db,
            action="smart_deck.element_variation",
            result="failure",
            actor=current_user,
            resource_type="deck",
            resource_id=deck_id,
            request=request,
            details={"reason": exc.__class__.__name__, "generatedSlideId": generated_slide_id, "elementId": element_id},
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Element variation failed") from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated slide not found")
    variation_job, element, output_version, generated_slide, design_version, workspace = result
    record_security_event(
        db,
        action="smart_deck.element_variation",
        result="success",
        actor=current_user,
        resource_type="element_variation_job",
        resource_id=variation_job["id"],
        request=request,
        details={"deckId": deck_id, "generatedSlideId": generated_slide_id, "elementId": element_id},
        commit=True,
    )
    return CreateElementVariationJobResponse(
        variationJob=variation_job,
        element=element,
        outputVersion=output_version,
        generatedSlide=generated_slide,
        designVersion=design_version,
        workspace=workspace,
    )


@router.post(
    "/{deck_id}/generated-slides/{generated_slide_id}/elements/{element_id}/versions/{version_id}/apply",
    response_model=ApplyElementVersionResponse,
)
def smart_deck_apply_element_version(
    deck_id: str,
    generated_slide_id: str,
    element_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApplyElementVersionResponse:
    get_user_deck_or_404(db, current_user, deck_id)
    try:
        result = apply_element_version(db, deck_id, generated_slide_id, element_id, version_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Element version not found")
    element, applied_version, generated_slide = result
    return ApplyElementVersionResponse(element=element, appliedVersion=applied_version, generatedSlide=generated_slide)
