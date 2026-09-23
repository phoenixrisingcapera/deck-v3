from app.services.llm.ai_vc_retrieval import AIVCRetrievalRouter, RetrievalRequest, build_ai_vc_evidence_pack


def _router():
    return AIVCRetrievalRouter(
        company_facts=[{"factId": "arr", "text": "ARR is USD 1 million", "confidence": "high", "sourceSlideIds": ["s1"]}],
        external_research={"claims": [
            {"id": "market", "category": "external_research", "topic": "market_context", "text": "The category grew in 2025", "url": "https://example.com/market"},
            {"id": "competitor", "category": "external_research", "topic": "competitor_positioning", "text": "Incumbent sells scheduling", "url": "https://example.com/product"},
        ]},
    )


def test_company_fact_never_routes_to_web_research():
    results = _router().retrieve(RetrievalRequest(purpose="company_fact", query="current ARR"))
    assert [item.source_id for item in results] == ["arr"]
    assert {item.evidence_class for item in results} == {"COMPANY_SOURCE"}


def test_market_and_competitor_purposes_use_only_matching_external_topics():
    market = _router().retrieve(RetrievalRequest(purpose="market_context", query="category growth"))
    competitors = _router().retrieve(RetrievalRequest(purpose="competitor_landscape", query="incumbent"))
    assert [item.source_id for item in market] == ["market"]
    assert [item.source_id for item in competitors] == ["competitor"]
    assert all(item.evidence_class == "EXTERNAL_RESEARCH" for item in market + competitors)


def test_evidence_pack_preserves_purpose_and_does_not_mix_lanes():
    router = _router()
    pack = build_ai_vc_evidence_pack(
        company_facts=router.company_facts,
        external_research=router.external_research,
        questions=["market growth", "competitive landscape"],
    )
    assert pack["companyEvidence"][0]["source_type"] == "company_source"
    assert pack["companyFinancialEvidence"][0]["source_id"] == "arr"
    assert pack["externalEvidenceByPurpose"]["market_context"][0]["source_type"] == "external_research"
    assert pack["policy"]["company_fact"] == "company_source_only"
    assert pack["methodologyRetrievalTrace"]["retrievalMode"] == "lexical_fallback"


def test_research_tasks_route_by_vc_purpose_not_question_position():
    router = AIVCRetrievalRouter(
        company_facts=[],
        external_research={"claims": [
            {"id": "retention", "category": "external_research", "topic": "customer_economics",
             "text": "Retention economics benchmark", "url": "https://example.com/retention"},
            {"id": "market", "category": "external_research", "topic": "market_context",
             "text": "Market context", "url": "https://example.com/market"},
        ]},
    )
    pack = build_ai_vc_evidence_pack(
        company_facts=router.company_facts,
        external_research=router.external_research,
        questions=["How should retention be assessed?"],
        research_tasks=[{
            "purpose": "retention",
            "question": "How should retention be assessed?",
        }],
    )
    assert set(pack["externalEvidenceByPurpose"]) == {"retention"}
    assert [item["source_id"] for item in pack["externalEvidenceByPurpose"]["retention"]] == ["retention"]


def test_design_embeddings_are_advisory_product_knowledge_for_the_llm():
    router = _router()
    pack = build_ai_vc_evidence_pack(
        company_facts=router.company_facts,
        external_research=router.external_research,
        questions=["market growth"],
        design_guidance={
            "traceId": "design-trace",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "chunks": [{
                "chunkId": "design-chunk",
                "scope": "global_knowledge",
                "content": "Use a single dominant visual hierarchy for the thesis.",
                "similarityScore": 0.88,
            }],
        },
    )
    assert pack["visualDesignGuidance"][0]["evidence_class"] == "PRODUCT_KNOWLEDGE"
    assert pack["designKnowledgeTrace"] == {
        "retrievalMode": "semantic_embeddings",
        "traceId": "design-trace",
        "provider": "openai",
        "model": "text-embedding-3-small",
        "selectedChunkIds": ["design-chunk"],
        "evidenceClass": "PRODUCT_KNOWLEDGE",
        "factualAuthority": False,
    }


def test_evidence_pack_prefers_semantic_vc_methodology_embeddings(monkeypatch):
    calls = []

    def retrieve(_db, *, deck_id, query_text, chunk_types, limit):
        calls.append((deck_id, query_text, chunk_types, limit))
        return {
            "status": "ready",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "traceId": f"trace-{len(calls)}",
            "chunks": [{
                "id": "chunk-semantic",
                "sourceKey": "knowledge:vc_methodology:v1:semantic-paper",
                "contentText": "Semantic investment methodology selected for this company.",
                "similarityScore": 0.91,
                "metadata": {
                    "documentId": "semantic-paper",
                    "knowledgeVersion": "vc-investment-methodology.v1",
                    "knowledgeAge": "historical",
                    "title": "Semantic paper",
                    "publicationYear": 2020,
                    "contentHash": "a" * 64,
                    "sourceUrl": "https://example.com/paper",
                    "permittedRetrievalPurposes": [
                        "investment_screening", "team_assessment", "traction_interpretation",
                        "business_model_analysis", "financing_dynamics", "investment_objections",
                        "portfolio_value_creation",
                    ],
                },
            }],
        }

    monkeypatch.setattr("app.services.llm.vector_retrieval_service.retrieve_relevant_chunks", retrieve)
    router = _router()
    pack = build_ai_vc_evidence_pack(
        company_facts=router.company_facts,
        external_research=router.external_research,
        questions=["market growth", "competitive landscape"],
        db=object(),
        deck_id="deck-1",
    )
    trace = pack["methodologyRetrievalTrace"]
    assert trace["retrievalMode"] == "semantic_embeddings"
    assert trace["selectedDocumentIds"] == ["semantic-paper"]
    assert trace["vectorProvider"] == "openai"
    assert len(trace["vectorTraceIds"]) == 7
    assert len(calls) == 7
    assert all(call[2] == ["vc_methodology_knowledge"] for call in calls)
    assert all("Company context: ARR is USD 1 million" in call[1] for call in calls)
