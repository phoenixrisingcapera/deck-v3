#!/usr/bin/env python3
"""
build-corpus-manifest.py

Read sources.md, walk every file the collator would copy, and emit a
manifest with per-file YAML-frontmatter and content line counts. The
manifest is the pre-collation triage view — use it to spot stubs,
frontmatter-only stubs, and fully-drafted docs across the whole corpus
before running collate.py.

Output: corpus-manifest.md (sibling of sources.md). Pure auto-generated;
re-running fully regenerates.

Usage:
    python scripts/build-corpus-manifest.py
    python scripts/build-corpus-manifest.py --sources sources.md --output corpus-manifest.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml


KIT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = KIT_ROOT / "sources.md"
DEFAULT_OUTPUT = KIT_ROOT / "corpus-manifest.md"
DEFAULT_MONOREPO_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")

# Bucket thresholds — tune here.
STUB_MAX_CONTENT_LINES = 100        # < this → 'stub'
WORKED_ON_MIN_CONTENT_LINES = 500   # >= this → 'worked-on'
# Anything in between is 'idea-started'.

SKIP_FILES = {".gitkeep", ".DS_Store"}

# Path substrings that exclude a file from collation. `context-v/extra/` is
# the convention for "scratch / out-of-band" content inside a context-v dir
# that should not flow into the corpus.
SKIP_PATH_SUBSTRINGS = (
    "/context-v/extra/",
    "/context-v/skills/",  # tracked separately by build-skills-manifest.py
    "/context-v/changelog/",   # ship-log entries — separate downstream ingestion path
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


def count_lines(path: Path) -> tuple[int, int, int]:
    """Return (yaml_lines, content_lines, total_lines).

    yaml_lines counts lines strictly between the two '---' delimiters
    (excluding the delimiters themselves). If the file has no parseable
    frontmatter, yaml_lines is 0 and content_lines == total_lines.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0, 0, 0

    lines = text.splitlines()
    total = len(lines)

    if not lines or lines[0].strip() != "---":
        return 0, total, total

    # Find the closing delimiter.
    closing_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_idx = i
            break

    if closing_idx is None:
        # Open frontmatter without a close — treat as no frontmatter.
        return 0, total, total

    yaml_lines = closing_idx - 1  # lines between the two '---'
    content_lines = total - (yaml_lines + 2)  # subtract yaml + both delimiters
    return yaml_lines, max(0, content_lines), total


def bucket_for(content_lines: int) -> str:
    if content_lines >= WORKED_ON_MIN_CONTENT_LINES:
        return "worked-on"
    if content_lines >= STUB_MAX_CONTENT_LINES:
        return "idea-started"
    return "stub"


def path_from_monorepo_root(abs_path: Path, monorepo_root: Path) -> str:
    try:
        return str(abs_path.relative_to(monorepo_root))
    except ValueError:
        return str(abs_path)


def relpath_from(target_abs: Path, anchor_dir: Path) -> str:
    """Path of `target_abs` relative to `anchor_dir`. Used to render
    markdown links that VS Code / Cursor / Windsurf / Trae markdown
    previews recognize as clickable to-open-in-editor."""
    import os
    return os.path.relpath(str(target_abs), str(anchor_dir))


def build_entries(sources: list[dict], monorepo_root: Path) -> list[dict]:
    entries: list[dict] = []
    for s in sources:
        if s.get("include") is not True:
            continue
        src = Path(s["path"])
        if not src.exists():
            continue
        slug = repo_slug_for(s["path"])
        kind = s.get("kind", "context-v")
        subdirs = s.get("subdirs")
        for f in iter_markdown_files(src, kind, subdirs):
            yaml_lines, content_lines, total_lines = count_lines(f)
            try:
                rel = f.relative_to(src)
            except ValueError:
                rel = Path(f.name)
            entries.append(
                {
                    "source_repo_slug": slug,
                    "source_root": str(src),
                    "kind": kind,
                    "relative_path": str(rel),
                    "path_from_monorepo_root": path_from_monorepo_root(f, monorepo_root),
                    "yaml_lines": yaml_lines,
                    "content_lines": content_lines,
                    "total_lines": total_lines,
                    "bucket": bucket_for(content_lines),
                    "has_frontmatter": yaml_lines > 0,
                }
            )
    entries.sort(key=lambda e: (e["source_repo_slug"], e["relative_path"]))
    return entries


def build_summary(entries: list[dict]) -> dict:
    by_bucket: dict[str, int] = {"stub": 0, "idea-started": 0, "worked-on": 0}
    no_fm_by_bucket: dict[str, int] = {"stub": 0, "idea-started": 0, "worked-on": 0}
    no_frontmatter = 0
    for e in entries:
        by_bucket[e["bucket"]] = by_bucket.get(e["bucket"], 0) + 1
        if not e["has_frontmatter"]:
            no_frontmatter += 1
            no_fm_by_bucket[e["bucket"]] = no_fm_by_bucket.get(e["bucket"], 0) + 1
    return {
        "total_files": len(entries),
        "by_bucket": by_bucket,
        "without_frontmatter": no_frontmatter,
        "without_frontmatter_by_bucket": no_fm_by_bucket,
    }


def build_fillout_candidates(entries: list[dict]) -> dict[str, list[dict]]:
    """Files that are worked-on or idea-started but missing frontmatter.

    These are agent-actionable: real content exists; just needs YAML.
    Stubs are excluded — they need more than frontmatter to be useful.
    """
    out: dict[str, list[dict]] = {"worked-on": [], "idea-started": []}
    for e in entries:
        if e["has_frontmatter"]:
            continue
        if e["bucket"] not in out:
            continue
        out[e["bucket"]].append(
            {
                "path": e["path_from_monorepo_root"],
                "content_lines": e["content_lines"],
                "source_repo_slug": e["source_repo_slug"],
            }
        )
    for bucket in out:
        out[bucket].sort(key=lambda f: (-f["content_lines"], f["path"]))
    return out


def render_body(
    entries: list[dict],
    summary: dict,
    fillout: dict[str, list[dict]],
    monorepo_root: Path,
    manifest_dir: Path,
) -> str:
    lines: list[str] = []
    lines.append("# Corpus Manifest")
    lines.append("")
    lines.append(
        "Auto-generated triage view for the corpus. Re-run "
        "`python scripts/build-corpus-manifest.py` after editing `sources.md` "
        "or after files change on disk. Pure derived artifact — no human "
        "curation here; put curation in the source file itself."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total files: **{summary['total_files']}**")
    lines.append(f"- `worked-on` (≥{WORKED_ON_MIN_CONTENT_LINES} content lines): "
                 f"{summary['by_bucket'].get('worked-on', 0)}")
    lines.append(f"- `idea-started` ({STUB_MAX_CONTENT_LINES}–{WORKED_ON_MIN_CONTENT_LINES - 1} content lines): "
                 f"{summary['by_bucket'].get('idea-started', 0)}")
    lines.append(f"- `stub` (<{STUB_MAX_CONTENT_LINES} content lines): "
                 f"{summary['by_bucket'].get('stub', 0)}")
    lines.append(f"- Without YAML frontmatter: {summary['without_frontmatter']} (orthogonal — see cross-tab below)")
    lines.append("")
    lines.append("### No-frontmatter × bucket cross-tab")
    lines.append("")
    no_fm = summary.get("without_frontmatter_by_bucket", {})
    by_bucket = summary.get("by_bucket", {})
    lines.append("| bucket | total | without frontmatter | % missing fm |")
    lines.append("|---|---:|---:|---:|")
    for b in ("worked-on", "idea-started", "stub"):
        total = by_bucket.get(b, 0)
        missing = no_fm.get(b, 0)
        pct = f"{(missing / total * 100):.0f}%" if total else "—"
        lines.append(f"| `{b}` | {total} | {missing} | {pct} |")
    lines.append("")
    lines.append("## Frontmatter fill-out candidates")
    lines.append("")
    lines.append(
        "Files with real content (`worked-on` or `idea-started`) that are missing "
        "YAML frontmatter. Agent-actionable in batch — the content exists; just needs "
        "the metadata. Stubs are excluded; they need more than frontmatter."
    )
    lines.append("")
    for bucket in ("worked-on", "idea-started"):
        items = fillout.get(bucket, [])
        lines.append(f"### `{bucket}` ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_None._")
            lines.append("")
            continue
        for f in items:
            abs_path = monorepo_root / f["path"]
            link = relpath_from(abs_path, manifest_dir)
            lines.append(f"- [`{f['path']}`]({link}) — {f['content_lines']} content lines")
        lines.append("")
    lines.append("## Top 10 stubs (lowest content_lines first)")
    lines.append("")
    stubs = [e for e in entries if e["bucket"] == "stub"]
    stubs.sort(key=lambda e: (e["content_lines"], e["source_repo_slug"], e["relative_path"]))
    if not stubs:
        lines.append("_No stubs detected._")
    else:
        lines.append("| content_lines | yaml_lines | source | path |")
        lines.append("|---:|---:|---|---|")
        for e in stubs[:10]:
            abs_path = Path(e["source_root"]) / e["relative_path"]
            link = relpath_from(abs_path, manifest_dir)
            lines.append(
                f"| {e['content_lines']} | {e['yaml_lines']} | "
                f"{e['source_repo_slug']} | [{e['relative_path']}]({link}) |"
            )
    lines.append("")
    return "\n".join(lines)


def write_manifest(
    path: Path,
    entries: list[dict],
    summary: dict,
    fillout: dict[str, list[dict]],
    today: str,
    monorepo_root: Path,
) -> None:
    fm = {
        "title": "Context Vigilance Kit — Corpus Manifest",
        "description": (
            "Per-file inventory of every markdown file the collator would "
            "copy into corpus/, with line counts to help triage stubs vs. "
            "idea-started vs. worked-on docs."
        ),
        "date_generated": today,
        "schema_version": 1,
        "thresholds": {
            "stub_max_content_lines": STUB_MAX_CONTENT_LINES,
            "worked_on_min_content_lines": WORKED_ON_MIN_CONTENT_LINES,
        },
        "summary": summary,
        "frontmatter_fillout_candidates": fillout,
        "files": entries,
    }
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip()
    body = render_body(entries, summary, fillout, monorepo_root, path.parent)
    path.write_text(f"---\n{fm_text}\n---\n\n{body}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--monorepo-root",
        type=Path,
        default=DEFAULT_MONOREPO_ROOT,
        help=f"Root for `path_from_monorepo_root` (default: {DEFAULT_MONOREPO_ROOT})",
    )
    args = parser.parse_args()

    if not args.sources.exists():
        print(f"error: sources file does not exist: {args.sources}", file=sys.stderr)
        print("hint: run scripts/assemble-context-v-sources.py first.", file=sys.stderr)
        return 2

    fm = parse_sources_file(args.sources)
    sources = fm.get("sources") or []
    entries = build_entries(sources, args.monorepo_root)
    summary = build_summary(entries)
    fillout = build_fillout_candidates(entries)
    today = dt.date.today().isoformat()
    write_manifest(args.output, entries, summary, fillout, today, args.monorepo_root)

    no_fm = summary["without_frontmatter_by_bucket"]
    print(f"wrote {args.output}")
    print(f"  total files: {summary['total_files']}")
    print(f"  by bucket:")
    print(f"    worked-on:    {summary['by_bucket'].get('worked-on', 0):>4}  "
          f"(no frontmatter: {no_fm.get('worked-on', 0)})")
    print(f"    idea-started: {summary['by_bucket'].get('idea-started', 0):>4}  "
          f"(no frontmatter: {no_fm.get('idea-started', 0)})")
    print(f"    stub:         {summary['by_bucket'].get('stub', 0):>4}  "
          f"(no frontmatter: {no_fm.get('stub', 0)})")
    print(f"  no frontmatter (total): {summary['without_frontmatter']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
