#!/usr/bin/env python3
"""
collate.py

Read sources.md, walk every included source directory, and copy each
markdown file into corpus/ with provenance frontmatter keys appended.
Files marked `private: true` in their frontmatter are skipped.

Originals are never modified. The corpus is the destination.

Usage:
    python scripts/collate.py
    python scripts/collate.py --sources sources.md --corpus corpus
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

import yaml


KIT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = KIT_ROOT / "sources.md"
DEFAULT_CORPUS = KIT_ROOT / "corpus"
DEFAULT_MONOREPO_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")

# Filenames inside a context-v/ directory that are infrastructure, not content.
SKIP_FILES = {".gitkeep", ".DS_Store"}

# Path substrings that exclude a file from collation. `context-v/extra/` is
# the convention for "scratch / out-of-band" content inside a context-v dir
# that should not flow into the corpus.
SKIP_PATH_SUBSTRINGS = (
    "/context-v/extra/",
    "/context-v/skills/",  # skills go through build-skills-manifest.py / a future skills collator
    "/context-v/changelog/",   # ship-log entries get their own downstream path
    "/context-v/changelogs/",  # plural-form variant exists in the wild
)


def parse_sources_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"error: {path} has no YAML frontmatter")
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise SystemExit(f"error: {path} frontmatter not terminated by '---'")
    return yaml.safe_load(parts[0].lstrip("-").lstrip("\n")) or {}


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    """Return (frontmatter_dict_or_None, body_text)."""
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


def repo_slug_for(source_path: str) -> str:
    """Derive a short identifier from a source root path."""
    parts = [p for p in Path(source_path).parts if p not in ("/", "")]
    if not parts:
        return "root"
    # Drop a trailing 'context-v' so e.g. .../ai-labs/context-v -> 'ai-labs'.
    if parts[-1] == "context-v" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def iter_markdown_files(source_path: Path, kind: str, subdirs: list[str] | None) -> list[Path]:
    """Yield .md files under a source root, scoped by kind."""
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


def collate_file(
    src_file: Path,
    source_root: Path,
    repo_slug: str,
    corpus_root: Path,
    today: str,
    monorepo_root: Path,
) -> tuple[bool, str]:
    """Copy one file into the corpus with provenance keys appended.

    Returns (was_written, reason_if_skipped).
    """
    text = src_file.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)

    if fm is not None and fm.get("private") is True:
        return False, "private: true"

    fm_out = dict(fm) if fm else {}
    # Strip any pre-existing provenance keys so re-collation produces clean output.
    for key in ("source_root", "source_relative_path", "source_repo_slug",
                "collated_at", "source_path"):
        fm_out.pop(key, None)

    fm_out["source_root"] = str(source_root)
    try:
        rel = src_file.relative_to(source_root)
    except ValueError:
        rel = Path(src_file.name)
    fm_out["source_relative_path"] = str(rel)
    fm_out["source_repo_slug"] = repo_slug
    fm_out["collated_at"] = today

    # Compute the bottom-line `source_path` — the file's path relative to the
    # lossless-monorepo root. Quoted explicitly with double quotes per
    # team convention so it's easy to grep / template / process downstream.
    try:
        source_path = src_file.resolve().relative_to(monorepo_root.resolve())
    except ValueError:
        source_path = src_file  # fallback: outside monorepo, keep absolute

    fm_text = yaml.safe_dump(fm_out, sort_keys=False, allow_unicode=True).rstrip()
    fm_text = f'{fm_text}\nsource_path: "{source_path}"'

    out_text = f"---\n{fm_text}\n---\n\n{body}" if body else f"---\n{fm_text}\n---\n"

    dest = corpus_root / repo_slug / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out_text, encoding="utf-8")
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--monorepo-root",
        type=Path,
        default=DEFAULT_MONOREPO_ROOT,
        help=f"Root for `source_path` frontmatter key (default: {DEFAULT_MONOREPO_ROOT})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove corpus contents before collating (default: incremental).",
    )
    args = parser.parse_args()

    if not args.sources.exists():
        print(f"error: sources file does not exist: {args.sources}", file=sys.stderr)
        print("hint: run scripts/assemble-context-v-sources.py first.", file=sys.stderr)
        return 2

    fm = parse_sources_file(args.sources)
    sources = fm.get("sources") or []
    included = [s for s in sources if s.get("include") is True]

    if args.clean and args.corpus.exists():
        for child in args.corpus.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    args.corpus.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    written = 0
    skipped_private = 0
    skipped_missing = 0
    for entry in included:
        src = Path(entry["path"])
        kind = entry.get("kind", "context-v")
        subdirs = entry.get("subdirs")
        slug = repo_slug_for(entry["path"])

        if not src.exists():
            print(f"  ! source missing on disk, skipping: {src}", file=sys.stderr)
            skipped_missing += 1
            continue

        files = iter_markdown_files(src, kind, subdirs)
        for f in files:
            ok, reason = collate_file(f, src, slug, args.corpus, today, args.monorepo_root)
            if ok:
                written += 1
            elif reason == "private: true":
                skipped_private += 1

    print(f"collated {written} file(s) into {args.corpus}")
    print(f"  skipped private: {skipped_private}")
    print(f"  sources missing on disk: {skipped_missing}")
    print(f"  total included sources: {len(included)} of {len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
