from __future__ import annotations

from hashlib import sha256
import math
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree

from pptx import Presentation
from pptx.oxml.ns import qn

from app.template.contracts import (
    TemplateCapacity,
    TemplateProfile,
    TemplateRelationship,
    TemplateShapeProfile,
    TemplateSlideProfile,
    TemplateTextStyle,
    TemplateTheme,
)
from app.template.package import MAX_TEMPLATE_SHAPES, TemplateInputError, validate_template_package


EMU_PER_INCH = 914400
YEAR_RE = re.compile(r"(?:19|20)\d{2}|(?:Q[1-4]|M\d+)", re.IGNORECASE)
SAFE_CLONE_RELATION_SUFFIXES = (
    "/slideLayout",
    "/image",
    "/notesSlide",
)
STRIPPABLE_RELATION_SUFFIXES = ("/tags", "/audio", "/media", "/hyperlink")


def extract_template_profile(path: Path) -> TemplateProfile:
    path = path.resolve()
    validate_template_package(path)
    try:
        presentation = Presentation(path)
    except Exception as exc:
        raise TemplateInputError("E003", "template_file", f"python-pptx 无法读取模板: {exc}") from exc

    shape_count = sum(sum(1 for _shape in _iter_shapes(slide.shapes)) for slide in presentation.slides)
    if shape_count > MAX_TEMPLATE_SHAPES:
        raise TemplateInputError("E001", "template_file", "模板形状总数超过 5000 个资源上限。")

    theme = _extract_theme(path)
    slides = [
        _extract_slide_profile(index, slide, presentation.slide_width, presentation.slide_height, theme)
        for index, slide in enumerate(presentation.slides, start=1)
    ]
    observed_colors = sorted(
        {
            color
            for slide in slides
            for shape in slide.shapes
            for color in (
                shape.style.color_hex if shape.style else None,
                shape.fill_color_hex,
                shape.line_color_hex,
            )
            if color is not None
        }
    )
    merged_colors = dict(theme.colors)
    for index, color in enumerate(observed_colors, start=1):
        merged_colors.setdefault(f"observed{index}", color)
    theme = theme.model_copy(update={"colors": merged_colors})
    return TemplateProfile(
        profile_version="1.0",
        source={"filename": path.name, "sha256": _file_sha256(path), "bytes": path.stat().st_size},
        slide_width_in=round(presentation.slide_width / EMU_PER_INCH, 4),
        slide_height_in=round(presentation.slide_height / EMU_PER_INCH, 4),
        theme=theme,
        slides=slides,
        warnings=[],
    )


def write_template_profile(profile: TemplateProfile, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _extract_slide_profile(index, slide, width: int, height: int, theme: TemplateTheme) -> TemplateSlideProfile:
    raw_shapes = [_raw_shape(shape, width, height, theme) for shape in _iter_shapes(slide.shapes)]
    role = _slide_role(index, raw_shapes)
    title_id = _title_shape_id(raw_shapes)
    shapes = [
        TemplateShapeProfile(
            shape_id=item["shape_id"],
            name=item["name"],
            kind=item["kind"],
            role=_shape_role(item, role, title_id),
            left_ratio=item["left_ratio"],
            top_ratio=item["top_ratio"],
            width_ratio=item["width_ratio"],
            height_ratio=item["height_ratio"],
            text_preview=item["text_preview"],
            style=item["style"],
            fill_color_hex=item["fill_color_hex"],
            line_color_hex=item["line_color_hex"],
            capacity=item["capacity"],
            relationship_ids=item["relationship_ids"],
        )
        for item in raw_shapes
    ]
    relationships = [_relationship_profile(rel) for rel in slide.part.rels.values()]
    referenced_relationships = {relationship_id for shape in shapes for relationship_id in shape.relationship_ids}
    exclusion_reasons = sorted(
        {
            f"unsupported relationship: {rel.reltype.rsplit('/', 1)[-1]}"
            for rel in slide.part.rels.values()
            if rel.rId in referenced_relationships and not _relationship_is_profile_safe(rel)
        }
    )
    has_chart = any(shape.kind == "chart" for shape in shapes)
    if has_chart:
        exclusion_reasons.append("prototype contains a chart relationship")
    slide_element = slide.element
    return TemplateSlideProfile(
        index=index,
        prototype_id=f"slide-{index:03d}",
        role=role,
        layout_name=getattr(slide.slide_layout, "name", None),
        master_name=getattr(getattr(slide.slide_layout, "slide_master", None), "name", None),
        safe_to_clone=not exclusion_reasons,
        exclusion_reasons=list(dict.fromkeys(exclusion_reasons)),
        has_transition=slide_element.find(qn("p:transition")) is not None,
        has_timing=slide_element.find(qn("p:timing")) is not None,
        notes_present=bool(getattr(slide, "has_notes_slide", False)),
        relationships=relationships,
        shapes=shapes,
    )


def _raw_shape(shape, slide_width: int, slide_height: int, theme: TemplateTheme) -> dict:
    text = ""
    if getattr(shape, "has_text_frame", False):
        text = "\n".join(paragraph.text for paragraph in shape.text_frame.paragraphs).strip()
    style = _text_style(shape, theme) if getattr(shape, "has_text_frame", False) else None
    font_size = style.font_size_pt if style and style.font_size_pt else 18.0
    # Placeholder shapes that inherit their geometry from a layout have no
    # <a:xfrm>, so shape.width/left are None; coerce them to 0 instead of
    # crashing the whole template profile.
    width_in = max(float(getattr(shape, "width", 0) or 0) / EMU_PER_INCH, 0)
    height_in = max(float(getattr(shape, "height", 0) or 0) / EMU_PER_INCH, 0)
    return {
        "shape_id": int(shape.shape_id),
        "name": str(shape.name or f"Shape {shape.shape_id}"),
        "kind": _shape_kind(shape),
        "left_ratio": round(float(getattr(shape, "left", 0) or 0) / slide_width, 5),
        "top_ratio": round(float(getattr(shape, "top", 0) or 0) / slide_height, 5),
        "width_ratio": round(float(getattr(shape, "width", 0) or 0) / slide_width, 5),
        "height_ratio": round(float(getattr(shape, "height", 0) or 0) / slide_height, 5),
        "text": text,
        "text_preview": _preview(text) if text else None,
        "style": style,
        "fill_color_hex": _fill_color(shape),
        "line_color_hex": _line_color(shape),
        "capacity": _capacity(width_in, height_in, font_size) if text or getattr(shape, "has_text_frame", False) else None,
        "relationship_ids": _shape_relationship_ids(shape),
    }


def _shape_kind(shape) -> str:
    if getattr(shape, "has_table", False):
        return "table"
    if getattr(shape, "has_chart", False):
        return "chart"
    shape_type = str(getattr(shape, "shape_type", ""))
    if "PICTURE" in shape_type:
        return "image"
    if "GROUP" in shape_type:
        return "group"
    if getattr(shape, "is_placeholder", False):
        return "placeholder"
    if getattr(shape, "has_text_frame", False):
        return "text"
    return "shape"


def _iter_shapes(shapes):
    for shape in shapes:
        if "GROUP" in str(getattr(shape, "shape_type", "")) and hasattr(shape, "shapes"):
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def _relationship_is_clone_safe(rel) -> bool:
    if rel.is_external:
        return False
    if rel.reltype.endswith(SAFE_CLONE_RELATION_SUFFIXES):
        return True
    return str(getattr(getattr(rel, "target_part", None), "content_type", "")).startswith("image/")


def _relationship_is_profile_safe(rel) -> bool:
    return _relationship_is_clone_safe(rel) or (
        not rel.is_external and rel.reltype.endswith(STRIPPABLE_RELATION_SUFFIXES)
    )


def _text_style(shape, theme: TemplateTheme) -> TemplateTextStyle:
    run = None
    paragraph = None
    for candidate in shape.text_frame.paragraphs:
        paragraph = paragraph or candidate
        for candidate_run in candidate.runs:
            if candidate_run.text.strip():
                run = candidate_run
                paragraph = candidate
                break
        if run is not None:
            break
    font = run.font if run is not None else None
    font_name = getattr(font, "name", None) if font is not None else None
    if not font_name:
        font_name = next(iter(theme.minor_fonts or theme.major_fonts), None)
    size = None
    if font is not None and font.size is not None:
        size = round(font.size.pt, 2)
    color = None
    if font is not None:
        try:
            if font.color.rgb is not None:
                color = str(font.color.rgb)
        except (AttributeError, TypeError, ValueError):
            color = None
    alignment = str(paragraph.alignment).split(" ", 1)[0] if paragraph is not None and paragraph.alignment is not None else None
    return TemplateTextStyle(
        font_name=font_name,
        font_size_pt=size,
        bold=font.bold if font is not None else None,
        color_hex=color,
        alignment=alignment,
    )


def _capacity(width_in: float, height_in: float, font_size_pt: float) -> TemplateCapacity:
    char_width_in = max(font_size_pt / 72, 0.08)
    line_height_in = max(font_size_pt * 1.3 / 72, 0.14)
    chars_per_line = max(1, math.floor(max(width_in - 0.12, 0.05) / char_width_in))
    lines = max(1, math.floor(max(height_in - 0.08, 0.05) / line_height_in))
    return TemplateCapacity(
        char_capacity=chars_per_line * lines,
        line_capacity=lines,
        list_item_capacity=min(8, max(1, lines // 2)),
    )


def _slide_role(index: int, shapes: list[dict]) -> str:
    text_shapes = [item for item in shapes if item["text"]]
    combined = "\n".join(item["text"] for item in text_shapes)
    folded = combined.casefold()
    if any(token in folded for token in ("请各位老师批评指正", "谢谢", "致谢", "thank you")):
        return "closing"
    if "目录" in combined or "contents" in folded or len(re.findall(r"\bpart\s*\d+", folded)) >= 3:
        return "agenda"
    if any(token in combined for token in ("总结", "结论", "未来发展", "展望")):
        return "conclusion"
    if any(token in combined for token in ("进度安排", "时间线", "里程碑")) or len(YEAR_RE.findall(combined)) >= 3:
        return "timeline"
    if any(item["kind"] == "chart" for item in shapes):
        return "chart"
    if any(item["kind"] == "table" for item in shapes):
        return "table"
    if index == 1:
        return "cover"
    if len(re.findall(r"\bpart\s*\d+", folded)) == 1 and len(text_shapes) <= 5:
        return "section"
    centers = sorted(
        item["left_ratio"] + item["width_ratio"] / 2
        for item in text_shapes
        if item["top_ratio"] > 0.18 and item["top_ratio"] < 0.88
    )
    if len(centers) >= 2 and any(current - previous >= 0.22 for previous, current in zip(centers, centers[1:])):
        return "two_column"
    comparable = [item for item in text_shapes if 0.12 <= item["width_ratio"] <= 0.4 and 0.08 <= item["height_ratio"] <= 0.45]
    if len(comparable) >= 3:
        return "cards"
    return "title_bullets"


def _title_shape_id(shapes: list[dict]) -> int | None:
    candidates = [
        item
        for item in shapes
        if item["text"] and item["top_ratio"] <= 0.34 and item["top_ratio"] >= -0.1
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            (item["style"].font_size_pt if item["style"] and item["style"].font_size_pt else 12) * 2
            + item["width_ratio"] * 20
            - item["top_ratio"] * 10
        ),
    )["shape_id"]


def _shape_role(item: dict, slide_role: str, title_id: int | None) -> str:
    if item["shape_id"] == title_id:
        return "title"
    if item["text"]:
        size = item["style"].font_size_pt if item["style"] and item["style"].font_size_pt else 12
        if item["top_ratio"] >= 0.88:
            return "footer"
        if item["top_ratio"] <= 0.18 and size <= 14 and item["width_ratio"] <= 0.55:
            return "brand"
        if slide_role == "agenda":
            return "agenda_item"
        if slide_role == "section" and size >= 18:
            return "section_label"
        if slide_role == "cover" and size >= 16:
            return "subtitle"
        return "body"
    if item["kind"] == "image" and item["width_ratio"] >= 0.28 and item["height_ratio"] >= 0.2:
        return "content_slot"
    return "decorative"


def _shape_relationship_ids(shape) -> list[str]:
    identifiers: set[str] = set()
    for element in shape.element.iter():
        for value in element.attrib.values():
            if isinstance(value, str) and value.startswith("rId"):
                identifiers.add(value)
    return sorted(identifiers)


def _relationship_profile(rel) -> TemplateRelationship:
    try:
        target = rel.target_ref
    except AttributeError:
        target = str(getattr(getattr(rel, "target_part", None), "partname", ""))
    return TemplateRelationship(
        relationship_id=rel.rId,
        relationship_type=rel.reltype,
        target=target,
        external=rel.is_external,
    )


def _fill_color(shape) -> str | None:
    try:
        rgb = shape.fill.fore_color.rgb
        return str(rgb) if rgb is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _line_color(shape) -> str | None:
    try:
        rgb = shape.line.color.rgb
        return str(rgb) if rgb is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _extract_theme(path: Path) -> TemplateTheme:
    major_fonts: list[str] = []
    minor_fonts: list[str] = []
    colors: dict[str, str] = {}
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    with zipfile.ZipFile(path) as package:
        theme_names = sorted(name for name in package.namelist() if name.startswith("ppt/theme/theme") and name.endswith(".xml"))
        for theme_name in theme_names:
            root = ElementTree.fromstring(package.read(theme_name))
            for family, destination in (("majorFont", major_fonts), ("minorFont", minor_fonts)):
                parent = root.find(f".//a:{family}", namespace)
                if parent is None:
                    continue
                for child in parent:
                    typeface = child.attrib.get("typeface", "").strip()
                    if typeface and typeface not in destination:
                        destination.append(typeface)
            scheme = root.find(".//a:clrScheme", namespace)
            if scheme is not None:
                for item in scheme:
                    if not list(item):
                        continue
                    color_node = list(item)[0]
                    value = color_node.attrib.get("val") or color_node.attrib.get("lastClr")
                    key = item.tag.rsplit("}", 1)[-1]
                    if value and re.fullmatch(r"[0-9A-Fa-f]{6}", value):
                        colors.setdefault(key, value.upper())
    if not major_fonts:
        major_fonts = ["Microsoft YaHei"]
    if not minor_fonts:
        minor_fonts = ["Microsoft YaHei"]
    colors.setdefault("accent1", "3494BA")
    colors.setdefault("tx1", "000000")
    colors.setdefault("bg1", "FFFFFF")
    return TemplateTheme(major_fonts=major_fonts, minor_fonts=minor_fonts, colors=colors)


def _preview(text: str, limit: int = 120) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "..."


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
