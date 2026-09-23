#!/usr/bin/env python3
"""
ingest-to-chroma.py

Read sources.md, walk every included markdown file, chunk by `## ` headings,
embed with the default model (all-MiniLM-L6-v2 via onnxruntime), and upsert
into a local Chroma PersistentClient.

Stable IDs — re-running is idempotent. Files unchanged on re-run produce
identical embeddings and overwrite themselves cleanly.

Usage:
    python scripts/ingest-to-chroma.py
    python scripts/ingest-to-chroma.py --reset       # drop + recreate collection
    python scripts/ingest-to-chroma.py --limit 50    # ingest first N files (smoke)
    python scripts/ingest-to-chroma.py --query "your question here"
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

import chromadb
import yaml


KIT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = KIT_ROOT / "sources.md"
DEFAULT_CHROMA_PATH = KIT_ROOT / ".chroma"
DEFAULT_COLLECTION = "context-vigilance-corpus"
DEFAULT_MONOREPO_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")

SKIP_FILES = {".gitkeep", ".DS_Store"}
SKIP_PATH_SUBSTRINGS = (
    "/context-v/extra/",
    "/context-v/skills/",
    "/context-v/changelog/",
    "/context-v/changelogs/",
)

# Frontmatter keys lifted to Chroma metadata (Chroma metadata only supports
# str/int/float/bool primitives). Lists are joined with ", ". Anything not
# in this allowlist stays inside the chunk text — still searchable
# semantically, just not filterable.
METADATA_FRONTMATTER_KEYS = (
    "title", "status", "semantic_version",
    "date_created", "date_modified",
    "type", "tags",
)


def parse_sources_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"error: {path} has no YAML frontmatter")
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise SystemExit(f"error: {path} frontmatter not terminated by '---'")
    return yaml.safe_load(parts[0].lstrip("-").lstrip("\n")) or {}


def repo_slug_for(source_path: str) -> str:
    parts = [p for p in Path(source_path).parts if p not in ("/", "")]
    if not parts:
        return "root"
    if parts[-1] == "context-v" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def iter_markdown_files(source_path: Path, kind: str, subdirs: list[str] | None) -> list[Path]:
    if not source_path.exists() or not source_path.is_dir():
        return []
    if kind == "legacy" and subdirs:
        roots = [source_path / s for s in subdirs if (source_path / s).is_dir()]
    else:
        roots = [source_path]
    files: list[Path] = []
    for root in roots:
        for p in root.rglob("*.md"):
            if p.name in SKIP_FILES:
                continue
            p_str = str(p)
            if any(s in p_str for s in SKIP_PATH_SUBSTRINGS):
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
    """Pull allowlisted frontmatter keys into Chroma-compatible metadata.
    Lists join to comma-separated strings. Non-primitive values are stringified.
    """
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
        else:
            out[f"fm_{key}"] = str(val)
    return out


def chunk_by_heading(body: str) -> list[tuple[str, str]]:
    """Split body on `## ` headings. Returns [(heading, chunk_text), ...].
    The portion before any `## ` heading becomes ('', preamble_text)."""
    if not body.strip():
        return []
    # Match `## ` at the start of a line. Captures the heading text.
    pattern = re.compile(r"(?m)^##\s+(.+)$")
    matches = list(pattern.finditer(body))
    if not matches:
        return _split_oversized("", body.strip())

    chunks: list[tuple[str, str]] = []
    first_start = matches[0].start()
    if first_start > 0:
        preamble = body[:first_start].strip()
        if preamble:
            chunks.append(("", preamble))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        chunk_start = m.start()
        chunk_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chunk_text = body[chunk_start:chunk_end].strip()
        chunks.append((heading, chunk_text))

    capped: list[tuple[str, str]] = []
    for h, c in chunks:
        capped.extend(_split_oversized(h, c))
    return capped


# Chroma Cloud rejects any single document over 16,384 bytes on upsert.
# Section chunking alone does not bound size: a doc with no `## ` headings
# returns its whole body as one chunk, and one long section does the same.
# 15,000 leaves headroom for the heading prefix we re-attach to each part.
MAX_CHUNK_BYTES = 15_000


def _split_oversized(heading: str, text: str) -> list[tuple[str, str]]:
    """Sub-split a chunk that exceeds MAX_CHUNK_BYTES.

    Tries progressively blunter seams: `### ` subheadings, then blank-line
    paragraph breaks, then a hard byte cut. Each part keeps the parent
    heading so chunks stay self-contained for retrieval, and is labelled
    `Heading (part n/N)` so a reader knows it was divided.
    """
    if len(text.encode()) <= MAX_CHUNK_BYTES:
        return [(heading, text)]

    for pattern in (r"(?m)^(?=###\s+)", r"\n\n"):
        pieces = [s for s in re.split(pattern, text) if s.strip()]
        if len(pieces) < 2:
            continue
        parts, buf = [], ""
        for piece in pieces:
            candidate = (buf + "\n\n" + piece) if buf else piece
            if buf and len(candidate.encode()) > MAX_CHUNK_BYTES:
                parts.append(buf)
                buf = piece
            else:
                buf = candidate
        if buf:
            parts.append(buf)
        if all(len(s.encode()) <= MAX_CHUNK_BYTES for s in parts) and len(parts) > 1:
            n = len(parts)
            return [(f"{heading} (part {i}/{n})" if heading else f"(part {i}/{n})", s)
                    for i, s in enumerate(parts, 1)]

    # Nothing seamed cleanly — hard-cut on bytes, decoding-safe.
    raw, parts = text.encode(), []
    while raw:
        head, raw = raw[:MAX_CHUNK_BYTES], raw[MAX_CHUNK_BYTES:]
        while raw and (raw[0] & 0xC0) == 0x80:      # don't split a UTF-8 sequence
            head, raw = head + raw[:1], raw[1:]
        parts.append(head.decode("utf-8", "ignore"))
    n = len(parts)
    return [(f"{heading} (part {i}/{n})" if heading else f"(part {i}/{n})", s)
            for i, s in enumerate(parts, 1)]


# Chroma Cloud caps document IDs at 128 bytes on upsert. Readable IDs are
# worth keeping — they make a raw collection dump diagnosable — so only the
# handful that overflow get shortened, and those keep a hash of the full
# path so they stay unique and stable across re-ingests.
MAX_ID_BYTES = 128


def stable_chunk_id(repo_slug: str, relative_path: str, chunk_idx: int) -> str:
    safe_rel = relative_path.replace("/", "__").replace(" ", "_")
    chunk_id = f"{repo_slug}::{safe_rel}::{chunk_idx:04d}"
    if len(chunk_id.encode()) <= MAX_ID_BYTES:
        return chunk_id

    digest = hashlib.sha1(f"{repo_slug}/{relative_path}".encode()).hexdigest()[:10]
    suffix = f"::~{digest}::{chunk_idx:04d}"
    budget = MAX_ID_BYTES - len(repo_slug.encode()) - len(suffix.encode()) - 2
    tail = safe_rel.encode()[-budget:].decode("utf-8", "ignore") if budget > 0 else ""
    return f"{repo_slug}::{tail}{suffix}"


def build_chunks_for_file(
    file_path: Path,
    source_root: Path,
    repo_slug: str,
    kind: str,
    today: str,
    monorepo_root: Path,
) -> list[tuple[str, str, dict]]:
    """Return [(id, document_text, metadata), ...] for one file, or []
    if the file is private or empty."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    fm, body = split_frontmatter(text)
    if fm is not None and fm.get("private") is True:
        return []

    try:
        rel = file_path.relative_to(source_root)
    except ValueError:
        rel = Path(file_path.name)

    # Path from monorepo root — same convention as collate.py's `source_path`
    # bottom-line frontmatter key, surfaced here as Chroma metadata so chunk
    # records and corpus files agree on a single canonical path string.
    try:
        source_path = str(file_path.resolve().relative_to(monorepo_root.resolve()))
    except ValueError:
        source_path = str(file_path)

    title = (fm or {}).get("title", file_path.stem)
    fm_metadata = flatten_metadata(fm, METADATA_FRONTMATTER_KEYS)

    chunks = chunk_by_heading(body)
    out: list[tuple[str, str, dict]] = []
    for idx, (heading, chunk_text) in enumerate(chunks):
        # Prepend lightweight context so the embedder sees the file title +
        # section heading. Keeps chunks self-contained for retrieval quality.
        prefix_parts = [f"[{title}]"]
        if heading:
            prefix_parts.append(f"## {heading}")
        document = "\n".join(prefix_parts) + "\n\n" + chunk_text

        chunk_id = stable_chunk_id(repo_slug, str(rel), idx)
        metadata = {
            "source_root": str(source_root),
            "source_relative_path": str(rel),
            "source_repo_slug": repo_slug,
            "source_path": source_path,
            "kind": kind,
            "chunk_index": idx,
            "chunk_heading": heading,
            "has_frontmatter": fm is not None,
            "ingested_at": today,
        }
        metadata.update(fm_metadata)
        out.append((chunk_id, document, metadata))
    return out


def get_or_create_collection(client: chromadb.PersistentClient, name: str, reset: bool):
    if reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=name,
        metadata={"description": "Lossless Group context vigilance corpus — collated context-v/ across the tree."},
    )


def ingest(
    sources_file: Path,
    chroma_path: Path,
    collection_name: str,
    reset: bool,
    limit: int | None,
    monorepo_root: Path,
    batch_size: int = 64,
) -> dict:
    fm = parse_sources_file(sources_file)
    sources = [s for s in (fm.get("sources") or []) if s.get("include") is True]

    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = get_or_create_collection(client, collection_name, reset=reset)

    today = dt.date.today().isoformat()
    files_seen = 0
    chunks_added = 0
    files_skipped_private = 0
    files_skipped_missing = 0

    pending_ids: list[str] = []
    pending_docs: list[str] = []
    pending_meta: list[dict] = []

    def flush() -> None:
        nonlocal chunks_added
        if not pending_ids:
            return
        collection.upsert(ids=pending_ids, documents=pending_docs, metadatas=pending_meta)
        chunks_added += len(pending_ids)
        pending_ids.clear()
        pending_docs.clear()
        pending_meta.clear()

    for s in sources:
        src = Path(s["path"])
        if not src.exists():
            files_skipped_missing += 1
            continue
        slug = repo_slug_for(s["path"])
        kind = s.get("kind", "context-v")
        subdirs = s.get("subdirs")
        for f in iter_markdown_files(src, kind, subdirs):
            if limit is not None and files_seen >= limit:
                break
            files_seen += 1
            chunks = build_chunks_for_file(f, src, slug, kind, today, monorepo_root)
            if not chunks:
                files_skipped_private += 1
                continue
            for cid, doc, meta in chunks:
                pending_ids.append(cid)
                pending_docs.append(doc)
                pending_meta.append(meta)
                if len(pending_ids) >= batch_size:
                    flush()
        if limit is not None and files_seen >= limit:
            break
    flush()

    return {
        "files_seen": files_seen,
        "chunks_added": chunks_added,
        "files_skipped_private": files_skipped_private,
        "files_skipped_missing": files_skipped_missing,
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
        head = meta.get("chunk_heading") or "(preamble)"
        print(f"  #{rank + 1}  d={dist:.4f}  [{meta.get('source_repo_slug')}] "
              f"{meta.get('source_relative_path')}  ›  {head}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", type=str, default=DEFAULT_COLLECTION)
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate the collection before ingesting.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ingest at most N files (smoke testing).")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--monorepo-root",
        type=Path,
        default=DEFAULT_MONOREPO_ROOT,
        help=f"Root for `source_path` chunk metadata (default: {DEFAULT_MONOREPO_ROOT})",
    )
    parser.add_argument("--query", type=str, default=None,
                        help="Skip ingest; just run a query against the existing collection.")
    args = parser.parse_args()

    if args.query:
        query_demo(args.chroma_path, args.collection, args.query)
        return 0

    if not args.sources.exists():
        print(f"error: sources file does not exist: {args.sources}", file=sys.stderr)
        print("hint: run scripts/assemble-context-v-sources.py first.", file=sys.stderr)
        return 2

    stats = ingest(
        sources_file=args.sources,
        chroma_path=args.chroma_path,
        collection_name=args.collection,
        reset=args.reset,
        limit=args.limit,
        monorepo_root=args.monorepo_root,
        batch_size=args.batch_size,
    )

    print(f"\ningested into Chroma at {stats['chroma_path']}")
    print(f"  collection:           {stats['collection_name']}")
    print(f"  files seen:           {stats['files_seen']}")
    print(f"  chunks added:         {stats['chunks_added']}")
    print(f"  skipped (private):    {stats['files_skipped_private']}")
    print(f"  skipped (missing):    {stats['files_skipped_missing']}")
    print(f"  collection size now:  {stats['collection_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
