from __future__ import annotations

from dataclasses import dataclass, field

from app.ai_orchestration.schemas import LlmGenerationOutput, SlideSceneGraph


@dataclass
class ValidationResult:
    valid: bool
    messages: list[str] = field(default_factory=list)


class SceneGraphValidator:
    width = 1280
    height = 720
    supported_types = {"text", "shape", "image", "chart_placeholder"}

    def validate_output(self, output: LlmGenerationOutput, selected_slide_ids: list[str]) -> ValidationResult:
        messages: list[str] = []
        expected = list(dict.fromkeys(selected_slide_ids))
        actual = [slide.source_slide_id for slide in output.generated_slides]
        if actual != expected:
            messages.append("generated slide source ids must exactly match selectedSlideIds in order")

        for slide in output.generated_slides:
            result = self.validate_scene_graph(slide.scene_graph, slide.source_slide_id)
            if not result.valid:
                messages.extend(result.messages)

        return ValidationResult(valid=len(messages) == 0, messages=messages or ["valid"])

    def validate_scene_graph(self, scene_graph: SlideSceneGraph, source_slide_id: str = "") -> ValidationResult:
        messages: list[str] = []
        prefix = f"{source_slide_id}: " if source_slide_id else ""

        if scene_graph.width != self.width or scene_graph.height != self.height:
            messages.append(f"{prefix}scene graph must be 1280x720")

        seen_ids: set[str] = set()
        for element in scene_graph.elements:
            if element.id in seen_ids:
                messages.append(f"{prefix}duplicate element id {element.id}")
            seen_ids.add(element.id)

            if element.type not in self.supported_types:
                messages.append(f"{prefix}{element.id} has unsupported type {element.type}")
            if element.width <= 0 or element.height <= 0:
                messages.append(f"{prefix}{element.id} must have positive dimensions")
            if element.x < 0 or element.y < 0:
                messages.append(f"{prefix}{element.id} is outside the canvas")
            if element.x + element.width > self.width or element.y + element.height > self.height:
                messages.append(f"{prefix}{element.id} exceeds canvas bounds")
            if element.type == "text" and not (element.text or "").strip():
                messages.append(f"{prefix}{element.id} text element requires text")

        return ValidationResult(valid=len(messages) == 0, messages=messages or ["valid"])
