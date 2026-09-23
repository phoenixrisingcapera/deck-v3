from pydantic import TypeAdapter

from app.schemas.deck_workflow import WorkflowPhase, WorkflowPublishedPhase
from app.workers.runtime.generation_runtime import handle_instant_deck_generation


def test_every_published_ai_vc_phase_is_a_valid_workflow_phase() -> None:
    workflow_phase = TypeAdapter(WorkflowPhase)
    published_phase = TypeAdapter(WorkflowPublishedPhase)

    for value in (
        "ai_vc_understanding",
        "ai_vc_research",
        "ai_vc_analysis",
        "narrative_reconstruction",
        "visual_direction",
        "visual_asset_planning",
    ):
        assert published_phase.validate_python(value) == value
        assert workflow_phase.validate_python(value) == value


def test_mounted_worker_uses_model_plan_before_public_research() -> None:
    """Protect the production mount, not only isolated planning helpers."""
    import inspect

    mounted_source = inspect.getsource(handle_instant_deck_generation)
    planning = mounted_source.index("ensure_model_research_plan(")
    research = mounted_source.index("ensure_generation_public_research(")
    strategy = mounted_source.index("ensure_vc_strategy(")

    assert planning < research < strategy
    assert "resolve_model_skill_plan(model_research_plan)" in mounted_source
    assert "build_universal_research_plan(" not in mounted_source
    assert "build_research_questions(" not in mounted_source
    assert "resolve_skill_plan(" not in mounted_source
