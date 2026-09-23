import pytest

from app.services.rendering.html_deck_compiler import (
    BANDED_BODY_COMPILER_VERSION,
    COMPILER_VERSION,
    DENSE_METRICS_COMPILER_VERSION,
    EDITORIAL_DENSITY_COMPILER_VERSION,
    HtmlDeckCompileError,
    compile_html_deck,
)


SAFE_DECK = """<!doctype html>
<html><head><title>Test deck</title>
<style>:root{--color-ink:#111827}.deck-section{width:1920px;height:1080px}</style>
</head><body><main>
<section class="deck-section" data-source-slide-ids="source_1" data-layout-intent="hero">
  <h1>Problem</h1><p>Overview</p>
</section>
</main></body></html>"""


def test_same_payload_compiles_to_same_ordered_presentation() -> None:
    first = compile_html_deck(
        SAFE_DECK,
        selected_source_slide_ids=["source_1"],
        persistence_identity_scope="operation_1",
    )
    second = compile_html_deck(
        SAFE_DECK,
        selected_source_slide_ids=["source_1"],
        persistence_identity_scope="operation_1",
    )

    assert first.compilation_hash == second.compilation_hash
    assert first.sanitized_sha256 == second.sanitized_sha256
    assert first.safe_slide_documents == second.safe_slide_documents
    assert "<title>Problem</title>" in first.safe_slide_documents[0]
    assert "body{background:#fff;color:#000}" in first.safe_slide_documents[0]
    assert [slide["ordinal"] for slide in first.manifest["slides"]] == [1]
    assert first.manifest["slides"][0]["sourceSlideIds"] == ["source_1"]
    assert first.manifest["coverageComplete"] is True


def test_ai_vc_visual_brief_is_a_required_ordered_compiler_contract() -> None:
    planned = SAFE_DECK.replace(
        'data-layout-intent="hero"',
        'data-layout-intent="hero" data-plan-slide-id="thesis" '
        'data-visual-primitive="hero" data-evidence-ids="fact-1" '
        'data-calculation-ids="calc-1"',
    )
    brief = {
        "slide_id": "thesis",
        "visual_primitive": "hero",
        "evidence_ids": ["fact-1"],
        "calculation_ids": ["calc-1"],
    }

    compiled = compile_html_deck(
        planned,
        selected_source_slide_ids=["source_1"],
        visual_slide_briefs=[brief],
    )

    assert compiled.manifest["slides"][0]["planSlideId"] == "thesis"
    assert compiled.manifest["slides"][0]["visualPrimitive"] == "hero"
    assert compiled.manifest["slides"][0]["plannedEvidenceIds"] == ["fact-1"]
    assert compiled.manifest["slides"][0]["plannedCalculationIds"] == ["calc-1"]

    for invalid in (
        planned.replace('data-plan-slide-id="thesis"', 'data-plan-slide-id="source-slide-1"'),
        planned.replace('data-visual-primitive="hero"', 'data-visual-primitive="text"'),
        planned.replace('data-evidence-ids="fact-1"', 'data-evidence-ids=""'),
        planned.replace('data-calculation-ids="calc-1"', 'data-calculation-ids="calc-2"'),
    ):
        with pytest.raises(HtmlDeckCompileError) as raised:
            compile_html_deck(
                invalid,
                selected_source_slide_ids=["source_1"],
                visual_slide_briefs=[brief],
            )
        assert raised.value.code == "visual_plan_binding_invalid"

    # A factual-review advisory draft preserves the renderable design and
    # records plan drift internally. Plan metadata is not factual evidence and
    # must not turn a safe, exportable deck into a terminal failure.
    advisory = compile_html_deck(
        planned.replace('data-visual-primitive="hero"', 'data-visual-primitive="text"'),
        selected_source_slide_ids=["source_1"],
        visual_slide_briefs=[brief],
        advisory_review=True,
    )
    assert advisory.manifest["evidencePolicy"] == "advisory-draft.v1"
    assert advisory.manifest["draftVisualPlanWarnings"] == [{
        "severity": "warning",
        "category": "structure",
        "code": "visual_plan_binding_invalid",
        "message": "Generated slide 1 differs from its AI-VC visual brief; the rendered design remains available and the mismatch is retained for internal review.",
        "blocking": False,
        "sectionOrdinal": 1,
        "planSlideId": "thesis",
    }]


def test_duplicate_planning_ids_normalize_and_do_not_fail_compilation() -> None:
    planned = SAFE_DECK.replace(
        'data-layout-intent="hero"',
        'data-layout-intent="hero" data-plan-slide-id="thesis" '
        'data-visual-primitive="hero" data-evidence-ids="fact-1 fact-2 fact-1" '
        'data-calculation-ids="calc-1 calc-1"',
    )
    brief = {
        "slide_id": "thesis",
        "visual_primitive": "hero",
        "evidence_ids": ["fact-1", "fact-2"],
        "calculation_ids": ["calc-1"],
    }

    compiled = compile_html_deck(
        planned,
        selected_source_slide_ids=["source_1"],
        visual_slide_briefs=[brief],
    )

    assert compiled.manifest["slides"][0]["plannedEvidenceIds"] == ["fact-1", "fact-2"]
    assert compiled.manifest["slides"][0]["plannedCalculationIds"] == ["calc-1"]

    advisory = compile_html_deck(
        planned,
        selected_source_slide_ids=["source_1"],
        visual_slide_briefs=[brief],
        advisory_review=True,
    )
    assert advisory.manifest["evidencePolicy"] == "advisory-draft.v1"
    assert advisory.manifest["slides"][0]["plannedEvidenceIds"] == ["fact-1", "fact-2"]
    assert advisory.manifest["slides"][0]["plannedCalculationIds"] == ["calc-1"]


def test_unsafe_runtime_markup_is_removed_before_compilation() -> None:
    unsafe = SAFE_DECK.replace("<h1>Problem</h1>", "<script>alert(1)</script><h1 onclick=\"alert(2)\">Problem</h1>")
    compiled = compile_html_deck(
        unsafe,
        selected_source_slide_ids=["source_1"],
        persistence_identity_scope="operation_unsafe",
    )

    assert "<script" not in compiled.sanitized_html
    assert "onclick" not in compiled.sanitized_html
    assert all("<script" not in slide for slide in compiled.safe_slide_documents)


def test_duplicate_source_identity_is_rejected() -> None:
    with pytest.raises(HtmlDeckCompileError) as raised:
        compile_html_deck(
            SAFE_DECK,
            selected_source_slide_ids=["source_1", "source_1"],
            persistence_identity_scope="operation_duplicate",
        )
    assert raised.value.code == "selected_source_ids_invalid"


def test_unknown_fact_id_is_repaired_only_for_one_exact_lineage_match() -> None:
    provider_html = SAFE_DECK.replace(
        "<h1>Problem</h1><p>Overview</p>",
        '<h1>Problem</h1><p data-source-refs="fact_1">NexaFlow automates finance operations.</p>',
    )
    compiled = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        grounded_fact_ids=["fact_canonical"],
        grounded_fact_catalog=[{
            "factId": "fact_canonical",
            "text": "NexaFlow automates finance operations.",
            "sourceSlideIds": ["source_1"],
        }],
        grounded_fact_sources={"fact_canonical": ["source_1"]},
        grounded_fact_traceability={
            "fact_canonical": {"sourceType": "source_slide", "sourceSlideIds": ["source_1"]},
        },
        persistence_identity_scope="operation_exact_repair",
    )

    assert 'data-source-refs="fact_canonical"' in compiled.sanitized_html
    assert 'data-da-binding-method="unknown_id_exact_repair"' in compiled.sanitized_html
    assert compiled.manifest["sourceCoverage"]["evidenceBackedSourceSlideIds"] == ["source_1"]


def test_unknown_fact_id_with_non_exact_claim_stays_rejected() -> None:
    provider_html = SAFE_DECK.replace(
        "<h1>Problem</h1><p>Overview</p>",
        '<h1>Problem</h1><p data-source-refs="fact_1">NexaFlow transforms every finance team.</p>',
    )
    with pytest.raises(HtmlDeckCompileError) as raised:
        compile_html_deck(
            provider_html,
            selected_source_slide_ids=["source_1"],
            grounded_fact_ids=["fact_canonical"],
            grounded_fact_catalog=[{
                "factId": "fact_canonical",
                "text": "NexaFlow automates finance operations.",
                "sourceSlideIds": ["source_1"],
            }],
            grounded_fact_sources={"fact_canonical": ["source_1"]},
            grounded_fact_traceability={
                "fact_canonical": {"sourceType": "source_slide", "sourceSlideIds": ["source_1"]},
            },
            persistence_identity_scope="operation_unknown_rejected",
        )

    assert raised.value.code == "grounded_fact_unknown"


def test_current_compiler_blocks_semantic_numeric_substitution_with_valid_fact_id() -> None:
    canonical = "Customers: 2023 = 16; 2024 = 28; 2025 = 48."
    kwargs = dict(
        selected_source_slide_ids=["source_1"],
        grounded_fact_ids=["fact_customers"],
        grounded_fact_texts={"fact_customers": canonical},
        grounded_fact_catalog=[{
            "factId": "fact_customers", "text": canonical,
            "sourceSlideIds": ["source_1"],
        }],
        grounded_fact_sources={"fact_customers": ["source_1"]},
        grounded_fact_traceability={
            "fact_customers": {"sourceType": "source_slide", "sourceId": "source_1", "sourceSlideIds": ["source_1"]},
        },
    )
    correct = SAFE_DECK.replace(
        "<h1>Problem</h1><p>Overview</p>",
        '<h1>Problem</h1><p data-source-refs="fact_customers">2023 customers: 16</p>',
    )
    assert "2023 customers: 16" in compile_html_deck(correct, **kwargs).sanitized_html

    substituted = correct.replace("2023 customers: 16", "2023 customers: 48")
    with pytest.raises(HtmlDeckCompileError) as raised:
        compile_html_deck(substituted, **kwargs)
    assert raised.value.code == "grounded_numeric_period_mismatch"


def test_current_compiler_blocks_cross_slide_numeric_contradictions() -> None:
    facts = [
        {"factId":"fact_a", "text":"2025 customers: 48 actual", "sourceSlideIds":["source_1"]},
        {"factId":"fact_b", "text":"2025 customers: 52 actual", "sourceSlideIds":["source_1"]},
    ]
    html = SAFE_DECK.replace(
        '<h1>Problem</h1><p>Overview</p>',
        '<h1>Traction</h1><p data-source-refs="fact_a">2025 customers: 48 actual</p>',
    ).replace(
        '</main>',
        '<section class="deck-section" data-source-slide-ids="source_1" data-layout-intent="metrics">'
        '<h1>Overview</h1><p data-source-refs="fact_b">2025 customers: 52 actual</p>'
        '</section></main>',
    )
    with pytest.raises(HtmlDeckCompileError) as raised:
        compile_html_deck(
            html, selected_source_slide_ids=["source_1"],
            grounded_fact_ids=["fact_a", "fact_b"],
            grounded_fact_catalog=facts,
            grounded_fact_sources={"fact_a":["source_1"], "fact_b":["source_1"]},
            grounded_fact_traceability={
                fact["factId"]:{"sourceType":"source_slide", "sourceSlideIds":["source_1"]}
                for fact in facts
            },
        )
    assert raised.value.code == "cross_slide_numeric_contradiction"


def test_unknown_heading_id_repairs_unique_exact_catalog_prefix() -> None:
    provider_html = SAFE_DECK.replace(
        "<h1>Problem</h1><p>Overview</p>",
        '<h2 data-source-refs="fact_wrong">Built by operators who understand AI workflows</h2>',
    )
    compiled = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        grounded_fact_ids=["fact_canonical"],
        grounded_fact_catalog=[{
            "factId": "fact_canonical",
            "text": "Built by operators who understand AI workflows Synthetic team slide for testing people and roles.",
            "sourceSlideIds": ["source_1"],
        }],
        grounded_fact_sources={"fact_canonical": ["source_1"]},
        grounded_fact_traceability={
            "fact_canonical": {"sourceType": "source_slide", "sourceSlideIds": ["source_1"]},
        },
        persistence_identity_scope="operation_heading_prefix_repair",
    )

    assert 'data-source-refs="fact_canonical"' in compiled.sanitized_html
    assert 'data-da-binding-method="unknown_id_heading_prefix_repair"' in compiled.sanitized_html


def test_unknown_non_heading_prefix_stays_rejected() -> None:
    provider_html = SAFE_DECK.replace(
        "<h1>Problem</h1><p>Overview</p>",
        '<p data-source-refs="fact_wrong">Built by operators who understand AI workflows</p>',
    )
    with pytest.raises(HtmlDeckCompileError) as raised:
        compile_html_deck(
            provider_html,
            selected_source_slide_ids=["source_1"],
            grounded_fact_ids=["fact_canonical"],
            grounded_fact_catalog=[{
                "factId": "fact_canonical",
                "text": "Built by operators who understand AI workflows Synthetic team slide for testing people and roles.",
                "sourceSlideIds": ["source_1"],
            }],
            grounded_fact_sources={"fact_canonical": ["source_1"]},
            grounded_fact_traceability={
                "fact_canonical": {"sourceType": "source_slide", "sourceSlideIds": ["source_1"]},
            },
            persistence_identity_scope="operation_paragraph_prefix_rejected",
        )

    assert raised.value.code == "grounded_fact_unknown"


def test_current_compiler_does_not_force_dark_fallback_text_into_bands() -> None:
    provider_html = SAFE_DECK.replace(
        "<h1>Problem</h1><p>Overview</p>",
        '<div class="band"><p>Overview</p></div>',
    ).replace(
        "</style>",
        ".band{background:#111c32;color:#e6eef8}</style>",
    )
    current = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        compiler_version=COMPILER_VERSION,
    )
    historical = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        compiler_version=BANDED_BODY_COMPILER_VERSION,
    )

    assert "color-body,#0f172a" not in current.sanitized_html
    assert "color-body,#0f172a" in historical.sanitized_html


def test_current_compiler_does_not_shrink_metric_layouts_and_preserves_v17_replay() -> None:
    provider_html = SAFE_DECK.replace(
        'data-layout-intent="hero"',
        'data-layout-intent="asymmetric-metrics"',
    ).replace(
        '<h1>Problem</h1><p>Overview</p>',
        '<div class="section-inner layout-metrics"><div class="metric">'
        '<img alt="Source preview" src="data:image/png;base64,AA==">'
        '</div></div>',
    )

    current = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        compiler_version=COMPILER_VERSION,
    )
    replay_v17 = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        compiler_version=DENSE_METRICS_COMPILER_VERSION,
    )

    assert "height:clamp(120px,18vh,190px);object-fit:contain" not in current.sanitized_html
    assert "font-size:clamp(13px,1.1vw,16px)" not in current.sanitized_html
    assert "height:clamp(120px,18vh,190px);object-fit:contain" in replay_v17.sanitized_html
    assert "font-size:clamp(13px,1.1vw,16px)" in replay_v17.sanitized_html


def test_current_compiler_does_not_shrink_editorial_layouts_and_preserves_v18_replay() -> None:
    provider_html = SAFE_DECK.replace(
        'data-layout-intent="hero"',
        'data-layout-intent="evidence-wall"',
    ).replace(
        '<h1>Problem</h1><p>Overview</p>',
        '<div class="section-inner"><ul class="wall"><li>Overview</li></ul></div>',
    )

    current = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        compiler_version=COMPILER_VERSION,
    )
    replay_v18 = compile_html_deck(
        provider_html,
        selected_source_slide_ids=["source_1"],
        compiler_version=EDITORIAL_DENSITY_COMPILER_VERSION,
    )

    assert "grid-template-columns:repeat(6,minmax(0,1fr))!important" not in current.sanitized_html
    assert "font-size:clamp(11px,.72vw,14px)!important" not in current.sanitized_html
    assert "grid-template-columns:repeat(6,minmax(0,1fr))!important" in replay_v18.sanitized_html
    assert "font-size:clamp(11px,.72vw,14px)!important" in replay_v18.sanitized_html


def test_full_source_block_digest_restores_only_request_owned_section_identity() -> None:
    from app.services.rendering.html_deck_compiler import SVG_STYLES_COMPILER_VERSION

    digests = ["a" * 64, "b" * 64]
    facts = ["fact_source_block_" + digest for digest in digests]
    html = SAFE_DECK.replace(
        "<p>Overview</p>",
        '<table><tr><td data-source-refs="' + " ".join(digests) + '">200 families</td></tr></table>',
    )
    kwargs = dict(
        selected_source_slide_ids=["source_1"], grounded_fact_ids=facts,
        grounded_fact_texts={facts[0]: "Community includes 200 families", facts[1]: "Families participate in workshops"},
        grounded_fact_sources={fact: ["source_1"] for fact in facts},
        persistence_identity_scope="digest-prefix-regression",
    )
    with pytest.raises(HtmlDeckCompileError, match="unknown grounded fact"):
        compile_html_deck(html, compiler_version=SVG_STYLES_COMPILER_VERSION, **kwargs)
    compiled = compile_html_deck(html, **kwargs)
    assert 'data-source-refs="' + " ".join(facts) + '"' in compiled.sanitized_html
    cell = next(e for e in compiled.manifest["slides"][0]["elements"] if e["tagName"] == "td")
    assert cell["sourceFactIds"] == facts
    assert cell["bindingMethod"] == "source_block_digest_prefix_repair"
    assert compile_html_deck(html, **kwargs).compilation_hash == compiled.compilation_hash
    for bad in ("c" * 64, "a" * 63):
        with pytest.raises(HtmlDeckCompileError, match="unknown grounded fact"):
            compile_html_deck(html.replace(digests[0], bad), **kwargs)
    cross_section = {**kwargs, "selected_source_slide_ids": ["source_1", "source_2"],
                     "grounded_fact_sources": {facts[0]: ["source_2"], facts[1]: ["source_1"]}}
    with pytest.raises(HtmlDeckCompileError, match="unknown grounded fact"):
        compile_html_deck(html, **cross_section)
