"""Purpose-driven retrieval boundary for the AI-VC workflow.

Retrieval policy is product logic: a market lookup must not establish company
traction, and product methodology must not become business evidence. Backends
can change later without leaking framework-specific retriever objects into the
investment workflow.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


from app.services.ai_vc.models import RetrievalPurpose


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: RetrievalPurpose
    query: str = Field(min_length=2, max_length=500)
    filters: dict[str, Any] = Field(default_factory=dict)
    max_results: int = Field(default=6, ge=1, le=20)


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    source_type: Literal[
        "company_source", "external_research", "product_knowledge",
        "visual_design_knowledge", "workspace_history",
    ]
    source_id: str
    evidence_class: Literal["COMPANY_SOURCE", "EXTERNAL_RESEARCH", "PRODUCT_KNOWLEDGE", "WORKSPACE_HISTORY"]
    url: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)
    corpus_version: str | None = None
    knowledge_age: Literal["historical", "recent"] | None = None
    current_market_authority: bool | None = None


_EXTERNAL_PURPOSE_TOPICS = {
    "problem_severity": {"market_context", "customer_economics"},
    "customer_buyer": {"market_context", "customer_economics"},
    "market_context": {"market_context"},
    "market_size": {"market_context"},
    "competitor_landscape": {"competitor_positioning"},
    "why_now": {"why_now"},
    "business_model_benchmark": {"business_model_benchmark"},
    "regulatory_context": {"regulatory_context"},
    "customer_economics": {"customer_economics"},
    "acquisition_dynamics": {"acquisition_dynamics"},
    "comparable_outcomes": {"comparable_outcomes"},
    "funding_outcomes": {"comparable_outcomes"},
    "pricing": {"business_model_benchmark"},
    "retention": {"customer_economics"},
    "margins": {"business_model_benchmark", "customer_economics"},
    "sales_motion": {"acquisition_dynamics"},
    "scalability": {"market_context", "business_model_benchmark"},
    "capital_intensity": {"business_model_benchmark", "comparable_outcomes"},
    "substitutes": {"competitor_positioning"},
    "differentiation": {"competitor_positioning"},
    "defensibility": {"competitor_positioning", "market_context"},
    "major_risks": {"market_context", "regulatory_context"},
    "milestones": {"comparable_outcomes", "regulatory_context"},
    "investor_objections": {"market_context", "competitor_positioning", "customer_economics"},
    "financial_potential": {"business_model_benchmark", "customer_economics", "market_context"},
}
_VISUAL_GUIDANCE_PURPOSES = {
    "design_guidance", "visual_chart_guidance", "visual_diagram_guidance",
    "visual_composition_guidance", "visual_financial_guidance", "visual_market_guidance",
    "visual_rhythm_guidance",
}
_VC_METHODOLOGY_PURPOSES = {
    "investment_screening", "team_assessment", "traction_interpretation",
    "business_model_analysis", "financing_dynamics", "investment_objections",
    "portfolio_value_creation",
}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", value.lower()) if token not in {"the", "and", "for", "with"}}


def _rank(query: str, content: str) -> tuple[int, int]:
    overlap = len(_tokens(query) & _tokens(content))
    return overlap, -len(content)


class AIVCRetrievalRouter:
    """Route retrieval by factual purpose, never by a generic RAG switch."""

    def __init__(
        self, *, company_facts: list[dict], external_research: dict,
        product_guidance: list[dict] | None = None, workspace_history: list[dict] | None = None,
    ) -> None:
        self.company_facts = company_facts
        self.external_research = external_research
        self.product_guidance = product_guidance or []
        self.workspace_history = workspace_history or []

    def retrieve(self, request: RetrievalRequest) -> list[RetrievalResult]:
        if request.purpose in {"company_fact", "company_hypothesis"}:
            return self._company(request)
        if request.purpose in _EXTERNAL_PURPOSE_TOPICS:
            return self._external(request)
        if request.purpose in _VISUAL_GUIDANCE_PURPOSES:
            eligible = [
                item for item in self.product_guidance
                if not item.get("purposes") or request.purpose in item.get("purposes", [])
            ]
            return self._advisory(request, eligible, "visual_design_knowledge", "PRODUCT_KNOWLEDGE")
        if request.purpose in _VC_METHODOLOGY_PURPOSES:
            from app.ai.vc_methodology_knowledge_context import retrieve_vc_methodology

            return [
                RetrievalResult(
                    content=item["content"], source_type="product_knowledge",
                    evidence_class="PRODUCT_KNOWLEDGE", source_id=item["sourceId"],
                    provenance=item["provenance"], corpus_version=item["corpusVersion"],
                    knowledge_age=item["knowledgeAge"], current_market_authority=False,
                    confidence=1.0,
                )
                for item in retrieve_vc_methodology(
                    purpose=request.purpose, query=request.query, limit=request.max_results,
                )
            ]
        if request.purpose == "historical_company_context":
            return self._advisory(request, self.workspace_history, "workspace_history", "WORKSPACE_HISTORY")
        return []

    def _company(self, request: RetrievalRequest) -> list[RetrievalResult]:
        rows = []
        for fact in self.company_facts:
            text = str(fact.get("text") or "").strip()
            if not text:
                continue
            rows.append(RetrievalResult(
                content=text, source_type="company_source", evidence_class="COMPANY_SOURCE",
                source_id=str(fact.get("factId") or ""),
                provenance={"sourceSlideIds": fact.get("sourceSlideIds") or [], "field": fact.get("field")},
                confidence=1.0 if fact.get("confidence") == "high" else 0.5,
            ))
        return sorted(rows, key=lambda item: _rank(request.query, item.content), reverse=True)[:request.max_results]

    def _external(self, request: RetrievalRequest) -> list[RetrievalResult]:
        allowed_topics = _EXTERNAL_PURPOSE_TOPICS[request.purpose]
        rows = []
        for claim in self.external_research.get("claims", []):
            if claim.get("category") != "external_research" or claim.get("topic") not in allowed_topics:
                continue
            rows.append(RetrievalResult(
                content=str(claim.get("text") or ""), source_type="external_research",
                evidence_class="EXTERNAL_RESEARCH", source_id=str(claim.get("id") or ""),
                url=claim.get("url"), confidence=1.0,
                provenance={"publisher": claim.get("publisher"), "publicationDate": claim.get("publicationDate"),
                            "retrievalDate": claim.get("retrievalDate"), "evidenceSha256": claim.get("evidenceSha256")},
            ))
        return sorted(rows, key=lambda item: _rank(request.query, item.content), reverse=True)[:request.max_results]

    def _advisory(self, request: RetrievalRequest, values: list[dict], source_type: str, evidence_class: str) -> list[RetrievalResult]:
        rows = [RetrievalResult(content=str(item.get("content") or item.get("text") or ""),
                                source_type=source_type, evidence_class=evidence_class,
                                source_id=str(item.get("sourceId") or item.get("id") or ""),
                                provenance=item.get("provenance") or {}, confidence=item.get("confidence"))
                for item in values if item.get("content") or item.get("text")]
        return sorted(rows, key=lambda item: _rank(request.query, item.content), reverse=True)[:request.max_results]


def build_ai_vc_evidence_pack(
    *, company_facts: list[dict], external_research: dict, questions: list[str],
    research_tasks: list[dict] | None = None, db: Any | None = None,
    deck_id: str | None = None, design_guidance: dict | None = None,
) -> dict:
    """Build a compact purpose-labelled pack without rereading the source deck."""
    router = AIVCRetrievalRouter(company_facts=company_facts, external_research=external_research)
    company = router.retrieve(RetrievalRequest(purpose="company_fact", query="company product customer traction business model", max_results=12))
    company_financial_candidates = router.retrieve(RetrievalRequest(
        purpose="company_fact",
        query="revenue ARR MRR pricing growth retention churn margin customers burn runway funding capital milestones",
        max_results=12,
    ))
    financial_terms = {
        "revenue", "arr", "mrr", "pricing", "price", "growth", "retention", "churn",
        "margin", "customers", "burn", "runway", "funding", "capital", "valuation",
        "profit", "loss", "bookings", "gmv", "cac", "ltv", "subscription",
    }
    company_financial = [
        item for item in company_financial_candidates
        if (_tokens(item.content) & financial_terms)
        or re.search(r"(?:[$£€]\s?\d|\d(?:[\d,.]*\d)?\s?%)", item.content)
    ]
    external: dict[str, list[dict]] = {}
    if research_tasks:
        routed_tasks = [
            (str(task.get("purpose") or ""), str(task.get("question") or ""))
            for task in research_tasks[:12]
            if isinstance(task, dict) and str(task.get("purpose") or "") in _EXTERNAL_PURPOSE_TOPICS
        ]
    else:
        legacy_purposes = [
            "market_context", "why_now", "competitor_landscape", "business_model_benchmark",
            "regulatory_context", "customer_economics", "acquisition_dynamics", "comparable_outcomes",
        ]
        routed_tasks = list(zip(legacy_purposes, questions[: len(legacy_purposes)]))
    for purpose, question in routed_tasks:
        external[purpose] = [item.model_dump() for item in router.retrieve(
            RetrievalRequest(purpose=purpose, query=question, max_results=3)
        )]
    external_suppressed: list[dict[str, Any]] = []
    seen_external: set[tuple[str, str]] = set()
    for purpose, values in external.items():
        unique = []
        for item in values:
            content = str(item.get("content") or "")
            identity = (str(item.get("source_id") or ""), hashlib.sha256(content.encode()).hexdigest())
            if identity in seen_external:
                external_suppressed.append({
                    "sourceId": identity[0], "contentHash": identity[1], "purpose": purpose,
                    "characterCount": len(content), "estimatedTokens": max(1, len(content.encode()) // 4),
                    "reason": "duplicate_content_suppressed",
                })
                continue
            seen_external.add(identity)
            unique.append(item)
        external[purpose] = unique
    methodology_queries = {
        "investment_screening": "venture investment screening criteria product market team risk",
        "team_assessment": "founder management team assessment venture capital",
        "traction_interpretation": "startup traction commercialization validation evidence",
        "business_model_analysis": "venture business model economics scalability",
        "financing_dynamics": "venture financing stages valuation investment outcomes",
        "investment_objections": "venture rejection criteria uncertainty investor objections",
        "portfolio_value_creation": "venture capital value creation post investment outcomes",
    }
    lexical_methodology = {
        purpose: [item.model_dump() for item in router.retrieve(
            RetrievalRequest(purpose=purpose, query=query, max_results=3)
        )]
        for purpose, query in methodology_queries.items()
    }
    methodology = dict(lexical_methodology)
    vector_trace_ids: list[str] = []
    vector_provider = None
    vector_model = None
    semantic_purposes: list[str] = []
    business_context = " ".join(
        [str(item.get("text") or "") for item in company_facts[:6]] + list(questions[:3])
    ).strip()[:1200]
    if db is not None and deck_id:
        from app.services.llm.vector_retrieval_service import retrieve_relevant_chunks

        for purpose, base_query in methodology_queries.items():
            retrieval = retrieve_relevant_chunks(
                db,
                deck_id=deck_id,
                query_text=f"{base_query}. Company context: {business_context}",
                chunk_types=["vc_methodology_knowledge"],
                limit=6,
            )
            semantic = []
            for chunk in retrieval.get("chunks") or []:
                metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
                if purpose not in (metadata.get("permittedRetrievalPurposes") or []):
                    continue
                semantic.append({
                    "content": str(chunk.get("contentText") or ""),
                    "source_type": "product_knowledge",
                    "source_id": str(metadata.get("documentId") or chunk.get("sourceKey") or chunk.get("id") or ""),
                    "evidence_class": "PRODUCT_KNOWLEDGE",
                    "url": metadata.get("sourceUrl"),
                    "provenance": {
                        "title": metadata.get("title"),
                        "publicationYear": metadata.get("publicationYear"),
                        "contentHash": metadata.get("contentHash"),
                        "retrievalTraceId": retrieval.get("traceId"),
                        "similarityScore": chunk.get("similarityScore"),
                    },
                    "confidence": chunk.get("similarityScore"),
                    "corpus_version": metadata.get("knowledgeVersion"),
                    "knowledge_age": metadata.get("knowledgeAge"),
                    "current_market_authority": False,
                })
                if len(semantic) >= 3:
                    break
            if semantic:
                methodology[purpose] = semantic
                semantic_purposes.append(purpose)
                if retrieval.get("traceId"):
                    vector_trace_ids.append(str(retrieval["traceId"]))
                vector_provider = retrieval.get("provider") or vector_provider
                vector_model = retrieval.get("model") or vector_model
    if len(semantic_purposes) == len(methodology_queries):
        retrieval_mode = "semantic_embeddings"
    elif semantic_purposes:
        retrieval_mode = "hybrid_semantic_lexical"
    else:
        retrieval_mode = "lexical_fallback"
    methodology_suppressed: list[dict[str, Any]] = []
    seen_methodology: set[tuple[str, str]] = set()
    for purpose, values in methodology.items():
        unique = []
        for item in values:
            content = str(item.get("content") or "")
            source_id = str(item.get("source_id") or item.get("sourceId") or "")
            identity = (source_id, hashlib.sha256(content.encode()).hexdigest())
            if identity in seen_methodology:
                methodology_suppressed.append({
                    "sourceId": source_id, "contentHash": identity[1], "purpose": purpose,
                    "characterCount": len(content), "estimatedTokens": max(1, len(content.encode()) // 4),
                    "reason": "duplicate_content_suppressed",
                })
                continue
            seen_methodology.add(identity)
            unique.append(item)
        methodology[purpose] = unique
    selected_methodology_ids = sorted({
        item["source_id"] for values in methodology.values() for item in values
    })
    guidance_chunks = [
        {
            "content": str(item.get("content") or ""),
            "source_type": "visual_design_knowledge",
            "source_id": str(item.get("chunkId") or item.get("sourceKey") or ""),
            "evidence_class": "PRODUCT_KNOWLEDGE",
            "similarity_score": item.get("similarityScore"),
        }
        for item in (design_guidance or {}).get("chunks") or []
        if isinstance(item, dict)
        and str(item.get("scope") or "") == "global_knowledge"
        and str(item.get("content") or "").strip()
    ]
    return {
        "schemaVersion": "ai-vc-evidence-pack.v1",
        "companyEvidence": [item.model_dump() for item in company],
        "companyFinancialEvidence": [item.model_dump() for item in company_financial],
        "externalEvidenceByPurpose": external,
        "vcMethodologyByPurpose": methodology,
        "visualDesignGuidance": guidance_chunks,
        "methodologyRetrievalTrace": {
            "corpusVersion": "vc-investment-methodology.v1",
            "selectedDocumentIds": selected_methodology_ids,
            "evidenceClass": "PRODUCT_KNOWLEDGE",
            "currentMarketAuthority": False,
            "retrievalMode": retrieval_mode,
            "semanticPurposes": semantic_purposes,
            "vectorTraceIds": vector_trace_ids,
            "vectorProvider": vector_provider,
            "vectorModel": vector_model,
            "businessContextHash": hashlib.sha256(business_context.encode("utf-8")).hexdigest(),
            "queryHashes": {
                purpose: hashlib.sha256(query.encode("utf-8")).hexdigest()
                for purpose, query in methodology_queries.items()
            },
            "suppressedDuplicates": methodology_suppressed,
        },
        "designKnowledgeTrace": {
            "retrievalMode": "semantic_embeddings" if guidance_chunks else "unavailable",
            "traceId": (design_guidance or {}).get("traceId"),
            "provider": (design_guidance or {}).get("provider"),
            "model": (design_guidance or {}).get("model"),
            "selectedChunkIds": [item["source_id"] for item in guidance_chunks],
            "evidenceClass": "PRODUCT_KNOWLEDGE",
            "factualAuthority": False,
        },
        "externalRetrievalTrace": {
            "queryHashes": {
                purpose: hashlib.sha256(question.encode("utf-8")).hexdigest()
                for purpose, question in routed_tasks
            },
            "suppressedDuplicates": external_suppressed,
        },
        "policy": {
            "company_fact": "company_source_only",
            "company_financial_fact": "company_source_only_with_status_and_period_preserved",
            "external_purposes": "verified_external_research_only",
            "design_guidance": "advisory_not_factual",
            "historical_company_context": "requires_separate_company_provenance",
            "vc_methodology": "internal_reasoning_only_never_current_market_or_company_evidence",
        },
    }
