"""Internal, content-minimizing observability for the mounted AI-VC path.

Artifacts produced here contain identities, hashes, counts and usage metadata.
They deliberately do not copy confidential source prose or provider bodies.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.core.security import generate_id
from app.db.models import DeckLlmArtifact


TRACE_TYPE = "instant_deck_ai_vc_operation_trace"
MANIFEST_TYPE = "instant_deck_provider_context_manifest"
TRACE_SCHEMA = "instant-deck-ai-vc-observability.v1"
MANIFEST_SCHEMA = "instant-deck-provider-context-manifest.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def approximate_tokens(value: Any) -> int:
    return max(1, len(_canonical(value).encode("utf-8")) // 4)


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _evidence_ids(value: Any) -> tuple[set[str], set[str]]:
    company: set[str] = set()
    external: set[str] = set()
    if isinstance(value, dict):
        fact_id = value.get("factId")
        if fact_id:
            company.add(str(fact_id))
        if value.get("category") == "external_research" and value.get("id"):
            external.add(str(value["id"]))
        for item in value.values():
            nested_company, nested_external = _evidence_ids(item)
            company.update(nested_company)
            external.update(nested_external)
    elif isinstance(value, list):
        for item in value:
            nested_company, nested_external = _evidence_ids(item)
            company.update(nested_company)
            external.update(nested_external)
    return company, external


def _entry(
    *, lane: str, purpose: str, rank: int, value: dict[str, Any], provider_strings: set[str],
) -> tuple[dict[str, Any], str]:
    content = str(value.get("content") or value.get("text") or "")
    source_id = str(value.get("source_id") or value.get("sourceId") or value.get("id") or "")
    provenance = value.get("provenance") if isinstance(value.get("provenance"), dict) else {}
    content_hash = _hash(content)
    injected = bool(source_id and content and source_id in provider_strings and content in provider_strings)
    record = {
        "lane": lane,
        "retrievalPurpose": purpose,
        "queryHash": _hash(purpose),
        "chunkId": source_id,
        "documentId": str(
            provenance.get("documentId") or provenance.get("sourceKey") or source_id
        ),
        "chunkType": str(value.get("source_type") or value.get("sourceType") or lane),
        "evidenceClass": str(value.get("evidence_class") or value.get("evidenceClass") or ""),
        "score": value.get("similarity_score", value.get("confidence")),
        "rank": rank,
        "contentHash": content_hash,
        "characterCount": len(content),
        "estimatedTokens": max(1, len(content.encode("utf-8")) // 4) if content else 0,
        "injected": injected,
        "injectedStages": ["analysis", "narrative"] if injected else [],
        "droppedReason": None if injected else "absent_from_provider_context",
        "corpusVersion": value.get("corpus_version") or value.get("corpusVersion"),
        "knowledgeAge": value.get("knowledge_age") or value.get("knowledgeAge"),
    }
    return record, content_hash


def build_retrieval_context_trace(
    *, evidence_pack: dict[str, Any], provider_payload: dict[str, Any], skill_trace: dict[str, Any],
    active_skills_by_stage: dict[str, dict[str, Any]], company_evidence_ids: set[str],
    company_financial_ids: set[str], external_evidence_ids: set[str],
    ambiguous_evidence_ids: set[str] | None = None,
    external_research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe retrieval and actual injection without storing retrieved prose."""
    provider_strings = set(_strings(provider_payload))
    raw: list[tuple[str, str, dict[str, Any]]] = []
    raw.extend(("company_evidence", "company_fact", item) for item in evidence_pack.get("companyEvidence", []))
    raw.extend(("company_financial", "financial_potential", item) for item in evidence_pack.get("companyFinancialEvidence", []))
    for purpose, values in (evidence_pack.get("externalEvidenceByPurpose") or {}).items():
        raw.extend(("external_research", str(purpose), item) for item in values)
    for purpose, values in (evidence_pack.get("vcMethodologyByPurpose") or {}).items():
        raw.extend(("product_knowledge", str(purpose), item) for item in values)
    raw.extend(("design_knowledge", "design_guidance", item) for item in evidence_pack.get("visualDesignGuidance", []))

    records: list[dict[str, Any]] = []
    for lane, purpose, value in raw:
        if not isinstance(value, dict):
            continue
        rank = 1 + sum(1 for record in records if record["lane"] == lane and record["retrievalPurpose"] == purpose)
        record, _ = _entry(
            lane=lane, purpose=purpose, rank=rank, value=value,
            provider_strings=provider_strings,
        )
        records.append(record)
    methodology_query_hashes = (evidence_pack.get("methodologyRetrievalTrace") or {}).get("queryHashes") or {}
    external_query_hashes = (evidence_pack.get("externalRetrievalTrace") or {}).get("queryHashes") or {}
    for record in records:
        if record["lane"] == "product_knowledge":
            record["queryHash"] = methodology_query_hashes.get(record["retrievalPurpose"], record["queryHash"])
        elif record["lane"] == "external_research":
            record["queryHash"] = external_query_hashes.get(record["retrievalPurpose"], record["queryHash"])
    for lane, trace_key in (
        ("product_knowledge", "methodologyRetrievalTrace"),
        ("external_research", "externalRetrievalTrace"),
    ):
        for item in (evidence_pack.get(trace_key) or {}).get("suppressedDuplicates", []):
            purpose = str(item.get("purpose") or "unknown")
            query_hashes = methodology_query_hashes if lane == "product_knowledge" else external_query_hashes
            records.append({
                "lane": lane,
                "retrievalPurpose": purpose,
                "queryHash": query_hashes.get(purpose, _hash(purpose)),
                "chunkId": str(item.get("sourceId") or ""),
                "documentId": str(item.get("sourceId") or ""),
                "chunkType": lane,
                "evidenceClass": "PRODUCT_KNOWLEDGE" if lane == "product_knowledge" else "EXTERNAL_RESEARCH",
                "score": None,
                "rank": None,
                "contentHash": item.get("contentHash"),
                "characterCount": int(item.get("characterCount") or 0),
                "estimatedTokens": int(item.get("estimatedTokens") or 0),
                "injected": False,
                "injectedStages": [],
                "droppedReason": str(item.get("reason") or "duplicate_content_suppressed"),
                "corpusVersion": None,
                "knowledgeAge": None,
            })

    selected_skills: list[dict[str, Any]] = []
    selection_reason = {
        str(item.get("name")): item.get("reason")
        for item in skill_trace.get("selectedSkills", []) if isinstance(item, dict)
    }
    hashes = skill_trace.get("skillHashes") or {}
    for stage, active in active_skills_by_stage.items():
        for skill in active.get("skills", []) if isinstance(active, dict) else []:
            if not isinstance(skill, dict):
                continue
            selected_skills.append({
                "skillId": skill.get("name"),
                "name": skill.get("name"),
                "contentHash": skill.get("contentHash") or hashes.get(skill.get("name")),
                "stage": stage,
                "reason": selection_reason.get(str(skill.get("name"))) or "selected_for_stage",
                "injected": str(skill.get("name") or "") in provider_strings
                    and str(skill.get("instructions") or "") in provider_strings,
            })

    injected = [item for item in records if item["injected"]]
    lane_counts = {
        lane: {
            "retrieved": sum(item["lane"] == lane for item in records),
            "injected": sum(item["lane"] == lane and item["injected"] for item in records),
            "dropped": sum(item["lane"] == lane and not item["injected"] for item in records),
        }
        for lane in sorted({item["lane"] for item in records})
    }
    return {
        "schemaVersion": TRACE_SCHEMA,
        "skillCatalogVersion": skill_trace.get("catalogVersion"),
        "skills": selected_skills,
        "retrievalRecords": records,
        "laneCounts": lane_counts,
        "totalRetrieved": len(records),
        "totalInjected": len(injected),
        "totalDropped": len(records) - len(injected),
        "totalRetrievalTokens": sum(item["estimatedTokens"] for item in records),
        "methodology": evidence_pack.get("methodologyRetrievalTrace") or {},
        "designKnowledge": evidence_pack.get("designKnowledgeTrace") or {},
        "companyEvidence": {
            "allowedIds": sorted(company_evidence_ids),
            "allowedCount": len(company_evidence_ids),
            "financialIds": sorted(company_financial_ids),
            "financialCount": len(company_financial_ids),
            "selectedIds": sorted({item["chunkId"] for item in injected if item["lane"].startswith("company_")}),
            "ambiguousIds": sorted(ambiguous_evidence_ids or set()),
        },
        "externalResearch": {
            "admittedClaimIds": sorted(external_evidence_ids),
            "admittedClaimCount": len(external_evidence_ids),
            "injectedClaimIds": sorted({item["chunkId"] for item in injected if item["lane"] == "external_research"}),
            "sourceIds": sorted({
                str(claim.get("url") or claim.get("sourceId") or "")
                for claim in (external_research or {}).get("claims", [])
                if isinstance(claim, dict) and (claim.get("url") or claim.get("sourceId"))
            }),
            "rejectedCandidateCount": len((external_research or {}).get("gaps", [])),
            "rejectionReasons": sorted({
                str(gap.get("reason") or "unspecified")[:160]
                for gap in (external_research or {}).get("gaps", []) if isinstance(gap, dict)
            }),
        },
    }


def build_provider_context_manifest(
    *, operation_id: str, stage: str, provider: str, model: str,
    system: str, payload: dict[str, Any], retrieval_trace: dict[str, Any] | None = None,
    prompt_version: str | None = None,
    system_hash: str | None = None,
) -> dict[str, Any]:
    """Hash the exact logical context assembled immediately before transport."""
    payload_strings = set(_strings(payload))
    injected_chunks = []
    for record in (retrieval_trace or {}).get("retrievalRecords", []):
        if stage not in (record.get("injectedStages") or []):
            continue
        chunk_id = str(record.get("chunkId") or "")
        if not chunk_id or chunk_id not in payload_strings:
            raise ValueError(f"Retrieval trace declares absent injected chunk: {chunk_id or 'missing-id'}")
        injected_chunks.append({
            "chunkId": chunk_id,
            "contentHash": record.get("contentHash"),
            "lane": record.get("lane"),
        })
    active_skills = []
    for item in (retrieval_trace or {}).get("skills", []):
        if not item.get("injected") or item.get("stage") != stage:
            continue
        skill_id = str(item.get("skillId") or "")
        if not skill_id or skill_id not in payload_strings:
            raise ValueError(f"Skill trace declares absent active skill: {skill_id or 'missing-id'}")
        active_skills.append({
            "skillId": skill_id, "contentHash": item.get("contentHash"), "stage": item.get("stage")
        })
    discovered_company_ids, discovered_external_ids = _evidence_ids(payload)
    authoring = payload.get("authoringContext") if isinstance(payload.get("authoringContext"), dict) else {}
    company_component = payload.get("companyIntelligence") or authoring.get("companyIntelligence") or {}
    architecture_component = (
        payload.get("deckArchitecture")
        or (payload.get("strategy") or {}).get("deckArchitecture")
        or (authoring.get("strategy") or {}).get("deckArchitecture")
        or []
    )
    visual_component = payload.get("visualIntelligence") or authoring.get("visualIntelligence") or {}
    approved_assets = payload.get("approvedAssets") or authoring.get("approvedAssets") or []
    return {
        "schemaVersion": MANIFEST_SCHEMA,
        "operationId": operation_id,
        "stage": stage,
        "provider": provider,
        "model": model,
        "promptVersion": prompt_version,
        "systemHash": system_hash or _hash(system),
        "logicalPayloadHash": _hash(_canonical(payload)),
        "approximateInputTokens": approximate_tokens({"system": system, "payload": payload}),
        "companyEvidenceIds": sorted({
            *(str(item) for item in payload.get("allowedCompanyEvidenceIds", [])),
            *discovered_company_ids,
        } or set((retrieval_trace or {}).get("companyEvidence", {}).get("selectedIds", []))),
        "externalEvidenceIds": sorted({
            *(str(item) for item in payload.get("allowedExternalEvidenceIds", [])),
            *discovered_external_ids,
        } or set((retrieval_trace or {}).get("externalResearch", {}).get("injectedClaimIds", []))),
        "injectedChunks": injected_chunks,
        "activeSkills": active_skills,
        "methodologyChunkIds": sorted(item["chunkId"] for item in injected_chunks if item["lane"] == "product_knowledge"),
        "designChunkIds": sorted(item["chunkId"] for item in injected_chunks if item["lane"] == "design_knowledge"),
        "memoryRecordIds": sorted({
            str(item.get("id") or item.get("memoryId"))
            for item in payload.get("historicalAdvisoryMemory", {}).get("memories", [])
            if isinstance(item, dict) and (item.get("id") or item.get("memoryId"))
        }),
        "componentHashes": {
            "companyIntelligence": _hash(_canonical(company_component)),
            "deckArchitectureInputs": _hash(_canonical(architecture_component)),
            "visualIntelligenceInputs": _hash(_canonical(visual_component)),
            "approvedAssetReferences": _hash(_canonical(approved_assets)),
        },
        "componentCounts": {
            "companyEvidence": len(discovered_company_ids),
            "externalEvidence": len(discovered_external_ids),
            "approvedAssets": len(approved_assets) if isinstance(approved_assets, list) else 0,
            "renderedVisualAssets": len(visual_component.get("rendered_assets", []))
                if isinstance(visual_component, dict) else 0,
        },
    }


def grounding_metrics(
    output: dict[str, Any], *, company_ids: set[str], external_ids: set[str],
    product_knowledge_ids: set[str], calculation_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Measure evidence references and authority-boundary violations."""
    references: list[str] = []
    numeric_objects = 0
    unsupported_numeric_objects = 0
    architecture_total = 0
    architecture_grounded = 0
    numeric_pattern = re.compile(r"(?:[$£€]\s?\d|\b\d+(?:[.,]\d+)?\s?%)")

    def visit(value: Any) -> None:
        nonlocal numeric_objects, unsupported_numeric_objects
        if isinstance(value, dict):
            local_refs: list[str] = []
            for key in ("evidenceRefs", "evidence_ids", "sourceFactIds", "source_ids"):
                if isinstance(value.get(key), list):
                    local_refs.extend(str(item) for item in value[key])
            references.extend(local_refs)
            textual = " ".join(str(item) for item in value.values() if isinstance(item, str))
            if numeric_pattern.search(textual):
                numeric_objects += 1
                if not set(local_refs) & (company_ids | external_ids | (calculation_ids or set())):
                    unsupported_numeric_objects += 1
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(output)
    slides = output.get("deckArchitecture") if isinstance(output.get("deckArchitecture"), list) else []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        architecture_total += 1
        slide_refs = {str(item) for item in slide.get("evidenceRefs", [])}
        if slide_refs & (company_ids | external_ids | (calculation_ids or set())):
            architecture_grounded += 1
    unique = set(references)
    valid_company = unique & company_ids
    valid_external = unique & external_ids
    invalid = unique - company_ids - external_ids - (calculation_ids or set())
    product_as_fact = unique & product_knowledge_ids
    valid = valid_company | valid_external | (unique & (calculation_ids or set()))
    return {
        "referencedCompanyEvidenceIds": sorted(valid_company),
        "referencedExternalEvidenceIds": sorted(valid_external),
        "invalidEvidenceReferences": sorted(invalid),
        "productKnowledgeUsedAsEvidenceIds": sorted(product_as_fact),
        "unsupportedNumericClaimObjects": unsupported_numeric_objects,
        "numericClaimObjects": numeric_objects,
        "architectureSlides": architecture_total,
        "architectureSlidesWithEvidenceBasis": architecture_grounded,
        "traceableReferencePercent": round((len(valid) / len(unique) * 100), 2) if unique else 100.0,
        "authorityBoundaryValid": not invalid and not product_as_fact,
    }


def persist_internal_artifact(
    db: Session, *, deck_id: str, artifact_type: str, artifact_key: str,
    schema_version: str, summary: str, payload: dict[str, Any], metrics: dict[str, Any] | None = None,
) -> DeckLlmArtifact:
    row = db.query(DeckLlmArtifact).filter_by(deck_id=deck_id, artifact_key=artifact_key).one_or_none()
    if row is None:
        row = DeckLlmArtifact(
            id=generate_id("aivcobs"), deck_id=deck_id, artifact_type=artifact_type,
            artifact_key=artifact_key, schema_version=schema_version, status="ready",
            summary=summary, payload_json=payload, metrics_json=metrics or {},
        )
        db.add(row)
    else:
        row.artifact_type = artifact_type
        row.schema_version = schema_version
        row.status = "ready"
        row.summary = summary
        row.payload_json = payload
        row.metrics_json = metrics or {}
    db.flush()
    return row


def refresh_operation_usage_trace(
    db: Session, *, deck_id: str, operation_id: str,
) -> dict[str, Any] | None:
    """Aggregate every mounted paid lane into the single operation trace."""
    from app.db.models import InstantDeckOperation, InstantDeckProviderAttempt

    trace = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id, artifact_key=f"ai-vc-trace:{operation_id}",
    ).one_or_none()
    if trace is None:
        return None
    operation = db.query(InstantDeckOperation).filter_by(id=operation_id).one_or_none()
    operation_attempts = (
        db.query(InstantDeckProviderAttempt).filter_by(operation_id=operation_id).all()
        if operation is not None
        else []
    )
    strategy_attempts = db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck_id,
        DeckLlmArtifact.artifact_type == "instant_deck_vc_strategy_stage_attempt",
        DeckLlmArtifact.artifact_key.like(f"vc-strategy-stage:{operation_id}:%"),
    ).all()
    research_attempts = [
        row for row in db.query(DeckLlmArtifact).filter(
            DeckLlmArtifact.deck_id == deck_id,
            DeckLlmArtifact.artifact_type == "instant_deck_public_research_attempt",
        ).all()
        if str(((row.payload_json or {}).get("authorization") or {}).get("authorization_id") or "")
        .startswith(f"instant-{operation_id}-")
    ]
    strategy_cost = sum(float((row.metrics_json or {}).get("estimatedCostCents") or 0) for row in strategy_attempts)
    research_cost = sum(float((row.metrics_json or {}).get("researchProviderDollars") or 0) * 100 for row in research_attempts)
    operation_cost = float(getattr(operation, "actual_provider_cost_cents", 0) or 0)
    operation_input = int(getattr(operation, "actual_input_tokens", 0) or 0)
    operation_output = int(getattr(operation, "actual_output_tokens", 0) or 0)
    strategy_input = sum(int((row.metrics_json or {}).get("inputTokens") or 0) for row in strategy_attempts)
    strategy_output = sum(int((row.metrics_json or {}).get("outputTokens") or 0) for row in strategy_attempts)
    research_input = sum(int((row.metrics_json or {}).get("inputTokens") or 0) for row in research_attempts)
    research_output = sum(int((row.metrics_json or {}).get("outputTokens") or 0) for row in research_attempts)
    measured_cost = operation_cost + strategy_cost + research_cost
    known_input = operation_input + strategy_input + research_input
    known_output = operation_output + strategy_output + research_output
    unknown_artifact_outcomes = [
        row for row in [*strategy_attempts, *research_attempts]
        if (row.metrics_json or {}).get("transportStarted") is True
        and (row.metrics_json or {}).get("outcomeKnown") is not True
    ]
    unknown_operation_outcomes = [
        row for row in operation_attempts
        if row.outcome_known is not True
    ]
    cost_complete = not unknown_operation_outcomes and all(
        (row.metrics_json or {}).get("costKnown") is True
        for row in [*strategy_attempts, *research_attempts]
    )
    usage_complete = not unknown_artifact_outcomes and not unknown_operation_outcomes
    unknown_outcome_count = len(unknown_artifact_outcomes) + len(unknown_operation_outcomes)
    usage = {
        "operationProviderCostCents": round(operation_cost, 4),
        "aiVCStrategyCostCents": round(strategy_cost, 4),
        "externalResearchCostCents": round(research_cost, 4),
        "knownMeasuredCostCents": round(measured_cost, 4),
        "totalMeasuredCostCents": round(measured_cost, 4) if cost_complete else None,
        "knownInputTokens": known_input,
        "knownOutputTokens": known_output,
        "inputTokens": known_input if usage_complete else None,
        "outputTokens": known_output if usage_complete else None,
        "providerStarts": int(getattr(operation, "provider_request_starts", 0) or 0)
            + sum(int((row.metrics_json or {}).get("providerStarts") or 0) for row in strategy_attempts)
            + sum(int((row.metrics_json or {}).get("providerStarts") or 0) for row in research_attempts),
        "usageMeasurementComplete": usage_complete,
        "costMeasurementComplete": cost_complete,
        "unknownProviderOutcomeCount": unknown_outcome_count,
    }
    trace.metrics_json = {**(trace.metrics_json or {}), **usage}
    trace.payload_json = {**(trace.payload_json or {}), "providerUsage": usage}
    db.flush()
    return usage


def operation_observability_read_model(
    db: Session, *, deck_id: str, operation_id: str,
) -> dict[str, Any] | None:
    """Internal read model for one operation; never mount as a public payload."""
    trace = db.query(DeckLlmArtifact).filter_by(
        deck_id=deck_id, artifact_key=f"ai-vc-trace:{operation_id}",
    ).one_or_none()
    if trace is None:
        return None
    manifests = db.query(DeckLlmArtifact).filter(
        DeckLlmArtifact.deck_id == deck_id,
        DeckLlmArtifact.artifact_type == MANIFEST_TYPE,
        DeckLlmArtifact.artifact_key.like(f"%{operation_id}%"),
    ).order_by(DeckLlmArtifact.created_at.asc()).all()
    return {
        "schemaVersion": TRACE_SCHEMA,
        "operationId": operation_id,
        "traceArtifactId": trace.id,
        "trace": trace.payload_json or {},
        "metrics": trace.metrics_json or {},
        "providerContextManifests": [
            {
                "artifactId": row.id,
                "stage": (row.payload_json or {}).get("stage"),
                "provider": (row.payload_json or {}).get("provider"),
                "model": (row.payload_json or {}).get("model"),
                "logicalPayloadHash": (row.payload_json or {}).get("logicalPayloadHash"),
                "approximateInputTokens": (row.payload_json or {}).get("approximateInputTokens"),
            }
            for row in manifests
        ],
    }
