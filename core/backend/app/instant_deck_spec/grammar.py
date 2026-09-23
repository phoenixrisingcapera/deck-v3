"""Explicit structural grammar for the offline composition compiler.

The schema names eight archetypes in this slice. ``process_pathway`` and
``timeline_milestones`` form one pathway family with deliberately different
spatial grammars, yielding seven composition families overall.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import CompositionVariant, SlideArchetype, VisualType


@dataclass(frozen=True, slots=True)
class PrimitiveGrammar:
    family: str
    narrative_purpose: str
    required_content: tuple[str, ...]
    optional_content: tuple[str, ...]
    dominant_visual_element: str
    permitted_density: tuple[str, ...]
    typography_hierarchy: tuple[str, ...]
    variants: tuple[CompositionVariant, ...]
    prohibited_when: str
    visual_types: tuple[VisualType, ...]
    text_budget: int


STRUCTURAL_GRAMMARS: dict[SlideArchetype, PrimitiveGrammar] = {
    SlideArchetype.THESIS_COVER: PrimitiveGrammar(
        family="thesis",
        narrative_purpose="Establish one deck-level thesis and art-direction promise.",
        required_content=("headline", "source-backed thesis evidence"),
        optional_content=("subhead", "one concise support line"),
        dominant_visual_element="A thesis-bearing relationship between home, community and action.",
        permitted_density=("sparse",),
        typography_hierarchy=("display", "subhead", "body"),
        variants=(CompositionVariant.LEFT_FOCAL, CompositionVariant.RIGHT_FOCAL, CompositionVariant.CENTERED_MONUMENT),
        prohibited_when="The slide needs multiple claims, a process, or detailed proof.",
        visual_types=(VisualType.TYPOGRAPHIC, VisualType.IMAGE),
        text_budget=240,
    ),
    SlideArchetype.PROBLEM_LANDSCAPE: PrimitiveGrammar(
        family="problem_landscape",
        narrative_purpose="Make a fragmented present state legible as one causal problem system.",
        required_content=("headline", "three to six evidenced visual items"),
        optional_content=("subhead", "one consequence line"),
        dominant_visual_element="A tension field or converging fracture, never equal cards.",
        permitted_density=("balanced", "dense"),
        typography_hierarchy=("headline", "item-label", "item-detail"),
        variants=(CompositionVariant.FIELD, CompositionVariant.DIAGONAL_FLOW),
        prohibited_when="The items are independent features or no causal tension is evidenced.",
        visual_types=(VisualType.COMPARISON, VisualType.SYSTEM_MAP),
        text_budget=560,
    ),
    SlideArchetype.KEY_INSIGHT: PrimitiveGrammar(
        family="key_insight",
        narrative_purpose="Land one decisive conclusion and visibly attach its supporting evidence.",
        required_content=("dominant assertion", "two to four evidenced proof items"),
        optional_content=("subhead", "one qualification"),
        dominant_visual_element="An assertion monument crossed by an evidence spine or lens.",
        permitted_density=("sparse", "balanced"),
        typography_hierarchy=("display-assertion", "proof-label", "proof-detail"),
        variants=(CompositionVariant.CENTERED_MONUMENT, CompositionVariant.EDGE_TO_EDGE),
        prohibited_when="Several conclusions have equal weight or the evidence is only a quotation.",
        visual_types=(VisualType.PROOF_STRIP, VisualType.COMPARISON),
        text_budget=420,
    ),
    SlideArchetype.PROCESS_PATHWAY: PrimitiveGrammar(
        family="pathway",
        narrative_purpose="Show the operating transformation and the output of each step.",
        required_content=("headline", "three to seven ordered steps"),
        optional_content=("subhead", "one process qualification"),
        dominant_visual_element="A directional transformation ribbon with differentiated stages.",
        permitted_density=("balanced", "dense"),
        typography_hierarchy=("headline", "step-number", "step-label", "step-detail"),
        variants=(CompositionVariant.DIAGONAL_FLOW, CompositionVariant.STACKED),
        prohibited_when="Calendar time matters more than transformation or order is not evidenced.",
        visual_types=(VisualType.PROCESS,),
        text_budget=620,
    ),
    SlideArchetype.TIMELINE_MILESTONES: PrimitiveGrammar(
        family="pathway",
        narrative_purpose="Show distinct phases or milestones across an explicit progression.",
        required_content=("headline", "three to seven ordered milestones"),
        optional_content=("subhead", "milestone detail"),
        dominant_visual_element="A time-specific vertical cadence or chapter strip, not a process ribbon.",
        permitted_density=("balanced",),
        typography_hierarchy=("headline", "phase-marker", "milestone-label", "milestone-detail"),
        variants=(CompositionVariant.STRIP, CompositionVariant.STACKED),
        prohibited_when="The sequence is a workflow with no phase or milestone meaning.",
        visual_types=(VisualType.TIMELINE,),
        text_budget=620,
    ),
    SlideArchetype.METRIC_PROOF: PrimitiveGrammar(
        family="metric_proof",
        narrative_purpose="Make one sourced number the proof and subordinate related numbers.",
        required_content=("headline", "one to four evidenced metrics"),
        optional_content=("subhead", "source qualification"),
        dominant_visual_element="A numeric monument with proportional proof geometry driven by supplied metrics.",
        permitted_density=("sparse", "balanced"),
        typography_hierarchy=("metric-primary", "metric-label", "metric-secondary", "body"),
        variants=(CompositionVariant.LEFT_FOCAL, CompositionVariant.RIGHT_FOCAL, CompositionVariant.CENTERED_MONUMENT),
        prohibited_when="No reliable metric exists or unrelated values would imply a false scale.",
        visual_types=(VisualType.METRIC, VisualType.PROOF_STRIP),
        text_budget=420,
    ),
    SlideArchetype.SYSTEM_MAP: PrimitiveGrammar(
        family="system_map",
        narrative_purpose="Explain actors, components and flows as a connected operating system.",
        required_content=("headline", "three to eight evidenced items", "at least two evidenced edges"),
        optional_content=("subhead", "edge labels"),
        dominant_visual_element="Relationship geometry whose connectors encode real flows.",
        permitted_density=("balanced", "dense"),
        typography_hierarchy=("headline", "node-label", "node-detail", "edge-label"),
        variants=(CompositionVariant.ORBIT, CompositionVariant.RADIAL),
        prohibited_when="The items have no evidenced relationships or form only a directory.",
        visual_types=(VisualType.SYSTEM_MAP,),
        text_budget=620,
    ),
    SlideArchetype.COMPARISON_SHIFT: PrimitiveGrammar(
        family="comparison_shift",
        narrative_purpose="Show a consequential transition between two states.",
        required_content=("headline", "two labelled groups with at least two evidenced items each"),
        optional_content=("subhead", "transition label"),
        dominant_visual_element="A threshold, bridge or diagonal transition between unequal fields.",
        permitted_density=("balanced", "dense"),
        typography_hierarchy=("headline", "state-label", "item-label", "item-detail"),
        variants=(CompositionVariant.SPLIT_40_60, CompositionVariant.DIAGONAL_FLOW),
        prohibited_when="The states are merely feature columns or no direction of change is evidenced.",
        visual_types=(VisualType.COMPARISON,),
        text_budget=560,
    ),
}


def grammar_for(archetype: SlideArchetype) -> PrimitiveGrammar | None:
    return STRUCTURAL_GRAMMARS.get(archetype)
