#!/usr/bin/env python3
"""
ingest-changelogs-to-graphiti.py

Ingest every `changelog/` entry across the Lossless monorepo tree into a
Graphiti temporal knowledge graph backed by Neo4j.

Why the changelog and not the whole corpus
------------------------------------------
Graphiti is not Chroma. Chroma costs one cheap local embedding per chunk;
Graphiti runs an LLM extraction call plus dedup calls per episode. At the
time of writing the four Chroma collections held ~28,000 chunks — a full
Graphiti pass over that is a serious bill and many hours of wall clock.

Changelog entries are the right first slice for a reason beyond cost: they
are *dated events*. Graphiti's whole thesis is bi-temporal edges —
`valid_at` / `invalid_at` as separate axes from `created_at` / `expired_at`.
A dated ship log is the data shape that model was designed for. Specs and
plans are mostly atemporal by comparison.

Discovery is deliberately NOT reimplemented — this imports the same
`find_changelog_dirs` / `iter_changelog_files` / `split_frontmatter` used by
ingest-changelogs-to-chroma.py, so the two indexes always cover exactly the
same set of files. Divergence there would be invisible and maddening.

Idempotency
-----------
Graphiti has no content-hash skip of its own, and re-extracting an unchanged
entry costs real money. This script keeps its own state file
(.graphiti-state/changelog-ingest.json) mapping source_path → sha256, and
skips files whose hash it has already ingested. `--reset` drops both the
state file and the graph partition.

Usage:
    python scripts/ingest-changelogs-to-graphiti.py --dry-run
    python scripts/ingest-changelogs-to-graphiti.py --limit 5      # smoke run
    python scripts/ingest-changelogs-to-graphiti.py
    python scripts/ingest-changelogs-to-graphiti.py --reset
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

import graphiti_clients as gc


KIT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MONOREPO_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")
STATE_DIR = KIT_ROOT / ".graphiti-state"
STATE_FILE = STATE_DIR / "changelog-ingest.json"

# Graphiti partition key. Keeping the changelog graph in its own group_id
# means a later context-v ingest can land in a sibling partition without
# entity resolution smearing the two together — and either can be cleared
# independently.
GROUP_ID = "lossless-changelog"

# Episodes should be modest. Changelog entries are short by convention, but
# a few long ones exist and a runaway episode is both expensive and worse at
# extraction (the model loses the thread).
MAX_EPISODE_CHARS = 12_000


# ---------------------------------------------------------------------------
# Ontology
#
# Custom Pydantic entity types are Graphiti's ontology surface — the LLM
# assigns extracted entities to these types and the typed fields land in
# EntityNode.attributes. Per the study profile: define these early, because
# retrofitting types over an existing graph is painful.
#
# These five are tuned to what Lossless changelogs actually talk about.
# ---------------------------------------------------------------------------


class Repo(BaseModel):
    """A repository or project in the Lossless monorepo tree — e.g. augment-it,
    dididecks-ai, astro-knots, context-vigilance-kit. Includes child repos and
    client sites, not directories inside a repo."""

    tree_path: str | None = Field(
        None, description="Path within the monorepo if stated, e.g. ai-labs/augment-it"
    )
    role: str | None = Field(
        None, description="What the repo is for, in a short phrase"
    )


class Capability(BaseModel):
    """A user-facing or agent-facing capability that was shipped, changed, or
    removed — a feature, surface, page, endpoint, script, or command. The thing
    the changelog entry is announcing."""

    surface: str | None = Field(
        None, description="Where it lives: CLI, splash site, MCP server, API, skill, etc."
    )
    change_kind: str | None = Field(
        None, description="One of: added, updated, fixed, removed, refactored"
    )


class Convention(BaseModel):
    """A practice, standard, or rule the team adopted — a skill, a naming
    convention, a frontmatter schema, a branch tier model, a directory taxonomy.
    Distinct from a Capability: a Convention governs how work is done rather
    than being a thing that was built."""

    scope: str | None = Field(
        None, description="Where it applies: one repo, a family of repos, tree-wide"
    )


class Tool(BaseModel):
    """An external tool, service, library, framework, or model the work depends
    on — Astro, ChromaDB, Neo4j, Railway, Playwright, Firecrawl, a Claude model.
    Third-party, not something Lossless built."""

    category: str | None = Field(
        None, description="e.g. framework, database, hosting, MCP server, LLM"
    )


class Person(BaseModel):
    """A named human — an author, collaborator, client contact, or maintainer."""

    affiliation: str | None = Field(
        None, description="Organization or role, if stated"
    )


ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Repo": Repo,
    "Capability": Capability,
    "Convention": Convention,
    "Tool": Tool,
    "Person": Person,
}

EXTRACTION_INSTRUCTIONS = (
    "This episode is a changelog entry from the Lossless Group's monorepo tree. "
    "Extract the repository the work landed in, the capabilities that were added "
    "or changed, any conventions or practices adopted, and third-party tools "
    "involved. Prefer specific named things over generic categories: extract "
    "'context-vigilance-kit' rather than 'the repo', and 'Pagefind' rather than "
    "'a search library'. Do not invent entities that the entry does not mention."
)


# ---------------------------------------------------------------------------
# Reuse the Chroma ingester's discovery so both indexes cover the same files.
# The filename is hyphenated and therefore not importable by name.
# ---------------------------------------------------------------------------


def load_chroma_ingester():
    path = SCRIPT_DIR / "ingest-changelogs-to-chroma.py"
    spec = importlib.util.spec_from_file_location("_cl_chroma", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"error: cannot load discovery helpers from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def coerce_date(value) -> dt.datetime | None:
    """Frontmatter dates arrive as date, datetime, or string depending on how
    the entry was authored. Normalize to an aware UTC datetime — Neo4j and
    Graphiti both want tz-aware values."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
    if isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        for parse in (dt.datetime.fromisoformat,):
            try:
                parsed = parse(raw)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
            except ValueError:
                pass
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y"):
            try:
                return dt.datetime.strptime(raw, fmt).replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue
    return None


class Episode:
    """One changelog entry, resolved into everything add_episode() needs."""

    __slots__ = ("name", "body", "source_description", "reference_time",
                 "source_path", "repo_slug", "sha")

    def __init__(self, name, body, source_description, reference_time,
                 source_path, repo_slug, sha):
        self.name = name
        self.body = body
        self.source_description = source_description
        self.reference_time = reference_time
        self.source_path = source_path
        self.repo_slug = repo_slug
        self.sha = sha


def build_episodes(mod, monorepo_root: Path) -> tuple[list[Episode], int, int]:
    """Returns (episodes sorted oldest-first, files_skipped_private, files_undated).

    Oldest-first ordering matters. Graphiti resolves each episode against the
    most recent prior episodes, so replaying the log in chronological order is
    what lets the bi-temporal model see a fact being established and later
    superseded. Ingesting newest-first inverts that story.
    """
    episodes: list[Episode] = []
    skipped_private = 0
    undated = 0

    for cl_dir in mod.find_changelog_dirs(monorepo_root):
        repo_slug = mod.repo_slug_for(cl_dir, monorepo_root)
        for f in mod.iter_changelog_files(cl_dir):
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            fm, body = mod.split_frontmatter(text)
            if fm is not None:
                if fm.get("private") is True or fm.get("publish") is False:
                    skipped_private += 1
                    continue

            fm = fm or {}
            title = fm.get("title") or f.stem.replace("-", " ")
            lede = fm.get("lede")

            # The temporal anchor, in order of editorial honesty.
            # `date_authored_initial_draft` is the tree-wide convention for
            # "when this content was first set" — that is what a timeline wants.
            # `date` is the pre-convention spelling of the same thing, retained
            # until the tree-wide rename finishes. `date_created` /
            # `date_modified` are filesystem facts and only a fallback: Obsidian
            # bumps mtime on a mere open, so they overstate recency.
            ref = (
                coerce_date(fm.get("date_authored_initial_draft"))
                or coerce_date(fm.get("date"))
                or coerce_date(fm.get("date_created"))
                or coerce_date(fm.get("date_modified"))
            )
            if ref is None:
                # Fall back to mtime, but count it — a changelog entry with no
                # date in frontmatter is a convention violation worth knowing
                # about, and mtime is a poor temporal anchor (a reformat pass
                # rewrites it).
                ref = dt.datetime.fromtimestamp(
                    f.stat().st_mtime, tz=dt.timezone.utc
                )
                undated += 1

            try:
                source_path = str(f.resolve().relative_to(monorepo_root.resolve()))
            except ValueError:
                source_path = str(f)

            # Front-load repo and title into the episode text. The extractor
            # sees only this string, so the repo the work landed in has to be
            # stated rather than left implicit in the file path.
            header = f"Repository: {repo_slug}\nEntry: {title}"
            if lede:
                header += f"\nSummary: {lede}"
            content = f"{header}\n\n{body or text}"
            if len(content) > MAX_EPISODE_CHARS:
                content = content[:MAX_EPISODE_CHARS] + "\n\n[...truncated]"

            episodes.append(
                Episode(
                    name=f"{repo_slug}: {title}",
                    body=content,
                    source_description=f"Lossless changelog entry ({source_path})",
                    reference_time=ref,
                    source_path=source_path,
                    repo_slug=repo_slug,
                    sha=sha256_text(text),
                )
            )

    episodes.sort(key=lambda e: e.reference_time)
    return episodes, skipped_private, undated


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


async def run(args) -> int:
    settings = gc.GraphitiSettings.from_env()

    mod = load_chroma_ingester()
    episodes, skipped_private, undated = build_episodes(mod, args.monorepo_root)

    state = {} if args.reset else load_state()
    pending = [e for e in episodes if state.get(e.source_path) != e.sha]
    already = len(episodes) - len(pending)

    if args.limit:
        pending = pending[: args.limit]

    print("Graphiti changelog ingest")
    print(gc.describe(settings))
    print()
    print(f"  entries discovered:      {len(episodes)}")
    print(f"  skipped (private):       {skipped_private}")
    print(f"  undated (mtime fallback):{undated}")
    print(f"  already ingested:        {already}")
    print(f"  to ingest this run:      {len(pending)}")
    if episodes:
        print(f"  date range:              {episodes[0].reference_time.date()} "
              f"→ {episodes[-1].reference_time.date()}")
    print()

    if args.dry_run:
        print("[dry-run] first 10 episodes in ingest order:")
        for e in pending[:10]:
            print(f"  {e.reference_time.date()}  [{e.repo_slug}]  {e.name[:70]}")
        if not pending:
            print("  (nothing pending)")
        return 0

    if not pending and not args.reset:
        print("nothing to do — every entry is already in the graph.")
        return 0

    gc.prepare_environment(settings)
    graphiti = gc.build_graphiti(settings)

    from graphiti_core.nodes import EpisodeType
    from graphiti_core.utils.maintenance.graph_data_operations import clear_data

    try:
        if args.reset:
            print(f"resetting graph partition group_id={GROUP_ID!r} ...")
            await clear_data(graphiti.driver, group_ids=[GROUP_ID])
            state = {}
            save_state(state)

        print("building indices and constraints ...")
        await graphiti.build_indices_and_constraints()
        print()

        started = time.monotonic()
        succeeded = failed = 0

        for i, ep in enumerate(pending, start=1):
            label = f"[{i}/{len(pending)}] {ep.reference_time.date()} {ep.name[:56]}"
            try:
                await graphiti.add_episode(
                    name=ep.name,
                    episode_body=ep.body,
                    source_description=ep.source_description,
                    reference_time=ep.reference_time,
                    source=EpisodeType.text,
                    group_id=GROUP_ID,
                    entity_types=ENTITY_TYPES,
                    custom_extraction_instructions=EXTRACTION_INSTRUCTIONS,
                )
            except Exception as exc:  # noqa: BLE001 — one bad entry must not kill the run
                failed += 1
                print(f"{label}\n    FAILED: {type(exc).__name__}: {exc}")
                continue

            succeeded += 1
            # Persist after every success. An ingest this expensive must be
            # resumable from wherever it died — including a Ctrl-C.
            state[ep.source_path] = ep.sha
            save_state(state)

            elapsed = time.monotonic() - started
            rate = elapsed / succeeded
            remaining = (len(pending) - i) * rate
            print(f"{label}  ({elapsed:.0f}s elapsed, ~{remaining / 60:.0f}m left)")

        print()
        print(f"done — {succeeded} ingested, {failed} failed, "
              f"{time.monotonic() - started:.0f}s total")
        if failed:
            print("failed entries were not recorded in the state file; "
                  "re-run to retry just those.")
        print()
        print("inspect the graph:  http://localhost:7474")
        print("query it:           python scripts/query-graphiti.py \"your question\"")
        return 0 if failed == 0 else 1
    finally:
        await graphiti.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monorepo-root", type=Path, default=DEFAULT_MONOREPO_ROOT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be ingested without calling any LLM.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ingest at most N pending entries (smoke run).")
    parser.add_argument("--reset", action="store_true",
                        help="Clear the graph partition and the state file first.")
    args = parser.parse_args()

    gc.load_env_chain(KIT_ROOT)

    if not args.monorepo_root.exists():
        print(f"error: monorepo root does not exist: {args.monorepo_root}",
              file=sys.stderr)
        return 2

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
