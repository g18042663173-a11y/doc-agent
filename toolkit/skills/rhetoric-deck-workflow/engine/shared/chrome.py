from __future__ import annotations

import re



DEFAULT_CLASSIFICATION = "HUAWEI CONFIDENTIAL"
FOOTER_TOP_RATIO = 0.88
CLASSIFICATION_LINE_RE = re.compile(r"(?:密级|classification)\s*[:：]\s*(.+)$", re.IGNORECASE)
CLASSIFICATION_HINT_RE = re.compile(
    r"confidential|secret|internal|classification|密级|秘密|内部|公开|机密",
    re.IGNORECASE,
)
DROP_SKIP_REASONS = frozenset({"omitted", "empty", "reject"})


def extract_classification(text: str) -> str:
    for line in text.splitlines():
        match = CLASSIFICATION_LINE_RE.match(line.strip())
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            return value[:80]
    return DEFAULT_CLASSIFICATION


def rewrite_classification_chrome(presentation, classification: str) -> None:
    value = (classification or DEFAULT_CLASSIFICATION).strip() or DEFAULT_CLASSIFICATION
    height = int(getattr(presentation, "slide_height", 0) or 0)
    for master in presentation.slide_masters:
        _rewrite_shape_tree(master.shapes, value, height, masters=True)
        for layout in master.slide_layouts:
            _rewrite_shape_tree(layout.shapes, value, height, masters=True)
    for slide in presentation.slides:
        _rewrite_shape_tree(slide.shapes, value, height, masters=False)


def drop_skipped_slides(presentation, skip_pages: list[dict]) -> None:
    # A low fit score never grants permission to discard source pages.
    return

def _rewrite_shape_tree(shapes, classification: str, slide_height: int, *, masters: bool) -> None:
    for shape in _walk_shapes(shapes):
        if _has_page_field(shape) or not getattr(shape, "has_text_frame", False):
            continue
        text = (shape.text or "").strip()
        if not text:
            continue
        if text.casefold() == DEFAULT_CLASSIFICATION.casefold() or re.fullmatch(r"(?:保密级别|密级|classification)\s*[:：].*", text, re.IGNORECASE):
            _set_shape_text(shape, classification)


def _is_footer_shape(shape, slide_height: int) -> bool:
    if slide_height <= 0:
        return False
    try:
        top = int(shape.top)
        height = int(shape.height)
    except (AttributeError, TypeError, ValueError):
        return False
    return top >= int(slide_height * FOOTER_TOP_RATIO) or (top + height) >= int(slide_height * 0.92)


def _has_page_field(shape) -> bool:
    element = getattr(shape, "_element", None)
    if element is None:
        return False
    return bool(element.xpath('.//*[local-name()="fld"]'))


def _set_shape_text(shape, value: str) -> None:
    frame = shape.text_frame
    paragraphs = list(frame.paragraphs)
    if not paragraphs:
        frame.text = value
        return
    first = paragraphs[0]
    if first.runs:
        first.runs[0].text = value
        for run in first.runs[1:]:
            run.text = ""
    else:
        first.text = value
    for paragraph in paragraphs[1:]:
        for run in paragraph.runs:
            run.text = ""


def _walk_shapes(shapes):
    for shape in shapes:
        yield shape
        if getattr(shape, "shape_type", None) == 6:
            yield from _walk_shapes(shape.shapes)
