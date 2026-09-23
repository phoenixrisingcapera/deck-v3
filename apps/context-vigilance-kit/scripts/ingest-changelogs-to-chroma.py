#!/usr/bin/env python3
"""
ingest-changelogs-to-chroma.py

Walk every `changelog/` and `changelogs/` directory under the Lossless
monorepo tree, ingest each `.md` entry as one Chroma document, and upsert
into the `lossless-changelog` collection.

Design notes
------------
Changelog entries are short and write-once, so the shape is simpler than
the context-v ingester:
  - one file = one document (no `## ` chunking)
  - stable IDs: {repo_slug}::{path-relative-to-monorepo}
  - `content_sha256` stored in metadata; re-runs skip files whose hash
    matches the existing record (cheap idempotency, no re-embedding)
  - `upsert` cleanly handles the rare edited entry

Skips:
  - any file under `node_modules`, `.git`, `.venv`, `dist`, `build`, etc.
  - `splash/dist/changelog` (Astro build output)
  - `site/src/components/changelog` (React/Astro component dir, not entries)
  - files with frontmatter `private: true` or `publish: false`

Usage:
    python scripts/ingest-changelogs-to-chroma.py
    python scripts/ingest-changelogs-to-chroma.py --reset
    python scripts/ingest-changelogs-to-chroma.py --dry-run
    python scripts/ingest-changelogs-to-chroma.py --query "OG image work"
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import sys
from pathlib import Path

import chromadb
import yaml


KIT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHROMA_PATH = KIT_ROOT / ".chroma"
DEFAULT_COLLECTION = "lossless-changelog"
DEFAULT_MONOREPO_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")

# Directory names we never descend into during the tree walk.
SKIP_DIR_NAMES = {
    "node_modules", ".git", ".venv", "venv",
    "dist", "build", ".next", ".cache", ".vercel",
    "__pycache__", ".pytest_cache",
    "site_archive", "tmp", ".chroma",
}

# Path substrings: if a discovered `changelog`/`changelogs` dir's path
# contains any of these, it is not a canonical entries directory and is
# skipped. Per the changelog-conventions skill, the canonical location is
# `<repo-root>/changelog/`. Astro page routes (`src/pages/changelog`),
# content collections (`src/content/changelog`), layouts/components, splash
# rollup output, public/dist mirrors, and vendored study repos all match
# the name but are not source of truth.
SKIP_PATH_SUBSTRINGS = (
    "/src/",
    "/public/",
    "/dist/",
    "/.vercel/",
    "/studies/",
    "/splash/dist/",
    "/splash/src/rollup/",
)

# Frontmatter keys lifted into Chroma metadata. Chroma only stores
# str/int/float/bool primitives; lists join to comma-separated strings.
# `date_authored_initial_draft` / `date_authored_current_draft` are the
# tree-wide editorial dates — when the content was first *set* and when it last
# received a substantive revision. They are what timeline questions should read,
# not `date_created` / `date_modified`, which are filesystem facts and get bumped
# by merely opening a file in Obsidian.
#
# `date` is retained only for back-compat: entries authored before the
# convention landed used a bare `date:` key, which is being renamed to
# `date_authored_initial_draft` as those files are touched. Drop `date` once
# the tree-wide sweep is finished.
METADATA_FRONTMATTER_KEYS = (
    "title", "lede", "publish", "semantic_version", "at_semantic_version",
    "date_authored_initial_draft", "date_authored_current_draft",
    "date_last_updated",
    "date", "date_created", "date_modified",
    "authors", "tags",
)


def is_repo_root(path: Path) -> bool:
    """A directory is a 'repo root' if it contains a `.git` — works for
    top-level repos (`.git/` dir) and submodules (`.git` file pointing
    into the parent worktree)."""
    return (path / ".git").exists()


def find_changelog_dirs(root: Path) -> list[Path]:
    """Walk `root` and return every canonical changelog directory.

    Two canonical patterns, per Lossless changelog conventions:
      - `<repo>/changelog/`              — standard
      - `<repo>/context-v/changelogs/`   — nested form

    `<repo>` is verified by presence of a `.git` (file or dir). Anything
    else with a `changelog`-shaped name (Astro routes under `src/`,
    skill-internal changelogs at `<root>/context-v/skills/changelog`, build
    output, etc.) is rejected."""
    out: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for d in dirnames:
            full = Path(dirpath) / d
            full_str = str(full) + "/"
            if any(s in full_str for s in SKIP_PATH_SUBSTRINGS):
                continue
            if d == "changelog":
                # Canonical form: <repo>/changelog
                if is_repo_root(full.parent):
                    out.append(full)
            elif d == "changelogs":
                # Canonical form: <repo>/context-v/changelogs
                if (
                    full.parent.name == "context-v"
                    and is_repo_root(full.parent.parent)
                ):
                    out.append(full)
    return sorted(out)


def iter_changelog_files(changelog_dir: Path) -> list[Path]:
    """Markdown entries inside one changelog directory. Skips README.md
    (convention: meta-docs about the directory, not entries)."""
    files: list[Path] = []
    for p in changelog_dir.rglob("*.md"):
        if p.name.lower() == "readme.md":
            continue
        files.append(p)
    return sorted(files)


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return None, text
    try:
        fm = yaml.safe_load(parts[0].lstrip("-").lstrip("\n")) or {}
    except yaml.YAMLError:
        return None, text
    if not isinstance(fm, dict):
        return None, text
    return fm, parts[1].lstrip("\n")


def flatten_metadata(fm: dict | None, allowlist: tuple[str, ...]) -> dict:
    out: dict = {}
    if not fm:
        return out
    for key in allowlist:
        if key not in fm:
            continue
        val = fm[key]
        if isinstance(val, (str, int, float, bool)):
            out[f"fm_{key}"] = val
        elif isinstance(val, list):
            out[f"fm_{key}"] = ", ".join(str(v) for v in val)
        elif isinstance(val, (dt.date, dt.datetime)):
            out[f"fm_{key}"] = val.isoformat()
        else:
            out[f"fm_{key}"] = str(val)
    return out


def repo_slug_for(changelog_dir: Path, monorepo_root: Path) -> str:
    """The directory that *contains* the changelog/ dir is the repo slug.
    e.g. /…/ai-labs/changelog → 'ai-labs'."""
    try:
        rel = changelog_dir.resolve().relative_to(monorepo_root.resolve())
    except ValueError:
        return changelog_dir.parent.name or "root"
    parts = rel.parts
    if len(parts) <= 1:
        return "root"
    return parts[-2]


def stable_id(repo_slug: str, source_path: str) -> str:
    safe = source_path.replace("/", "__").replace(" ", "_")
    return f"{repo_slug}::{safe}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_record(
    file_path: Path,
    changelog_dir: Path,
    repo_slug: str,
    monorepo_root: Path,
    today: str,
) -> tuple[str, str, dict, str] | None:
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fm, body = split_frontmatter(text)
    if fm is not None:
        if fm.get("private") is True:
            return None
        if fm.get("publish") is False:
            return None

    try:
        source_path = str(file_path.resolve().relative_to(monorepo_root.resolve()))
    except ValueError:
        source_path = str(file_path)
    try:
        rel_to_dir = str(file_path.relative_to(changelog_dir))
    except ValueError:
        rel_to_dir = file_path.name
    try:
        cl_rel = str(changelog_dir.resolve().relative_to(monorepo_root.resolve()))
    except ValueError:
        cl_rel = str(changelog_dir)

    cid = stable_id(repo_slug, source_path)
    sha = sha256_text(text)
    title = (fm or {}).get("title") or file_path.stem
    fm_meta = flatten_metadata(fm, METADATA_FRONTMATTER_KEYS)

    document = f"[{title}]\n\n{body if body else text}"
    metadata = {
        "source_path": source_path,
        "source_relative_path": rel_to_dir,
        "source_repo_slug": repo_slug,
        "changelog_dir": cl_rel,
        "kind": "changelog",
        "content_sha256": sha,
        "file_mtime": dt.datetime.fromtimestamp(
            file_path.stat().st_mtime
        ).isoformat(timespec="seconds"),
        "has_frontmatter": fm is not None,
        "ingested_at": today,
    }
    metadata.update(fm_meta)
    return cid, document, metadata, sha


def get_or_create_collection(
    client: chromadb.PersistentClient, name: str, reset: bool
):
    if reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=name,
        metadata={
            "description": (
                "Lossless Group changelog rollup — every changelog/ entry "
                "across the monorepo tree, one document per file."
            )
        },
    )


def ingest(
    chroma_path: Path,
    collection_name: str,
    monorepo_root: Path,
    reset: bool,
    dry_run: bool,
    batch_size: int = 64,
) -> dict:
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = get_or_create_collection(client, collection_name, reset=reset)

    today = dt.date.today().isoformat()
    changelog_dirs = find_changelog_dirs(monorepo_root)

    candidates: list[tuple[str, str, dict, str, Path]] = []
    for cl_dir in changelog_dirs:
        slug = repo_slug_for(cl_dir, monorepo_root)
        for f in iter_changelog_files(cl_dir):
            rec = build_record(f, cl_dir, slug, monorepo_root, today)
            if rec is None:
                continue
            cid, doc, meta, sha = rec
            candidates.append((cid, doc, meta, sha, f))

    # Single batched lookup of existing sha256 so we can skip unchanged files.
    existing_sha: dict[str, str | None] = {}
    if candidates:
        existing = collection.get(
            ids=[c[0] for c in candidates], include=["metadatas"]
        )
        for cid, meta in zip(existing["ids"], existing["metadatas"] or []):
            existing_sha[cid] = (meta or {}).get("content_sha256")

    to_upsert = [
        (cid, doc, meta)
        for cid, doc, meta, sha, _ in candidates
        if existing_sha.get(cid) != sha
    ]
    skipped_unchanged = len(candidates) - len(to_upsert)

    if dry_run:
        print(f"[dry-run] changelog dirs found:     {len(changelog_dirs)}")
        print(f"[dry-run] candidate files:          {len(candidates)}")
        print(f"[dry-run] skipped (sha unchanged):  {skipped_unchanged}")
        print(f"[dry-run] would upsert:             {len(to_upsert)}")
        print()
        print("[dry-run] changelog directories discovered:")
        for cl_dir in changelog_dirs:
            try:
                rel = cl_dir.resolve().relative_to(monorepo_root.resolve())
                print(f"  {rel}")
            except ValueError:
                print(f"  {cl_dir}")
        return {
            "dry_run": True,
            "changelog_dirs": len(changelog_dirs),
            "files_seen": len(candidates),
            "skipped_unchanged": skipped_unchanged,
            "would_upsert": len(to_upsert),
        }

    upserted = 0
    for i in range(0, len(to_upsert), batch_size):
        batch = to_upsert[i:i + batch_size]
        collection.upsert(
            ids=[b[0] for b in batch],
            documents=[b[1] for b in batch],
            metadatas=[b[2] for b in batch],
        )
        upserted += len(batch)

    return {
        "changelog_dirs": len(changelog_dirs),
        "files_seen": len(candidates),
        "skipped_unchanged": skipped_unchanged,
        "upserted": upserted,
        "collection_size": collection.count(),
        "collection_name": collection_name,
        "chroma_path": str(chroma_path),
    }


def query_demo(chroma_path: Path, collection_name: str, q: str, n: int = 5) -> None:
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_collection(collection_name)
    result = collection.query(query_texts=[q], n_results=n)
    print(f"\nquery: {q!r}")
    for rank, (doc_id, dist, meta) in enumerate(
        zip(result["ids"][0], result["distances"][0], result["metadatas"][0])
    ):
        print(
            f"  #{rank + 1}  d={dist:.4f}  "
            f"[{meta.get('source_repo_slug')}] "
            f"{meta.get('source_relative_path')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", type=str, default=DEFAULT_COLLECTION)
    parser.add_argument("--monorepo-root", type=Path, default=DEFAULT_MONOREPO_ROOT)
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate the collection before ingesting.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing to Chroma.")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--query", type=str, default=None,
                        help="Skip ingest; query the existing collection.")
    args = parser.parse_args()

    if args.query:
        query_demo(args.chroma_path, args.collection, args.query)
        return 0

    if not args.monorepo_root.exists():
        print(f"error: monorepo root does not exist: {args.monorepo_root}",
              file=sys.stderr)
        return 2

    stats = ingest(
        chroma_path=args.chroma_path,
        collection_name=args.collection,
        monorepo_root=args.monorepo_root,
        reset=args.reset,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
    )

    if stats.get("dry_run"):
        return 0

    print(f"\ningested changelog rollup into Chroma at {stats['chroma_path']}")
    print(f"  collection:           {stats['collection_name']}")
    print(f"  changelog dirs:       {stats['changelog_dirs']}")
    print(f"  files seen:           {stats['files_seen']}")
    print(f"  skipped (unchanged):  {stats['skipped_unchanged']}")
    print(f"  upserted:             {stats['upserted']}")
    print(f"  collection size now:  {stats['collection_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
