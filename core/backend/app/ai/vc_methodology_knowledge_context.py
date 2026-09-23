from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any


CORPUS_VERSION = "vc-investment-methodology.v1"
ALLOWED_PURPOSES = frozenset({
    "investment_screening", "team_assessment", "traction_interpretation",
    "business_model_analysis", "financing_dynamics", "investment_objections",
    "portfolio_value_creation",
})


def _corpus_path() -> Path:
    return Path(__file__).resolve().parents[2] / "llm_knowledge" / "vc_investment_methodology" / "corpus.json"


@lru_cache(maxsize=1)
def load_vc_methodology_corpus() -> dict[str, Any]:
    path = _corpus_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"corpusVersion": "missing", "documents": [], "status": "missing"}
    if payload.get("corpusVersion") != CORPUS_VERSION or payload.get("evidenceClass") != "PRODUCT_KNOWLEDGE":
        return {"corpusVersion": "invalid", "documents": [], "status": "invalid"}
    documents = []
    for item in payload.get("documents") or []:
        purposes = set(item.get("permittedRetrievalPurposes") or [])
        if (
            isinstance(item, dict)
            and item.get("evidenceClass") == "PRODUCT_KNOWLEDGE"
            and item.get("currentMarketAuthority") is False
            and purposes
            and purposes <= ALLOWED_PURPOSES
        ):
            documents.append(item)
    return {**payload, "documents": documents, "status": "ready"}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", value.lower()) if token not in {"the", "and", "for", "with"}}


def retrieve_vc_methodology(*, purpose: str, query: str, limit: int = 4) -> list[dict[str, Any]]:
    if purpose not in ALLOWED_PURPOSES:
        return []
    corpus = load_vc_methodology_corpus()
    query_tokens = _tokens(query)
    eligible = []
    for item in corpus.get("documents") or []:
        if purpose not in (item.get("permittedRetrievalPurposes") or []):
            continue
        searchable = " ".join((str(item.get("title") or ""), str(item.get("abstract") or ""), str(item.get("category") or "")))
        overlap = len(query_tokens & _tokens(searchable))
        if overlap:
            eligible.append((overlap, str(item.get("documentId") or ""), item))
    eligible.sort(key=lambda row: (-row[0], row[1]))
    return [
        {
            "content": item["abstract"],
            "sourceType": "product_knowledge",
            "evidenceClass": "PRODUCT_KNOWLEDGE",
            "sourceId": item["documentId"],
            "corpusVersion": corpus["corpusVersion"],
            "knowledgeAge": item["knowledgeAge"],
            "currentMarketAuthority": False,
            "provenance": {
                "title": item["title"],
                "authors": item["authors"],
                "publication": item["publication"],
                "publicationYear": item["publicationYear"],
                "url": item["sourceUrl"],
                "contentHash": item["contentHash"],
            },
        }
        for _, _, item in eligible[: max(1, min(limit, 8))]
    ]


def vc_methodology_knowledge_health() -> dict[str, Any]:
    corpus = load_vc_methodology_corpus()
    documents = corpus.get("documents") or []
    return {
        "ready": corpus.get("status") == "ready" and bool(documents),
        "name": corpus.get("name") or "VC investment methodology corpus",
        "version": corpus.get("corpusVersion"),
        "source": "compiled_json" if corpus.get("status") == "ready" else corpus.get("status"),
        "indexPath": str(_corpus_path()),
        "documentCount": len(documents),
        "sourceRecordCount": corpus.get("sourceRecordCount", 0),
        "rejectedRecordCount": len(corpus.get("rejectedRecords") or []),
        "evidenceClass": "PRODUCT_KNOWLEDGE",
        "currentMarketAuthority": False,
    }
