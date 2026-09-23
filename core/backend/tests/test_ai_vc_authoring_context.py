import json
import pytest

from app.services.ai_vc.authoring_context import (
    build_ai_vc_contexts, provider_safe_ai_vc_context, research_usage_observations,
)
from app.services.llm.full_html_generation_service import build_full_html_provider_runtime_context


def _approved_assets_with_bytes() -> list[dict[str, object]]:
    encoded = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    return [
        {
            "assetId": "asset_1",
            "mimeType": "image/png",
            "altText": "Primary logo",
            "resolvedDataUrl": f"data:image/png;base64,{encoded}",
            "originalSha256": "a" * 64,
        },
        {
            "assetId": "asset_2",
            "mimeType": "image/webp",
            "altText": "Hero image",
            "resolvedDataUrl": f"data:image/webp;base64,{encoded}",
            "originalSha256": "b" * 64,
        },
    ]


def test_authoring_context_excludes_editorial_source_and_internal_critique():
    context = {
        "objective": "Investor deck", "audience": "VC",
        "sourceSlides": [{"sourceSlideId": "source_1", "text": "Use this deck to test Deck V2"}],
        "sourceFacts": [
            {"factId": "fact_1", "text": "The product connects the workflow."},
            {"factId": "fact_meta", "text": "Concept test deck and key test notes."},
        ],
        "requiredSourceCoverage": [{"sourceSlideId": "source_1"}],
        "vcStrategy": {
            "companyIntelligence": {
                "businessEvidence": [{"text": "The product connects the workflow."}],
                "metaEditorial": [{"text": "Use this deck to test Deck V2"}],
            },
            "investmentMemo": {"thesis": "A workflow layer"},
            "investmentCommitteeReview": {"concerns": ["Internal warning"]},
            "diagnostics": [{"code": "schema_validation"}],
            "skillExecutionTrace": {"selectedSkills": [{"name": "investment-memo"}]},
        },
        "externalResearch": {
            "claims": [{
                "id": "external_1", "category": "external_research",
                "text": "Verified market evidence.",
            }],
            "gaps": [{"reason": "Internal research gap"}],
            "reflectionTrace": [{"decision": "continue"}],
            "costs": {"researchProviderDollars": "1.00"},
        }, "brand": {}, "approvedAssets": [],
        "visualIntelligence": {},
    }
    audit, authoring = build_ai_vc_contexts(context)
    runtime = provider_safe_ai_vc_context(context)
    mounted_runtime = build_full_html_provider_runtime_context(context)
    assert "Use this deck to test" in json.dumps(audit)
    encoded = json.dumps(authoring)
    assert "Use this deck to test" not in encoded
    assert "Internal warning" not in encoded
    assert "schema_validation" not in encoded
    assert "investment-memo" not in encoded
    assert "Verified market evidence" in encoded
    assert "Internal research gap" not in encoded
    assert "researchProviderDollars" not in encoded
    assert [item["factId"] for item in runtime["sourceFacts"]] == ["fact_1"]
    assert runtime["sourceSlides"] == [{
        "sourceSlideId": "source_1",
        "authoringPolicy": "lineage_only; source presentation is not an outline",
    }]
    assert mounted_runtime["authoringContext"]["schemaVersion"] == "ai-vc-authoring-context.v1"
    assert "Internal warning" not in json.dumps(mounted_runtime)
    assert "Internal research gap" not in json.dumps(mounted_runtime)


def test_authoring_context_mounts_reference_only_approved_assets():
    context = {
        "objective": "Investor deck",
        "audience": "VC",
        "sourceSlides": [{"sourceSlideId": "source_1", "text": "Facts only."}],
        "sourceFacts": [{"factId": "fact_1", "text": "The product connects the workflow."}],
        "requiredSourceCoverage": [{"sourceSlideId": "source_1"}],
        "vcStrategy": {
            "companyIntelligence": {"businessEvidence": [{"text": "Business."}]},
            "investmentMemo": {"thesis": "A workflow layer"},
        },
        "externalResearch": {"claims": []},
        "brand": {},
        "approvedAssets": _approved_assets_with_bytes(),
        "visualIntelligence": {
            "rendered_assets": [
                {"assetId": "chart_1", "title": "Pie", "data_url": "data:image/svg+xml;base64,PHN2Zz4="},
            ]
        },
    }
    encoded = json.dumps(build_ai_vc_contexts(context)[1])
    assert "resolvedDataUrl" not in encoded
    assert "data:image" not in encoded
    assert "data_url" not in encoded
    assert "asset_1" in encoded
    assert "asset_2" in encoded
    assert "chart_1" in encoded

    mounted = json.dumps(build_full_html_provider_runtime_context(context))
    assert "resolvedDataUrl" not in mounted
    assert "data:image" not in mounted
    assert "iVBORw0KGgo" not in mounted


def test_provider_runtime_context_stays_within_token_budget_with_base64_assets():
    from app.core.openai_full_html_policy import (
        FULL_HTML_MAX_INPUT_TOKENS,
        validate_token_feasibility,
    )
    from app.services.llm.full_html_generation_service import (
        _context_prompt_version,
        _system_prompt,
    )

    context = {
        "objective": "Investor deck",
        "audience": "VC",
        "sourceSlides": [{"sourceSlideId": "source_1", "text": "Facts only."}],
        "sourceFacts": [{"factId": "fact_1", "text": "The product connects the workflow."}],
        "requiredSourceCoverage": [{"sourceSlideId": "source_1"}],
        "vcStrategy": {
            "companyIntelligence": {"businessEvidence": [{"text": "Business."}]},
            "investmentMemo": {"thesis": "A workflow layer"},
        },
        "externalResearch": {"claims": []},
        "brand": {},
        "approvedAssets": _approved_assets_with_bytes(),
        "visualIntelligence": {},
    }
    provider_pack = build_full_html_provider_runtime_context(context)
    user_prompt = json.dumps(provider_pack, separators=(",", ":"), default=str)
    system_prompt = _system_prompt(_context_prompt_version(context) or "full-html-system-prompt.v38")
    feasibility = validate_token_feasibility(
        model="gpt-5-2025-08-07",
        prompt_parts=(system_prompt, user_prompt),
        max_output_tokens=128000,
    )
    assert feasibility.input_tokens < FULL_HTML_MAX_INPUT_TOKENS


def test_model_authored_strategy_requires_exact_visual_architecture_handoff():
    context = {
        "sourceSlides": [{"sourceSlideId": "source_1"}],
        "sourceFacts": [{"factId": "fact_1", "text": "Evidence."}],
        "vcStrategy": {
            "architectureSource": "model_authored",
            "investmentMemo": {"thesis": "Investable thesis"},
            "typedDeckArchitecture": {"slides": [{"id": "thesis", "title": "Thesis"}]},
        },
        "visualIntelligence": {"slide_visual_briefs": [{"slide_id": "thesis"}]},
    }
    _, authoring = build_ai_vc_contexts(context)
    assert authoring["policy"]["strategyAndVisualPlanAreAuthoringAuthority"] is True
    assert authoring["strategy"]["typedDeckArchitecture"]["slides"][0]["id"] == "thesis"
    context["visualIntelligence"]["slide_visual_briefs"][0]["slide_id"] = "source_1"
    with pytest.raises(ValueError, match="preserve architecture order"):
        build_ai_vc_contexts(context)


def test_model_selected_research_is_injected_with_qualification_and_use_is_observable():
    claims = [
        {"id": "external_use", "category": "external_research", "text": "Useful evidence.",
         "publisher": "example.org", "publicationDate": "2026-01-01",
         "retrievalDate": "2026-09-22T00:00:00+00:00", "url": "https://example.org/use"},
        {"id": "external_reject", "category": "external_research", "text": "Weak evidence.",
         "publisher": "example.org", "publicationDate": None,
         "retrievalDate": "2026-09-22T00:00:00+00:00", "url": "https://example.org/reject"},
    ]
    strategy = {
        "architectureSource": "model_authored", "investmentMemo": {"thesis": "Thesis"},
        "typedDeckArchitecture": {"slides": [{"id": "s1"}]},
        "researchSynthesis": {"finding_impacts": [
            {"evidence_ids": ["external_use"], "disposition": "use", "affects": ["thesis"],
             "explanation": "Clarifies adoption risk.", "qualification": "Industry context, not company proof."},
            {"evidence_ids": ["external_reject"], "disposition": "reject", "affects": ["market_discussion"],
             "explanation": "Too weak.", "qualification": "Do not use."},
        ]},
    }
    context = {
        "sourceSlides": [{"sourceSlideId": "source_1"}], "sourceFacts": [],
        "vcStrategy": strategy, "externalResearch": {"claims": claims},
        "visualIntelligence": {"slide_visual_briefs": [{"slide_id": "s1"}]},
    }
    _, authoring = build_ai_vc_contexts(context)
    research = authoring["verifiedExternalResearch"]
    assert [claim["id"] for claim in research["claims"]] == ["external_use"]
    assert research["claims"][0]["citationFactId"] == "external_use_citation"
    assert research["claims"][0]["strategyImpacts"][0]["qualification"] == "Industry context, not company proof."

    observations = research_usage_observations(
        strategy=strategy, authoring_research=research,
        compilation_manifest={"slides": [{"elements": [
            {"sourceFactIds": ["external_use"]},
            {"sourceFactIds": ["external_use_citation"]},
        ]}]},
    )
    assert observations["selectedEvidenceIds"] == ["external_use"]
    assert observations["injectedEvidenceIds"] == ["external_use"]
    assert observations["reflectedEvidenceIds"] == ["external_use"]
    assert observations["readablyCitedEvidenceIds"] == ["external_use"]
