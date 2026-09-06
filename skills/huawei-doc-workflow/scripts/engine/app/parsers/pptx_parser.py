from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import posixpath
import re
from xml.etree import ElementTree
import zipfile

from pptx import Presentation
from pptx.oxml.ns import qn

from app.ir.document_ir import DocumentIR
from app.parsers.errors import parser_error_boundary
from app.parsers.office_preflight import preflight_source_office
from app.parsers.source_metadata import deterministic_parsed_at
from app.parsers.text_limits import TextLimiter


@parser_error_boundary
def parse_pptx(path: Path) -> DocumentIR:
    warnings = preflight_source_office(path)
    presentation = Presentation(str(path))
    slide_summaries: list[dict] = []
    embedding_warnings, package_warnings = _embedding_warnings(path)
    warnings.extend(package_warnings)
    limiter = TextLimiter(warnings)
    image_count = 0

    for index, slide in enumerate(presentation.slides, start=1):
        shape_warnings: list[str] = []
        shape_warnings.extend(embedding_warnings.get(_slide_part_number(slide, index), []))
        shapes = list(_iter_shapes(slide.shapes, shape_warnings))
        shape_warnings.extend(_slide_warnings(slide, shapes))
        if shape_warnings:
            warnings.extend(f"slide {index}: {warning}" for warning in shape_warnings)
        image_count += _image_count(shapes)
        slide_summaries.append(
            {
                "index": index,
                "layout_name": slide.slide_layout.name,
                "title": _slide_title(slide, shapes, limiter=limiter, slide_index=index),
                "bodies": _slide_bodies(slide, shapes, limiter=limiter, slide_index=index),
                "tables": _slide_tables(slide, shapes, limiter=limiter, slide_index=index),
                "notes": _slide_notes(slide, limiter=limiter, slide_index=index),
                "shape_warnings": shape_warnings,
            }
        )

    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {
                "filename": path.name,
                "format": "pptx",
                "size_kb": round(path.stat().st_size / 1024, 2),
                "parsed_at": deterministic_parsed_at(path),
            },
            "stats": {
                "headings": sum(1 for slide in slide_summaries if slide.get("title")),
                "paragraphs": sum(len(slide.get("bodies", [])) for slide in slide_summaries),
                "tables": sum(len(slide.get("tables", [])) for slide in slide_summaries),
                "images": image_count,
            },
            "warnings": warnings,
            "content": {"slides": slide_summaries},
        }
    )


def _slide_title(
    slide,
    shapes: list | None = None,
    *,
    limiter: TextLimiter | None = None,
    slide_index: int = 1,
) -> str | None:
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None and getattr(title_shape, "has_text_frame", False):
        text = title_shape.text.strip()
        if text:
            return limiter.limit(text, loc=f"pptx slide {slide_index} title") if limiter is not None else text
    fallback = _fallback_title_shape(slide, shapes)
    if fallback is None:
        return None
    text = fallback.text.strip()
    if not text:
        return None
    # A fallback shape with several paragraphs is really a body box: only its
    # first line is title-like, the remaining paragraphs stay in the bodies.
    title = text.splitlines()[0].strip()
    if not title:
        return None
    candidates = shapes if shapes is not None else list(_iter_shapes(slide.shapes, []))
    shape_index = next((index for index, candidate in enumerate(candidates, start=1) if candidate is fallback), 0)
    loc = f"pptx slide {slide_index} fallback title shape {shape_index}"
    return limiter.limit(title, loc=loc) if limiter is not None else title


def _fallback_title_shape(slide, shapes: list | None):
    candidates = shapes if shapes is not None else list(_iter_shapes(slide.shapes, []))
    for shape in candidates:
        if getattr(shape, "has_text_frame", False) and shape.text.strip():
            return shape
    return None


def _slide_bodies(
    slide,
    shapes: list | None = None,
    *,
    limiter: TextLimiter | None = None,
    slide_index: int = 1,
) -> list[str]:
    title_shape = getattr(slide.shapes, "title", None)
    fallback_shape = None
    if title_shape is None or not getattr(title_shape, "has_text_frame", False) or not title_shape.text.strip():
        fallback_shape = _fallback_title_shape(slide, shapes)
    bodies: list[str] = []
    for shape_index, shape in enumerate(shapes if shapes is not None else _iter_shapes(slide.shapes, []), start=1):
        if shape is title_shape or shape is fallback_shape:
            # A multi-paragraph fallback title keeps its non-title paragraphs
            # as body content instead of swallowing the whole shape.
            if shape is fallback_shape and getattr(shape, "has_text_frame", False):
                parts = [part.strip() for part in shape.text.splitlines() if part.strip()]
                for part_index, part in enumerate(parts[1:], start=2):
                    bodies.append(
                        limiter.limit(
                            part,
                            loc=f"pptx slide {slide_index} shape {shape_index} paragraph {part_index}",
                        )
                        if limiter is not None
                        else part
                    )
            continue
        if getattr(shape, "has_table", False):
            continue
        if getattr(shape, "has_text_frame", False):
            text = shape.text.strip()
            if text:
                for part_index, part in enumerate((part.strip() for part in text.splitlines() if part.strip()), start=1):
                    bodies.append(
                        limiter.limit(
                            part,
                            loc=f"pptx slide {slide_index} shape {shape_index} paragraph {part_index}",
                        )
                        if limiter is not None
                        else part
                    )
        elif getattr(shape, "has_chart", False):
            chart_title = _chart_title(shape.chart)
            if chart_title and limiter is not None:
                chart_title = limiter.limit(chart_title, loc=f"pptx slide {slide_index} chart {shape_index} title")
            label = f"{chart_title} " if chart_title else ""
            bodies.append(f"[chart] {label}{shape.chart.chart_type}")
    return bodies


def _slide_tables(
    slide,
    shapes: list | None = None,
    *,
    limiter: TextLimiter | None = None,
    slide_index: int = 1,
) -> list[dict]:
    tables: list[dict] = []
    for shape_index, shape in enumerate(shapes if shapes is not None else _iter_shapes(slide.shapes, []), start=1):
        if not getattr(shape, "has_table", False):
            continue
        table = shape.table
        if not table.rows or not table.columns:
            continue
        column_count = min(len(table.columns), 12)
        if len(table.columns) > column_count and limiter is not None:
            limiter.warnings.append(f"W103: pptx slide {slide_index} table {shape_index} truncated to 12 columns")
        header = _table_row_values(
            table.rows[0],
            column_count=column_count,
            limiter=limiter,
            slide_index=slide_index,
            table_index=shape_index,
            row_index=0,
        )
        rows: list[list[str]] = []
        for row_index in range(1, min(len(table.rows), 21)):
            rows.append(
                _table_row_values(
                    table.rows[row_index],
                    column_count=column_count,
                    limiter=limiter,
                    slide_index=slide_index,
                    table_index=shape_index,
                    row_index=row_index,
                )
            )
        if len(table.rows) > 21 and limiter is not None:
            limiter.warnings.append(f"W103: pptx slide {slide_index} table {shape_index} preview truncated to 20 rows")
        tables.append({"header": header, "rows": rows})
    return tables


def _table_row_values(
    row,
    *,
    column_count: int,
    limiter: TextLimiter | None,
    slide_index: int,
    table_index: int,
    row_index: int,
) -> list[str]:
    """Extract one physical PPTX table row, expanding gridSpan cells.

    ``table.cell(row, col)`` indexes the physical tc list and ignores
    ``gridSpan``, so a header merged across columns raises IndexError and
    kills the whole file with E001. Read the row's physical cells instead and
    expand each across its grid span so the preview stays rectangular.
    """
    values: list[str] = []
    column = 0
    for cell in row.cells:
        span = max(1, int(cell._tc.get(qn("a:gridSpan")) or 1))
        text = _cell_text(
            cell,
            limiter=limiter,
            loc=f"pptx slide {slide_index} table {table_index} row {row_index} column {column + 1}",
        )
        for _ in range(span):
            values.append(text)
            column += 1
            if column >= column_count:
                break
        if column >= column_count:
            break
    values.extend([""] * (column_count - len(values)))
    return values


def _chart_title(chart) -> str | None:
    if not getattr(chart, "has_title", False):
        return None
    try:
        text = chart.chart_title.text_frame.text.strip()
    except (AttributeError, ValueError):
        return None
    return text or None


def _cell_text(cell, *, limiter: TextLimiter | None = None, loc: str = "pptx table cell") -> str:
    value = "\n".join(paragraph.text.strip() for paragraph in cell.text_frame.paragraphs if paragraph.text.strip())
    return limiter.limit(value, loc=loc) if limiter is not None else value


def _slide_notes(slide, *, limiter: TextLimiter | None = None, slide_index: int = 1) -> str | None:
    try:
        text = slide.notes_slide.notes_text_frame.text.strip()
    except (AttributeError, ValueError):
        return None
    if text and limiter is not None:
        return limiter.limit(text, loc=f"pptx slide {slide_index} notes")
    return text or None


def _slide_warnings(slide, shapes: list) -> list[str]:
    xml = slide.element.xml
    warnings: list[str] = []
    if "<p:transition" in xml:
        warnings.append("transition unsupported")
    if "<p:timing" in xml:
        warnings.append("animation timing unsupported")
    if "dgm:" in xml or "<dgm:" in xml:
        warnings.append("SmartArt unsupported")
    if "<p:oleObj" in xml:
        warnings.append("embedded/OLE object unsupported; binary skipped")
    for shape in shapes:
        if "PICTURE" in str(getattr(shape, "shape_type", "")):
            warnings.append(f"image present width={_emu_to_inches(shape.width):.2f}in height={_emu_to_inches(shape.height):.2f}in")
    return warnings


def _image_count(shapes: list) -> int:
    return sum(1 for shape in shapes if "PICTURE" in str(getattr(shape, "shape_type", "")))


def _iter_shapes(shapes: Iterable, shape_warnings: list[str]) -> Iterable:
    try:
        iterator = iter(shapes)
    except Exception:
        shape_warnings.append("group shape traversal failed; child shapes skipped")
        return
    while True:
        try:
            shape = next(iterator)
        except StopIteration:
            return
        except Exception:
            shape_warnings.append("group shape traversal failed; child shapes skipped")
            return
        yield shape
        try:
            child_shapes = getattr(shape, "shapes", None)
            if child_shapes is not None:
                yield from _iter_shapes(child_shapes, shape_warnings)
        except Exception:
            shape_warnings.append("group shape traversal failed; child shapes skipped")


def _slide_part_number(slide, fallback: int) -> int:
    partname = getattr(getattr(slide, "part", None), "partname", None)
    if partname is not None:
        match = re.search(r"slide(\d+)\.xml$", str(partname))
        if match is not None:
            return int(match.group(1))
    return fallback


def _emu_to_inches(value) -> float:
    try:
        return int(value) / 914400
    except (TypeError, ValueError):
        return 0.0


def _embedding_warnings(path: Path) -> tuple[dict[int, list[str]], list[str]]:
    by_slide: dict[int, list[str]] = {}
    package_warnings: list[str] = []
    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        embedding_parts = {name for name in names if name.startswith("ppt/embeddings/")}
        referenced: set[str] = set()
        for rel_name in names:
            match = re.fullmatch(r"ppt/slides/_rels/slide(\d+)\.xml\.rels", rel_name)
            if match is None:
                continue
            slide_index = int(match.group(1))
            root = ElementTree.fromstring(package.read(rel_name))
            for relationship in root:
                target = relationship.attrib.get("Target", "")
                if "embeddings/" not in target:
                    continue
                part = posixpath.normpath(posixpath.join("ppt/slides", target))
                referenced.add(part)
                size = package.getinfo(part).file_size if part in names else 0
                by_slide.setdefault(slide_index, []).append(
                    f"embedded/OLE object unsupported at part {part}, bytes={size}; binary skipped"
                )
        for part in sorted(embedding_parts - referenced):
            package_warnings.append(
                f"pptx embedded/OLE object unsupported at unreferenced part {part}, "
                f"bytes={package.getinfo(part).file_size}; binary skipped"
            )
    return by_slide, package_warnings
