#!/usr/bin/env python3
"""Compile deck archetype Markdown files into LLM-readable JSON.

Usage:
  python compile_deck_archetypes.py \
    --src backend/llm_knowledge/deck_archetype_knowledge/source_md \
    --out backend/llm_knowledge/deck_archetype_knowledge/compiled_json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("Missing dependency: PyYAML. Install with `pip install pyyaml`.") from exc


STARTUP_CANONICAL_FLOW = [
    "problem",
    "why-now",
    "regulatory-tailwinds",
    "solution",
    "product-demo",
    "market-size",
    "business-model",
    "competition",
    "blue-ocean-strategy",
    "positioning",
    "traction",
    "lighthouse-customers",
    "media-mentions",
    "thought-leadership",
    "core-team",
    "extended-team",
    "roadmap",
    "ask",
    "who-is-in",
    "use-of-proceeds",
    "references",
]

VC_FUND_CANONICAL_FLOW = [
    "fund-thesis",
    "why-now",
    "regulatory-tailwinds",
    "positioning",
    "blue-ocean-strategy",
    "track-record",
    "recent-exits",
    "portfolio-construction",
    "pipeline",
    "lighthouse-customers",
    "thought-leadership",
    "media-mentions",
    "core-team",
    "extended-team",
    "lp-terms",
    "who-is-in",
    "references",
]

DECK_TYPES = {
    "startup_pitch": {
        "description": "Company fundraising deck for angels, seed funds, venture funds, or strategic investors.",
        "canonical_flow": STARTUP_CANONICAL_FLOW,
        "required_core": [
            "problem",
            "solution",
            "market-size",
            "business-model",
            "competition",
            "positioning",
            "traction",
            "core-team",
            "ask",
        ],
        "optional_contextual": [
            "why-now",
            "regulatory-tailwinds",
            "product-demo",
            "lighthouse-customers",
            "roadmap",
            "use-of-proceeds",
            "who-is-in",
            "references",
            "media-mentions",
            "thought-leadership",
            "blue-ocean-strategy",
        ],
    },
    "vc_fund_pitch": {
        "description": "LP fundraising deck for venture funds, emerging managers, syndicates, or investment vehicles.",
        "canonical_flow": VC_FUND_CANONICAL_FLOW,
        "required_core": [
            "fund-thesis",
            "positioning",
            "track-record",
            "portfolio-construction",
            "pipeline",
            "core-team",
            "lp-terms",
        ],
        "optional_contextual": [
            "why-now",
            "regulatory-tailwinds",
            "blue-ocean-strategy",
            "recent-exits",
            "lighthouse-customers",
            "thought-leadership",
            "media-mentions",
            "extended-team",
            "who-is-in",
            "references",
        ],
    },
}

DEFAULT_RENDER_CONTRACT = {
    "schema_version": "smart-deck-render-schema.v1",
    "renderer": "GeneratedSlideRenderer.svelte",
    "output_mode": "render_schema_json",
    "forbidden_output": [
        "raw Svelte code",
        "Tailwind utility classes",
        "HTML fragments",
        "unverified external images",
    ],
    "default_layout_patterns": [
        "claim_with_evidence",
        "two_column_before_after",
        "metric_with_context",
        "matrix_or_map",
    ],
    "safe_bounds": {
        "canvas_width": 1920,
        "canvas_height": 1080,
        "safe_margin_px": 72,
    },
}

DEFAULT_QUALITY_RUBRIC = {
    "excellent": [
        "The slide has one clear narrative job.",
        "The headline is a defensible claim grounded in supplied context.",
        "The layout makes the main point visible before details.",
        "The render schema is valid and bounded.",
        "Missing evidence is surfaced honestly.",
    ],
    "weak": [
        "The slide is a generic template with no project-specific judgment.",
        "The headline is only a label.",
        "The layout has too many competing groups.",
        "The output invents metrics or customer proof.",
    ],
}

DEFAULT_EVIDENCE_HIERARCHY = [
    {
        "level": 1,
        "name": "Strong evidence",
        "examples": [
            "customer data",
            "usage data",
            "revenue data",
            "signed commitments",
            "named source facts",
            "verified regulatory or legal source",
        ],
    },
    {
        "level": 2,
        "name": "Moderate evidence",
        "examples": [
            "industry benchmark",
            "survey",
            "public research",
            "customer quote",
            "pipeline stage",
        ],
    },
    {
        "level": 3,
        "name": "Weak evidence",
        "examples": [
            "generic market trend",
            "founder opinion",
            "unsourced projection",
            "unverified claim",
        ],
    },
]

DEFAULT_REWRITE_MODES = {
    "clearer": {
        "instruction": "Remove vague language and make the claim more specific without changing facts.",
    },
    "more_investor_grade": {
        "instruction": "Tie the point to investor decision criteria, urgency, evidence, and risk without exaggeration.",
    },
    "shorter": {
        "instruction": "Reduce to one claim headline and no more than three concise proof points.",
    },
    "more_visual": {
        "instruction": "Translate the idea into a renderable visual pattern such as before/after, metric row, workflow, matrix, or evidence cards.",
    },
}

DEFAULT_OUTPUT_CONTRACT = {
    "required_semantic_fields": [
        "archetype",
        "headline",
        "subheadline",
        "supporting_points",
        "visual_suggestion",
        "speaker_notes",
        "missing_inputs",
        "quality_warnings",
        "source_facts_used",
        "assumptions",
        "confidence",
    ],
    "render_schema_mapping": {
        "headline": "primary text element",
        "supporting_points": "secondary text elements or evidence cards",
        "visual_suggestion": "renderSchema element layout",
        "missing_inputs": "renderSchema.analytics.missingInputs",
        "quality_warnings": "renderSchema.analytics.qualityWarnings",
        "source_facts_used": "renderSchema.analytics.sourceFactsUsed",
        "assumptions": "renderSchema.analytics.assumptions",
        "confidence": "renderSchema.analytics.confidence",
    },
}

DEFAULT_FRONTEND_RENDER_HINTS = {
    "renderer": "GeneratedSlideRenderer.svelte",
    "editable_fields": [
        "headline",
        "subheadline",
        "supporting_points",
        "speaker_notes",
    ],
    "show_missing_inputs_panel": True,
    "show_quality_warnings": True,
    "show_source_facts": True,
}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def title_from_slug(slug: str) -> str:
    return " ".join(
        part.upper() if part in {"lp", "vc", "gtm", "tam", "sam", "som"} else part.capitalize()
        for part in slug.split("-")
    )


def deck_types_from_tags(tags: list[str]) -> list[str]:
    output: set[str] = set()
    for tag in tags:
        if "Startup" in tag:
            output.add("startup_pitch")
        if "VC" in tag:
            output.add("vc_fund_pitch")
    return sorted(output)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_knowledge_modules(base: Path) -> dict[str, Any]:
    manifest = _load_yaml_file(base / "manifest.yaml")
    modules: dict[str, Any] = {}
    for module in manifest.get("knowledge_modules", []) if isinstance(manifest, dict) else []:
        if not isinstance(module, dict):
            continue
        module_id = str(module.get("id") or "").strip()
        module_path = str(module.get("path") or "").strip()
        if not module_id or not module_path:
            continue
        payload = _load_yaml_file(base / module_path)
        modules[module_id] = {
            "id": module_id,
            "path": module_path,
            "retrieval_priority": module.get("retrieval_priority") or "medium",
            "payload": payload,
        }
    return {
        "manifest": manifest,
        "modules": modules,
    }


def compile_one(path: Path) -> dict[str, Any]:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    slug = meta.get("default_slug") or path.stem
    description = meta.get("description", "")
    before = meta.get("often_before_slides") or []
    after = meta.get("often_after_slides") or []
    required_inputs = meta.get("required_inputs") or [
        {"field": "deck_specific_facts", "description": "Facts from the active deck, uploaded files, or user instruction.", "required": True},
        {"field": "proof_source", "description": "Evidence supporting the slide claim.", "required": True},
        {"field": "audience_context", "description": "The reader and decision the slide must influence.", "required": True},
    ]
    return {
        "id": f"{'.'.join(deck_types_from_tags(meta.get('tags') or []) or ['deck'])}.{slug}.v1",
        "slug": slug,
        "title": title_from_slug(slug),
        "description": description,
        "deck_types": deck_types_from_tags(meta.get("tags") or []),
        "deck_families": deck_types_from_tags(meta.get("tags") or []),
        "tags": meta.get("tags") or [],
        "slug_variants": meta.get("slug_variants") or [],
        "dates": {
            "created": str(meta.get("date_created", "")),
            "updated": str(meta.get("date_updated", "")),
        },
        "sequence": {
            "often_before_slides": before,
            "often_after_slides": after,
        },
        "body_md": body,
        "narrative_role": {
            "primary_job": description,
            "emotional_effect": "The audience should understand why this slide matters now.",
            "business_effect": "The audience should connect the slide claim to investor, LP, buyer, or operator decision-making.",
            "comes_before": after,
            "comes_after": before,
        },
        "use_when": [
            f"The deck needs a {title_from_slug(slug).lower()} slide to advance the narrative.",
            "The active deck context contains enough source facts to support this slide job.",
        ],
        "do_not_use_when": [
            "The slide would duplicate the previous slide's narrative job.",
            "Required evidence is absent and the user asked for a factual proof slide.",
        ],
        "required_inputs": required_inputs,
        "optional_inputs": [
            "customer quote",
            "market source",
            "metric",
            "visual asset",
            "speaker note",
        ],
        "evidence_hierarchy": DEFAULT_EVIDENCE_HIERARCHY,
        "generation_rules": {
            "headline": {
                "goal": "State one specific, evidence-led claim.",
                "avoid": [
                    "generic slide labels",
                    "unsupported superlatives",
                    "raw feature lists without audience relevance",
                ],
            },
            "body": {
                "recommended_structure": [
                    "claim",
                    "source-backed support",
                    "audience implication",
                    "missing input note when needed",
                ],
                "max_bullets": 4,
            },
            "speaker_notes": {
                "goal": "Explain the slide's argument and caveats without inventing facts.",
            },
        },
        "critique_rules": [
            {
                "rule": "source_fact_required",
                "description": "Flag unsupported claims, metrics, named customers, investors, regulatory claims, returns, or projections.",
                "severity": "high",
            },
            {
                "rule": "single_narrative_job",
                "description": "Flag the slide when it tries to do too many unrelated jobs.",
                "severity": "medium",
            },
            {
                "rule": "render_schema_validity",
                "description": "Flag output that cannot be rendered by the Svelte Smart Deck renderer.",
                "severity": "high",
            },
        ],
        "rewrite_modes": DEFAULT_REWRITE_MODES,
        "visual_guidance": [
            {
                "type": "claim_with_evidence",
                "best_when": "The slide needs one argument and a few proof points.",
                "description": "Use a dominant headline with evidence cards or a metric row.",
            },
            {
                "type": "two_column_before_after",
                "best_when": "The slide compares current state with unlocked future state.",
                "description": "Use two clear columns and a bridge label that explains the change.",
            },
        ],
        "llm_contract": {
            "narrative_function": (description + (" " + body if body else "")).strip(),
            "required_inputs": required_inputs,
            "quality_criteria": [
                "specific",
                "evidence-led",
                "fits the surrounding deck sequence",
                "valid render_schema_json",
            ],
            "common_mistakes": [
                "vague claims",
                "unsupported facts",
                "decorative slide with no narrative job",
                "raw Svelte, Tailwind classes, or CSS in model output",
            ],
            "output_expectation": {
                "slide_goal": "One clear investor-facing job for this slide.",
                "headline": "Short, specific, evidence-led headline.",
                "supporting_points": "3-5 proof points or claims, each grounded in provided company/fund context.",
                "visual_suggestion": "A suitable render_schema_json layout pattern.",
                "missing_inputs": "Questions or placeholders when required context is absent.",
            },
        },
        "render_contract": DEFAULT_RENDER_CONTRACT,
        "quality_rubric": DEFAULT_QUALITY_RUBRIC,
        "output_contract": DEFAULT_OUTPUT_CONTRACT,
        "validation_rules": [
            "Render schema must pass backend Pydantic validation.",
            "Do not emit raw Svelte, HTML, Tailwind, CSS, JavaScript, or base64 assets.",
            "All factual claims must be supported by source facts or listed as assumptions.",
            "If required evidence is absent, populate missing_inputs instead of inventing details.",
        ],
        "frontend_render_hints": DEFAULT_FRONTEND_RENDER_HINTS,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, help="Source folder containing archetype .md files")
    parser.add_argument("--out", required=True, help="Output folder for compiled JSON")
    args = parser.parse_args()

    src = Path(args.src)
    base = src.parent
    out = Path(args.out)
    detail_dir = out / "archetypes"
    module_dir = out / "modules"
    detail_dir.mkdir(parents=True, exist_ok=True)
    module_dir.mkdir(parents=True, exist_ok=True)

    archetypes = [compile_one(path) for path in sorted(src.glob("*.md"))]
    knowledge_modules = load_knowledge_modules(base)
    slug_lookup: dict[str, str] = {}
    relationship_graph: dict[str, Any] = {}

    for archetype in archetypes:
        slug = archetype["slug"]
        slug_lookup[slug] = slug
        for variant in archetype["slug_variants"]:
            slug_lookup[variant] = slug
        relationship_graph[slug] = archetype["sequence"]
        (detail_dir / f"{slug}.json").write_text(
            json.dumps(archetype, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    for module_id, module in knowledge_modules["modules"].items():
        (module_dir / f"{module_id}.json").write_text(
            json.dumps(module, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    index = {
        "version": knowledge_modules["manifest"].get("version") or "0.2.0",
        "name": "deck_archetype_knowledge",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Central LLM-readable knowledge base for investor deck narrative structure, "
            "slide archetype classification, generation, critique, and sequencing."
        ),
        "source_folder": "source_md",
        "manifest": knowledge_modules["manifest"],
        "knowledge_modules": knowledge_modules["modules"],
        "runtime_contract": {
            "load_this_file_first": "compiled_json/archetypes.index.json",
            "then_load_archetype_detail_by_id": "compiled_json/archetypes/{id}.json",
            "then_load_modules_by_id": "compiled_json/modules/{id}.json",
            "safe_runtime_mode": (
                "Read-only knowledge by default. User/company/fund facts must come from the "
                "active project context, not from this knowledge base."
            ),
            "llm_rule": (
                "Use the archetype knowledge to structure and critique decks. Do not invent "
                "traction, customers, investors, financials, regulatory claims, or team credentials."
            ),
            "renderer_rule": (
                "For Smart Deck, the LLM returns backend-validated render_schema_json. "
                "GeneratedSlideRenderer.svelte renders that JSON; the LLM must not emit Svelte code."
            ),
        },
        "deck_types": knowledge_modules["modules"]
        .get("deck_types", {})
        .get("payload", {})
        .get("deck_types", DECK_TYPES),
        "slug_lookup": slug_lookup,
        "relationship_graph": relationship_graph,
        "archetype_count": len(archetypes),
        "archetypes": archetypes,
    }
    (out / "archetypes.index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Compiled {len(archetypes)} archetypes into {out}")


if __name__ == "__main__":
    main()
