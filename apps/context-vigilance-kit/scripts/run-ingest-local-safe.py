#!/usr/bin/env python3
"""
run-ingest-local-safe.py

Thin wrapper around ingest-changelogs-to-graphiti.py that makes the ingest
survive local models which return richer attribute shapes than hosted Claude.

Why this exists
---------------
The entity types in the ingest script declare a docstring and no fields:

    class Repo(BaseModel):
        \"\"\"A repository or project in the Lossless monorepo tree...\"\"\"

With no declared attributes, Graphiti's attribute-extraction step is
unconstrained — the model may return whatever shape it likes. Neo4j node
properties accept only primitives or arrays of primitives, so a nested object
fails the write:

    CypherTypeError: Property values can only be of primitive types or arrays
    thereof. Encountered: Map{tree_path -> ..., supports -> List{...}, ...}

Hosted claude-haiku-4-5 happened to return flat primitives across 150 episodes
(batches 1-3, zero failures). gemma-3-12b-it-qat returns nested objects and
failed on episode 1 of the local run on 2026-08-20.

This wrapper coerces any non-primitive attribute value to a JSON string right
after extraction and before the write, so the graph stays writable regardless
of which model did the extracting. Flat values pass through untouched, so a
Haiku run through this wrapper is byte-identical to running the script directly.

Deliberately a separate file: the tracked ingest script is unmodified, and this
monkeypatch stays visible rather than buried in it. If the fix proves out, the
right home is the ingest script itself (or an upstream graphiti guard).

Usage — identical flags to the underlying script:
    python scripts/run-ingest-local-safe.py --limit 1
    python scripts/run-ingest-local-safe.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "ingest-changelogs-to-graphiti.py"

# The ingest script imports `graphiti_clients` as a top-level module.
sys.path.insert(0, str(SCRIPT_DIR))

PRIMITIVES = (str, int, float, bool, type(None))


def _coerce(value):
    """Return a Neo4j-storable version of one attribute value."""
    if isinstance(value, PRIMITIVES):
        return value
    if isinstance(value, list) and all(isinstance(i, PRIMITIVES) for i in value):
        return value
    # Nested dict, list-of-dicts, or anything else Neo4j will reject.
    return json.dumps(value, ensure_ascii=False, default=str)


def _sanitize(container) -> int:
    """Make one node/edge writable by Neo4j. Returns the number of fixes.

    Two distinct problems, both from unconstrained local-model output:

    1. Non-primitive attribute VALUES -> CypherTypeError.
    2. Empty attribute KEYS and empty LABELS -> TokenNameError:
       "'' is not a valid token name." Neo4j calls labels, relationship types
       and property keys "tokens", and none of them may be empty. A model that
       emits {"": "..."} or a blank entity type produces one.
    """
    fixed = 0

    attributes = getattr(container, "attributes", None)
    if attributes:
        for key, value in list(attributes.items()):
            # An unusable key cannot be repaired — the name carried the meaning.
            if not isinstance(key, str) or not key.strip():
                del attributes[key]
                fixed += 1
                continue
            coerced = _coerce(value)
            if coerced is not value:
                attributes[key] = coerced
                fixed += 1

    # Labels become Neo4j tokens directly. Drop blanks, keep order, dedupe.
    labels = getattr(container, "labels", None)
    if isinstance(labels, list):
        cleaned, seen = [], set()
        for label in labels:
            if isinstance(label, str) and label.strip() and label not in seen:
                seen.add(label)
                cleaned.append(label)
        if cleaned != labels:
            fixed += len(labels) - len(cleaned)
            # Every entity must keep at least one label or it stops being findable.
            container.labels = cleaned or ["Entity"]

    return fixed


def install_patch() -> None:
    """Wrap graphiti's attribute extraction so its output is always writable.

    Patches the name bound inside graphiti_core.graphiti, not the defining
    module — graphiti.py does `from ...node_operations import
    extract_attributes_from_nodes` at import time, so patching the source
    module would leave the already-bound reference untouched.
    """
    import graphiti_core.graphiti as graphiti_module

    original = graphiti_module.extract_attributes_from_nodes
    state = {"fixed": 0, "reported": False}

    async def patched(*args, **kwargs):
        nodes = await original(*args, **kwargs)
        for node in nodes or []:
            state["fixed"] += _sanitize(node)
        if state["fixed"] and not state["reported"]:
            print(
                f"  [local-safe] coerced {state['fixed']} non-primitive "
                f"attribute(s) to JSON strings (further fixes silent)",
                flush=True,
            )
            state["reported"] = True
        return nodes

    graphiti_module.extract_attributes_from_nodes = patched


def preflight() -> list[str]:
    """Check both local services answer before spending an hour finding out.

    This stack needs TWO endpoints, and a failure in either surfaces as the
    same opaque `APIConnectionError: Connection error.` from the openai client:

      * the LLM  (LM Studio / Ollama) — entity and edge extraction
      * the EMBEDDER (Ollama :11434)  — 384-dim all-minilm vectors

    On 2026-08-20 Ollama died mid-run while LM Studio stayed healthy. Every
    episode failed identically, the LLM tested fine, and the misdiagnosis
    burned hours. Errors that cannot distinguish which dependency died need a
    check that can.
    """
    import urllib.request

    problems: list[str] = []
    llm_base = os.getenv("GRAPHITI_LLM_BASE_URL", "http://localhost:1234/v1")
    embed_base = os.getenv("GRAPHITI_EMBED_BASE_URL", "http://localhost:11434/v1")

    for label, url in (("llm", f"{llm_base}/models"), ("embedder", f"{embed_base}/models")):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                if r.status != 200:
                    problems.append(f"{label}: HTTP {r.status} from {url}")
        except Exception as exc:  # noqa: BLE001 — any failure is disqualifying
            problems.append(f"{label}: unreachable at {url} ({type(exc).__name__})")

    # A reachable Ollama that has forgotten the model is just as fatal.
    if not any(p.startswith("embedder") for p in problems):
        model = os.getenv("GRAPHITI_EMBED_MODEL", "all-minilm")
        body = json.dumps({"model": model, "input": "preflight"}).encode()
        req = urllib.request.Request(
            f"{embed_base}/embeddings", data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                dims = len(json.load(r)["data"][0]["embedding"])
            print(f"  preflight: embedder OK ({model}, {dims}-dim)", flush=True)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"embedder: {model} did not embed ({type(exc).__name__})")

    return problems


def main() -> int:
    problems = preflight()
    if problems:
        print("preflight FAILED — not starting:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print("  (start LM Studio and/or `ollama serve`, then retry)", file=sys.stderr)
        return 3

    install_patch()

    spec = importlib.util.spec_from_file_location("ingest_changelogs", TARGET)
    if spec is None or spec.loader is None:
        print(f"error: cannot load {TARGET}", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_changelogs"] = module
    spec.loader.exec_module(module)

    # argparse in the target reads sys.argv, which still holds our flags.
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
