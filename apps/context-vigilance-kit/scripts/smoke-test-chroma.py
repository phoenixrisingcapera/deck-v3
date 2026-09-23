#!/usr/bin/env python3
"""
smoke-test-chroma.py

Minimal end-to-end probe of ChromaDB integration. Reads a handful of real
markdown files from the included sources, ingests them into a
PersistentClient at .chroma/, and runs a sample similarity query.

Goal: prove the integration is easy and elegant before formalizing deps
or writing the real ingester. Throwaway script — delete after the real
ingest-to-chroma.py lands.

Usage:
    python scripts/smoke-test-chroma.py
"""
from __future__ import annotations

from pathlib import Path

import chromadb


KIT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_PATH = KIT_ROOT / ".chroma"
COLLECTION_NAME = "smoke-test-corpus"

# A small, hand-picked set of real corpus files spanning multiple sources.
SAMPLE_FILES = [
    "/Users/mpstaton/code/lossless-monorepo/context-v/skills/pseudomonorepos/SKILL.md",
    "/Users/mpstaton/code/lossless-monorepo/context-v/skills/context-vigilance/SKILL.md",
    "/Users/mpstaton/code/lossless-monorepo/ai-labs/context-v/explorations/Collate-Context-Files-into-Context-Vigilance-as-Repo-&-Project.md",
    "/Users/mpstaton/code/lossless-monorepo/ai-labs/context-v/explorations/ChromaDB-as-Context-Improvement-Across-Everything-Everyone.md",
    "/Users/mpstaton/code/lossless-monorepo/ai-labs/context-vigilance-kit/README.md",
]

QUERIES = [
    "what is the boundary between a kit corpus and the splash rollup?",
    "how do agent skills work in this repo?",
    "why are we using chromadb",
]


def main() -> int:
    print(f"chromadb version: {chromadb.__version__}")
    print(f"persistent client path: {CHROMA_PATH}")
    print()

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # Reset on each smoke run for deterministic output.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Smoke test for context-vigilance-kit Chroma integration."},
    )

    docs: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []
    for i, path_str in enumerate(SAMPLE_FILES):
        p = Path(path_str)
        if not p.exists():
            print(f"  skip (missing): {path_str}")
            continue
        text = p.read_text(encoding="utf-8")
        docs.append(text)
        metadatas.append(
            {
                "source_path": str(p),
                "filename": p.name,
                "size_chars": len(text),
            }
        )
        ids.append(f"smoke-{i}")
        print(f"  ingested: {p.name}  ({len(text)} chars)")

    print()
    print("adding to collection (auto-embeds with default all-MiniLM-L6-v2 via onnxruntime)...")
    collection.add(documents=docs, metadatas=metadatas, ids=ids)
    print(f"collection size: {collection.count()}")
    print()

    for q in QUERIES:
        print(f"query: {q!r}")
        result = collection.query(query_texts=[q], n_results=2)
        for rank, (doc_id, dist, meta) in enumerate(
            zip(result["ids"][0], result["distances"][0], result["metadatas"][0])
        ):
            print(f"  #{rank + 1}  distance={dist:.4f}  {meta['filename']}  ({doc_id})")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
