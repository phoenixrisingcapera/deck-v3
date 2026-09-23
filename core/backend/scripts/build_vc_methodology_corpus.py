#!/usr/bin/env python3
"""Compile the historical Studying VC index into product-owned methodology JSON."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import yaml


CORPUS_VERSION = "vc-investment-methodology.v1"
PURPOSES_BY_CATEGORY = {
    "decision": ["investment_screening", "team_assessment", "investment_objections"],
    "finance": ["financing_dynamics", "business_model_analysis", "portfolio_value_creation"],
    "angel": ["investment_screening", "financing_dynamics", "investment_objections"],
    "economics": ["business_model_analysis", "traction_interpretation", "portfolio_value_creation"],
    "strategy": ["investment_screening", "business_model_analysis", "portfolio_value_creation"],
    "entrepreneurship": ["team_assessment", "traction_interpretation", "investment_screening"],
    "accelerator": ["team_assessment", "traction_interpretation", "portfolio_value_creation"],
    "diversity": ["team_assessment", "investment_objections"],
}


def _frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    _, raw, _ = text.split("---", 2)
    try:
        payload = yaml.safe_load(raw.replace("\t", " "))
    except yaml.YAMLError:
        return None
    return payload if isinstance(payload, dict) else None


def _year(source: str) -> int | None:
    matches = re.findall(r"(?:19|20)\d{2}", source)
    return int(matches[-1]) if matches else None


def compile_corpus(source_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    article_paths = sorted((source_root / "_articles").glob("*.md"))
    for path in article_paths:
        payload = _frontmatter(path)
        if payload is None:
            rejected.append({"path": path.name, "reason": "missing_frontmatter"})
            continue
        title = str(payload.get("title") or "").strip()
        abstract = str(payload.get("abstract") or "").strip()
        url = str(payload.get("link") or "").strip()
        publication = str(payload.get("source") or "").strip()
        category = str(payload.get("category") or "").strip().lower()
        if not title or not abstract or not url or not publication:
            rejected.append({"path": path.name, "reason": "incomplete_provenance_or_content"})
            continue
        key = (title.casefold(), url.casefold())
        if key in seen:
            rejected.append({"path": path.name, "reason": "duplicate"})
            continue
        seen.add(key)
        authors = [
            str(item.get("name") or "").strip()
            for item in (payload.get("authors") or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        publication_year = _year(publication)
        stable = json.dumps(
            {"title": title, "abstract": abstract, "url": url, "publication": publication},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        records.append({
            "documentId": "vc-methodology-" + sha256(stable.encode()).hexdigest()[:20],
            "title": title,
            "authors": authors,
            "publication": publication,
            "publicationYear": publication_year,
            "category": category or "uncategorized",
            "abstract": abstract,
            "sourceUrl": url,
            "sourcePath": f"_articles/{path.name}",
            "evidenceClass": "PRODUCT_KNOWLEDGE",
            "authorityLevel": "scholarly_abstract",
            # This source index was last curated in 2017. Its role is durable
            # methodology, never a moving assertion of present market state.
            "knowledgeAge": "historical",
            "permittedRetrievalPurposes": PURPOSES_BY_CATEGORY.get(
                category,
                ["investment_screening", "investment_objections"],
            ),
            "currentMarketAuthority": False,
            "contentHash": sha256(abstract.encode()).hexdigest(),
            "status": "active",
        })
    return {
        "schemaVersion": "vc-methodology-corpus.v1",
        "corpusVersion": CORPUS_VERSION,
        "name": "Studying Venture Capital methodology corpus",
        "evidenceClass": "PRODUCT_KNOWLEDGE",
        "currentMarketAuthority": False,
        "license": {
            "spdx": "MIT",
            "copyright": "Copyright (c) 2017 Francis Jervis",
            "sourceRepository": "https://github.com/francisjervis/venture-capital-research",
        },
        "sourceRecordCount": len(article_paths),
        "acceptedRecordCount": len(records),
        "rejectedRecords": rejected,
        "documents": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    corpus = compile_corpus(args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(corpus, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
