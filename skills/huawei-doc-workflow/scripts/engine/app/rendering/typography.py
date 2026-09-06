from __future__ import annotations

from dataclasses import dataclass
import math
import unicodedata


PT_PER_INCH = 72.0


@dataclass(frozen=True)
class TextStackFit:
    font_size_pt: float
    item_heights_in: tuple[float, ...]
    overflow: bool


def fit_text_stack(
    texts: list[str],
    candidates_pt: list[float],
    *,
    width_in: float,
    height_in: float,
    line_spacing: float,
    item_gap_in: float,
    baseline_pt: float,
    horizontal_margin_in: float = 0.1,
    vertical_margin_in: float = 0.04,
) -> TextStackFit:
    if not candidates_pt:
        raise ValueError("candidates_pt must not be empty")

    normalized = [str(text) for text in texts]
    for size in candidates_pt:
        heights = measure_text_stack(
            normalized,
            size,
            width_in=width_in,
            line_spacing=line_spacing,
            baseline_pt=baseline_pt,
            horizontal_margin_in=horizontal_margin_in,
            vertical_margin_in=vertical_margin_in,
        )
        if _stack_height(heights, item_gap_in) <= height_in + 1e-6:
            return TextStackFit(float(size), tuple(heights), False)

    minimum = float(candidates_pt[-1])
    heights = measure_text_stack(
        normalized,
        minimum,
        width_in=width_in,
        line_spacing=line_spacing,
        baseline_pt=baseline_pt,
        horizontal_margin_in=horizontal_margin_in,
        vertical_margin_in=vertical_margin_in,
    )
    return TextStackFit(minimum, tuple(heights), True)


def measure_text_stack(
    texts: list[str],
    font_size_pt: float,
    *,
    width_in: float,
    line_spacing: float,
    baseline_pt: float,
    horizontal_margin_in: float = 0.1,
    vertical_margin_in: float = 0.04,
) -> list[float]:
    return [
        estimate_text_height_in(
            text,
            font_size_pt,
            width_in=width_in,
            line_spacing=line_spacing,
            baseline_pt=baseline_pt,
            horizontal_margin_in=horizontal_margin_in,
            vertical_margin_in=vertical_margin_in,
        )
        for text in texts
    ]


def estimate_text_height_in(
    text: str,
    font_size_pt: float,
    *,
    width_in: float,
    line_spacing: float,
    baseline_pt: float,
    horizontal_margin_in: float = 0.1,
    vertical_margin_in: float = 0.04,
) -> float:
    line_count = estimate_line_count(
        text,
        font_size_pt,
        width_in=width_in,
        horizontal_margin_in=horizontal_margin_in,
    )
    height_pt = line_count * font_size_pt * line_spacing + vertical_margin_in * 2 * PT_PER_INCH
    snapped_pt = math.ceil(height_pt / baseline_pt) * baseline_pt
    return snapped_pt / PT_PER_INCH


def estimate_line_count(
    text: str,
    font_size_pt: float,
    *,
    width_in: float,
    horizontal_margin_in: float = 0.1,
) -> int:
    available_width_pt = max((width_in - horizontal_margin_in * 2) * PT_PER_INCH, font_size_pt)
    units_per_line = max(available_width_pt / font_size_pt, 1.0)
    logical_lines = str(text).splitlines() or [""]
    return sum(max(math.ceil(text_units(line) / units_per_line), 1) for line in logical_lines)


def text_units(text: str) -> float:
    return sum(1.0 if unicodedata.east_asian_width(char) in {"W", "F"} else 0.5 for char in text)


def constrained_stack_heights(fit: TextStackFit, *, height_in: float, item_gap_in: float) -> tuple[float, ...]:
    if not fit.item_heights_in or not fit.overflow:
        return fit.item_heights_in
    gaps = item_gap_in * max(len(fit.item_heights_in) - 1, 0)
    available = max(height_in - gaps, 0.0)
    total = sum(fit.item_heights_in)
    if total <= 0:
        return fit.item_heights_in
    scale = available / total
    return tuple(height * scale for height in fit.item_heights_in)


def _stack_height(heights: list[float], item_gap_in: float) -> float:
    return sum(heights) + item_gap_in * max(len(heights) - 1, 0)
