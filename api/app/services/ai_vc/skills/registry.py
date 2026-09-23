"""Load the immutable product skill catalog with bounded parsing."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import re

import yaml

from app.services.ai_vc.skills.models import AIVCSkill

_BUILTINS = Path(__file__).resolve().parent / "builtins"
_MAX_SKILL_BYTES = 64 * 1024
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_ALLOWED_TOOLS = {
    "public_research", "evidence_search", "methodology_retrieval",
    "company_memory", "financial_calculation",
}


def _load_skill(path: Path) -> AIVCSkill:
    raw = path.read_bytes()
    if len(raw) > _MAX_SKILL_BYTES:
        raise ValueError(f"AI-VC skill exceeds size limit: {path.name}")
    text = raw.decode("utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ValueError(f"AI-VC skill has no YAML frontmatter: {path}")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError(f"AI-VC skill frontmatter must be a mapping: {path}")
    tools = [str(value) for value in metadata.get("allowed_tools") or []]
    if set(tools) - _ALLOWED_TOOLS:
        raise ValueError(f"AI-VC skill declares an unsupported tool: {path}")
    if str(metadata.get("name") or "") != path.parent.name:
        raise ValueError(f"AI-VC skill name must match its directory: {path}")
    return AIVCSkill(
        name=str(metadata.get("name") or ""),
        description=str(metadata.get("description") or ""),
        phases=list(metadata.get("phases") or []),
        retrieval_purposes=list(metadata.get("retrieval_purposes") or []),
        allowed_tools=tools,
        sector_signals=[str(value).lower() for value in metadata.get("sector_signals") or []],
        instructions=match.group(2).strip(),
        path=str(path.relative_to(_BUILTINS.parent)),
        content_hash=sha256(raw).hexdigest(),
    )


@lru_cache(maxsize=1)
def load_builtin_skill_catalog() -> dict[str, AIVCSkill]:
    """Return checked-in skills only; customer content cannot define capabilities."""
    catalog = {_skill.name: _skill for _skill in (_load_skill(path) for path in sorted(_BUILTINS.glob("*/SKILL.md")))}
    if not catalog:
        raise RuntimeError("AI-VC product skill catalog is empty")
    return catalog
