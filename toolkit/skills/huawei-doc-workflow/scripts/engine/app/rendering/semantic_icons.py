from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt


ICON_SHAPES = {
    "person": MSO_SHAPE.OVAL,
    "team": MSO_SHAPE.OVAL,
    "organization": MSO_SHAPE.RECTANGLE,
    "target": MSO_SHAPE.DONUT,
    "risk": MSO_SHAPE.DIAMOND,
    "cost": MSO_SHAPE.HEXAGON,
    "quality": MSO_SHAPE.PENTAGON,
    "data": MSO_SHAPE.CAN,
    "cloud": MSO_SHAPE.CLOUD,
    "device": MSO_SHAPE.ROUNDED_RECTANGLE,
    "security": MSO_SHAPE.OCTAGON,
    "process": MSO_SHAPE.FLOWCHART_PROCESS,
    "time": MSO_SHAPE.PIE,
    "growth": MSO_SHAPE.UP_ARROW,
    "decline": MSO_SHAPE.DOWN_ARROW,
    "check": MSO_SHAPE.CHEVRON,
    "warning": MSO_SHAPE.LIGHTNING_BOLT,
    "idea": MSO_SHAPE.SUN,
    "service": MSO_SHAPE.GEAR_6,
    "network": MSO_SHAPE.HEXAGON,
    "database": MSO_SHAPE.CAN,
    "document": MSO_SHAPE.FOLDED_CORNER,
    "settings": MSO_SHAPE.GEAR_6,
    "delivery": MSO_SHAPE.RIGHT_ARROW,
}


def add_semantic_icon(slide, name: str, box: dict[str, float], theme: dict, *, color_key: str = "hw_red"):
    shape_type = ICON_SHAPES[name]
    shape = slide.shapes.add_shape(
        shape_type,
        Inches(box["left_in"]),
        Inches(box["top_in"]),
        Inches(box["width_in"]),
        Inches(box["height_in"]),
    )
    shape.name = f"HW_SEMANTIC_ICON:{name}"
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(theme["colors"][color_key])
    shape.line.color.rgb = _rgb(theme["colors"][color_key])
    shape.line.width = Pt(theme["layouts"]["infographic"]["border_pt"])
    return shape


def _rgb(hex_color: str):
    from pptx.dml.color import RGBColor

    return RGBColor(*bytes.fromhex(hex_color.lstrip("#")))
