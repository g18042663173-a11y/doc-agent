from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import sys

from PIL import ImageFont
from pptx.oxml.ns import qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt


EMU_PER_INCH = 914400
PX_PER_INCH = 96
FONT_FILE_ALIASES = {
    "arial": ("arial",),
    "aptos": ("aptos",),
    "calibri": ("calibri",),
    "cambria": ("cambria",),
    "microsoftyahei": ("msyh", "microsoftyahei"),
    "微软雅黑": ("msyh",),
    "simhei": ("simhei",),
    "黑体": ("simhei",),
    "simsun": ("simsun",),
    "宋体": ("simsun",),
    "timesnewroman": ("times", "timesnewroman"),
}


def replace_text_preserving_style(
    shape,
    text: str,
    *,
    role: str,
    fallback_font_name: str | None = None,
    allowed_font_names: set[str] | None = None,
    preserve_source_size: bool = False,
    source_run_lengths: list[list[int]] | None = None,
) -> bool:
    if not getattr(shape, "has_text_frame", False):
        return False
    if preserve_source_size:
        return _replace_source_text(shape, text, role, source_run_lengths)
    frame = shape.text_frame
    source_paragraph = frame.paragraphs[0] if frame.paragraphs else None
    source_ppr = (
        deepcopy(source_paragraph._p.pPr)
        if source_paragraph is not None and source_paragraph._p.pPr is not None
        else None
    )
    source_run = next((run for paragraph in frame.paragraphs for run in paragraph.runs), None)
    source_rpr = deepcopy(source_run._r.rPr) if source_run is not None and source_run._r.rPr is not None else None
    source_size = (
        source_run.font.size.pt
        if source_run is not None and source_run.font.size is not None
        else (28 if role == "title" else 16)
    )
    font_name = source_run.font.name if source_run is not None else None
    font_allowed = allowed_font_names is None or font_name in allowed_font_names
    rendered_font_name = font_name if font_is_available(font_name) and font_allowed else fallback_font_name
    measurement_font_name = rendered_font_name or font_name

    # The template paragraph may render its own bullet (a:buChar / a:buAutoNum).
    # When it does, a caller-supplied "• " prefix (used for plain-text bodies)
    # must be stripped or the slide shows a double bullet.
    template_owns_bullet = source_ppr is not None and (
        source_ppr.find(qn("a:buChar")) is not None or source_ppr.find(qn("a:buAutoNum")) is not None
    )
    lines = text.splitlines() or [""]
    frame.clear()
    for index, line in enumerate(lines):
        if template_owns_bullet:
            line = line.removeprefix("• ").removeprefix("•")
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        if source_ppr is not None:
            existing = paragraph._p.pPr
            if existing is not None:
                paragraph._p.remove(existing)
            paragraph._p.insert(0, deepcopy(source_ppr))
        for run in paragraph.runs:
            if source_rpr is not None:
                existing_rpr = run._r.rPr
                if existing_rpr is not None:
                    run._r.remove(existing_rpr)
                run._r.insert(0, deepcopy(source_rpr))

    fitted_size = _fitted_font_size(shape, text, measurement_font_name, float(source_size), role)
    for paragraph in frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(fitted_size)
            if rendered_font_name:
                _set_run_font_name(run, rendered_font_name)
    return _text_fits(shape, text, measurement_font_name, fitted_size)


def _replace_source_text(shape, text: str, role: str, source_run_lengths: list[list[int]] | None = None) -> bool:
    """Imitation keeps each paragraph's native styling and never enlarges it."""
    frame = shape.text_frame
    originals = [deepcopy(p._p) for p in frame.paragraphs]
    source_run = next((run for p in frame.paragraphs for run in p.runs), None)
    font_name = source_run.font.name if source_run is not None else None
    explicit_sizes = [run.font.size.pt for p in frame.paragraphs for run in p.runs if run.font.size is not None]
    start = explicit_sizes[0] if explicit_sizes else 16.0
    for p in list(frame.paragraphs):
        frame._txBody.remove(p._p)
    for index, line in enumerate(text.splitlines() or [""]):
        element = deepcopy(originals[min(index, len(originals) - 1)]) if originals else OxmlElement("a:p")
        runs = element.findall(qn("a:r"))
        if not runs:
            run = OxmlElement("a:r")
            run.append(OxmlElement("a:t"))
            element.append(run)
            runs = [run]
        ppr = element.find(qn("a:pPr"))
        if ppr is not None and (ppr.find(qn("a:buChar")) is not None or ppr.find(qn("a:buAutoNum")) is not None):
            line = line.removeprefix("• ").removeprefix("•")
        texts = element.findall(".//" + qn("a:t"))
        weights = source_run_lengths[min(index, len(source_run_lengths) - 1)] if source_run_lengths else [len(node.text or "") for node in texts]
        if len(weights) != len(texts) or not sum(weights):
            weights = [1] * len(texts)
        total = sum(weights)
        consumed = 0
        cumulative = 0
        for position, node in enumerate(texts):
            cumulative += weights[position]
            end = len(line) if position == len(texts) - 1 else round(len(line) * cumulative / total)
            node.text = line[consumed:end]
            consumed = end
        frame._txBody.append(element)
    if shape.width is None or shape.height is None:
        return False
    size = float(start)
    minimum = min(size, 10.5 if role != "title" else 18.0)
    while size > minimum and not _source_text_fits(shape, text, font_name, size):
        size = max(minimum, size - 0.5)
    ratio = size / start
    if ratio < 1:
        for p in frame.paragraphs:
            for run in p.runs:
                if run.font.size is not None:
                    run.font.size = Pt(run.font.size.pt * ratio)
    return _source_text_fits(shape, text, font_name, size)


def _source_text_fits(shape, text: str, font_name: str | None, size_pt: float) -> bool:
    """Measure ink on the first line, then baseline advances and paragraph gaps.

    Multiplying the height of the arbitrary probe ``国Ag`` by 1.2 for every
    line falsely rejects a source 9pt label in a 10.8pt inner text region.
    Leading separates baselines; it is not padding above and below one line.
    """
    frame = shape.text_frame
    width_px = max(1, (shape.width - frame.margin_left - frame.margin_right) / EMU_PER_INCH * PX_PER_INCH)
    height_px = max(1, (shape.height - frame.margin_top - frame.margin_bottom) / EMU_PER_INCH * PX_PER_INCH)
    size_px = max(1, round(size_pt * PX_PER_INCH / 72))
    font = _load_font(font_name, size_px)
    body_pr = frame._txBody.find(qn("a:bodyPr"))
    no_wrap = body_pr is not None and body_pr.get("wrap") == "none"
    total_height = 0.0
    paragraphs = list(frame.paragraphs)
    for index, line in enumerate(text.splitlines() or [""]):
        if no_wrap and font.getlength(line) > width_px + 1:
            return False
        count = 1 if no_wrap else _wrapped_line_count(line, font, width_px)
        box = font.getbbox(line or "Ag")
        ink_height = max(1, box[3] - box[1])
        advance = max(ink_height, size_px * 1.2)
        ppr = paragraphs[min(index, len(paragraphs) - 1)]._p.pPr if paragraphs else None
        before = after = 0.0
        if ppr is not None:
            for tag in ("lnSpc", "spcBef", "spcAft"):
                spacing = ppr.find(qn("a:" + tag))
                if spacing is None or not len(spacing):
                    continue
                value = spacing[0]
                measured = float(value.get("val", 0)) / 100 * PX_PER_INCH / 72 if value.tag == qn("a:spcPts") else size_px * float(value.get("val", 100000)) / 100000
                if tag == "lnSpc":
                    advance = measured
                elif tag == "spcBef":
                    before = measured
                else:
                    after = measured
        total_height += ink_height + (count - 1) * advance + before + after
    return total_height <= height_px + 1


def _set_run_font_name(run, font_name: str) -> None:
    run.font.name = font_name
    rpr = run._r.get_or_add_rPr()
    east_asia = rpr.find(qn("a:ea"))
    if east_asia is None:
        east_asia = OxmlElement("a:ea")
        rpr.append(east_asia)
    east_asia.set("typeface", font_name)


def font_is_available(font_name: str | None) -> bool:
    if not font_name or font_name.startswith("+"):
        return False
    return _font_path(font_name) is not None


def _fitted_font_size(shape, text: str, font_name: str | None, start_size: float, role: str) -> float:
    minimum = 18.0 if role == "title" else 10.5
    size = max(start_size, minimum)
    while size > minimum and not _text_fits(shape, text, font_name, size):
        size = max(minimum, size - 0.5)
    return size


def _text_fits(shape, text: str, font_name: str | None, size_pt: float) -> bool:
    if shape.width is None or shape.height is None:
        # A placeholder shape without explicit <a:xfrm> inherits its geometry
        # from the layout, which python-pptx cannot resolve here. Treat the
        # text as fitting instead of crashing on the None subtraction.
        return True
    frame = shape.text_frame
    width_px = max(
        1,
        (shape.width - frame.margin_left - frame.margin_right) / EMU_PER_INCH * PX_PER_INCH,
    )
    height_px = max(
        1,
        (shape.height - frame.margin_top - frame.margin_bottom) / EMU_PER_INCH * PX_PER_INCH,
    )
    font = _load_font(font_name, max(1, round(size_pt * PX_PER_INCH / 72)))
    line_height = max(font.getbbox("国Ag")[3] - font.getbbox("国Ag")[1], 1) * 1.2
    lines = text.splitlines() or [""]
    body_pr = frame._txBody.find(qn("a:bodyPr"))
    wrap_none = body_pr is not None and body_pr.get("wrap") == "none"
    if wrap_none:
        # wrap="none" clips instead of wrapping: every explicit line must fit the
        # width as a single line, or the content is silently cut off.
        for line in lines:
            if font.getlength(line) > width_px + 1:
                return False
        line_counts = [1] * len(lines)
    else:
        line_counts = [_wrapped_line_count(line, font, width_px) for line in lines]
    return sum(line_counts) * line_height <= height_px + 1


def _wrapped_line_count(text: str, font, width_px: float) -> int:
    if not text:
        return 1
    lines = 1
    current = ""
    for character in text:
        candidate = current + character
        if current and font.getlength(candidate) > width_px:
            lines += 1
            current = character
        else:
            current = candidate
    return lines


@lru_cache(maxsize=64)
def _load_font(font_name: str | None, size_px: int):
    path = _font_path(font_name)
    if path is not None:
        try:
            return ImageFont.truetype(str(path), size_px)
        except OSError:
            pass
    for fallback in _fallback_fonts():
        try:
            return ImageFont.truetype(str(fallback), size_px)
        except OSError:
            continue
    return ImageFont.load_default(size=max(10, size_px))


@lru_cache(maxsize=32)
def _font_path(font_name: str | None) -> Path | None:
    if not font_name:
        return None
    folded = font_name.casefold().replace(" ", "")
    aliases = FONT_FILE_ALIASES.get(folded, (folded,))
    for path in _font_files():
        stem = path.stem.casefold().replace(" ", "")
        if any(alias in stem for alias in aliases):
            return path
    return None


@lru_cache(maxsize=1)
def _font_files() -> tuple[Path, ...]:
    roots: list[Path] = []
    if sys.platform == "win32":
        roots.append(Path("C:/Windows/Fonts"))
    elif sys.platform == "darwin":
        roots.extend([Path("/System/Library/Fonts"), Path("/Library/Fonts")])
    else:
        roots.extend([Path("/usr/share/fonts"), Path("/usr/local/share/fonts")])
    return tuple(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*")
        if path.suffix.lower() in {".ttf", ".ttc", ".otf"}
    )


def _fallback_fonts() -> tuple[Path, ...]:
    preferred = ("msyh", "simhei", "arial", "noto", "dejavu")
    files = _font_files()
    return tuple(path for token in preferred for path in files if token in path.stem.casefold())
