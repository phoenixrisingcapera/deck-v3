from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
import json
import os
from pathlib import Path
import re


FALLBACK_SLIDE_ARCHETYPES = [
    {
        "slug": "why-now",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["timing", "market-timing", "the-moment", "inflection", "macro-tailwinds", "why-this-moment"],
        "description": "The market-timing argument. What changed that makes this the moment for the bet.",
        "before": ["problem", "fund-thesis", "market-size"],
        "after": ["regulatory-tailwinds", "solution", "market-size", "positioning", "track-record"],
    },
    {
        "slug": "problem",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["the-problem", "pain-point", "the-pain"],
        "description": "The pain the startup exists to relieve and who hurts.",
        "before": [],
        "after": ["why-now", "solution", "market-size"],
    },
    {
        "slug": "solution",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["the-solution", "our-solution", "approach"],
        "description": "The thesis-level answer to the problem.",
        "before": ["problem"],
        "after": ["product-demo", "market-size", "business-model"],
    },
    {
        "slug": "product-demo",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["product", "demo", "how-it-works", "what-we-built", "the-product"],
        "description": "Show, don't tell. Screenshots, flow, or video that make the solution concrete.",
        "before": ["solution"],
        "after": ["business-model", "traction"],
    },
    {
        "slug": "market-size",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["tam", "tam-sam-som", "market-opportunity", "market", "opportunity-size"],
        "description": "How large the addressable opportunity is.",
        "before": ["problem", "solution"],
        "after": ["business-model", "competition", "positioning"],
    },
    {
        "slug": "traction",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["progress", "metrics", "momentum", "milestones", "kpis", "traction-and-metrics"],
        "description": "Evidence the thing is working.",
        "before": ["product-demo", "business-model", "positioning"],
        "after": ["core-team", "roadmap"],
    },
    {
        "slug": "business-model",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["go-to-market", "gtm", "revenue-model", "monetization", "how-we-make-money", "unit-economics"],
        "description": "How the company captures value.",
        "before": ["solution", "product-demo"],
        "after": ["traction", "competition", "positioning"],
    },
    {
        "slug": "competition",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["competitive-landscape", "market-landscape", "landscape", "competitors", "alternatives"],
        "description": "A map of who else is in the space.",
        "before": ["business-model", "market-size"],
        "after": ["positioning", "traction"],
    },
    {
        "slug": "positioning",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["differentiation", "moat", "why-us", "unique-value", "competitive-advantage", "our-edge"],
        "description": "The defensible difference.",
        "before": ["competition", "market-size", "fund-thesis"],
        "after": ["traction", "core-team", "track-record"],
    },
    {
        "slug": "core-team",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["team", "founders", "leadership", "founding-team", "the-team", "executive-team"],
        "description": "The operating people behind the company or fund.",
        "before": ["traction", "positioning", "portfolio-construction"],
        "after": ["extended-team", "roadmap", "ask"],
    },
    {
        "slug": "extended-team",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["advisors", "board", "team-extended", "advisory-board", "investors-and-advisors", "backers-and-advisors"],
        "description": "The credibility ring around the core.",
        "before": ["core-team"],
        "after": ["roadmap", "ask", "lp-terms"],
    },
    {
        "slug": "roadmap",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["plan", "milestones-roadmap", "next-12-months", "what-we-will-do", "vision", "18-month-plan"],
        "description": "What the company will do with the runway.",
        "before": ["traction", "core-team", "extended-team"],
        "after": ["ask", "use-of-proceeds"],
    },
    {
        "slug": "ask",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["the-ask", "raise", "round", "raising", "funding-ask", "we-are-raising"],
        "description": "How much the company is raising and what milestones the round funds.",
        "before": ["roadmap", "core-team", "extended-team"],
        "after": ["use-of-proceeds"],
    },
    {
        "slug": "use-of-proceeds",
        "tags": ["Startup-Pitch-Narratives"],
        "aliases": ["uop", "where-the-money-goes", "deployment", "spend-plan", "fund-allocation", "capital-allocation"],
        "description": "How the raised capital is deployed.",
        "before": ["ask", "roadmap"],
        "after": [],
    },
    {
        "slug": "fund-thesis",
        "tags": ["VC-Pitch-Narratives"],
        "aliases": ["thesis", "investment-thesis", "our-thesis", "why-this-fund", "fund-strategy"],
        "description": "The world-view the fund invests behind.",
        "before": [],
        "after": ["why-now", "positioning", "track-record", "portfolio-construction"],
    },
    {
        "slug": "track-record",
        "tags": ["VC-Pitch-Narratives"],
        "aliases": ["past-performance", "returns", "history", "prior-funds", "track", "performance"],
        "description": "The fund's prior performance.",
        "before": ["fund-thesis", "positioning"],
        "after": ["recent-exits", "portfolio-construction"],
    },
    {
        "slug": "recent-exits",
        "tags": ["VC-Pitch-Narratives"],
        "aliases": ["exits", "wins", "notable-exits", "realizations", "liquidity-events"],
        "description": "Specific named exits with multiples and attribution.",
        "before": ["track-record"],
        "after": ["portfolio-construction", "pipeline"],
    },
    {
        "slug": "portfolio-construction",
        "tags": ["VC-Pitch-Narratives"],
        "aliases": ["portfolio", "portfolio-strategy", "allocation-model", "check-sizes", "construction", "portfolio-model"],
        "description": "How the fund deploys capital.",
        "before": ["fund-thesis", "track-record"],
        "after": ["pipeline", "core-team"],
    },
    {
        "slug": "pipeline",
        "tags": ["VC-Pitch-Narratives"],
        "aliases": ["deal-flow", "active-pipeline", "live-deals", "near-term-investments", "current-pipeline"],
        "description": "Live deals the fund is actively diligencing.",
        "before": ["portfolio-construction", "recent-exits"],
        "after": ["core-team", "lp-terms"],
    },
    {
        "slug": "who-is-in",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["existing-investors", "current-investors", "round-participants", "committed-capital", "anchor-investors", "soft-commits"],
        "description": "Who has already committed to this round or fund.",
        "before": ["ask", "lp-terms", "extended-team"],
        "after": ["use-of-proceeds", "pipeline"],
    },
    {
        "slug": "lp-terms",
        "tags": ["VC-Pitch-Narratives"],
        "aliases": ["terms", "fund-terms", "lp-economics", "fees-and-carry", "fund-structure", "economics"],
        "description": "The economic and structural terms of the LP commitment.",
        "before": ["pipeline", "extended-team", "core-team"],
        "after": [],
    },
    {
        "slug": "lighthouse-customers",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["marquee-customers", "design-partners", "anchor-customers", "named-customers", "logo-slide", "customer-logos", "flagship-customers"],
        "description": "Named marquee customers or design partners.",
        "before": ["traction", "product-demo", "business-model"],
        "after": ["traction", "business-model", "references", "media-mentions", "core-team"],
    },
    {
        "slug": "references",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["customer-references", "lp-references", "vouchers", "references-available", "willing-references", "backchannel-references"],
        "description": "Named people willing to take a diligence call.",
        "before": ["traction", "extended-team", "media-mentions", "recent-exits"],
        "after": ["ask", "use-of-proceeds", "lp-terms"],
    },
    {
        "slug": "thought-leadership",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["content", "writing", "publications", "talks", "podcast", "substack", "original-research", "papers"],
        "description": "Original content that demonstrates point-of-view and category authority.",
        "before": ["positioning", "core-team", "fund-thesis", "track-record"],
        "after": ["media-mentions", "references", "extended-team", "traction"],
    },
    {
        "slug": "media-mentions",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["press", "as-seen-in", "media", "press-coverage", "in-the-news", "press-logos", "media-coverage"],
        "description": "Third-party validation via press.",
        "before": ["traction", "track-record", "recent-exits"],
        "after": ["extended-team", "core-team", "references"],
    },
    {
        "slug": "regulatory-tailwinds",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["regulation", "regulatory-environment", "policy-tailwinds", "regulatory-backdrop", "policy", "compliance-tailwinds"],
        "description": "The policy or regulatory shift that creates the opening.",
        "before": ["why-now", "problem", "fund-thesis", "market-size"],
        "after": ["solution", "market-size", "business-model", "positioning"],
    },
    {
        "slug": "blue-ocean-strategy",
        "tags": ["Startup-Pitch-Narratives", "VC-Pitch-Narratives"],
        "aliases": ["strategy-canvas", "value-curve", "eric-grid", "eric-framework", "four-actions", "blue-ocean", "value-innovation"],
        "description": "Positioning via the Strategy Canvas against incumbents.",
        "before": ["competition", "positioning", "market-size"],
        "after": ["positioning", "traction", "business-model", "fund-thesis"],
    },
]


def _default_knowledge_index_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "llm_knowledge"
        / "deck_archetype_knowledge"
        / "compiled_json"
        / "archetypes.index.json"
    )


def _knowledge_index_candidates() -> list[Path]:
    configured = os.getenv("DECK_KNOWLEDGE_INDEX_PATH", "").strip()
    default_path = _default_knowledge_index_path()
    candidates = [Path(configured)] if configured else []
    if default_path not in candidates:
        candidates.append(default_path)
    return candidates


def _normalise_knowledge_archetype(archetype: dict) -> dict:
    sequence = archetype.get("sequence") if isinstance(archetype.get("sequence"), dict) else {}
    return {
        "slug": archetype.get("slug") or archetype.get("id"),
        "tags": archetype.get("tags") or [],
        "aliases": archetype.get("slug_variants") or archetype.get("aliases") or [],
        "description": archetype.get("description") or "",
        "before": sequence.get("often_before_slides") or archetype.get("before") or [],
        "after": sequence.get("often_after_slides") or archetype.get("after") or [],
        "deck_types": archetype.get("deck_types") or [],
        "llm_contract": archetype.get("llm_contract") or {},
        "render_contract": archetype.get("render_contract") or {},
        "quality_rubric": archetype.get("quality_rubric") or {},
        "narrative_role": archetype.get("narrative_role") or {},
        "required_inputs": archetype.get("required_inputs") or [],
        "optional_inputs": archetype.get("optional_inputs") or [],
        "evidence_hierarchy": archetype.get("evidence_hierarchy") or [],
        "generation_rules": archetype.get("generation_rules") or {},
        "critique_rules": archetype.get("critique_rules") or [],
        "rewrite_modes": archetype.get("rewrite_modes") or {},
        "visual_guidance": archetype.get("visual_guidance") or [],
        "output_contract": archetype.get("output_contract") or {},
        "validation_rules": archetype.get("validation_rules") or [],
        "frontend_render_hints": archetype.get("frontend_render_hints") or {},
    }


def _compact_modules(modules: dict) -> dict:
    if not isinstance(modules, dict):
        return {}
    compacted: dict[str, dict] = {}
    for module_id, module in modules.items():
        if not isinstance(module, dict):
            continue
        payload = module.get("payload") if isinstance(module.get("payload"), dict) else {}
        compacted[module_id] = {
            "retrievalPriority": module.get("retrieval_priority"),
            "payload": payload,
        }
    return compacted


@lru_cache(maxsize=1)
def load_deck_archetype_knowledge() -> dict:
    candidates = _knowledge_index_candidates()
    index_path = next((path for path in candidates if path.exists()), candidates[0])
    if not index_path.exists():
        return {
            "source": "fallback",
            "index_path": str(index_path),
            "version": "fallback-static",
            "name": "static_slide_archetypes",
            "deck_types": {},
            "archetypes": FALLBACK_SLIDE_ARCHETYPES,
        }

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        archetypes = [
            item
            for item in (_normalise_knowledge_archetype(item) for item in payload.get("archetypes", []))
            if item.get("slug")
        ]
        if not archetypes:
            raise ValueError("Knowledge index contains no archetypes.")
        return {
            "source": "compiled_json",
            "index_path": str(index_path),
            "version": payload.get("version") or "unknown",
            "name": payload.get("name") or "deck_archetype_knowledge",
            "deck_types": payload.get("deck_types") or {},
            "runtime_contract": payload.get("runtime_contract") or {},
            "manifest": payload.get("manifest") or {},
            "knowledge_modules": _compact_modules(payload.get("knowledge_modules") or {}),
            "archetypes": archetypes,
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "source": "fallback",
            "index_path": str(index_path),
            "version": "fallback-static",
            "name": "static_slide_archetypes",
            "deck_types": {},
            "archetypes": FALLBACK_SLIDE_ARCHETYPES,
        }


SLIDE_ARCHETYPES = load_deck_archetype_knowledge()["archetypes"]


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _slugs_from(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    seen: list[str] = []
    for value in values:
        slug = value.strip().lower()
        if slug and slug not in seen:
            seen.append(slug)
    return seen


def _score_archetype(archetype: dict, haystack: str, haystack_tokens: set[str]) -> int:
    score = 0
    slug = archetype["slug"]
    if slug in haystack:
        score += 6
    if slug.replace("-", " ") in haystack:
        score += 4
    for alias in archetype["aliases"]:
        alias_tokens = _tokens(alias)
        if alias in haystack:
            score += 5
        elif alias_tokens and alias_tokens.issubset(haystack_tokens):
            score += 3
    for word in archetype["description"].lower().split():
        if word in haystack_tokens:
            score += 1
    return score


def infer_slide_archetypes(*values: object, limit: int = 3) -> list[dict]:
    text_parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, dict):
            text_parts.extend(str(item) for item in value.values() if item is not None)
        elif isinstance(value, Iterable):
            text_parts.extend(str(item) for item in value if item is not None)
        else:
            text_parts.append(str(value))
    haystack = " ".join(text_parts).lower()
    haystack_tokens = _tokens(haystack)

    scored = []
    for archetype in SLIDE_ARCHETYPES:
        score = _score_archetype(archetype, haystack, haystack_tokens)
        if score:
            scored.append((score, archetype))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def build_slide_archetype_context(
    *,
    audience: str | None,
    purpose: str | None,
    slide_texts: list[str] | None = None,
    slide_titles: list[str] | None = None,
    slide_roles: list[str] | None = None,
) -> dict:
    knowledge = load_deck_archetype_knowledge()
    archetypes = knowledge["archetypes"]
    inferred = infer_slide_archetypes(audience, purpose, slide_texts or [], slide_titles or [], slide_roles or [])
    audience_text = f"{audience or ''} {purpose or ''}".lower()
    if any(marker in audience_text for marker in ("vc", "venture", "fund", "partner review", "lp")):
        if not any(item["slug"] == "fund-thesis" for item in inferred):
            fund_thesis = next((item for item in archetypes if item["slug"] == "fund-thesis"), None)
            if fund_thesis is not None:
                inferred = [fund_thesis] + inferred
    deck_types = knowledge.get("deck_types") or {}
    startup_type = deck_types.get("startup_pitch")
    fund_type = deck_types.get("vc_fund_pitch")
    startup_flow = (
        startup_type.get("canonical_flow") if isinstance(startup_type, dict) else None
    )
    fund_flow = fund_type.get("canonical_flow") if isinstance(fund_type, dict) else None
    is_fund_context = any(
        marker in audience_text for marker in ("vc", "venture", "fund", "partner review", "lp")
    )
    recommended_sequence = fund_flow if is_fund_context else startup_flow
    if not recommended_sequence:
        recommended_sequence = [
            "fund-thesis" if "fund" in (audience or "").lower() or "vc" in (audience or "").lower() else "problem",
            "why-now",
            "solution",
            "traction",
            "business-model",
            "competition",
            "positioning",
            "core-team",
            "roadmap",
            "ask",
            "use-of-proceeds",
        ]
    return {
        "schemaVersion": "slide-archetype-context.v1",
        "knowledgeSource": {
            "name": knowledge.get("name"),
            "version": knowledge.get("version"),
            "source": knowledge.get("source"),
            "archetypeCount": len(archetypes),
        },
        "audience": audience,
        "purpose": purpose,
        "recommendedSequence": _slugs_from(recommended_sequence),
        "inferredArchetypes": [
            {
                "slug": item["slug"],
                "description": item["description"],
                "before": item["before"],
                "after": item["after"],
                "tags": item["tags"],
                "llmContract": item.get("llm_contract") or {},
                "renderContract": item.get("render_contract") or {},
                "qualityRubric": item.get("quality_rubric") or {},
                "narrativeRole": item.get("narrative_role") or {},
                "requiredInputs": item.get("required_inputs") or [],
                "optionalInputs": item.get("optional_inputs") or [],
                "evidenceHierarchy": item.get("evidence_hierarchy") or [],
                "generationRules": item.get("generation_rules") or {},
                "critiqueRules": item.get("critique_rules") or [],
                "rewriteModes": item.get("rewrite_modes") or {},
                "visualGuidance": item.get("visual_guidance") or [],
                "outputContract": item.get("output_contract") or {},
                "validationRules": item.get("validation_rules") or [],
                "frontendRenderHints": item.get("frontend_render_hints") or {},
            }
            for item in inferred
        ],
        "knowledgeModules": knowledge.get("knowledge_modules") or {},
        "runtimeContract": knowledge.get("runtime_contract") or {},
        "narrativeGuidance": [
            "Use the archetype order to shape slide sequence and the amount of evidence per slide.",
            "Prefer the archetype whose description best matches the slide's job, not just its title.",
            "If a slide sits between two archetypes, preserve the adjacency the corpus expects.",
            "For VC decks, weight fund-thesis, why-now, track-record, portfolio-construction, "
            "pipeline, who-is-in, and lp-terms heavily.",
            "For startup decks, weight problem, why-now, solution, product-demo, market-size, "
            "traction, business-model, competition, positioning, team, roadmap, ask, and "
            "use-of-proceeds heavily.",
        ],
    }
