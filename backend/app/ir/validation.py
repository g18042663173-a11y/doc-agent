from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from app.ir.common import (
    BulletListBlock,
    HeadingBlock,
    ImagePlaceholderBlock,
    NumberedListBlock,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)
from app.ir.deck_ir import (
    AgendaSlide,
    ArchitectureDiagramSlide,
    ArchitectureEdge,
    ArchitectureGroup,
    ArchitectureManualHints,
    ArchitectureNode,
    CardsSlide,
    ChartSlide,
    ChartSeries,
    ChartSideTable,
    ChartSpec,
    ChartThreshold,
    ConclusionSlide,
    CoverSlide,
    DeckTable,
    DeckTableCell,
    DeckIR,
    DiagramPosition,
    DiagramSize,
    ImageSlide,
    SectionSlide,
    TableSlide,
    TitleBulletsSlide,
    TwoColumnSlide,
)
from app.ir.document_ir import DocumentIR
from app.ir.document_ir import DocumentContent, DocumentSource, DocumentStats
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.word_ir import WordIR, WordMeta


MAX_WORD_TEXT_CHARS = 2000


WORD_BLOCK_MODELS: dict[str, Type[BaseModel]] = {
    "heading": HeadingBlock,
    "paragraph": ParagraphBlock,
    "bullet_list": BulletListBlock,
    "numbered_list": NumberedListBlock,
    "table": TableBlock,
    "image_placeholder": ImagePlaceholderBlock,
    "page_break": PageBreakBlock,
}

DECK_SLIDE_MODELS: dict[str, Type[BaseModel]] = {
    "cover": CoverSlide,
    "agenda": AgendaSlide,
    "section": SectionSlide,
    "title_bullets": TitleBulletsSlide,
    "two_column": TwoColumnSlide,
    "table": TableSlide,
    "cards": CardsSlide,
    "chart": ChartSlide,
    "architecture_diagram": ArchitectureDiagramSlide,
    "image": ImageSlide,
    "conclusion": ConclusionSlide,
}


def _parse_raw(raw: str | Mapping[str, Any], json_code: str) -> tuple[dict[str, Any] | None, list[ValidationItem]]:
    if isinstance(raw, Mapping):
        return dict(raw), []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [
            ValidationItem(
                code=json_code,
                level="Error",
                loc="",
                message=f"无法解析为 JSON: {exc.msg}",
                suggestion="检查是否存在尾逗号、截断内容或多个混杂代码块。",
            )
        ]
    if not isinstance(parsed, dict):
        return None, [
            ValidationItem(
                code=json_code,
                level="Error",
                loc="",
                message="IR 顶层必须是 JSON 对象。",
            )
        ]
    return parsed, []


def _warning_unknown(loc: str) -> ValidationItem:
    return ValidationItem(
        code="W104",
        level="Warning",
        loc=loc,
        message="未知字段已忽略。",
        suggestion="若这是新契约字段,先升 ir_version 并更新 Schema 与样例。",
    )


def _warning(code: str, loc: str, message: str, suggestion: str | None = None) -> ValidationItem:
    return ValidationItem(code=code, level="Warning", loc=loc, message=message, suggestion=suggestion)


def _info(code: str, loc: str, message: str, suggestion: str | None = None) -> ValidationItem:
    return ValidationItem(code=code, level="Info", loc=loc, message=message, suggestion=suggestion)


def _loc(parts: tuple[Any, ...] | list[Any]) -> str:
    text = ""
    for part in parts:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}" if text else str(part)
    return text


def _unknown_fields(data: Mapping[str, Any], allowed: set[str], prefix: str = "") -> list[ValidationItem]:
    warnings: list[ValidationItem] = []
    for key in data:
        if key not in allowed:
            warnings.append(_warning_unknown(f"{prefix}.{key}" if prefix else str(key)))
    return warnings


def _model_input_fields(model: Type[BaseModel]) -> set[str]:
    fields: set[str] = set()
    for name, field in model.model_fields.items():
        fields.add(field.alias or name)
    return fields


def _collect_word_unknowns(data: Mapping[str, Any]) -> list[ValidationItem]:
    warnings = _unknown_fields(data, set(WordIR.model_fields))
    meta = data.get("meta")
    if isinstance(meta, Mapping):
        warnings.extend(_unknown_fields(meta, set(WordMeta.model_fields), "meta"))
    blocks = data.get("blocks")
    if isinstance(blocks, list):
        for index, block in enumerate(blocks):
            if not isinstance(block, Mapping):
                continue
            block_type = block.get("type")
            model = WORD_BLOCK_MODELS.get(str(block_type))
            if model is None:
                continue
            block_prefix = f"blocks[{index}]"
            warnings.extend(_unknown_fields(block, set(model.model_fields), block_prefix))
    return warnings


def _collect_deck_unknowns(data: Mapping[str, Any]) -> list[ValidationItem]:
    warnings = _unknown_fields(data, set(DeckIR.model_fields))
    meta = data.get("meta")
    if isinstance(meta, Mapping):
        warnings.extend(_unknown_fields(meta, set(DeckIR.model_fields["meta"].annotation.model_fields), "meta"))
    slides = data.get("slides")
    if isinstance(slides, list):
        for index, slide in enumerate(slides):
            if not isinstance(slide, Mapping):
                continue
            layout = slide.get("layout")
            model = DECK_SLIDE_MODELS.get(str(layout))
            if model is None:
                continue
            slide_prefix = f"slides[{index}]"
            warnings.extend(_unknown_fields(slide, set(model.model_fields), slide_prefix))
            table = slide.get("table")
            if layout == "table" and isinstance(table, Mapping):
                warnings.extend(_unknown_fields(table, set(DeckTable.model_fields), f"{slide_prefix}.table"))
                rows = table.get("rows")
                if isinstance(rows, list):
                    for row_index, row in enumerate(rows):
                        if not isinstance(row, list):
                            continue
                        for col_index, cell in enumerate(row):
                            if isinstance(cell, Mapping):
                                warnings.extend(
                                    _unknown_fields(
                                        cell,
                                        set(DeckTableCell.model_fields),
                                        f"{slide_prefix}.table.rows[{row_index}][{col_index}]",
                                    )
                                )
            chart = slide.get("chart")
            if layout == "chart" and isinstance(chart, Mapping):
                chart_prefix = f"{slide_prefix}.chart"
                warnings.extend(_unknown_fields(chart, set(ChartSpec.model_fields), chart_prefix))
                series_items = chart.get("series")
                if isinstance(series_items, list):
                    for series_index, series in enumerate(series_items):
                        if isinstance(series, Mapping):
                            warnings.extend(_unknown_fields(series, set(ChartSeries.model_fields), f"{chart_prefix}.series[{series_index}]"))
                thresholds = chart.get("thresholds")
                if isinstance(thresholds, list):
                    for threshold_index, threshold in enumerate(thresholds):
                        if isinstance(threshold, Mapping):
                            warnings.extend(_unknown_fields(threshold, set(ChartThreshold.model_fields), f"{chart_prefix}.thresholds[{threshold_index}]"))
                side_table = chart.get("side_table")
                if isinstance(side_table, Mapping):
                    warnings.extend(_unknown_fields(side_table, set(ChartSideTable.model_fields), f"{chart_prefix}.side_table"))
            if layout == "architecture_diagram":
                nodes = slide.get("nodes")
                if isinstance(nodes, list):
                    for node_index, node in enumerate(nodes):
                        if not isinstance(node, Mapping):
                            continue
                        node_prefix = f"{slide_prefix}.nodes[{node_index}]"
                        warnings.extend(_unknown_fields(node, _model_input_fields(ArchitectureNode), node_prefix))
                        position = node.get("position")
                        if isinstance(position, Mapping):
                            warnings.extend(_unknown_fields(position, _model_input_fields(DiagramPosition), f"{node_prefix}.position"))
                        size = node.get("size")
                        if isinstance(size, Mapping):
                            warnings.extend(_unknown_fields(size, _model_input_fields(DiagramSize), f"{node_prefix}.size"))
                edges = slide.get("edges")
                if isinstance(edges, list):
                    for edge_index, edge in enumerate(edges):
                        if isinstance(edge, Mapping):
                            warnings.extend(
                                _unknown_fields(
                                    edge,
                                    _model_input_fields(ArchitectureEdge),
                                    f"{slide_prefix}.edges[{edge_index}]",
                                )
                            )
                groups = slide.get("groups")
                if isinstance(groups, list):
                    for group_index, group in enumerate(groups):
                        if isinstance(group, Mapping):
                            warnings.extend(
                                _unknown_fields(
                                    group,
                                    _model_input_fields(ArchitectureGroup),
                                    f"{slide_prefix}.groups[{group_index}]",
                                )
                            )
                manual_hints = slide.get("manual_hints")
                if isinstance(manual_hints, Mapping):
                    manual_prefix = f"{slide_prefix}.manual_hints"
                    warnings.extend(_unknown_fields(manual_hints, _model_input_fields(ArchitectureManualHints), manual_prefix))
                    for field_name, model in (("node_positions", DiagramPosition), ("node_sizes", DiagramSize)):
                        hints = manual_hints.get(field_name)
                        if not isinstance(hints, Mapping):
                            continue
                        for node_id, hint in hints.items():
                            if isinstance(hint, Mapping):
                                warnings.extend(
                                    _unknown_fields(
                                        hint,
                                        _model_input_fields(model),
                                        f"{manual_prefix}.{field_name}.{node_id}",
                                    )
                                )
    return warnings


def _collect_document_unknowns(data: Mapping[str, Any]) -> list[ValidationItem]:
    warnings = _unknown_fields(data, set(DocumentIR.model_fields))
    source = data.get("source")
    if isinstance(source, Mapping):
        warnings.extend(_unknown_fields(source, set(DocumentSource.model_fields), "source"))
    stats = data.get("stats")
    if isinstance(stats, Mapping):
        warnings.extend(_unknown_fields(stats, set(DocumentStats.model_fields), "stats"))
    content = data.get("content")
    if isinstance(content, Mapping):
        warnings.extend(_unknown_fields(content, set(DocumentContent.model_fields), "content"))
        blocks = content.get("blocks")
        if isinstance(blocks, list):
            for index, block in enumerate(blocks):
                if not isinstance(block, Mapping):
                    continue
                block_type = block.get("type")
                model = WORD_BLOCK_MODELS.get(str(block_type))
                if model is None:
                    continue
                warnings.extend(_unknown_fields(block, set(model.model_fields), f"content.blocks[{index}]"))
    return warnings


def _normalize_word_data(data: Mapping[str, Any]) -> tuple[dict[str, Any], list[ValidationItem], list[ValidationItem]]:
    normalized = copy.deepcopy(dict(data))
    warnings: list[ValidationItem] = []
    infos: list[ValidationItem] = []

    meta = normalized.get("meta")
    if isinstance(meta, Mapping) and "classification" not in meta:
        infos.append(
            _info(
                "I201",
                "meta.classification",
                "未提供 classification,已使用默认密级文案。",
                "如需其它密级,在 meta.classification 中显式提供。",
            )
        )

    blocks = normalized.get("blocks")
    if not isinstance(blocks, list):
        return normalized, warnings, infos

    repaired_blocks: list[Any] = []
    previous_heading_level = 0
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            repaired_blocks.append(block)
            continue
        block_type = block.get("type")
        if block_type == "paragraph":
            text = block.get("text")
            if isinstance(text, str) and not text.strip():
                warnings.append(
                    _warning(
                        "W102",
                        f"blocks[{index}]",
                        "空段落已自动跳过。",
                        "删除空 paragraph,或填写实际正文。",
                    )
                )
                continue
            _truncate_text_field(block, "text", f"blocks[{index}].text", warnings)
        elif block_type == "heading":
            level = block.get("level")
            if isinstance(level, int) and 1 <= level <= 4:
                allowed = previous_heading_level + 1 if previous_heading_level else 1
                if level > allowed:
                    block["level"] = allowed
                    warnings.append(
                        _warning(
                            "W101",
                            f"blocks[{index}].level",
                            f"标题层级从 {level} 降为 {allowed},避免跳级。",
                            "按 1、2、3、4 的顺序组织标题层级。",
                        )
                    )
                previous_heading_level = block["level"]
        elif block_type == "table":
            _truncate_sequence(block.get("header"), f"blocks[{index}].header", warnings)
            rows = block.get("rows")
            if isinstance(rows, list):
                for row_index, row in enumerate(rows):
                    _truncate_sequence(row, f"blocks[{index}].rows[{row_index}]", warnings)
        repaired_blocks.append(block)
    normalized["blocks"] = repaired_blocks
    return normalized, warnings, infos


def _truncate_sequence(value: Any, loc: str, warnings: list[ValidationItem]) -> None:
    if not isinstance(value, list):
        return
    for index, item in enumerate(value):
        if isinstance(item, str) and len(item) > MAX_WORD_TEXT_CHARS:
            value[index] = item[:MAX_WORD_TEXT_CHARS]
            warnings.append(
                _warning(
                    "W103",
                    f"{loc}[{index}]",
                    "单元格 / 段落超长已按上限截断。",
                    f"控制在 {MAX_WORD_TEXT_CHARS} 字以内,或拆分为多个段落 / 单元格。",
                )
            )


def _truncate_text_field(block: dict[str, Any], field: str, loc: str, warnings: list[ValidationItem]) -> None:
    value = block.get(field)
    if isinstance(value, str) and len(value) > MAX_WORD_TEXT_CHARS:
        block[field] = value[:MAX_WORD_TEXT_CHARS]
        warnings.append(
            _warning(
                "W103",
                loc,
                "单元格 / 段落超长已按上限截断。",
                f"控制在 {MAX_WORD_TEXT_CHARS} 字以内,或拆分为多个段落 / 单元格。",
            )
        )


def _word_item(error: dict[str, Any]) -> ValidationItem:
    loc = _loc(error.get("loc", ()))
    message = str(error.get("msg", "校验失败"))
    error_type = str(error.get("type", ""))

    if loc in {"meta.title", "meta"} or "meta.title" in loc:
        code = "E002"
    elif error_type == "union_tag_invalid" or "Input tag" in message:
        code = "E003"
    elif _is_word_table_error(loc, message):
        code = "E004"
    elif "level" in loc:
        code = "E005"
    elif loc == "blocks" or loc.endswith(".items") or "items" in loc:
        code = "E006"
    elif "image_placeholder" in loc or "image_placeholder" in message:
        code = "E006"
    else:
        code = "E001"

    return ValidationItem(code=code, level="Error", loc=loc, message=message)


def _is_word_table_error(loc: str, message: str) -> bool:
    table_terms = ("header", "rows", "col_widths", "column", "table")
    return any(term in loc for term in table_terms) or any(term in message for term in table_terms)


def _deck_item(error: dict[str, Any]) -> ValidationItem:
    loc = _loc(error.get("loc", ()))
    message = str(error.get("msg", "校验失败"))
    error_type = str(error.get("type", ""))

    if loc in {"meta.title", "meta"} or "meta.title" in loc:
        code = "D002"
    elif error_type == "union_tag_invalid" or "Input tag" in message:
        code = "D003"
    elif any(term in loc for term in ("table", "rows", "header", "col_widths", "column_groups", "row_groups", "cell_spans", "conclusion_col")):
        code = "D005"
    elif "bullets" in loc:
        code = "D006"
    elif error_type == "missing":
        code = "D004"
    else:
        code = "D004"

    return ValidationItem(code=code, level="Error", loc=loc, message=message)


def _normalize_deck_data(data: Mapping[str, Any]) -> tuple[dict[str, Any], list[ValidationItem]]:
    normalized = copy.deepcopy(dict(data))
    warnings: list[ValidationItem] = []
    slides = normalized.get("slides")
    if not isinstance(slides, list):
        return normalized, warnings
    for slide_index, slide in enumerate(slides):
        if not isinstance(slide, dict) or slide.get("layout") != "table":
            continue
        table = slide.get("table")
        if not isinstance(table, dict):
            continue
        header = table.get("header")
        rows = table.get("rows")
        if not isinstance(header, list) or not header or not isinstance(rows, list):
            continue
        evidence, indexes = _one_based_table_index_evidence(table, len(header), len(rows))
        if not evidence:
            continue
        loc = f"slides[{slide_index}].table"
        if indexes and all(index >= 1 for index in indexes):
            _shift_table_indexes_to_zero_based(table)
            warnings.append(
                _warning(
                    "D005",
                    loc,
                    "检测到整张表疑似使用 1 起始索引,已统一转换为 0 起始索引。",
                    "后续输出请直接使用 0 起始索引；span/rowspan/colspan 始终表示数量。",
                )
            )
        else:
            warnings.append(
                _warning(
                    "D005",
                    loc,
                    "检测到表格疑似混用 0 起始与 1 起始索引,未自动转换。",
                    "统一改为 0 起始索引后重试；span/rowspan/colspan 保持数量语义。",
                )
            )
    return normalized, warnings


def _one_based_table_index_evidence(table: Mapping[str, Any], column_count: int, row_count: int) -> tuple[bool, list[int]]:
    indexes: list[int] = []
    evidence = False

    def inspect(index: Any, span: Any, limit: int) -> None:
        nonlocal evidence
        if not isinstance(index, int) or isinstance(index, bool):
            return
        indexes.append(index)
        if (
            isinstance(span, int)
            and not isinstance(span, bool)
            and index >= 1
            and index + span > limit
            and index - 1 + span <= limit
        ):
            evidence = True

    inspect(table.get("conclusion_col"), 1, column_count)
    for group in table.get("column_groups", []):
        if isinstance(group, Mapping):
            inspect(group.get("start_col"), group.get("span"), column_count)
    for group in table.get("row_groups", []):
        if isinstance(group, Mapping):
            inspect(group.get("start_row"), group.get("span"), row_count)
    for span in table.get("cell_spans", []):
        if not isinstance(span, Mapping):
            continue
        inspect(span.get("col"), span.get("colspan", 1), column_count)
        area_rows = 1 if span.get("area", "body") == "header" else row_count
        inspect(span.get("row"), span.get("rowspan", 1), area_rows)
    return evidence, indexes


def _shift_table_indexes_to_zero_based(table: dict[str, Any]) -> None:
    if isinstance(table.get("conclusion_col"), int) and not isinstance(table.get("conclusion_col"), bool):
        table["conclusion_col"] -= 1
    for field_name, index_name in (("column_groups", "start_col"), ("row_groups", "start_row")):
        for item in table.get(field_name, []):
            if (
                isinstance(item, dict)
                and isinstance(item.get(index_name), int)
                and not isinstance(item.get(index_name), bool)
            ):
                item[index_name] -= 1
    for span in table.get("cell_spans", []):
        if not isinstance(span, dict):
            continue
        for index_name in ("row", "col"):
            if isinstance(span.get(index_name), int) and not isinstance(span.get(index_name), bool):
                span[index_name] -= 1


def validate_word_ir(raw: str | Mapping[str, Any]) -> ValidationResult[WordIR]:
    data, parse_errors = _parse_raw(raw, "E001")
    if data is None:
        return ValidationResult(value=None, errors=parse_errors)
    warnings = _collect_word_unknowns(data)
    data, normalization_warnings, infos = _normalize_word_data(data)
    warnings.extend(normalization_warnings)
    try:
        return ValidationResult(value=WordIR.model_validate(data), warnings=warnings, infos=infos)
    except ValidationError as exc:
        return ValidationResult(value=None, errors=[_word_item(error) for error in exc.errors()], warnings=warnings, infos=infos)


def validate_document_ir(raw: str | Mapping[str, Any]) -> ValidationResult[DocumentIR]:
    data, parse_errors = _parse_raw(raw, "E001")
    if data is None:
        return ValidationResult(value=None, errors=parse_errors)
    warnings = _collect_document_unknowns(data)
    try:
        return ValidationResult(value=DocumentIR.model_validate(data), warnings=warnings)
    except ValidationError as exc:
        return ValidationResult(
            value=None,
            errors=[ValidationItem(code="E001", level="Error", loc=_loc(error.get("loc", ())), message=str(error.get("msg", "校验失败"))) for error in exc.errors()],
            warnings=warnings,
        )


def validate_deck_ir(raw: str | Mapping[str, Any]) -> ValidationResult[DeckIR]:
    data, parse_errors = _parse_raw(raw, "D001")
    if data is None:
        return ValidationResult(value=None, errors=parse_errors)
    warnings = _collect_deck_unknowns(data)
    data, normalization_warnings = _normalize_deck_data(data)
    warnings.extend(normalization_warnings)
    try:
        return ValidationResult(value=DeckIR.model_validate(data), warnings=warnings)
    except ValidationError as exc:
        return ValidationResult(value=None, errors=[_deck_item(error) for error in exc.errors()], warnings=warnings)
