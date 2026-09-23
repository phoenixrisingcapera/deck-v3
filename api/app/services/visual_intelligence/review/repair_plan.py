from __future__ import annotations

from app.services.visual_intelligence.models import (
    VisionReview, VisualRepairInstruction, VisualRepairPlan,
)


_REPAIR_TYPE = {
    "focal_point": "hierarchy", "hierarchy": "hierarchy", "balance": "composition",
    "composition": "composition", "scale": "composition", "alignment": "composition",
    "contrast": "typography", "text_density": "density", "chart_readability": "chart",
    "diagram_readability": "diagram", "image_quality": "image", "brand_fit": "composition",
    "visual_storytelling": "composition", "rhythm": "composition", "repetition": "composition",
}


def build_visual_repair_plan(review: VisionReview) -> VisualRepairPlan:
    """Create one bounded targeted advisory plan; execution requires a separately accounted node."""
    instructions = []
    for finding in review.findings:
        if not finding.slide_id or finding.severity == "advisory":
            continue
        instructions.append(VisualRepairInstruction(
            slide_id=finding.slide_id,
            issue=finding.issue,
            repair_type=_REPAIR_TYPE[finding.dimension],
            requested_change=f"Repair only this slide's {finding.dimension.replace('_', ' ')} while preserving all grounded claims, source bindings and numerical meaning.",
            preserve=["evidence IDs", "calculation IDs", "claim text meaning", "brand tokens"],
        ))
    return VisualRepairPlan(instructions=instructions[:20])
