import pytest
from io import BytesIO
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import CoreBase
from app.db.models import Deck, DeckLlmArtifact, User, Workspace
from app.services.visual_intelligence.charts import render_chart_svg
from app.services.visual_intelligence.diagrams import render_diagram_svg
from app.services.visual_intelligence.director import build_visual_intelligence
from app.services.visual_intelligence.models import ChartSpec, DiagramSpec
from app.services.visual_intelligence.persistence import (
    ARTIFACT_TYPE, persist_visual_intelligence, visual_intelligence_status,
)
from app.services.visual_intelligence.assets import render_asset_plan
from app.services.visual_intelligence.models import AssetPlan, ImageBrief
from app.services.rendering.html_deck_compiler import HtmlDeckCompileError, compile_html_deck
from app.services.visual_intelligence.review.deck_review import (
    CONTACT_SHEET_TYPE, RENDERED_SLIDE_TYPE, VISION_REVIEW_TYPE, VISUAL_REPAIR_PLAN_TYPE,
    VISION_REVIEW_ATTEMPT_TYPE, enhance_rendered_deck_review_with_llm,
    persist_rendered_deck_review, vision_review_status,
)
from app.core.config import settings
from app.schemas.instant_deck_context import (
    CanonicalSourceDeck, CanonicalSourceSlide, InstantDeckGenerationContext,
)
from app.services.llm.instant_deck_context_builder import context_to_grounded_pack


def _strategy(role: str = "product") -> dict:
    return {
        "narrativeStrategy": {"thesis": "A workflow becomes an investable system."},
        "deckArchitecture": [{
            "id": "slide-1", "role": role, "title": "The operating layer",
            "purpose": "Explain the product system", "evidenceRefs": ["fact-1"],
            "calculationIds": ["calc-1"],
        }],
    }


def test_visual_director_is_sector_neutral_and_preserves_lineage():
    saas = build_visual_intelligence(
        vc_strategy=_strategy(), brand={"companyName": "Generic SaaS"},
        approved_assets=[{"assetId": "asset-1"}], input_artifact_ids=["vc-strategy:op"],
    )
    biotech = build_visual_intelligence(
        vc_strategy=_strategy(), brand={"companyName": "Generic Biotech"},
        approved_assets=[], input_artifact_ids=["vc-strategy:op"],
    )
    assert saas.slide_visual_briefs[0].visual_primitive == "product_ui"
    assert biotech.slide_visual_briefs[0].visual_primitive == "product_ui"
    assert saas.slide_visual_briefs[0].evidence_ids == ["fact-1"]
    assert saas.slide_visual_briefs[0].calculation_ids == ["calc-1"]
    assert saas.asset_plan.generated_images_are_evidence is False
    assert saas.publication_blocking is False


def test_visual_director_honors_the_llm_authored_primitive_and_intent():
    strategy = {
        "narrativeStrategy": {"thesis": "A workflow becomes an investable system."},
        "typedDeckArchitecture": {"slides": [{
            "id": "slide-1",
            "index": 1,
            "role": "product_wedge",
            "objective": "Explain the integrated system",
            "headline_direction": "One operating layer",
            "evidence_ids": ["fact-1"],
            "calculation_ids": [],
            "visual_primitive": "platform_architecture",
            "visual_intent": "Reveal the connected lifecycle as one coherent system.",
        }]},
    }
    bundle = build_visual_intelligence(
        vc_strategy=strategy, brand={}, approved_assets=[], input_artifact_ids=["vc-strategy:op"],
    )
    brief = bundle.slide_visual_briefs[0]
    assert brief.visual_primitive == "platform_architecture"
    assert brief.composition_strategy == "Reveal the connected lifecycle as one coherent system."


def test_visual_director_uses_versioned_investor_composition_knowledge():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy("financial"), brand={"companyName": "Company"}, approved_assets=[],
        metrics=[{
            "metric": "ARR", "category": "2025", "period": "2025", "value": 5,
            "unit": "USDm", "status": "actual", "evidenceRefs": ["fact-1"],
        }],
    )
    brief = bundle.slide_visual_briefs[0]
    assert bundle.knowledge_version == "investor-visual-design.2026-09-22.v2"
    assert brief.visual_primitive == "financial_bridge"
    assert "actuals, assumptions, and projections" in brief.composition_strategy


def test_visual_contract_is_separate_from_factual_evidence_lanes():
    bundle = build_visual_intelligence(
        vc_strategy=_strategy(), brand={}, approved_assets=[], input_artifact_ids=["vc-strategy:op"],
    )
    context = InstantDeckGenerationContext(
        deck_id="deck", source_deck=CanonicalSourceDeck(slides=[CanonicalSourceSlide(
            id="source-1", index=0, slide_number=1, title="Product", raw_text="Supported source.",
        )]),
        vc_strategy=_strategy(), visual_intelligence=bundle.model_dump(mode="json"),
    )
    pack = context_to_grounded_pack(context)
    assert pack["visualIntelligence"]["schema_version"] == "visual-intelligence.v1"
    assert "visualIntelligence" not in pack["evidenceLanes"]
    assert pack["evidenceLanes"]["vcInference"] == _strategy()


def test_chart_specs_require_calculation_lineage_and_aligned_finite_values():
    with pytest.raises(ValidationError):
        ChartSpec(id="bad", chart_type="bar", title="Bad", categories=["A", "B"], series=[{
            "label": "Series", "values": [1.0], "calculation_ids": ["calc-1"],
        }])
    with pytest.raises(ValidationError):
        ChartSpec(id="bad", chart_type="line", title="Bad", categories=["A"], series=[{
            "label": "Series", "values": [float("inf")], "calculation_ids": ["calc-1"],
        }])


def test_chart_and_diagram_renderers_are_deterministic_and_escape_labels():
    chart = ChartSpec(id="chart", chart_type="bar", title="Growth <proof>", categories=["2025", "2026"], series=[{
        "label": "Revenue", "values": [1.0, 2.0], "calculation_ids": ["c1", "c2"],
    }])
    first = render_chart_svg(chart)
    assert first == render_chart_svg(chart)
    assert "Growth &lt;proof&gt;" in first
    diagram = DiagramSpec(id="flow", diagram_type="workflow", title="Lifecycle", nodes=[
        {"id": "a", "label": "Acquire <lead>"}, {"id": "b", "label": "Retain"},
    ], edges=[{"source": "a", "target": "b"}])
    rendered = render_diagram_svg(diagram)
    assert rendered == render_diagram_svg(diagram)
    assert "Acquire &lt;lead&gt;" in rendered

    assets = render_asset_plan(AssetPlan(charts=[chart], diagrams=[diagram]))
    assert [asset.asset_type for asset in assets] == ["chart_svg", "diagram_svg"]
    assert all(asset.data_url.startswith("data:image/svg+xml;base64,") for asset in assets)
    assert assets[0].calculation_ids == ["c1", "c2"]


def test_compiler_resolves_only_digest_bound_application_visual_assets():
    diagram = DiagramSpec(
        id="lifecycle", diagram_type="workflow", title="Client lifecycle",
        nodes=[{"id": "a", "label": "Acquire"}, {"id": "b", "label": "Retain"}],
        edges=[{"source": "a", "target": "b"}], evidence_ids=["fact-1"],
    )
    asset = render_asset_plan(AssetPlan(diagrams=[diagram]))[0]
    html = """<html><head><title>Deck</title></head><body><main>
    <section class="deck-section" data-source-slide-ids="source-1">
    <h1 data-source-refs="fact-1">Client lifecycle</h1>
    <figure data-visual-asset-ref="rendered-diagram-lifecycle"></figure>
    </section></main></body></html>"""
    kwargs = {
        "selected_source_slide_ids": ["source-1"],
        "grounded_fact_ids": ["fact-1"],
        "grounded_fact_texts": {"fact-1": "Client lifecycle"},
        "grounded_fact_sources": {"fact-1": ["source-1"]},
        "grounded_fact_traceability": {
            "fact-1": {"sourceType": "source_slide", "sourceSlideIds": ["source-1"]},
        },
        "rendered_visual_assets": {
            asset.id: {
                "data_url": asset.data_url,
                "content_sha256": asset.content_sha256,
                "evidence_ids": asset.evidence_ids,
            },
        },
    }
    compiled = compile_html_deck(html, **kwargs)
    assert "<svg" in compiled.sanitized_html
    assert "Acquire" in compiled.sanitized_html
    assert compiled.manifest["renderedVisualAssetIds"] == [asset.id]
    assert asset.data_url not in compiled.sanitized_html

    tampered = dict(kwargs["rendered_visual_assets"][asset.id])
    tampered["content_sha256"] = "0" * 64
    with pytest.raises(HtmlDeckCompileError, match="durable digest"):
        compile_html_deck(html, **{**kwargs, "rendered_visual_assets": {asset.id: tampered}})


def test_diagram_rejects_dangling_edges():
    with pytest.raises(ValidationError):
        DiagramSpec(id="bad", diagram_type="workflow", title="Bad", nodes=[
            {"id": "a", "label": "A"}, {"id": "b", "label": "B"},
        ], edges=[{"source": "a", "target": "missing"}])


def test_generated_image_brief_cannot_claim_source_evidence():
    with pytest.raises(ValidationError):
        ImageBrief(
            id="image", slide_id="slide", purpose="Explain the concept", source="generated",
            factual_role="source_evidence",
        )


def test_visual_intelligence_is_a_durable_internal_non_blocking_artifact():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(id="user", email="owner@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="workspace", name="Workspace", user_id=user.id)
        deck = Deck(
            id="deck", workspace_id=workspace.id, user_id=user.id, title="Deck",
            audience="Investors", purpose="Fundraising", status="ready",
        )
        session.add_all([user, workspace, deck])
        session.commit()
        bundle = build_visual_intelligence(
            vc_strategy=_strategy(), brand={}, approved_assets=[], input_artifact_ids=["vc-strategy:op"],
        )
        persist_visual_intelligence(session, deck_id=deck.id, operation_id="op", bundle=bundle)
        session.commit()
        payload = visual_intelligence_status(session, deck.id)
        assert payload is not None
        assert payload["internalProductOnly"] is True
        assert payload["publicationBlocking"] is False
        row = session.query(DeckLlmArtifact).filter_by(artifact_type=ARTIFACT_TYPE).one()
        assert row.metrics_json["providerStarts"] == 0
        assert row.metrics_json["publicationBlocking"] is False
        assert row.metrics_json["selectedKnowledgeModules"]
        assert deck.status == "ready"
    finally:
        session.close()
        engine.dispose()


def test_rendered_pixels_contact_sheet_and_review_are_durable_and_advisory(tmp_path, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    previous_root = settings.uploads_root
    monkeypatch.setattr(settings, "uploads_root", str(tmp_path))
    try:
        user = User(id="visual-user", email="visual@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="visual-workspace", name="Workspace", user_id=user.id)
        deck = Deck(
            id="visual-deck", workspace_id=workspace.id, user_id=user.id, title="Deck",
            audience="Investors", purpose="Fundraising", status="ready",
        )
        session.add_all([user, workspace, deck])
        session.commit()
        output = BytesIO()
        Image.new("RGB", (1920, 1080), (14, 20, 36)).save(output, format="PNG")
        payload = persist_rendered_deck_review(
            session, deck_id=deck.id, operation_id="visual-op",
            rendered_slides=[{"slideId": "slide-1", "screenshot": output.getvalue(), "metrics": {}}],
        )
        session.commit()
        assert payload is not None and payload["publication_blocking"] is False
        assert vision_review_status(session, deck.id)["publicationBlocking"] is False
        rows = session.query(DeckLlmArtifact).all()
        assert {row.artifact_type for row in rows} == {
            RENDERED_SLIDE_TYPE, CONTACT_SHEET_TYPE, VISION_REVIEW_TYPE, VISUAL_REPAIR_PLAN_TYPE,
        }
        assert all(row.metrics_json["publicationBlocking"] is False for row in rows)
        persist_rendered_deck_review(
            session, deck_id=deck.id, operation_id="visual-op",
            rendered_slides=[{"slideId": "slide-1", "screenshot": output.getvalue(), "metrics": {}}],
        )
        session.commit()
        assert session.query(DeckLlmArtifact).count() == 4
    finally:
        monkeypatch.setattr(settings, "uploads_root", previous_root)
        session.close()
        engine.dispose()


def test_llm_investor_handoff_review_is_internal_advice_and_updates_repair_plan(tmp_path, monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CoreBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(settings, "uploads_root", str(tmp_path))
    monkeypatch.setattr(settings, "ai_vc_vision_review_max_cost_cents", 100)
    monkeypatch.setattr(settings, "ai_vc_vision_review_enabled", True)
    monkeypatch.setattr(
        "app.services.llm.generation_service.get_generation_provider_config",
        lambda *_args, **_kwargs: {
            "provider": "openai", "model": settings.openai_model, "apiKey": "test-key",
        },
    )
    review_payload = {
        "strengths": ["The thesis is immediately legible."],
        "findings": [{
            "slide_id": "slide-1",
            "issue": "The financial proof deserves stronger hierarchy.",
            "severity": "important",
            "dimension": "hierarchy",
        }],
        "recommended_changes": ["Promote the strongest verified metric."],
        "handoff_assessment": "Credible investor handoff with one important proof hierarchy improvement.",
        "overall_score": 86,
        "narrative_score": 90,
        "financial_credibility_score": 82,
        "investor_clarity_score": 88,
        "visual_quality_score": 84,
        "brand_consistency_score": 91,
        "publication_blocking": False,
    }
    monkeypatch.setattr(
        "app.services.llm.openai_provider.call_openai_response",
        lambda **_kwargs: {"usage": {"input_tokens": 100, "output_tokens": 100}},
    )
    monkeypatch.setattr(
        "app.services.llm.openai_provider.parse_openai_structured_response",
        lambda _response: __import__("json").dumps(review_payload),
    )
    monkeypatch.setattr(
        "app.services.llm.instant_html_operation_service.estimate_model_cost_cents",
        lambda *_args, **_kwargs: 1,
    )
    try:
        user = User(id="review-user", email="review@example.test", name="Owner", password_hash="unused")
        workspace = Workspace(id="review-workspace", name="Workspace", user_id=user.id)
        deck = Deck(
            id="review-deck", workspace_id=workspace.id, user_id=user.id, title="Deck",
            audience="Investors", purpose="Fundraising", status="ready",
        )
        session.add_all([user, workspace, deck])
        session.commit()
        output = BytesIO()
        Image.new("RGB", (1920, 1080), (14, 20, 36)).save(output, format="PNG")
        rendered = [{"slideId": "slide-1", "screenshot": output.getvalue(), "metrics": {}}]
        persist_rendered_deck_review(
            session, deck_id=deck.id, operation_id="review-op", rendered_slides=rendered,
        )
        session.commit()

        result = enhance_rendered_deck_review_with_llm(
            session, deck_id=deck.id, operation_id="review-op", rendered_slides=rendered,
        )

        assert result["review_source"] == "llm_assisted"
        assert result["overall_score"] == 86
        assert result["publication_blocking"] is False
        status = vision_review_status(session, deck.id)
        assert status["internalProductOnly"] is True
        assert status["publicationBlocking"] is False
        assert status["recommended_changes"] == ["Promote the strongest verified metric."]
        attempt = session.query(DeckLlmArtifact).filter_by(
            artifact_type=VISION_REVIEW_ATTEMPT_TYPE,
        ).one()
        assert attempt.status == "ready"
        repair = session.query(DeckLlmArtifact).filter_by(
            artifact_type=VISUAL_REPAIR_PLAN_TYPE,
        ).one()
        assert repair.payload_json["instructions"][0]["repair_type"] == "hierarchy"

        repeated = persist_rendered_deck_review(
            session, deck_id=deck.id, operation_id="review-op", rendered_slides=rendered,
        )
        assert repeated["review_source"] == "llm_assisted"
        assert repeated["overall_score"] == 86
        preserved = session.query(DeckLlmArtifact).filter_by(
            artifact_type=VISION_REVIEW_TYPE,
        ).one()
        assert preserved.payload_json["review_source"] == "llm_assisted"
    finally:
        session.close()
        engine.dispose()
