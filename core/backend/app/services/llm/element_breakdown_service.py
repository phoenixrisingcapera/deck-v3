from __future__ import annotations

from typing import Any, Literal

from app.schemas.smart_deck import RenderSchema, RenderSchemaBackground, RenderSchemaElement


PROPERTY_LABELS: dict[str, str] = {
    "text": "Text Content",
    "fontSize": "Font Size",
    "fontWeight": "Font Weight",
    "colorToken": "Text Color",
    "fillToken": "Fill Color",
    "assetUrl": "Image URL",
    "analyticsKey": "Analytics Key",
    "opacity": "Opacity",
    "radius": "Corner Radius",
    "x": "X Position",
    "y": "Y Position",
    "width": "Width",
    "height": "Height",
    "zIndex": "Z-Index",
    "rotation": "Rotation",
    "shape": "Shape Type",
    "visible": "Visible",
    "locked": "Locked",
}


def _label(key: str, fallback: str = "") -> str:
    return PROPERTY_LABELS.get(key, fallback or key.replace("_", " ").title())


def _property(
    key: str,
    ptype: Literal["string", "number", "boolean", "color", "select"],
    value: Any,
    *,
    editable: bool = True,
    options: list[Any] | None = None,
    label: str | None = None,
    constraints: dict | None = None,
) -> dict:
    return {
        "key": key,
        "type": ptype,
        "label": label or _label(key),
        "value": value,
        "editable": editable,
        **({"options": options} if options else {}),
        **({"constraints": constraints} if constraints else {}),
    }


def _break_element(element: RenderSchemaElement) -> dict:
    element_type = element.type
    label = element_type.replace("_", " ").title()
    if element_type == "text" and element.text:
        label = f"Text: {element.text[:60].strip()}"
    if element_type == "image":
        label = "Image"
    if element_type == "chart_placeholder":
        label = "Chart Placeholder"

    element_id = element.id

    props: list[dict] = []

    if element_type == "text":
        props.append(_property("text", "string", element.text or "", label="Text Content",
                                constraints={"maxLength": 1000}))
        if element.fontSize is not None:
            props.append(_property("fontSize", "number", element.fontSize,
                                    constraints={"min": 8, "max": 160}))
        if element.fontWeight is not None:
            props.append(_property("fontWeight", "string", element.fontWeight,
                                    options=["normal", "bold", "light", "medium", "semibold"]))
        if element.colorToken is not None:
            props.append(_property("colorToken", "color", element.colorToken,
                                    options=["brand.heading", "brand.body", "brand.accent", "brand.muted"]))
        if element.fillToken is not None:
            props.append(_property("fillToken", "color", element.fillToken))

    elif element_type == "shape":
        if element.fillToken is not None:
            props.append(_property("fillToken", "color", element.fillToken,
                                    options=["brand.surface", "brand.surfaceAlt", "brand.accent", "brand.muted"]))
        if element.text:
            props.append(_property("text", "string", element.text, editable=False))

    elif element_type == "image":
        props.append(_property("assetUrl", "string", element.assetUrl or "", label="Image URL",
                                editable=bool(element.assetUrl)))
        if element.fillToken:
            props.append(_property("fillToken", "color", element.fillToken, editable=False))

    elif element_type == "chart_placeholder":
        props.append(_property("analyticsKey", "string", element.analyticsKey or "", label="Analytics Key",
                                editable=bool(element.analyticsKey)))

    props.append(_property("x", "number", element.x, constraints={"min": 0, "max": 1920}))
    props.append(_property("y", "number", element.y, constraints={"min": 0, "max": 1080}))
    props.append(_property("width", "number", element.width, constraints={"min": 1, "max": 1920}))
    props.append(_property("height", "number", element.height, constraints={"min": 1, "max": 1080}))
    props.append(_property("zIndex", "number", element.zIndex, constraints={"min": 0, "max": 100}))

    return {
        "elementId": element_id,
        "elementType": element_type,
        "label": label,
        "properties": props,
    }


def _break_background(background: RenderSchemaBackground) -> dict:
    bg_type = background.type
    props: list[dict] = []

    props.append(_property("type", "select", bg_type,
                            options=["token", "color", "gradient", "image", "layered"],
                            editable=True, label="Background Type"))

    if background.value is not None:
        if bg_type == "color":
            props.append(_property("value", "color", background.value, label="Color"))
        elif bg_type == "token":
            props.append(_property("value", "select", background.value,
                                    options=["brand.surface", "brand.surfaceAlt"]))
        elif bg_type == "gradient":
            props.append(_property("value", "string", background.value, label="Gradient"))
        elif bg_type == "image":
            props.append(_property("value", "string", background.value, label="Image URL"))

    if background.fill is not None:
        props.append(_property("fill", "color", background.fill,
                                options=["brand.surface", "brand.surfaceAlt"]))

    return {
        "elementId": "__background__",
        "elementType": "background",
        "label": "Slide Background",
        "properties": props,
    }


def breakdown_slide_render_schema(*, slide_id: str | None = None, render_schema: RenderSchema) -> dict:
    elements = [_break_element(el) for el in render_schema.elements]
    breakdown: dict = {
        "schemaVersion": "element-breakdown.v1",
        "elements": elements,
        "background": _break_background(render_schema.background),
    }
    if slide_id:
        breakdown["slideId"] = slide_id
    return breakdown
