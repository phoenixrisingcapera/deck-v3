#!/usr/bin/env python3
"""
build-skills-manifest.py

Walk every included source from sources.md and inventory the agent skills
it contains under any `context-v/skills/` directory. Emits a separate
manifest so skills don't pollute the corpus to-do list — yet they remain
visible for downstream indexing (ChromaDB, etc.).

Anthropic agent-skills shape (loosely):
    <root>/context-v/skills/<skill-name>/
        SKILL.md            ← required; YAML frontmatter (name, description, ...)
        references/*.md     ← optional supporting reference docs
        templates/*         ← optional templates
        scripts/*           ← optional helper scripts

Output: skills-manifest.md (sibling of sources.md). Pure auto-generated;
re-running fully regenerates.

Usage:
    python scripts/build-skills-manifest.py
    python scripts/build-skills-manifest.py --sources sources.md --output skills-manifest.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

import yaml


KIT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = KIT_ROOT / "sources.md"
DEFAULT_OUTPUT = KIT_ROOT / "skills-manifest.md"
DEFAULT_MONOREPO_ROOT = Path("/Users/mpstaton/code/lossless-monorepo")

# Filenames inside a skill directory that aren't content.
SKIP_FILES = {".gitkeep", ".DS_Store"}

# Required-and-recommended frontmatter keys per the Anthropic agent-skills spec.
REQUIRED_SKILL_KEYS = ("name", "description")
RECOMMENDED_SKILL_KEYS = ("name", "description", "model", "status")


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


def path_from_monorepo_root(abs_path: Path, monorepo_root: Path) -> str:
    try:
        return str(abs_path.relative_to(monorepo_root))
    except ValueError:
        return str(abs_path)


def relpath_from(target_abs: Path, anchor_dir: Path) -> str:
    return os.path.relpath(str(target_abs), str(anchor_dir))


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


def find_skill_dirs(source_path: Path) -> list[Path]:
    """A skill is a direct subdirectory of any `context-v/skills/` dir
    found under `source_path`. Only directories qualify; files at the
    skills/ top level (e.g. README.md, LICENSE, CANDIDATES.md) are ignored.
    """
    skill_dirs: list[Path] = []
    if not source_path.exists() or not source_path.is_dir():
        return skill_dirs
    for skills_root in source_path.rglob("skills"):
        if not skills_root.is_dir():
            continue
        if skills_root.parent.name != "context-v":
            continue
        # Skip if we're traversing inside a .git/modules tree.
        if any(part == ".git" for part in skills_root.parts):
            continue
        for child in sorted(skills_root.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            skill_dirs.append(child)
    return skill_dirs


def inventory_skill(skill_dir: Path) -> dict:
    """Read a skill directory and return a structured record."""
    skill_md = skill_dir / "SKILL.md"
    has_skill_md = skill_md.is_file()
    fm: dict | None = None
    body_lines = 0
    if has_skill_md:
        try:
            text = skill_md.read_text(encoding="utf-8")
            fm, body = split_frontmatter(text)
            body_lines = len(body.splitlines()) if body else 0
        except (OSError, UnicodeDecodeError):
            fm = None

    references = list((skill_dir / "references").rglob("*.md")) if (skill_dir / "references").is_dir() else []
    templates_dir = skill_dir / "templates"
    templates = [p for p in templates_dir.rglob("*") if p.is_file()] if templates_dir.is_dir() else []
    scripts_dir = skill_dir / "scripts"
    scripts = [p for p in scripts_dir.rglob("*") if p.is_file()] if scripts_dir.is_dir() else []

    md_total = sum(1 for _ in skill_dir.rglob("*.md") if _.name not in SKIP_FILES)

    missing_required = []
    if fm is None:
        missing_required = list(REQUIRED_SKILL_KEYS)
    else:
        missing_required = [k for k in REQUIRED_SKILL_KEYS if not fm.get(k)]

    completeness = "complete"
    if not has_skill_md:
        completeness = "no-skill-md"
    elif missing_required:
        completeness = "missing-required-fields"
    elif not references and not templates and not scripts:
        completeness = "skill-md-only"

    return {
        "name": skill_dir.name,
        "skill_dir": skill_dir,
        "has_skill_md": has_skill_md,
        "skill_md_frontmatter": fm or {},
        "skill_md_body_lines": body_lines,
        "missing_required_fields": missing_required,
        "asset_counts": {
            "references_md": len(references),
            "templates_files": len(templates),
            "scripts_files": len(scripts),
            "total_md": md_total,
        },
        "completeness": completeness,
    }


def build_records(sources: list[dict], monorepo_root: Path) -> list[dict]:
    records: list[dict] = []
    seen: set[Path] = set()
    for s in sources:
        if s.get("include") is not True:
            continue
        src = Path(s["path"])
        if not src.exists():
            continue
        slug = repo_slug_for(s["path"])
        for skill_dir in find_skill_dirs(src):
            if skill_dir in seen:
                continue
            seen.add(skill_dir)
            inv = inventory_skill(skill_dir)
            records.append(
                {
                    "name": inv["name"],
                    "source_repo_slug": slug,
                    "skill_dir_path": str(skill_dir),
                    "path_from_monorepo_root": path_from_monorepo_root(skill_dir, monorepo_root),
                    "has_skill_md": inv["has_skill_md"],
                    "skill_md_frontmatter": inv["skill_md_frontmatter"],
                    "skill_md_body_lines": inv["skill_md_body_lines"],
                    "missing_required_fields": inv["missing_required_fields"],
                    "asset_counts": inv["asset_counts"],
                    "completeness": inv["completeness"],
                }
            )
    records.sort(key=lambda r: (r["source_repo_slug"], r["name"]))
    return records


def build_summary(records: list[dict]) -> dict:
    by_repo: dict[str, int] = {}
    by_completeness: dict[str, int] = {
        "complete": 0,
        "skill-md-only": 0,
        "missing-required-fields": 0,
        "no-skill-md": 0,
    }
    with_skill_md = 0
    for r in records:
        by_repo[r["source_repo_slug"]] = by_repo.get(r["source_repo_slug"], 0) + 1
        by_completeness[r["completeness"]] = by_completeness.get(r["completeness"], 0) + 1
        if r["has_skill_md"]:
            with_skill_md += 1
    return {
        "total_skills": len(records),
        "with_skill_md": with_skill_md,
        "without_skill_md": len(records) - with_skill_md,
        "by_repo": by_repo,
        "by_completeness": by_completeness,
    }


def render_body(records: list[dict], summary: dict, monorepo_root: Path, manifest_dir: Path) -> str:
    lines: list[str] = []
    lines.append("# Skills Manifest")
    lines.append("")
    lines.append(
        "Auto-generated inventory of agent skills (Anthropic agent-skills spec) "
        "found under any `context-v/skills/` directory in the curated sources. "
        "Tracked separately from `corpus-manifest.md` so skills don't pollute "
        "the fill-out to-do list — but indexed downstream alongside the corpus. "
        "Re-run `python scripts/build-skills-manifest.py` after editing skills "
        "or `sources.md`."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total skills: **{summary['total_skills']}**")
    lines.append(f"- With `SKILL.md`: {summary['with_skill_md']}")
    lines.append(f"- Without `SKILL.md`: {summary['without_skill_md']}")
    lines.append("")
    lines.append("### By completeness")
    lines.append("")
    lines.append("| state | count |")
    lines.append("|---|---:|")
    for state in ("complete", "skill-md-only", "missing-required-fields", "no-skill-md"):
        lines.append(f"| `{state}` | {summary['by_completeness'].get(state, 0)} |")
    lines.append("")
    lines.append("### By source repo")
    lines.append("")
    lines.append("| source_repo_slug | count |")
    lines.append("|---|---:|")
    for repo in sorted(summary["by_repo"]):
        lines.append(f"| `{repo}` | {summary['by_repo'][repo]} |")
    lines.append("")
    lines.append("## Skills")
    lines.append("")
    if not records:
        lines.append("_No skills discovered. Are there any `context-v/skills/` directories under your included sources?_")
        return "\n".join(lines)
    lines.append("| name | source | completeness | refs | templates | scripts | description |")
    lines.append("|---|---|---|---:|---:|---:|---|")
    for r in records:
        skill_dir = Path(r["skill_dir_path"])
        link_target = skill_dir / "SKILL.md" if r["has_skill_md"] else skill_dir
        link = relpath_from(link_target, manifest_dir)
        name_cell = f"[`{r['name']}`]({link})"
        desc = r["skill_md_frontmatter"].get("description", "") or ""
        if len(desc) > 90:
            desc = desc[:87] + "…"
        desc = desc.replace("|", "\\|").replace("\n", " ")
        ac = r["asset_counts"]
        lines.append(
            f"| {name_cell} | `{r['source_repo_slug']}` | `{r['completeness']}` | "
            f"{ac['references_md']} | {ac['templates_files']} | {ac['scripts_files']} | {desc} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_manifest(
    path: Path,
    records: list[dict],
    summary: dict,
    today: str,
    monorepo_root: Path,
) -> None:
    fm = {
        "title": "Context Vigilance Kit — Skills Manifest",
        "description": (
            "Inventory of agent skills (Anthropic agent-skills spec) discovered "
            "under any context-v/skills/ directory in the curated sources. "
            "Tracked separately from the corpus manifest."
        ),
        "date_generated": today,
        "schema_version": 1,
        "summary": summary,
        "skills": records,
    }
    fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip()
    body = render_body(records, summary, monorepo_root, path.parent)
    path.write_text(f"---\n{fm_text}\n---\n\n{body}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--monorepo-root", type=Path, default=DEFAULT_MONOREPO_ROOT)
    args = parser.parse_args()

    if not args.sources.exists():
        print(f"error: sources file does not exist: {args.sources}", file=sys.stderr)
        print("hint: run scripts/assemble-context-v-sources.py first.", file=sys.stderr)
        return 2

    fm = parse_sources_file(args.sources)
    sources = fm.get("sources") or []
    records = build_records(sources, args.monorepo_root)
    summary = build_summary(records)
    today = dt.date.today().isoformat()
    write_manifest(args.output, records, summary, today, args.monorepo_root)

    print(f"wrote {args.output}")
    print(f"  total skills: {summary['total_skills']}")
    print(f"  with SKILL.md:    {summary['with_skill_md']}")
    print(f"  without SKILL.md: {summary['without_skill_md']}")
    print(f"  by completeness:")
    for state, count in summary["by_completeness"].items():
        print(f"    {state:>26}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
