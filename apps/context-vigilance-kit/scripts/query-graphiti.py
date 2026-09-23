#!/usr/bin/env python3
"""
query-graphiti.py

Query the Graphiti changelog knowledge graph from the terminal — the
equivalent of smoke-test-chroma.py for the graph index.

This exists so you can judge whether the graph is worth keeping *before*
wiring an MCP server and paying the per-session context cost of another
tool surface. Run a few real questions through it and look at the facts
that come back.

Three modes:

  facts   (default)  hybrid search over EntityEdges — returns natural-language
                     facts with their validity windows. This is the mode that
                     shows off the bi-temporal model.
  nodes              hybrid search over EntityNodes — returns entities with
                     their evolving summaries and typed attributes.
  around             BFS rooted at the entity best matching --center. This is
                     the thing Chroma structurally cannot do: "what do we know
                     around X", answered by traversal rather than similarity.

Usage:
    python scripts/query-graphiti.py "when did we ship the Chroma corpus"
    python scripts/query-graphiti.py --mode nodes "context vigilance"
    python scripts/query-graphiti.py --mode around --center "augment-it" "decile"
    python scripts/query-graphiti.py --stats
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import graphiti_clients as gc


KIT_ROOT = Path(__file__).resolve().parent.parent
GROUP_ID = "lossless-changelog"


def fmt_window(edge) -> str:
    """Render the bi-temporal window compactly. `valid_at`/`invalid_at` are
    real-world validity; `expired_at` is when Graphiti retired the record."""
    bits = []
    if getattr(edge, "valid_at", None):
        bits.append(f"valid {edge.valid_at.date()}")
    if getattr(edge, "invalid_at", None):
        bits.append(f"invalid {edge.invalid_at.date()}")
    if getattr(edge, "expired_at", None):
        bits.append(f"EXPIRED {edge.expired_at.date()}")
    return "  [" + ", ".join(bits) + "]" if bits else ""


async def show_stats(graphiti) -> None:
    counts = [
        ("episodes", "MATCH (n:Episodic {group_id: $gid}) RETURN count(n) AS c"),
        ("entities", "MATCH (n:Entity {group_id: $gid}) RETURN count(n) AS c"),
        ("communities", "MATCH (n:Community {group_id: $gid}) RETURN count(n) AS c"),
        ("fact edges", "MATCH ()-[r:RELATES_TO {group_id: $gid}]->() RETURN count(r) AS c"),
        ("mentions", "MATCH ()-[r:MENTIONS {group_id: $gid}]->() RETURN count(r) AS c"),
    ]
    print(f"graph partition: group_id={GROUP_ID!r}\n")
    for label, cypher in counts:
        try:
            records, _, _ = await graphiti.driver.execute_query(cypher, gid=GROUP_ID)
            value = records[0]["c"] if records else 0
        except Exception as exc:  # noqa: BLE001
            value = f"(query failed: {type(exc).__name__})"
        print(f"  {label:<14} {value}")

    print("\n  entities by type:")
    try:
        records, _, _ = await graphiti.driver.execute_query(
            "MATCH (n:Entity {group_id: $gid}) UNWIND labels(n) AS l "
            "WITH l WHERE l <> 'Entity' "
            "RETURN l AS label, count(*) AS c ORDER BY c DESC",
            gid=GROUP_ID,
        )
        if not records:
            print("    (none — has anything been ingested yet?)")
        for r in records:
            print(f"    {r['label']:<14} {r['c']}")
    except Exception as exc:  # noqa: BLE001
        print(f"    (query failed: {type(exc).__name__}: {exc})")


async def run(args) -> int:
    settings = gc.GraphitiSettings.from_env()
    gc.prepare_environment(settings)
    # Read-only: search uses the embedder, Neo4j and the cross-encoder, never
    # the extraction LLM. No Anthropic key required to query the graph.
    graphiti = gc.build_graphiti(settings, require_llm=False)

    try:
        if args.stats:
            await show_stats(graphiti)
            return 0

        if args.mode == "facts":
            edges = await graphiti.search(
                query=args.query,
                group_ids=[GROUP_ID],
                num_results=args.limit,
            )
            if not edges:
                print("no facts matched.")
                return 0
            print(f"facts for {args.query!r}:\n")
            for i, e in enumerate(edges, 1):
                print(f"  {i}. {e.fact}{fmt_window(e)}")
                print(f"     relation={e.name}  episodes={len(e.episodes)}")
            return 0

        from graphiti_core.search.search_config_recipes import (
            NODE_HYBRID_SEARCH_RRF,
        )

        if args.mode == "nodes":
            results = await graphiti.search_(
                query=args.query,
                config=NODE_HYBRID_SEARCH_RRF,
                group_ids=[GROUP_ID],
            )
            if not results.nodes:
                print("no entities matched.")
                return 0
            print(f"entities for {args.query!r}:\n")
            for i, n in enumerate(results.nodes[: args.limit], 1):
                types = [lbl for lbl in n.labels if lbl != "Entity"]
                print(f"  {i}. {n.name}  ({', '.join(types) or 'Entity'})")
                if n.summary:
                    print(f"     {n.summary[:200]}")
                if n.attributes:
                    keep = {k: v for k, v in n.attributes.items() if v}
                    if keep:
                        print(f"     {keep}")
            return 0

        # mode == around
        centers = await graphiti.search_(
            query=args.center,
            config=NODE_HYBRID_SEARCH_RRF,
            group_ids=[GROUP_ID],
        )
        if not centers.nodes:
            print(f"no entity matched {args.center!r} — nothing to center on.")
            return 0
        center = centers.nodes[0]
        print(f"centering on: {center.name}\n")

        edges = await graphiti.search(
            query=args.query or args.center,
            center_node_uuid=center.uuid,
            group_ids=[GROUP_ID],
            num_results=args.limit,
        )
        if not edges:
            print("no connected facts found.")
            return 0
        for i, e in enumerate(edges, 1):
            print(f"  {i}. {e.fact}{fmt_window(e)}")
        return 0
    finally:
        await graphiti.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="", help="What to ask.")
    parser.add_argument("--mode", choices=["facts", "nodes", "around"],
                        default="facts")
    parser.add_argument("--center", type=str, default=None,
                        help="Entity to root a BFS at, for --mode around.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--stats", action="store_true",
                        help="Print graph counts instead of searching.")
    args = parser.parse_args()

    gc.load_env_chain(KIT_ROOT)

    if not args.stats and not args.query and not args.center:
        parser.error("give a query, or use --stats")
    if args.mode == "around" and not args.center:
        parser.error("--mode around requires --center 'entity name'")

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
