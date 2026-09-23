"""Mounted, durable AI-VC strategy runtime for Instant Deck.

The LangGraph graph coordinates Deck-owned stages; paid calls still use the
existing provider transport and durable ``DeckLlmArtifact`` boundary.  A
known parse/validation failure may consume one smaller recovery call.  An
unknown transport outcome is never replayed automatically.
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from typing import get_args, get_origin

from app.core.config import settings
from app.core.security import generate_id
from app.db.models import DeckLlmArtifact
from app.services.ai_vc.graph import build_ai_vc_graph
from app.services.ai_vc.models import (
    DeckArchitecture,
    InvestmentCommitteeReview,
    NarrativeGapAnalysis,
    RetrievalPurpose,
    ResearchSynthesis,
)


ARTIFACT_TYPE = "instant_deck_vc_strategy"
ATTEMPT_TYPE = "instant_deck_vc_strategy_stage_attempt"
SCHEMA_VERSION = "instant-deck-vc-strategy.v3"

AnalysisStatus = Literal["ready", "recovering", "source_only_fallback", "failed"]


class AnalysisStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    researchSynthesis: ResearchSynthesis
    investmentMemo: dict[str, Any]
    financialAnalysis: dict[str, Any]
    vcInferences: list[dict[str, Any]] = Field(default_factory=list, max_length=24)
    evidenceGaps: list[str] = Field(default_factory=list, max_length=24)
    investmentCommitteeReview: InvestmentCommitteeReview


class NarrativeStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrativeGapAnalysis: NarrativeGapAnalysis
    narrativeStrategy: dict[str, Any]
    deckArchitecture: DeckArchitecture


class EvidenceInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=2, max_length=600)
    evidence_ids: list[str] = Field(min_length=1, max_length=16)
    confidence: Literal["high", "medium", "low", "unknown"]
    uncertainty: str | None = Field(default=None, max_length=500)


class MethodologySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=64)
    reason: str = Field(min_length=5, max_length=500)
    priority: Literal["critical", "high", "medium"] = "high"


class ModelResearchTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: RetrievalPurpose
    question: str = Field(min_length=8, max_length=600)
    rationale: str = Field(min_length=8, max_length=600)
    public_search_context: str = Field(min_length=3, max_length=320)
    evidence_ids: list[str] = Field(min_length=1, max_length=16)
    importance: Literal["critical", "high", "medium", "low"] = "high"


class ResearchPlanningStage(BaseModel):
    """Model-authored understanding and research agenda before web access."""

    model_config = ConfigDict(extra="forbid")

    what_company_sells: EvidenceInterpretation
    buyers: list[EvidenceInterpretation] = Field(min_length=1, max_length=8)
    business_models: list[EvidenceInterpretation] = Field(min_length=1, max_length=6)
    industry_contexts: list[EvidenceInterpretation] = Field(min_length=1, max_length=8)
    workflows: list[EvidenceInterpretation] = Field(default_factory=list, max_length=10)
    geographies: list[EvidenceInterpretation] = Field(default_factory=list, max_length=6)
    reporting_periods: list[EvidenceInterpretation] = Field(default_factory=list, max_length=10)
    uncertainties: list[str] = Field(default_factory=list, max_length=16)
    methodology_selections: list[MethodologySelection] = Field(min_length=1, max_length=16)
    research_tasks: list[ModelResearchTask] = Field(min_length=1, max_length=8)


class AIVCStageFailure(RuntimeError):
    def __init__(
        self, *, stage: str, code: str, category: str, recoverable: bool,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(code)
        self.stage = stage
        self.code = code
        self.category = category
        self.recoverable = recoverable
        self.details = details or {}

    def diagnostic(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "code": self.code,
            "category": self.category,
            "recoverable": self.recoverable,
            **self.details,
        }


def _classify_failure(stage: str, exc: Exception, *, outcome_known: bool) -> AIVCStageFailure:
    from app.services.llm.openai_provider import (
        OpenAIResponseFailed,
        OpenAIResponseIncomplete,
        OpenAIResponseMalformed,
        OpenAIResponseRefusal,
        OpenAITransportError,
    )

    if isinstance(exc, OpenAITransportError):
        return AIVCStageFailure(stage=stage, code="provider_transport", category="provider_transport", recoverable=False)
    if isinstance(exc, OpenAIResponseIncomplete):
        return AIVCStageFailure(stage=stage, code="provider_incomplete", category="provider_incomplete", recoverable=outcome_known)
    if isinstance(exc, OpenAIResponseRefusal):
        return AIVCStageFailure(stage=stage, code="provider_refusal", category="provider_refusal", recoverable=False)
    if isinstance(exc, OpenAIResponseFailed):
        return AIVCStageFailure(stage=stage, code="provider_failed", category="provider_transport", recoverable=False)
    if isinstance(exc, (OpenAIResponseMalformed, json.JSONDecodeError)):
        return AIVCStageFailure(stage=stage, code="structured_parse", category="structured_parse", recoverable=outcome_known)
    if isinstance(exc, ValidationError):
        return AIVCStageFailure(stage=stage, code="schema_validation", category="schema_validation", recoverable=outcome_known)
    message = str(exc)
    if "financial" in message.lower():
        category = "financial_validation"
    elif "evidence" in message.lower() or "unknown" in message.lower():
        category = "evidence_validation"
    elif "architecture" in message.lower() or "slide" in message.lower():
        category = "architecture_validation"
    elif "cost" in message.lower() or "allowance" in message.lower():
        category = "cost_validation"
    else:
        category = "unknown"
    return AIVCStageFailure(stage=stage, code=category, category=category, recoverable=outcome_known and category != "cost_validation")


def _nested_base_model(annotation: Any) -> type[BaseModel] | None:
    """Return the pydantic model carried by a field annotation.

    Handles an annotation directly typed as a model as well as ``list[X]``,
    ``X | None`` and similar containers that shallow validation wraps. This is
    used only to decide whether recursively pruning unknown keys is sound for a
    field, so the free ``dict[str, Any]`` strategy subdocuments stay untouched.
    """
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin is not None and origin is list:
        for arg in get_args(annotation):
            nested = _nested_base_model(arg)
            if nested is not None:
                return nested
    for arg in get_args(annotation):
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            return arg
    return None


def _prune_unknown_fields(value: Any, model: type[BaseModel]) -> tuple[Any, int]:
    """Recursively drop keys the response model does not declare.

    OpenAI ``strict=False`` JSON-schema responses may carry extra keys on the
    strictly-typed stage envelopes (``AnalysisStage``/``NarrativeStage`` and
    nested strategy models). The free ``dict[str, Any]`` subdocuments are not
    declared models and are preserved verbatim, so no strategy content is ever
    dropped. Returns ``(pruned, dropped)`` so the attempt can record the repair.
    """
    if isinstance(value, list):
        items: list[Any] = []
        dropped_total = 0
        for item in value:
            pruned, dropped = _prune_unknown_fields(item, model)
            items.append(pruned)
            dropped_total += dropped
        return items, dropped_total
    if not isinstance(value, dict):
        return value, 0
    fields = getattr(model, "model_fields", None)
    if fields is None:
        return value, 0
    pruned: dict[str, Any] = {}
    dropped = 0
    for key, item in value.items():
        field_info = fields.get(key)
        if field_info is None:
            dropped += 1
            continue
        nested_model = _nested_base_model(field_info.annotation)
        if nested_model is not None and isinstance(item, (dict, list)):
            pruned[key], nested_dropped = _prune_unknown_fields(item, nested_model)
            dropped += nested_dropped
        else:
            pruned[key] = item
    return pruned, dropped


def _stage_call(
    db: Session,
    *,
    deck: Any,
    operation_id: str,
    stage: str,
    payload: dict[str, Any],
    system: str,
    response_model: type[BaseModel],
    max_output_tokens: int,
    recovery: bool,
    retrieval_trace: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.services.llm.generation_service import get_generation_provider_config
    from app.services.llm.instant_html_operation_service import estimate_model_cost_cents
    from app.services.llm.openai_provider import call_openai_response, parse_openai_structured_response

    model = settings.openai_model
    config = get_generation_provider_config(db, deck, preferred_model=model, strict=True, use_case="analysis")
    if config["provider"] != "openai" or config["model"] != model:
        raise AIVCStageFailure(
            stage=stage, code="provider_unavailable", category="provider_transport", recoverable=False,
            details={"provider": config.get("provider"), "model": config.get("model"),
                     "attemptNumber": 2 if recovery else 1, "transportStarted": False,
                     "billingOutcomeKnown": True, "recoveryAttempted": recovery},
        )
    user = json.dumps(payload, separators=(",", ":"), default=str)
    estimated_max = estimate_model_cost_cents(
        "openai", model, input_tokens=max(1, len(user.encode("utf-8")) // 4),
        output_tokens=max_output_tokens,
    )
    allowance = settings.instant_html_vc_memo_max_cost_cents
    completed_cost = sum(
        float((row.metrics_json or {}).get("estimatedCostCents") or 0)
        for row in db.query(DeckLlmArtifact).filter(
            DeckLlmArtifact.deck_id == deck.id,
            DeckLlmArtifact.artifact_type == ATTEMPT_TYPE,
            DeckLlmArtifact.artifact_key.like(f"vc-strategy-stage:{operation_id}:%"),
        ).all()
        if row.status == "completed"
    )
    research_cost_cents = sum(
        float((row.metrics_json or {}).get("researchProviderDollars") or 0) * 100
        for row in db.query(DeckLlmArtifact).filter(
            DeckLlmArtifact.deck_id == deck.id,
            DeckLlmArtifact.artifact_type == "instant_deck_public_research_attempt",
        ).all()
        if str(((row.payload_json or {}).get("authorization") or {}).get("authorization_id") or "")
        .startswith(f"instant-{operation_id}-")
    )
    total_allowance = settings.ai_vc_max_total_cost_cents
    if allowance is not None and (
        estimated_max is None or completed_cost + float(estimated_max) > allowance
    ):
        raise AIVCStageFailure(
            stage=stage, code="cost_validation", category="cost_validation", recoverable=False,
            details={"provider": "openai", "model": model,
                     "attemptNumber": 2 if recovery else 1, "transportStarted": False,
                     "billingOutcomeKnown": True, "recoveryAttempted": recovery},
        )
    if total_allowance is not None and (
        estimated_max is None
        or research_cost_cents + completed_cost + float(estimated_max) > total_allowance
    ):
        raise AIVCStageFailure(
            stage=stage, code="cost_validation", category="cost_validation", recoverable=False,
            details={"provider": "openai", "model": model,
                     "attemptNumber": 2 if recovery else 1, "transportStarted": False,
                     "billingOutcomeKnown": True, "recoveryAttempted": recovery},
        )

    from app.services.ai_vc.observability import (
        MANIFEST_SCHEMA,
        MANIFEST_TYPE,
        build_provider_context_manifest,
        persist_internal_artifact,
    )

    manifest = build_provider_context_manifest(
        operation_id=operation_id, stage=stage, provider="openai", model=model,
        system=system, payload=payload, retrieval_trace=retrieval_trace,
        prompt_version=SCHEMA_VERSION,
    )
    manifest_row = persist_internal_artifact(
        db, deck_id=deck.id, artifact_type=MANIFEST_TYPE,
        artifact_key=f"ai-vc-context:{operation_id}:{stage}:{'recovery' if recovery else 'primary'}",
        schema_version=MANIFEST_SCHEMA,
        summary=f"Provider-bound AI-VC {stage} context manifest; hashes and IDs only.",
        payload=manifest,
        metrics={"approximateInputTokens": manifest["approximateInputTokens"]},
    )

    attempt_key = f"vc-strategy-stage:{operation_id}:{stage}:{'recovery' if recovery else 'primary'}"
    if db.query(DeckLlmArtifact).filter_by(deck_id=deck.id, artifact_key=attempt_key).first() is not None:
        raise AIVCStageFailure(stage=stage, code="attempt_already_consumed", category="provider_transport", recoverable=False)
    request_id = str(uuid4())
    attempt = DeckLlmArtifact(
        id=generate_id("vcstage"), deck_id=deck.id, artifact_type=ATTEMPT_TYPE,
        artifact_key=attempt_key, schema_version=SCHEMA_VERSION, status="running",
        summary=f"Durable AI-VC {stage} {'recovery' if recovery else 'primary'} stage.",
        payload_json={
            "stage": stage, "recovery": recovery, "providerStarts": 1,
            "clientRequestId": request_id, "model": model,
            "estimatedMaximumCostCents": estimated_max,
            "configuredCostCapCents": allowance,
            "contextManifestId": manifest_row.id,
        },
        metrics_json={"costKnown": False, "outcomeKnown": False},
    )
    db.add(attempt)
    db.commit()
    outcome_known = False
    repair_metrics: dict[str, Any] = {}
    response: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    actual_cost: float | None = None
    try:
        transport = getattr(call_openai_response, "__wrapped__", call_openai_response)
        response = transport(
            api_key=config["apiKey"], model=model, system=system, user=user,
            max_output_tokens=max_output_tokens,
            timeout=settings.ai_vc_max_runtime_seconds,
            timeout_ceiling=settings.ai_vc_max_runtime_seconds,
            response_format={
                "type": "json_schema", "name": f"ai_vc_{stage.replace('-', '_')}",
                # Several strategic subdocuments intentionally remain
                # extensible dictionaries. OpenAI strict schemas reject such
                # additionalProperties; Pydantic plus the evidence/financial
                # validators below remain the application authority.
                "strict": False, "schema": response_model.model_json_schema(),
            },
            client_request_id=request_id,
        )
        outcome_known = True
        usage = response.get("usage") or {}
        actual_cost = estimate_model_cost_cents(
            "openai", model, input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )
        if allowance is not None and (
            actual_cost is None or completed_cost + float(actual_cost) > allowance
        ):
            raise ValueError("cost allowance exceeded")
        if total_allowance is not None and (
            actual_cost is None
            or research_cost_cents + completed_cost + float(actual_cost) > total_allowance
        ):
            raise ValueError("total cost allowance exceeded")
        raw_text = parse_openai_structured_response(response)
        try:
            parsed = response_model.model_validate_json(raw_text)
        except ValidationError as primary_validation:
            # ``strict=False`` responses can carry undeclared keys on the typed
            # stage envelopes. Drop them deterministically before either
            # accepting the structure or paying for a recovery call. Free
            # ``dict[str, Any]`` strategy subdocuments are preserved verbatim.
            pruned, dropped = _prune_unknown_fields(
                json.loads(raw_text), response_model
            )
            if dropped:
                parsed = response_model.model_validate(pruned)
                repair_metrics = {"repairDroppedUnknownKeys": dropped}
            else:
                raise primary_validation
    except Exception as exc:
        failure = _classify_failure(stage, exc, outcome_known=outcome_known)
        failure.details.update({
            "provider": "openai", "model": model,
            "attemptNumber": 2 if recovery else 1,
            "transportStarted": True, "billingOutcomeKnown": outcome_known,
            "inputTokens": usage.get("input_tokens"),
            "outputTokens": usage.get("output_tokens"),
            "contextManifestId": manifest_row.id,
            "recoveryAttempted": recovery,
        })
        attempt.status = "failed"
        attempt.metrics_json = {
            "costKnown": actual_cost is not None, "outcomeKnown": outcome_known,
            "billingOutcomeKnown": outcome_known, "transportStarted": True,
            "provider": "openai", "model": model, "attemptNumber": 2 if recovery else 1,
            "contextManifestId": manifest_row.id,
            "inputTokens": usage.get("input_tokens"), "outputTokens": usage.get("output_tokens"),
            "estimatedCostCents": actual_cost,
            "providerStarts": 1, **failure.diagnostic(),
        }
        db.commit()
        raise failure from exc
    attempt.status = "completed"
    attempt.metrics_json = {
        "costKnown": bool(usage), "outcomeKnown": True, "providerStarts": 1,
        "estimatedCostCents": actual_cost,
        "inputTokens": usage.get("input_tokens"), "outputTokens": usage.get("output_tokens"),
        "providerResponseId": response.get("id"),
        "provider": "openai", "model": model,
        "transportStarted": True, "billingOutcomeKnown": True,
        "attemptNumber": 2 if recovery else 1,
        "contextManifestId": manifest_row.id,
        **repair_metrics,
    }
    db.commit()
    return parsed.model_dump(mode="json"), attempt.metrics_json


_ANALYSIS_SYSTEM = """Act as a venture investor, research synthesist and financial analyst.
Return only the requested structured JSON. Synthesize COMPANY_SOURCE, verified EXTERNAL_RESEARCH,
and advisory PRODUCT_KNOWLEDGE into an investment memo. Company claims and achieved metrics may cite
COMPANY_SOURCE only. Current market claims may cite verified EXTERNAL_RESEARCH only. PRODUCT_KNOWLEDGE
is methodology, never factual authority. Preserve every amount, currency, unit, period, qualifier and
actual/projected status. Do not invent TAM, revenue, customers, pricing, traction, integrations, an ask,
or forecasts. Identify why now, buyer, economic pain, wedge, business model, competition, expansion,
defensibility, financing logic, strongest reason to invest, strongest reason not to invest, missing proof,
and objections. Investment committee critique is advisory and publication_blocking is always false.
For each verified external finding you choose to use or reject, add a researchSynthesis.finding_impacts
entry with its exact external evidence IDs, use/reject disposition, the thesis, positioning, market discussion
or investor objection it affects, a concise explanation, and the material qualification. You may reject weak
or irrelevant findings; do not force every research result into the strategy or deck.
Exclude source editorial notes and do not write slide copy. Follow the supplied activeSkills as reasoning
procedures. Skills are internal methodology, not evidence, and their allowed tools have already been mediated
by Deck V2 application services."""

_NARRATIVE_SYSTEM = """Act as the lead partner and presentation strategist authoring a capital-raising narrative.
Return only the requested structured JSON. Use the supplied investment memo, financial analysis, verified
evidence and advisory committee recommendations to reconstruct the story from first principles. The source
deck is evidence, not a manuscript or slide-count target. The model owns the recommended slide count, roles,
order, headline direction, key message and visual primitive. Make the architecture comprehensive enough to
answer the material investor questions for this company, without padding or inventing proof. Every slide must
cite only allowed evidence IDs. External evidence cannot establish company traction. Never create slides for
editorial notes, methodology, citations, warnings, critique, diagnostics or source summaries. Choose the best
investor narrative, not the input page count. Follow only the supplied narrative-phase activeSkills; do not
copy their instructions or names into the deck."""

_RESEARCH_PLANNING_SYSTEM = """Act as the research partner for an investor diligence workflow.
Interpret the supplied COMPANY_SOURCE evidence before any web search. Identify what the company sells,
its buyers, business-model possibilities, relevant industry contexts, workflows, geography, reporting
periods and uncertainty. Distinguish the company's business model from the industries of its customers.
Negation matters: a statement that the company does not offer insurance is not evidence that it is fintech.
Support every interpretation and research task with supplied evidence IDs only. Preserve unknown and mixed
interpretations instead of forcing a familiar sector.

Choose relevant methodology only from the supplied catalog. Then author the bounded research priorities and
questions that matter for this company. public_search_context and question are allowed to reach web search:
they must describe only a public category, buyer type, workflow, geography or reporting period; never include
the private company name, customer identities, private metrics, source quotations, URLs or confidential terms.
Company discovery and category research are independent. Do not prescribe slides, a narrative sequence or
visuals. Return only the requested JSON schema."""


def _interpretation_payload(value: EvidenceInterpretation) -> dict[str, Any]:
    return {
        "statement": value.statement,
        "evidenceIds": value.evidence_ids,
        "confidence": value.confidence,
        "uncertainty": value.uncertainty,
    }


def _validate_model_research_plan(
    plan: ResearchPlanningStage, *, source_ids: set[str], deck_title: str,
    private_numeric_tokens: set[str] | None = None,
) -> dict[str, Any]:
    from app.services.ai_vc.skills.registry import load_builtin_skill_catalog

    interpretations = [
        plan.what_company_sells, *plan.buyers, *plan.business_models,
        *plan.industry_contexts, *plan.workflows, *plan.geographies,
        *plan.reporting_periods,
    ]
    for item in interpretations:
        if any(str(ref) not in source_ids for ref in item.evidence_ids):
            raise AIVCStageFailure(
                stage="research_planning", code="evidence_reference",
                category="evidence_validation", recoverable=True,
            )
    catalog = load_builtin_skill_catalog()
    if any(selection.name not in catalog for selection in plan.methodology_selections):
        raise AIVCStageFailure(
            stage="research_planning", code="methodology_reference",
            category="evidence_validation", recoverable=True,
        )

    forbidden_title = " ".join(str(deck_title or "").casefold().split())
    for task in plan.research_tasks:
        if any(str(ref) not in source_ids for ref in task.evidence_ids):
            raise AIVCStageFailure(
                stage="research_planning", code="evidence_reference",
                category="evidence_validation", recoverable=True,
            )
        public_text = " ".join((task.question + " " + task.public_search_context).split())
        folded = public_text.casefold()
        if "http://" in folded or "https://" in folded or "@" in public_text:
            raise AIVCStageFailure(
                stage="research_planning", code="privacy_violation",
                category="evidence_validation", recoverable=False,
            )
        if forbidden_title and len(forbidden_title) >= 5 and forbidden_title in folded:
            raise AIVCStageFailure(
                stage="research_planning", code="privacy_violation",
                category="evidence_validation", recoverable=False,
            )
        public_numeric_tokens = {
            re.sub(r"\s+", "", value.casefold())
            for value in re.findall(r"(?:[$£€]\s*)?\d[\d,.]*(?:\s*(?:%|[kmb]))?", public_text, re.IGNORECASE)
            if not re.fullmatch(r"(?:19|20)\d{2}", value.strip())
        }
        if public_numeric_tokens & (private_numeric_tokens or set()):
            raise AIVCStageFailure(
                stage="research_planning", code="privacy_violation",
                category="evidence_validation", recoverable=False,
            )

    understanding = {
        "whatCompanySells": _interpretation_payload(plan.what_company_sells),
        "buyers": [_interpretation_payload(item) for item in plan.buyers],
        "businessModels": [_interpretation_payload(item) for item in plan.business_models],
        "industryContexts": [_interpretation_payload(item) for item in plan.industry_contexts],
        "workflows": [_interpretation_payload(item) for item in plan.workflows],
        "geographies": [_interpretation_payload(item) for item in plan.geographies],
        "reportingPeriods": [_interpretation_payload(item) for item in plan.reporting_periods],
        "uncertainties": plan.uncertainties,
    }
    return {
        "schemaVersion": "ai-vc-model-research-plan.v1",
        "status": "model_authored",
        "companyUnderstanding": understanding,
        "methodologySelections": [selection.model_dump(mode="json") for selection in plan.methodology_selections],
        "researchTasks": [
            {
                "id": f"research_{index:02d}",
                "purpose": task.purpose,
                "question": task.question,
                "rationale": task.rationale,
                "publicSearchContext": task.public_search_context,
                "evidenceIds": task.evidence_ids,
                "importance": task.importance,
            }
            for index, task in enumerate(plan.research_tasks, 1)
        ],
        "researchQuestionsSource": "model_authored_presearch",
    }


def ensure_model_research_plan(
    db: Session, *, deck: Any, operation_id: str, company: dict[str, Any],
    source_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist one bounded, evidence-grounded interpretation before web search."""
    from app.services.ai_vc.skills.registry import load_builtin_skill_catalog

    key = f"ai-vc-research-plan:{operation_id}"
    existing = db.query(DeckLlmArtifact).filter_by(deck_id=deck.id, artifact_key=key).one_or_none()
    if existing is not None:
        return existing.payload_json or {}
    source_ids = {str(item.get("factId")) for item in source_facts if item.get("factId")}
    source_binding_rows = sorted(
        (str(item.get("factId")), sha256(str(item.get("text") or "").encode()).hexdigest())
        for item in source_facts if item.get("factId")
    )
    private_numeric_tokens = {
        re.sub(r"\s+", "", value.casefold())
        for item in source_facts
        for value in re.findall(
            r"(?:[$£€]\s*)?\d[\d,.]*(?:\s*(?:%|[kmb]))?",
            str(item.get("text") or ""), re.IGNORECASE,
        )
        if not re.fullmatch(r"(?:19|20)\d{2}", value.strip())
        and (len(re.sub(r"\D", "", value)) >= 2 or re.search(r"[$£€%kmb]", value, re.IGNORECASE))
    }
    catalog = load_builtin_skill_catalog()
    payload = {
        "companyEvidence": company,
        "allowedCompanyEvidenceIds": sorted(source_ids),
        "methodologyCatalog": [
            {
                "name": skill.name,
                "description": skill.description,
                "retrievalPurposes": skill.retrieval_purposes,
            }
            for skill in catalog.values()
        ],
        "limits": {
            "maxResearchTasks": min(8, settings.ai_vc_research_max_searches),
            "publicContextMustExcludePrivateFacts": True,
        },
    }
    diagnostics: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    try:
        raw, metrics = _stage_call(
            db, deck=deck, operation_id=operation_id, stage="research_planning",
            payload=payload, system=_RESEARCH_PLANNING_SYSTEM,
            response_model=ResearchPlanningStage,
            max_output_tokens=settings.ai_vc_research_max_tokens,
            recovery=False, retrieval_trace={"companyEvidenceIds": sorted(source_ids)},
        )
        parsed = ResearchPlanningStage.model_validate(raw)
        result = _validate_model_research_plan(
            parsed, source_ids=source_ids, deck_title=str(getattr(deck, "title", "") or ""),
            private_numeric_tokens=private_numeric_tokens,
        )
    except AIVCStageFailure as failure:
        diagnostics.append(failure.diagnostic())
        if failure.recoverable:
            try:
                raw, metrics = _stage_call(
                    db, deck=deck, operation_id=operation_id, stage="research_planning",
                    payload=payload, system=_RESEARCH_PLANNING_SYSTEM,
                    response_model=ResearchPlanningStage,
                    max_output_tokens=settings.ai_vc_research_max_tokens,
                    recovery=True, retrieval_trace={"companyEvidenceIds": sorted(source_ids)},
                )
                parsed = ResearchPlanningStage.model_validate(raw)
                result = _validate_model_research_plan(
                    parsed, source_ids=source_ids, deck_title=str(getattr(deck, "title", "") or ""),
                    private_numeric_tokens=private_numeric_tokens,
                )
            except Exception as recovery_failure:
                diagnostics.append(
                    recovery_failure.diagnostic()
                    if isinstance(recovery_failure, AIVCStageFailure)
                    else {"stage":"research_planning", "code":"plan_validation", "category":"evidence_validation"}
                )
                result = {
                    "schemaVersion":"ai-vc-model-research-plan.v1", "status":"unavailable",
                    "companyUnderstanding":{}, "methodologySelections":[], "researchTasks":[],
                    "researchQuestionsSource":"unavailable", "diagnostics":diagnostics,
                }
        else:
            result = {
                "schemaVersion":"ai-vc-model-research-plan.v1", "status":"unavailable",
                "companyUnderstanding":{}, "methodologySelections":[], "researchTasks":[],
                "researchQuestionsSource":"unavailable", "diagnostics":diagnostics,
            }
    except Exception as exc:
        result = {
            "schemaVersion":"ai-vc-model-research-plan.v1", "status":"unavailable",
            "companyUnderstanding":{}, "methodologySelections":[], "researchTasks":[],
            "researchQuestionsSource":"unavailable",
            "diagnostics":[{"stage":"research_planning", "code":"plan_validation", "category":"evidence_validation", "errorType":type(exc).__name__}],
        }
    result = {
        **result,
        "operationId": operation_id,
        "sourceEvidenceIds": sorted(source_ids),
        "sourceBindingHash": sha256(
            json.dumps(source_binding_rows, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    row = DeckLlmArtifact(
        id=generate_id("researchplan"), deck_id=deck.id,
        artifact_type="instant_deck_model_research_plan", artifact_key=key,
        schema_version="ai-vc-model-research-plan.v1", status="ready",
        summary="Evidence-grounded model-authored company understanding and research plan.",
        payload_json=result, metrics_json=metrics,
    )
    db.add(row)
    db.commit()
    return result


def _source_only_payload(
    *, company: dict[str, Any], questions: list[str], diagnostics: list[dict[str, Any]],
    evidence_pack: dict[str, Any], source_ids: set[str], external_ids: set[str],
    skill_trace: dict[str, Any], questions_source: str,
) -> dict[str, Any]:
    return {
        "companyIntelligence": company,
        "researchQuestions": questions,
        "researchSynthesis": ResearchSynthesis(unknowns=["AI-VC synthesis unavailable"]).model_dump(mode="json"),
        "investmentMemo": {"status": "source_only", "policy": "The final author must use classified current evidence only."},
        "financialAnalysis": {
            "verifiedCompanyMetrics": [item for item in company.get("financialEvidence", []) if item.get("evidenceClass") == "COMPANY_SOURCE"],
            "managementProjections": [item for item in company.get("financialEvidence", []) if item.get("evidenceClass") == "MANAGEMENT_PROJECTION"],
            "externalBenchmarks": [], "derivedCalculations": [], "investorImplications": [],
            "narrativeSelections": [], "missingFinancialProof": ["AI-VC financial analysis unavailable"],
        },
        "vcInferences": [],
        "narrativeGapAnalysis": NarrativeGapAnalysis().model_dump(mode="json"),
        "narrativeStrategy": {
            "status": "source_only_fallback",
            "instruction": "Author the strongest evidence-grounded investor narrative; do not mirror source order or count.",
        },
        # Deliberately no fake one-slide/fixed-role architecture. The final
        # designer remains the author in this truthfully degraded mode.
        "deckArchitecture": [],
        "evidenceGaps": ["AI-VC strategy unavailable; current source evidence remains authoritative."],
        "investmentCommitteeReview": InvestmentCommitteeReview(
            concerns=["AI-VC strategy analysis was unavailable."],
            missing_proof=["Review the internal run diagnostic before regeneration."],
        ).model_dump(mode="json"),
        "analysisStatus": "source_only_fallback",
        "architectureSource": "final_designer_source_only",
        "diagnostics": diagnostics,
        "methodologyRetrievalTrace": evidence_pack.get("methodologyRetrievalTrace") or {},
        "researchQuestionsSource": questions_source,
        "skillExecutionTrace": skill_trace,
        "architectureIntelligenceTrace": {
            "decisionBasis": "source_only_fallback", "companyEvidenceIds": sorted(source_ids),
            "externalEvidenceIds": sorted(external_ids),
        },
    }


def resolve_strategy_research_questions(
    company: dict[str, Any], external_research: dict[str, Any],
) -> tuple[list[str], str]:
    """Use only model-authored pre-search or executed-search questions."""
    authored = [
        str(attempt.get("modelResearchQuestion"))
        for attempt in external_research.get("attemptTrace", [])
        if isinstance(attempt, dict) and attempt.get("modelResearchQuestion")
    ]
    if authored:
        return list(dict.fromkeys(authored)), "model_authored_search"
    planned = [
        str(task.get("question"))
        for task in (external_research.get("modelResearchPlan") or {}).get("researchTasks", [])
        if isinstance(task, dict) and task.get("question")
    ]
    return list(dict.fromkeys(planned)), (
        "model_authored_presearch" if planned else "unavailable"
    )


def execute_ai_vc_runtime(
    db: Session, *, deck: Any, operation_id: str, source_facts: list[dict],
    source_slides: list[dict], external_research: dict, design_guidance: dict | None = None,
) -> dict[str, Any]:
    """Execute the production AI-VC graph and persist a truthful final state."""
    from app.services.ai_vc.advisory import persist_investment_critique
    from app.services.llm.ai_vc_retrieval import build_ai_vc_evidence_pack
    from app.services.llm.instant_vc_strategy import (
        _typed_deck_architecture,
        _validate_evidence_boundaries,
        build_company_intelligence,
        build_evidence_graph,
    )
    from app.services.ai_vc.skills.resolver import (
        resolve_core_skill_plan,
        resolve_model_skill_plan,
        skill_plan_trace,
        stage_skill_context,
    )

    final_key = "vc-strategy:" + operation_id
    existing = db.query(DeckLlmArtifact).filter_by(deck_id=deck.id, artifact_key=final_key).one_or_none()
    if existing is not None:
        if existing.status != "ready":
            raise ValueError("Existing VC strategy runtime is not safe to replay")
        return existing.payload_json or {}

    company = build_company_intelligence(source_facts, source_slides)
    model_research_plan = external_research.get("modelResearchPlan") or {}
    skill_plan = (
        resolve_model_skill_plan(model_research_plan)
        if model_research_plan.get("status") == "model_authored"
        else resolve_core_skill_plan()
    )
    questions, questions_source = resolve_strategy_research_questions(company, external_research)
    research_plan = {
        "schemaVersion":"ai-vc-model-research-plan.v1",
        "status":model_research_plan.get("status") or "unavailable",
        "tasks":model_research_plan.get("researchTasks") or [],
    }
    evidence_graph = build_evidence_graph(source_facts, external_research)
    evidence_pack = build_ai_vc_evidence_pack(
        company_facts=source_facts, external_research=external_research, questions=questions,
        research_tasks=research_plan["tasks"], db=db, deck_id=deck.id,
        design_guidance=design_guidance,
    )
    source_ids = {str(f.get("factId")) for f in source_facts if f.get("factId")}
    external_ids = {str(c.get("id")) for c in external_research.get("claims", []) if c.get("id")}
    allowed_ids = sorted(source_ids | external_ids)
    diagnostics: list[dict[str, Any]] = []
    stage_metrics: list[dict[str, Any]] = []
    recovery_used = False

    memory_context: dict[str, Any] = {
        "schemaVersion": "ai-vc-memory.v1", "memories": [],
        "policy": {"companyClaims": "current source evidence always outranks memory"},
    }
    memory_identity: str | None = None
    if settings.ai_database_url:
        try:
            from app.db.session import AiSessionLocal
            from app.services.ai_vc.memory import company_identity, load_memory_context

            memory_identity = company_identity(
                workspace_id=str(deck.workspace_id), company_name=str(deck.title or ""),
                website_url=getattr(getattr(deck, "brand_profile", None), "website_source_url", None),
            )
            memory_db = AiSessionLocal()
            try:
                memory_context = load_memory_context(
                    memory_db, workspace_id=str(deck.workspace_id),
                    company_identity_value=memory_identity, user_id=getattr(deck, "user_id", None),
                )
            finally:
                memory_db.close()
        except Exception:
            # Memory is advisory. Its outage cannot suppress the current deck.
            memory_context = {
                "schemaVersion": "ai-vc-memory.v1", "memories": [],
                "status": "unavailable",
                "policy": {"companyClaims": "current source evidence always outranks memory"},
            }

    active_skills_by_stage = {
        "analysis": stage_skill_context(skill_plan, "analysis"),
        "narrative": stage_skill_context(skill_plan, "narrative"),
    }
    common = {
        "companyIntelligence": company,
        "researchPlan": research_plan,
        "evidenceGraph": evidence_graph,
        "retrievalEvidencePack": evidence_pack,
        "verifiedExternalResearch": external_research,
        "researchQuestions": questions,
        "researchQuestionsSource": questions_source,
        "allowedCompanyEvidenceIds": sorted(source_ids),
        "allowedExternalEvidenceIds": sorted(external_ids),
        "historicalAdvisoryMemory": memory_context,
        "skillSelection": skill_plan_trace(skill_plan),
    }

    from app.services.ai_vc.observability import (
        TRACE_SCHEMA,
        TRACE_TYPE,
        build_retrieval_context_trace,
        persist_internal_artifact,
    )

    company_financial_ids = {
        str(item.get("source_id") or item.get("sourceId") or "")
        for item in evidence_pack.get("companyFinancialEvidence", [])
        if item.get("source_id") or item.get("sourceId")
    }
    trace_payload = {
        **common,
        "activeSkillsByStage": active_skills_by_stage,
    }
    retrieval_trace = build_retrieval_context_trace(
        evidence_pack=evidence_pack,
        provider_payload=trace_payload,
        skill_trace=skill_plan_trace(skill_plan),
        active_skills_by_stage=active_skills_by_stage,
        company_evidence_ids=source_ids,
        company_financial_ids=company_financial_ids,
        external_evidence_ids=external_ids,
        external_research=external_research,
    )
    trace_row = persist_internal_artifact(
        db, deck_id=deck.id, artifact_type=TRACE_TYPE,
        artifact_key=f"ai-vc-trace:{operation_id}", schema_version=TRACE_SCHEMA,
        summary="Internal AI-VC retrieval, context, grounding and stage trace.",
        payload={
            "operationId": operation_id,
            "sourceSlideCount": len(source_slides),
            "retrieval": retrieval_trace,
            "status": "pre_provider",
        },
        metrics={"retrievalTokens": retrieval_trace["totalRetrievalTokens"]},
    )
    db.commit()

    def run_stage(
        *, stage: str, payload: dict[str, Any], system: str,
        response_model: type[BaseModel], tokens: int,
    ) -> dict[str, Any]:
        nonlocal recovery_used
        try:
            value, metrics = _stage_call(
                db, deck=deck, operation_id=operation_id, stage=stage, payload=payload,
                system=system, response_model=response_model, max_output_tokens=tokens,
                recovery=False, retrieval_trace=retrieval_trace,
            )
            stage_metrics.append({"stage": stage, **metrics})
            return value
        except AIVCStageFailure as primary:
            diagnostics.append(primary.diagnostic())
            if recovery_used or not primary.recoverable:
                raise
            recovery_used = True
            reduced = {
                **payload,
                "recoveryInstruction": (
                    "Return the smallest schema-valid artifact. Preserve evidence IDs exactly; "
                    "leave unsupported arrays empty instead of explaining or inventing."
                ),
            }
            value, metrics = _stage_call(
                db, deck=deck, operation_id=operation_id, stage=stage, payload=reduced,
                system=system, response_model=response_model,
                # A recovery still needs the full stage output budget. Capping
                # it at a few thousand tokens cannot fit an AnalysisStage or
                # NarrativeStage and turns into a guaranteed max-token
                # truncation (provider_incomplete) on real decks.
                max_output_tokens=tokens, recovery=True, retrieval_trace=retrieval_trace,
            )
            stage_metrics.append({"stage": stage, "recovery": True, **metrics})
            return value

    analysis_holder: dict[str, Any] = {}

    def understand(_state):
        return {"company_intelligence": company, "evidence_nodes": evidence_graph.get("nodes", [])}

    def plan(_state):
        return {"research_tasks": research_plan["tasks"]}

    def research(_state):
        return {"external_research": external_research}

    def analyze(_state):
        value = run_stage(
            stage="analysis",
            payload={**common, "activeSkills": active_skills_by_stage["analysis"]},
            system=_ANALYSIS_SYSTEM,
            response_model=AnalysisStage, tokens=settings.ai_vc_analysis_max_tokens,
        )
        analysis_holder.update(value)
        return {"investment_memo": value["investmentMemo"], "evidence_gaps": value["evidenceGaps"]}

    def finance(_state):
        return {"financial_model": analysis_holder["financialAnalysis"]}

    def committee(_state):
        return {"ic_review": analysis_holder["investmentCommitteeReview"]}

    def follow_up(_state):
        return {"research_iterations": 1, "additional_reasoning_calls": 1}

    def narrative(_state):
        value = run_stage(
            stage="narrative",
            payload={
                **common,
                **analysis_holder,
                "activeSkills": active_skills_by_stage["narrative"],
            },
            system=_NARRATIVE_SYSTEM, response_model=NarrativeStage,
            tokens=settings.ai_vc_analysis_max_tokens,
        )
        return {
            "narrative_strategy": value["narrativeStrategy"],
            "deck_architecture": value["deckArchitecture"],
            "narrative_gap_analysis": value["narrativeGapAnalysis"],
        }

    graph = build_ai_vc_graph(
        understand=understand, plan=plan, research=research, analyze=analyze,
        finance=finance, committee=committee, follow_up=follow_up, narrative=narrative,
    )
    try:
        result = graph.invoke({
            "schema_version": SCHEMA_VERSION, "deck_id": deck.id, "operation_id": operation_id,
            "research_iterations": 0, "max_research_iterations": 1,
            "additional_reasoning_calls": 0, "max_additional_reasoning_calls": 1,
            "budget_remaining_cents": settings.instant_html_vc_memo_max_cost_cents,
        })
        raw_architecture = result["deck_architecture"]
        architecture = DeckArchitecture.model_validate(raw_architecture)
        slides = [
            {
                "id": slide.id or f"planned-slide-{index:02d}", "role": slide.role,
                "objective": slide.objective, "headlineDirection": slide.headline_direction,
                "keyMessage": slide.key_message, "evidenceRefs": slide.evidence_ids,
                "calculationIds": slide.calculation_ids, "visualPrimitive": slide.visual_primitive,
                "visualIntent": slide.visual_intent,
                "investorBelief": slide.investor_belief,
                "evidenceShape": slide.evidence_shape,
                "copyBudgetWords": slide.copy_budget_words,
            }
            for index, slide in enumerate(architecture.slides, 1)
        ]
        payload = {
            "companyIntelligence": company, "researchQuestions": questions,
            **analysis_holder,
            "narrativeGapAnalysis": result["narrative_gap_analysis"],
            "narrativeStrategy": {
                **result["narrative_strategy"],
                "recommendedSlideCount": architecture.recommended_slide_count,
                "slideCountRationale": architecture.rationale,
                "thesis": architecture.core_thesis,
            },
            "deckArchitecture": slides,
            "analysisStatus": "ready",
            "architectureSource": "model_authored",
            "diagnostics": diagnostics,
            "methodologyRetrievalTrace": evidence_pack.get("methodologyRetrievalTrace") or {},
            "researchQuestionsSource": questions_source,
            "skillExecutionTrace": skill_plan_trace(skill_plan),
            "architectureIntelligenceTrace": {
                "decisionBasis": "model_authored_from_investment_memo",
                "companyEvidenceIds": sorted(source_ids), "externalEvidenceIds": sorted(external_ids),
                "recommendedSlideCount": architecture.recommended_slide_count,
            },
        }
        payload = _validate_evidence_boundaries(payload, source_ids, external_ids)
        payload["typedDeckArchitecture"] = _typed_deck_architecture(payload)
        if set(
            evidence_id for slide in slides for evidence_id in slide.get("evidenceRefs", [])
        ) - set(allowed_ids):
            raise AIVCStageFailure(
                stage="narrative", code="architecture_validation",
                category="architecture_validation", recoverable=False,
            )
    except AIVCStageFailure as failure:
        diagnostics.append(failure.diagnostic())
        payload = _source_only_payload(
            company=company, questions=questions, diagnostics=diagnostics,
            evidence_pack=evidence_pack, source_ids=source_ids, external_ids=external_ids,
            skill_trace=skill_plan_trace(skill_plan), questions_source=questions_source,
        )
    except Exception as exc:
        failure = _classify_failure("strategy_validation", exc, outcome_known=True)
        diagnostics.append(failure.diagnostic())
        payload = _source_only_payload(
            company=company, questions=questions, diagnostics=diagnostics,
            evidence_pack=evidence_pack, source_ids=source_ids, external_ids=external_ids,
            skill_trace=skill_plan_trace(skill_plan), questions_source=questions_source,
        )

    from app.services.ai_vc.observability import grounding_metrics

    product_knowledge_ids = {
        str(item.get("source_id") or item.get("sourceId") or "")
        for values in evidence_pack.get("vcMethodologyByPurpose", {}).values()
        for item in values if isinstance(item, dict)
    } | {
        str(item.get("source_id") or item.get("sourceId") or "")
        for item in evidence_pack.get("visualDesignGuidance", []) if isinstance(item, dict)
    }
    grounding = grounding_metrics(
        payload, company_ids=source_ids, external_ids=external_ids,
        product_knowledge_ids=product_knowledge_ids,
    )
    trace_row.payload_json = {
        **(trace_row.payload_json or {}),
        "status": payload["analysisStatus"],
        "stageMetrics": stage_metrics,
        "failureDiagnostics": diagnostics,
        "grounding": grounding,
    }
    unknown_provider_outcomes = sum(
        bool(item.get("transportStarted"))
        and item.get("billingOutcomeKnown") is False
        for item in diagnostics
        if isinstance(item, dict)
    )
    known_input_tokens = sum(int(item.get("inputTokens") or 0) for item in stage_metrics)
    known_output_tokens = sum(int(item.get("outputTokens") or 0) for item in stage_metrics)
    known_cost_cents = sum(float(item.get("estimatedCostCents") or 0) for item in stage_metrics)
    trace_row.metrics_json = {
        **(trace_row.metrics_json or {}),
        "analysisStatus": payload["analysisStatus"],
        "knownInputTokens": known_input_tokens,
        "knownOutputTokens": known_output_tokens,
        "knownCostCents": known_cost_cents,
        "totalInputTokens": None if unknown_provider_outcomes else known_input_tokens,
        "totalOutputTokens": None if unknown_provider_outcomes else known_output_tokens,
        "totalCostCents": None if unknown_provider_outcomes else known_cost_cents,
        "usageMeasurementComplete": unknown_provider_outcomes == 0,
        "costMeasurementComplete": unknown_provider_outcomes == 0,
        "unknownProviderOutcomeCount": unknown_provider_outcomes,
        "recoveryUsed": recovery_used,
    }
    final = DeckLlmArtifact(
        id=generate_id("vcstrategy"), deck_id=deck.id, artifact_type=ARTIFACT_TYPE,
        artifact_key=final_key, schema_version=SCHEMA_VERSION, status="ready",
        summary=(
            "Model-authored AI-VC investment narrative."
            if payload["analysisStatus"] == "ready"
            else "Truthfully degraded source-only authoring; AI-VC strategy unavailable."
        ),
        payload_json=payload,
        metrics_json={
            "analysisStatus": payload["analysisStatus"],
            "architectureSource": payload["architectureSource"],
            "recoveryUsed": recovery_used, "stages": stage_metrics,
            "diagnostics": diagnostics, "traceArtifactId": trace_row.id,
            "grounding": grounding,
        },
    )
    db.add(final)
    persist_investment_critique(
        db, deck_id=deck.id, operation_id=operation_id,
        review=payload["investmentCommitteeReview"],
    )
    from app.services.ai_vc.observability import refresh_operation_usage_trace
    refresh_operation_usage_trace(db, deck_id=deck.id, operation_id=operation_id)
    db.commit()
    if (
        settings.ai_database_url
        and memory_identity
        and payload.get("analysisStatus") == "ready"
    ):
        try:
            from app.db.session import AiSessionLocal
            from app.services.ai_vc.memory import persist_company_snapshot

            memory_db = AiSessionLocal()
            try:
                persist_company_snapshot(
                    memory_db, workspace_id=str(deck.workspace_id),
                    company_identity_value=memory_identity, deck_id=deck.id,
                    user_id=getattr(deck, "user_id", None), source_artifact_id=final.id,
                    company_intelligence=company,
                    narrative_strategy=payload.get("narrativeStrategy") or {},
                )
                memory_db.commit()
            except Exception:
                memory_db.rollback()
            finally:
                memory_db.close()
        except Exception:
            pass
    return payload


def strategy_status(db: Session, *, deck_id: str, operation_id: str | None = None) -> dict[str, Any] | None:
    query = db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck_id,
        DeckLlmArtifact.artifact_type == ARTIFACT_TYPE,
    )
    if operation_id:
        query = query.filter(DeckLlmArtifact.artifact_key == "vc-strategy:" + operation_id)
    row = query.order_by(DeckLlmArtifact.created_at.desc()).first()
    if row is None:
        attempt_query = db.query(DeckLlmArtifact).filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == ATTEMPT_TYPE,
        )
        if operation_id:
            attempt_query = attempt_query.filter(
                DeckLlmArtifact.artifact_key.like(f"vc-strategy-stage:{operation_id}:%")
            )
        attempt = attempt_query.order_by(DeckLlmArtifact.created_at.desc()).first()
        if attempt is None:
            return None
        metrics = attempt.metrics_json or {}
        return {
            "status": "recovering" if attempt.status == "running" else "failed",
            "architectureSource": None,
            "recoveryUsed": bool((attempt.payload_json or {}).get("recovery")),
            "diagnostics": [
                {
                    key: metrics[key]
                    for key in ("stage", "code", "category", "recoverable")
                    if key in metrics
                }
            ] if attempt.status == "failed" else [],
        }
    payload = row.payload_json or {}
    metrics = row.metrics_json or {}
    return {
        "status": payload.get("analysisStatus") or "failed",
        "architectureSource": payload.get("architectureSource"),
        "recoveryUsed": bool(metrics.get("recoveryUsed")),
        "diagnostics": metrics.get("diagnostics") or [],
    }
