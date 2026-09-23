#!/usr/bin/env python3
"""
assemble-context-v-sources.py

Walk the configured root, find every `context-v/` directory, and write or
update `sources.md`. Existing entries in `sources.md` are authoritative —
the script never silently overwrites curation. Newly discovered paths are
appended with `include: false` and a dated note so the user opts them in.

Usage:
    python scripts/assemble-context-v-sources.py
    python scripts/assemble-context-v-sources.py --root /path/to/tree
    python scripts/assemble-context-v-sources.py --output sources.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml


DEFAULT_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "sources.md"

# Directories to skip while walking. Match by exact directory name.
SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".next",
    ".astro",
    ".cache",
}

# Path substrings to skip (covers e.g. corpus output directories anywhere
# under the kit, including ones nested in submodules of submodules).
SKIP_SUBSTRINGS = (
    "/context-vigilance-kit/corpus/",
    "/.git/modules/",
)


def find_context_v_dirs(root: Path) -> list[Path]:
    found: list[Path] = []
    root = root.resolve()
    for path in root.rglob("context-v"):
        if not path.is_dir():
            continue
        path_str = str(path)
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if any(s in path_str for s in SKIP_SUBSTRINGS):
            continue
        found.append(path)
    return sorted(found)


def parse_sources_file(path: Path) -> tuple[dict, str]:
    """Parse an existing sources.md into (frontmatter_dict, body_str).

    Returns ({}, '') if the file does not exist.
    """
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        # No frontmatter — treat entire file as body, no parsed sources.
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    fm_text = parts[0].lstrip("-").lstrip("\n")
    body = parts[1].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        print(f"warning: could not parse frontmatter in {path}: {exc}", file=sys.stderr)
        return {}, text
    return fm, body


def build_frontmatter(
    existing_fm: dict,
    discovered: list[Path],
    today: str,
) -> tuple[dict, list[Path], list[str]]:
    """Merge discovered paths into the existing sources list.

    Returns (new_fm, newly_added_paths, missing_paths). Existing entries
    are preserved verbatim. Newly-discovered paths are appended with
    include=false. Paths in sources.md that no longer exist on disk are
    reported back as warnings; they are NOT removed automatically.
    """
    sources = list(existing_fm.get("sources") or [])
    existing_paths = {entry.get("path") for entry in sources if entry.get("path")}
    discovered_strs = {str(p) for p in discovered}

    newly_added: list[Path] = []
    for p in discovered:
        if str(p) in existing_paths:
            continue
        sources.append(
            {
                "path": str(p),
                "kind": "context-v",
                "include": False,
                "note": f"auto-discovered {today}; review.",
            }
        )
        newly_added.append(p)

    missing: list[str] = [
        entry["path"]
        for entry in sources
        if entry.get("path")
        and entry["path"] not in discovered_strs
        and not Path(entry["path"]).exists()
    ]

    new_fm: dict = {
        "title": existing_fm.get("title", "Context Vigilance Kit — Sources"),
        "description": existing_fm.get(
            "description",
            "Curated list of context-v/ directories and legacy roots that the collator pulls from.",
        ),
        "date_created": existing_fm.get("date_created", today),
        "date_modified": today,
        "schema_version": existing_fm.get("schema_version", 1),
        "sources": sources,
    }
    # Preserve any unknown top-level keys the user may have added.
    for k, v in existing_fm.items():
        if k not in new_fm:
            new_fm[k] = v
    return new_fm, newly_added, missing


def write_sources_file(path: Path, fm: dict, body: str) -> None:
    if not body.strip():
        body = (
            "# Sources\n\n"
            "Auto-managed list of source directories the collator reads from. "
            "The frontmatter above is the machine-consumable part; this body "
            "is yours to use for curation rationale, decisions, and notes.\n\n"
            "Re-run `python scripts/assemble-context-v-sources.py` after "
            "moving directories or adding new repos to the tree.\n"
        )
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip()
    out = f"---\n{fm_text}\n---\n\n{body.lstrip()}"
    path.write_text(out, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Root to walk (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to sources.md (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    if not args.root.exists():
        print(f"error: root does not exist: {args.root}", file=sys.stderr)
        return 2

    today = dt.date.today().isoformat()
    discovered = find_context_v_dirs(args.root)
    existing_fm, body = parse_sources_file(args.output)
    new_fm, newly_added, missing = build_frontmatter(existing_fm, discovered, today)
    write_sources_file(args.output, new_fm, body)

    print(f"wrote {args.output}")
    print(f"  total entries: {len(new_fm['sources'])}")
    print(f"  newly added (include=false, awaiting curation): {len(newly_added)}")
    for p in newly_added:
        print(f"    + {p}")
    if missing:
        print(f"  warning: {len(missing)} entries reference paths no longer on disk:")
        for p in missing:
            print(f"    ! {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
