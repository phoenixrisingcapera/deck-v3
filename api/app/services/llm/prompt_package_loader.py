from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROMPT_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "llm" / "prompt_packages"
SHARED_PACKAGE = "shared"


@dataclass(frozen=True)
class PromptPackage:
    package_id: str
    version: str
    root: Path
    manifest: dict
    shared: dict[str, str]
    prompts: dict[str, str]
    output_schema: dict | None

    @property
    def sections(self) -> dict[str, str]:
        return {Path(filename).stem: value for filename, value in self.prompts.items()}

    def combined_prompt(self, files: list[str] | None = None, *, include_shared: bool = True) -> str:
        selected = files or list(self.prompts.keys())
        parts: list[str] = []
        if include_shared:
            parts.extend(value.strip() for _, value in sorted(self.shared.items()) if value.strip())
        for filename in selected:
            value = self.prompts.get(filename)
            if value is None:
                value = self.sections.get(filename)
            if value:
                parts.append(value.strip())
        return "\n\n".join(part for part in parts if part)

    def __getitem__(self, key: str):
        mapping = {
            "name": self.package_id,
            "version": self.version,
            "root": str(self.root),
            "shared": self.shared,
            "sections": self.sections,
            "outputSchema": self.output_schema,
        }
        return mapping[key]

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def _read_text_sections(path: Path, filenames: list[str] | None = None) -> dict[str, str]:
    if not path.exists() or not path.is_dir():
        return {}
    if filenames is None:
        candidates = sorted(entry.name for entry in path.iterdir() if entry.is_file())
    else:
        candidates = [str(filename) for filename in filenames]

    sections: dict[str, str] = {}
    for filename in candidates:
        entry = path / filename
        if not entry.is_file() or entry.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        if entry.name in {"output_schema.json", "manifest.json"}:
            continue
        sections[entry.stem] = entry.read_text(encoding="utf-8").strip()
    return sections


def _read_json(path: Path) -> dict | None:
    if not path.exists() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _package_version(package_name: str, manifest: dict, prompts: dict[str, str], shared: dict[str, str]) -> str:
    explicit_version = str(manifest.get("version") or "").strip()
    if explicit_version:
        return explicit_version
    section_fingerprint = sum(len(value) for value in prompts.values()) + sum(len(value) for value in shared.values())
    return f"{package_name}.v{section_fingerprint}"


@lru_cache(maxsize=32)
def load_prompt_package(package_name: str) -> PromptPackage:
    package_dir = PROMPT_PACKAGE_ROOT / package_name
    if not package_dir.exists() or not package_dir.is_dir():
        raise FileNotFoundError(f"Prompt package not found: {package_name}")

    manifest = _read_json(package_dir / "manifest.json") or {}
    prompt_files = manifest.get("promptFiles")
    prompts = _read_text_sections(package_dir, prompt_files)
    shared_sections = {} if package_name == SHARED_PACKAGE else _read_text_sections(PROMPT_PACKAGE_ROOT / SHARED_PACKAGE)
    output_schema_path = package_dir / str(manifest.get("outputSchema") or "output_schema.json")
    output_schema = _read_json(output_schema_path)
    version = _package_version(package_name, manifest, prompts, shared_sections)
    return PromptPackage(
        package_id=package_name,
        version=version,
        root=package_dir,
        manifest=manifest,
        shared=shared_sections,
        prompts=prompts,
        output_schema=output_schema,
    )


def build_prompt_package_text(
    package_name: str,
    section_name: str,
    *,
    context_label: str,
    context: dict,
    output_schema: dict | None = None,
) -> str:
    package = load_prompt_package(package_name)
    section_text = str(package.sections.get(section_name) or package.prompts.get(section_name) or "").strip()
    if not section_text:
        raise ValueError(f"Prompt section '{section_name}' is missing from package '{package_name}'")
    shared_blocks = [value.strip() for _, value in sorted(package.shared.items()) if value.strip()]
    parts = [
        f"Prompt package: {package.package_id}@{package.version}",
        *shared_blocks,
        section_text,
    ]
    resolved_output_schema = output_schema if output_schema is not None else package.output_schema
    if resolved_output_schema:
        parts.append("Structured output schema:\n" + json.dumps(resolved_output_schema, ensure_ascii=True))
    parts.append(f"{context_label}:\n" + json.dumps(context, ensure_ascii=True))
    return "\n\n".join(part for part in parts if part)


def reload_prompt_packages() -> None:
    load_prompt_package.cache_clear()
