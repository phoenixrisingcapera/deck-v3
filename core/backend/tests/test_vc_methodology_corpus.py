import json
from pathlib import Path

from app.ai.vc_methodology_knowledge_context import (
    CORPUS_VERSION,
    load_vc_methodology_corpus,
    retrieve_vc_methodology,
)
from app.services.llm.ai_vc_retrieval import AIVCRetrievalRouter, RetrievalRequest
from app.services.llm.deck_chunking_service import _instant_deck_knowledge_chunks


def test_compiled_corpus_accounts_for_all_75_source_records():
    corpus = load_vc_methodology_corpus()
    assert corpus["status"] == "ready"
    assert corpus["corpusVersion"] == CORPUS_VERSION
    assert corpus["sourceRecordCount"] == 75
    assert corpus["acceptedRecordCount"] == 72
    assert len(corpus["documents"]) + len(corpus["rejectedRecords"]) == 75
    assert {item["reason"] for item in corpus["rejectedRecords"]} <= {
        "missing_frontmatter", "incomplete_provenance_or_content", "duplicate",
    }


def test_every_document_is_historical_product_knowledge_with_provenance():
    documents = load_vc_methodology_corpus()["documents"]
    assert documents
    for document in documents:
        assert document["evidenceClass"] == "PRODUCT_KNOWLEDGE"
        assert document["currentMarketAuthority"] is False
        assert document["knowledgeAge"] == "historical"
        assert document["title"] and document["abstract"] and document["sourceUrl"]
        assert len(document["contentHash"]) == 64
        assert document["permittedRetrievalPurposes"]


def test_methodology_retrieval_cannot_route_as_company_or_external_evidence():
    router = AIVCRetrievalRouter(company_facts=[], external_research={"claims": []})
    results = router.retrieve(RetrievalRequest(
        purpose="investment_screening", query="venture investment decision team", max_results=3,
    ))
    assert results
    assert {item.evidence_class for item in results} == {"PRODUCT_KNOWLEDGE"}
    assert all(item.current_market_authority is False for item in results)
    assert router.retrieve(RetrievalRequest(purpose="company_fact", query="traction")) == []
    assert router.retrieve(RetrievalRequest(purpose="why_now", query="market growth")) == []


def test_methodology_is_part_of_the_global_ai_database_seed_set():
    chunks = [item for item in _instant_deck_knowledge_chunks() if item["chunk_type"] == "vc_methodology_knowledge"]
    assert len(chunks) == 72
    assert all(item["metadata_json"]["evidenceClass"] == "PRODUCT_KNOWLEDGE" for item in chunks)
    assert all(item["metadata_json"]["currentMarketAuthority"] is False for item in chunks)


def test_runtime_retrieval_is_deterministic():
    first = retrieve_vc_methodology(purpose="team_assessment", query="founder management team", limit=4)
    second = retrieve_vc_methodology(purpose="team_assessment", query="founder management team", limit=4)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
