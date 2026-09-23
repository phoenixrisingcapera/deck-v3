from __future__ import annotations

import re
from collections.abc import Iterable


VC_DILIGENCE_KEYWORDS = {
    "market": [
        "TAM",
        "SAM",
        "SOM",
        "market timing",
        "category growth",
        "ICP",
        "wedge",
        "beachhead",
    ],
    "traction": [
        "ARR",
        "MRR",
        "growth rate",
        "retention",
        "net revenue retention",
        "payback",
        "pipeline",
        "conversion",
    ],
    "unit_economics": [
        "gross margin",
        "CAC",
        "LTV",
        "burn multiple",
        "runway",
        "cash efficiency",
        "contribution margin",
    ],
    "competition": [
        "competitive moat",
        "differentiation",
        "switching cost",
        "incumbent",
        "category alternative",
        "defensibility",
    ],
    "team": [
        "founder-market fit",
        "technical depth",
        "go-to-market experience",
        "hiring plan",
        "advisor quality",
    ],
    "raise": [
        "use of funds",
        "milestones",
        "round size",
        "valuation",
        "ownership",
        "next financing risk",
    ],
    "risk": [
        "regulatory risk",
        "platform dependency",
        "concentration risk",
        "data quality",
        "implementation risk",
        "sales cycle risk",
    ],
}


VC_PERSONAS = [
    {
        "id": "investment_committee",
        "labels": ["investment committee", "ic", "partner meeting", "committee"],
        "name": "Investment Committee",
        "role": "Final investment decision group",
        "priorities": [
            "decision-ready narrative",
            "evidence density",
            "risk-adjusted return logic",
            "clear investment memo takeaways",
        ],
        "questions": [
            "Why this market now?",
            "What evidence proves urgency and willingness to pay?",
            "What could break the investment case?",
            "What milestones does this round unlock?",
        ],
        "tone": "concise, rigorous, risk-aware, memo-ready",
        "keywords": ["IC memo", "investment case", "decision risk", "milestones", "return potential"],
    },
    {
        "id": "vc_partner",
        "labels": ["vc partner", "partner", "general partner", "gp"],
        "name": "VC Partner",
        "role": "Deal sponsor and conviction owner",
        "priorities": [
            "non-obvious insight",
            "market scale",
            "founder-market fit",
            "fund-return potential",
        ],
        "questions": [
            "Can this become a fund-returning company?",
            "What is the insight others are missing?",
            "Why is this team uniquely positioned?",
            "What makes the opportunity urgent?",
        ],
        "tone": "sharp, high-conviction, selective, commercially grounded",
        "keywords": ["fund returner", "conviction", "market pull", "founder-market fit", "venture scale"],
    },
    {
        "id": "vc_associate",
        "labels": ["vc associate", "associate", "analyst"],
        "name": "VC Associate",
        "role": "First-pass evaluator and diligence preparer",
        "priorities": [
            "scannable evidence",
            "comparable metrics",
            "sourceable claims",
            "clear follow-up questions",
        ],
        "questions": [
            "Which claims need verification?",
            "What metrics should be benchmarked?",
            "Where are the diligence gaps?",
            "What should the partner ask next?",
        ],
        "tone": "structured, explicit, citation-seeking, analytical",
        "keywords": ["diligence checklist", "benchmark", "source", "claim", "follow-up"],
    },
    {
        "id": "principal",
        "labels": ["principal", "venture principal"],
        "name": "VC Principal",
        "role": "Thesis builder and deal-shaping reviewer",
        "priorities": [
            "thesis fit",
            "commercial proof",
            "investment narrative",
            "round strategy",
        ],
        "questions": [
            "How does the company fit the fund thesis?",
            "What proof converts interest into conviction?",
            "What are the strongest objections and answers?",
            "How should the round be positioned?",
        ],
        "tone": "strategic, thesis-led, practical, evidence-weighted",
        "keywords": ["thesis fit", "commercial proof", "round strategy", "objection handling"],
    },
    {
        "id": "corporate_venture",
        "labels": ["corporate venture", "cvc", "strategic investor", "strategic"],
        "name": "Corporate Venture",
        "role": "Strategic investor balancing financial and operating fit",
        "priorities": [
            "strategic alignment",
            "integration path",
            "enterprise readiness",
            "partnership leverage",
        ],
        "questions": [
            "Where is the strategic fit?",
            "What integration or channel leverage exists?",
            "What enterprise risks must be resolved?",
            "How does this complement the corporate roadmap?",
        ],
        "tone": "commercial, operational, partnership-aware, risk-controlled",
        "keywords": ["strategic fit", "integration", "channel leverage", "enterprise readiness"],
    },
    {
        "id": "operator_angel",
        "labels": ["angel", "operator", "operator angel", "advisor"],
        "name": "Operator Angel",
        "role": "Practical operator-investor reviewing execution credibility",
        "priorities": [
            "execution plan",
            "customer pain clarity",
            "go-to-market motion",
            "near-term operating risks",
        ],
        "questions": [
            "What must be true operationally in the next 90 days?",
            "Who feels the pain and how often?",
            "What sales motion is plausible?",
            "Where can an operator help most?",
        ],
        "tone": "plain-spoken, practical, execution-first, founder-friendly",
        "keywords": ["execution", "GTM motion", "customer pain", "operating risk"],
    },
]


DEFAULT_VC_PERSONA = VC_PERSONAS[0]


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def infer_vc_persona(audience: str | None, user_role: str | None = None) -> dict:
    haystack = f"{audience or ''} {user_role or ''}".lower()
    haystack_tokens = _tokens(haystack)
    for persona in VC_PERSONAS:
        for label in persona["labels"]:
            label_tokens = _tokens(label)
            if label in haystack or (label_tokens and label_tokens.issubset(haystack_tokens)):
                return persona
    return DEFAULT_VC_PERSONA


def extract_vc_keywords(*values: object, limit: int = 24) -> list[str]:
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

    found: list[str] = []
    for keywords in VC_DILIGENCE_KEYWORDS.values():
        for keyword in keywords:
            if keyword.lower() in haystack and keyword not in found:
                found.append(keyword)
    return found[:limit]


def build_vc_prompt_context(
    *,
    audience: str | None,
    purpose: str | None = None,
    user_role: str | None = None,
    audience_profile: dict | None = None,
    deck_metadata: dict | None = None,
    brand_evidence: dict | None = None,
    slide_texts: list[str] | None = None,
) -> dict:
    persona = infer_vc_persona(audience, user_role)
    database_focus = audience_profile.get("focus") if audience_profile else None
    if isinstance(database_focus, str):
        database_focus_items = [database_focus]
    elif isinstance(database_focus, list):
        database_focus_items = [str(item) for item in database_focus if str(item).strip()]
    else:
        database_focus_items = []

    database_tone = audience_profile.get("tone") if audience_profile else None
    detected_keywords = extract_vc_keywords(
        audience,
        purpose,
        deck_metadata or {},
        brand_evidence or {},
        slide_texts or [],
        database_focus_items,
    )

    return {
        "schemaVersion": "vc-audience-context.v1",
        "requestedAudience": audience,
        "purpose": purpose,
        "matchedPersona": {
            "id": persona["id"],
            "name": persona["name"],
            "role": persona["role"],
            "priorities": persona["priorities"],
            "questions": persona["questions"],
            "tone": database_tone or persona["tone"],
            "keywords": list(dict.fromkeys([*persona["keywords"], *detected_keywords]))[:24],
        },
        "databaseAudienceProfile": {
            "label": audience_profile.get("label") if audience_profile else None,
            "focus": database_focus_items,
            "tone": database_tone,
        },
        "diligenceKeywordMap": VC_DILIGENCE_KEYWORDS,
        "promptRules": [
            "Write for the matched VC persona, not a generic business audience.",
            "Prefer investor decision criteria: market, traction, unit economics, competition, team, raise, and risk.",
            "Separate deck-backed evidence from assumptions and missing evidence.",
            "Do not fabricate market sizes, customer proof, financials, or benchmarks.",
            "When rewriting slide text, preserve facts and increase specificity only when the source supports it.",
        ],
    }
