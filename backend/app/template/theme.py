from __future__ import annotations

from copy import deepcopy

from app.rendering.theme import load_theme
from app.template.contracts import TemplateProfile
from app.template.text_fit import font_is_available


def build_template_render_theme(theme_name: str, profile: TemplateProfile) -> dict:
    theme = deepcopy(load_theme(theme_name))
    source_width = float(theme["slide"]["width_in"])
    source_height = float(theme["slide"]["height_in"])
    scale_x = profile.slide_width_in / source_width
    scale_y = profile.slide_height_in / source_height
    _scale_geometry(theme, scale_x, scale_y)
    theme["slide"]["width_in"] = profile.slide_width_in
    theme["slide"]["height_in"] = profile.slide_height_in
    _apply_observed_content_margins(theme, profile)

    major, minor, _substitutions = select_template_fonts(profile)
    theme["fonts"]["east_asia"] = [minor]
    theme["fonts"]["latin"] = [major]
    theme["fonts"]["number"] = [major]
    theme["fonts"]["whitelist"] = list(dict.fromkeys([major, minor, "Arial", "Microsoft YaHei", "微软雅黑"]))

    colors = profile.theme.colors
    accent1 = _color(colors, "accent1", "3494BA")
    text = _color(colors, "tx1", _color(colors, "dk1", "000000").lstrip("#"))
    background = _color(colors, "bg1", _color(colors, "lt1", "FFFFFF").lstrip("#"))
    accents = [accent1] + [_color(colors, f"accent{index}", accent1.lstrip("#")) for index in range(2, 7)]
    theme["colors"].update(
        {
            "hw_red": accent1,
            "title": text,
            "body": text,
            "background": background,
            "accent1": accents[0],
            "accent2": accents[1],
            "accent3": accents[2],
            "accent4": accents[3],
            "accent5": accents[4],
            "accent6": accents[5],
            "hlink": accent1,
        }
    )
    for index, color in enumerate(dict.fromkeys(profile.theme.colors.values()), start=1):
        theme["colors"][f"template_observed_{index}"] = "#" + color
    theme["footer"]["security_prefix"] = ""
    theme["footer"]["copyright"] = ""
    return theme


def select_template_fonts(profile: TemplateProfile) -> tuple[str, str, list[tuple[str, str, str]]]:
    major, major_substitution = _resolve_font(
        profile.theme.major_fonts,
        ("Arial", "Microsoft YaHei"),
        "template.theme.major_fonts",
    )
    minor, minor_substitution = _resolve_font(
        profile.theme.minor_fonts,
        ("Microsoft YaHei", "Arial"),
        "template.theme.minor_fonts",
    )
    substitutions = [item for item in (major_substitution, minor_substitution) if item is not None]
    return major, minor, substitutions


def _resolve_font(
    fonts: list[str],
    fallbacks: tuple[str, ...],
    loc: str,
) -> tuple[str, tuple[str, str, str] | None]:
    declared = _usable_font(fonts)
    if declared and font_is_available(declared):
        return declared, None
    replacement = next((font for font in fallbacks if font_is_available(font)), fallbacks[0])
    substitution = (loc, declared, replacement) if declared else None
    return replacement, substitution


def _scale_geometry(value, scale_x: float, scale_y: float, key: str | None = None) -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if isinstance(child, (int, float)) and child_key.endswith("_in"):
                value[child_key] = child * _scale_for_key(child_key, scale_x, scale_y)
            else:
                _scale_geometry(child, scale_x, scale_y, child_key)
    elif isinstance(value, list):
        for child in value:
            _scale_geometry(child, scale_x, scale_y, key)


def _scale_for_key(key: str, scale_x: float, scale_y: float) -> float:
    folded = key.casefold()
    if any(token in folded for token in ("left", "right", "width", "column", "_x_")):
        return scale_x
    if any(token in folded for token in ("top", "bottom", "height", "row", "_y_")):
        return scale_y
    return min(scale_x, scale_y)


def _apply_observed_content_margins(theme: dict, profile: TemplateProfile) -> None:
    """Respect a template's established text/table safe area without trusting decoration."""

    edges: dict[str, list[float]] = {"left": [], "right": [], "top": [], "bottom": []}
    content_kinds = {"text", "placeholder", "table", "chart"}
    excluded_roles = {"decorative", "brand", "footer"}
    for slide in profile.slides:
        for shape in slide.shapes:
            if shape.kind not in content_kinds or shape.role in excluded_roles:
                continue
            left = shape.left_ratio * profile.slide_width_in
            top = shape.top_ratio * profile.slide_height_in
            right = profile.slide_width_in - (shape.left_ratio + shape.width_ratio) * profile.slide_width_in
            bottom = profile.slide_height_in - (shape.top_ratio + shape.height_ratio) * profile.slide_height_in
            edges["left"].append(max(left, 0.0))
            edges["right"].append(max(right, 0.0))
            edges["top"].append(max(top, 0.0))
            edges["bottom"].append(max(bottom, 0.0))

    for side, values in edges.items():
        if not values:
            continue
        key = f"margin_{side}_in"
        observed = max(0.35, min(values))
        theme["slide"][key] = min(float(theme["slide"][key]), observed)


def _usable_font(fonts: list[str]) -> str | None:
    return next((font for font in fonts if font and not font.startswith("+")), None)


def _color(colors: dict[str, str], key: str, fallback: str) -> str:
    return "#" + colors.get(key, fallback.lstrip("#")).lstrip("#").upper()
