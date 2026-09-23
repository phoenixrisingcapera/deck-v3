from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.llm.deck_chunking_service import _instant_deck_knowledge_chunks
from app.services.llm.instant_deck_context_builder import build_bounded_retrieved_guidance
from app.services.llm.instant_deck_context_builder import build_compact_instant_deck_agent_context
from app.services.llm.instant_deck_context_builder import _is_probable_ocr_debris
from app.services.llm.full_html_generation_service import (
    ART_DIRECTION_FULL_HTML_SYSTEM_PROMPT_VERSION,
    CHROMIUM_READABILITY_FULL_HTML_SYSTEM_PROMPT_VERSION,
    FULL_HTML_SYSTEM_PROMPT_VERSION,
    PRESENTATION_SCALE_FULL_HTML_SYSTEM_PROMPT_VERSION,
    PREVIOUS_ACTIVE_FULL_HTML_SYSTEM_PROMPT_VERSION,
    PRIOR_CURRENT_FULL_HTML_SYSTEM_PROMPT_VERSION,
    SOURCE_BACKED_FULL_HTML_SYSTEM_PROMPT_VERSION,
    VISUAL_SUBSTANCE_FULL_HTML_SYSTEM_PROMPT_VERSION,
    _system_prompt,
    build_full_html_provider_runtime_context,
    validate_full_html_presentation_quality,
)
from app.services.rendering.html_deck_compiler import HtmlDeckCompileError


def test_instant_deck_embedding_corpus_contains_only_product_owned_guidance() -> None:
    chunks = _instant_deck_knowledge_chunks()

    assert chunks
    assert {chunk["chunk_type"] for chunk in chunks} == {
        "instant_deck_knowledge", "vc_methodology_knowledge",
    }
    assert all(
        chunk["metadata_json"].get("scope") == "global_instant_deck"
        for chunk in chunks
    )
    assert all("deckId" not in chunk["metadata_json"] for chunk in chunks)
    assert any(
        chunk["metadata_json"].get("lane") == "design_quality_rule"
        for chunk in chunks
    )


def test_compact_agent_context_delivers_complete_design_policy_to_provider() -> None:
    context = build_compact_instant_deck_agent_context()

    rules = context["designQualityRules"]["rules"]
    rule_ids = {rule["id"] for rule in rules}
    assert "editorial-scale-and-canvas-use" in rule_ids
    assert "source-cleanup-not-transcription" in rule_ids
    assert "operator-metadata-not-investor-copy" in rule_ids
    assert "coherent-art-direction-varied-composition" in rule_ids
    assert "source-backed-palette-provenance" in rule_ids
    assert "visual-storytelling-coverage" in rule_ids
    assert "no-empty-or-unreadable-panels" in rule_ids
    assert "decisive-close-not-directory" in rule_ids
    assert context["factualAuthority"] == "canonical_source_only"


def test_current_investor_beta_prompt_excludes_operator_metadata_without_mutating_v2() -> None:
    from app.services.llm.full_html_generation_service import (
        BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
        LINEAGE_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
        PREVIOUS_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
    )

    current = _system_prompt(BETA_FULL_HTML_SYSTEM_PROMPT_VERSION)
    lineage = _system_prompt(LINEAGE_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION)
    previous = _system_prompt(PREVIOUS_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION)

    assert BETA_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-investor-beta.v7"
    assert LINEAGE_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-investor-beta.v5"
    assert PREVIOUS_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-investor-beta.v2"
    assert "OPERATOR-METADATA EXCLUSION" in current
    assert "CANONICAL SOURCE-ID REGISTRY" in current
    assert "INVESTOR-FINANCIAL-SELECTION CONTRACT" in current
    assert "BRAND-SOURCE-PRIORITY CONTRACT" in current
    assert "ADVISORY-STACK HANDOFF CONTRACT" in current
    assert "privately audit the complete draft" in current
    assert "Return only the improved deck HTML" in current
    assert "INVESTOR-FINANCIAL-SELECTION CONTRACT" not in lineage
    assert "CANONICAL SOURCE-ID REGISTRY" in lineage
    assert "use this deck to test" in current
    assert "OPERATOR-METADATA EXCLUSION" not in previous


def test_provider_context_makes_brand_source_priority_explicit(monkeypatch) -> None:
    from app.core.config import settings
    from app.schemas.instant_deck_context import (
        BrandProfileSnapshot,
        BrandTokenProvenance,
        CanonicalSourceDeck,
        CanonicalSourceSlide,
        InstantDeckGenerationContext,
    )
    from app.services.llm.instant_deck_context_builder import context_to_grounded_pack

    monkeypatch.setattr(settings, "instant_html_llm_first_beta", False)
    context = InstantDeckGenerationContext(
        deck_id="deck-brand-priority",
        source_deck=CanonicalSourceDeck(
            slide_count=1,
            slides=[CanonicalSourceSlide(id="source-slide-1", index=1)],
        ),
        brand_profile=BrandProfileSnapshot(
            primary_color="#102030",
            website_source_url="https://example.com",
            token_provenance={
                "colors.primary": BrandTokenProvenance(
                    classification="source-extracted",
                    source="deck_visual",
                ),
            },
        ),
    )
    brand = context_to_grounded_pack(context)["brand"]
    assert brand["sourcePriority"] == [
        "manual_or_brand_guidelines",
        "uploaded_deck_identity",
        "confirmed_company_website_enrichment",
        "neutral_fallback_when_brand_absent",
    ]
    assert brand["tokenProvenance"]["colors.primary"]["source"] == "deck_visual"
    assert "not a narrative template" in brand["identityPolicy"]


def test_current_investor_beta_rejects_visible_test_and_redesign_notes() -> None:
    from app.services.llm.full_html_generation_service import (
        BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
        PREVIOUS_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
    )

    failed = (
        '<html><body><main><section class="deck-section">'
        '<h1>Use this deck to test Deck V2</h1>'
        '<p>Key test: does the redesign make the story investor-ready?</p>'
        '</section></main></body></html>'
    )
    clean = (
        '<html><body><main><section class="deck-section">'
        '<h1>One operating layer for clinic growth</h1>'
        '<p>Connect content, bookings, follow-up and rebooking.</p>'
        '</section></main></body></html>'
    )

    with pytest.raises(HtmlDeckCompileError, match="test, evaluation, or redesign-process notes"):
        validate_full_html_presentation_quality(
            failed,
            system_prompt_version=BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
        )
    validate_full_html_presentation_quality(
        clean,
        system_prompt_version=BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
    )
    # Historical v2 output remains replayable under its original quality boundary.
    validate_full_html_presentation_quality(
        failed,
        system_prompt_version=PREVIOUS_BETA_FULL_HTML_SYSTEM_PROMPT_VERSION,
    )


def test_current_prompt_enforces_focal_scale_without_mutating_v16() -> None:
    current = _system_prompt(FULL_HTML_SYSTEM_PROMPT_VERSION)
    historical = _system_prompt(PRIOR_CURRENT_FULL_HTML_SYSTEM_PROMPT_VERSION)
    previous = _system_prompt(PREVIOUS_ACTIVE_FULL_HTML_SYSTEM_PROMPT_VERSION)
    presentation_scale = _system_prompt(PRESENTATION_SCALE_FULL_HTML_SYSTEM_PROMPT_VERSION)
    art_direction = _system_prompt(ART_DIRECTION_FULL_HTML_SYSTEM_PROMPT_VERSION)
    source_backed = _system_prompt(SOURCE_BACKED_FULL_HTML_SYSTEM_PROMPT_VERSION)
    visual_substance = _system_prompt(VISUAL_SUBSTANCE_FULL_HTML_SYSTEM_PROMPT_VERSION)
    chromium_readability = _system_prompt(CHROMIUM_READABILITY_FULL_HTML_SYSTEM_PROMPT_VERSION)

    assert FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v38"
    assert CHROMIUM_READABILITY_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v16"
    assert VISUAL_SUBSTANCE_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v15"
    assert SOURCE_BACKED_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v14"
    assert ART_DIRECTION_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v13"
    assert PRESENTATION_SCALE_FULL_HTML_SYSTEM_PROMPT_VERSION == "full-html-system-prompt.v12"
    assert "agentContext.designQualityRules" in current
    assert "generic source titles such as Slide 9" in current
    assert "body copy must normally render at 28px or larger" in current
    assert "below 110 visible words" in current
    assert "Never paste a miniature reproduction of a source page" in current
    assert "Every large panel must earn its area" in current
    assert "chip collection" in current
    assert "generated_accessibility as support neutrals" in current
    assert "Never use overflow:auto or overflow:scroll" in current
    assert "an SVG viewport is not visual proof by itself" in current
    assert "twelve words and eighty characters or fewer" in current
    assert "white cards floating on bright brand-colour fields" in current
    assert "compute to at least 24px" in current
    assert "median of those body elements on every slide must be at least 28px" in current
    assert "meaningful img or SVG occupies at least 12%" in current
    assert "meaningful img or SVG occupies at least 12%" not in chromium_readability
    assert "compute to at least 24px" in chromium_readability
    assert "compute to at least 24px" not in visual_substance
    assert "an SVG viewport is not visual proof by itself" in visual_substance
    assert "an SVG viewport is not visual proof by itself" not in source_backed
    assert "generated_accessibility as support neutrals" in source_backed
    assert "generated_accessibility as support neutrals" not in art_direction
    assert "Never paste a miniature reproduction of a source page" in art_direction
    assert _system_prompt(PRESENTATION_SCALE_FULL_HTML_SYSTEM_PROMPT_VERSION) == presentation_scale
    assert "below 110 visible words" not in previous
    assert "agentContext.designQualityRules" in previous
    assert "agentContext.designQualityRules" not in historical


def test_symbol_heavy_ocr_debris_is_not_promoted_to_source_evidence() -> None:
    debris = ". ™ iil oe ‘es “3 | a ’ ” cere 4. oe : 5 Sams ep | ' Ff . : ‘“ .. Ad ee Ld ® , . ‘ _ : ’ le - ¥."
    real_copy = "Angel House supports projects that turn into companies through workshops, consultation, and follow-up funding."

    assert _is_probable_ocr_debris(debris) is True
    assert _is_probable_ocr_debris(real_copy) is False


def test_provider_context_omits_compiler_owned_baseline_asset_bytes() -> None:
    context = {
        "approvedAssets": [{
            "assetId": "asset_1",
            "resolvedDataUrl": "data:image/png;base64,QUJD",
        }],
        "visualIntelligence": {
            "rendered_assets": [{
                "id": "rendered-diagram-1",
                "content_sha256": "0" * 64,
                "data_url": "data:image/svg+xml;base64,PHN2Zy8+",
            }],
        },
        "validatedBaseline": {
            "designVersionId": "designver_previous",
            "sanitizedHtml": (
                '<img data-asset-ref="approved:asset_1" '
                'src="data:image/png;base64,QUJD" alt="Evidence">'
            ),
        },
    }

    runtime = build_full_html_provider_runtime_context(context)

    assert "resolvedDataUrl" not in runtime["approvedAssets"][0]
    assert "data_url" not in runtime["visualIntelligence"]["rendered_assets"][0]
    assert runtime["visualIntelligence"]["rendered_assets"][0]["id"] == "rendered-diagram-1"
    assert "data:image/" not in runtime["validatedBaseline"]["sanitizedHtml"]
    assert 'data-asset-ref="approved:asset_1"' in runtime["validatedBaseline"]["sanitizedHtml"]
    assert 'alt="Evidence"' in runtime["validatedBaseline"]["sanitizedHtml"]
    assert "data:image/png;base64,QUJD" in context["validatedBaseline"]["sanitizedHtml"]
    assert context["visualIntelligence"]["rendered_assets"][0]["data_url"].startswith("data:image/svg+xml")


def test_provider_context_exposes_an_exact_canonical_source_id_registry() -> None:
    context = {
        "sourceSlides": [
            {"sourceSlideId": "source_opaque_02"},
            {"sourceSlideId": "source_opaque_09"},
        ],
    }
    runtime = build_full_html_provider_runtime_context(context)
    assert runtime["canonicalSourceIdRegistry"] == ["source_opaque_02", "source_opaque_09"]


def test_retrieval_requests_only_design_knowledge_and_rejects_deck_scoped_rows() -> None:
    observed: dict[str, object] = {}

    def retrieve(_db, **kwargs):
        observed.update(kwargs)
        return {
            "status": "ready",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "traceId": "retrieval_test",
            "chunks": [
                {
                    "id": "design_rule",
                    "chunkType": "instant_deck_knowledge",
                    "sourceKey": "knowledge:instant_deck:v2:design_rule:overflow",
                    "contentText": "Keep every visible element inside the fixed canvas.",
                    "scope": "global_knowledge",
                    "similarityScore": 0.91,
                },
                {
                    "id": "customer_source",
                    "chunkType": "slide_raw_text",
                    "sourceKey": "slide:customer:text",
                    "contentText": "Private customer source text",
                    "scope": "deck",
                    "similarityScore": 0.99,
                },
            ],
        }

    with (
        patch(
            "app.services.llm.deck_chunking_service.sync_deck_vector_chunks",
            return_value={"status": "excluded_by_policy"},
        ),
        patch(
            "app.services.llm.deck_chunking_service.sync_instant_deck_knowledge_chunks",
            return_value={
                "status": "ready",
                "provider": "openai",
                "model": "text-embedding-3-small",
                "embeddedChunkCount": 1,
            },
        ),
        patch("app.services.llm.vector_retrieval_service.retrieve_relevant_chunks", side_effect=retrieve),
        patch(
            "app.ai.instant_deck_knowledge_context.load_instant_deck_knowledge",
            return_value={"name": "instant_deck_knowledge_pack", "version": "v2"},
        ),
    ):
        result = build_bounded_retrieved_guidance(
            object(),
            deck=SimpleNamespace(id="deck_customer"),
            objective="Redesign the deck",
            audience="Investors",
            deck_type="investor_pitch",
        )

    assert observed["chunk_types"] == ["instant_deck_knowledge"]
    assert result["retrievalExecuted"] is True
    assert result["knowledgePackage"] == {
        "name": "instant_deck_knowledge_pack",
        "version": "v2",
    }
    assert result["retrievedItemIds"] == ["design_rule"]
    assert result["chunkCount"] == 1
    assert result["tokenCount"] > 0
    assert result["chunks"][0]["scope"] == "global_knowledge"
    assert "Private customer source text" not in str(result)
