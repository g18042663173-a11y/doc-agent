from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from app.ir.common import (
    BulletListBlock,
    CodeBlock,
    HeadingBlock,
    ImagePlaceholderBlock,
    ListItem,
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
    Card,
    CardsSlide,
    ChartSlide,
    ChartSeries,
    ChartSideTable,
    ChartSpec,
    ChartThreshold,
    CompositeRegion,
    CompositeSlide,
    ConclusionSlide,
    CoverSlide,
    ColumnContent,
    DeckTable,
    DeckTableCell,
    DeckIR,
    DiagramPosition,
    DiagramSize,
    ImageSlide,
    ProcessFlowSlide,
    ProcessStep,
    SectionSlide,
    TableSlide,
    TableCellSpan,
    TableColumnGroup,
    TableRowGroup,
    TitleBulletsSlide,
    TimelineMilestone,
    TimelineSlide,
    TwoColumnSlide,
    migrate_deck_payload,
)
from app.ir.document_ir import DocumentIR
from app.ir.document_ir import DocumentContent, DocumentSource, DocumentStats
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.word_ir import ControlRecord, DocumentControl, WordIR, WordMeta


MAX_WORD_TEXT_CHARS = 2000
REGISTERED_ARCHITECTURE_NODE_TYPES = frozenset({"primary", "secondary", "emphasis", "data", "job", "module"})


WORD_BLOCK_MODELS: dict[str, Type[BaseModel]] = {
    "heading": HeadingBlock,
    "paragraph": ParagraphBlock,
    "code_block": CodeBlock,
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
    "process_flow": ProcessFlowSlide,
    "timeline": TimelineSlide,
    "image": ImageSlide,
    "conclusion": ConclusionSlide,
    "composite": CompositeSlide,
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
        control = meta.get("document_control")
        if isinstance(control, Mapping):
            warnings.extend(_unknown_fields(control, set(DocumentControl.model_fields), "meta.document_control"))
            for record_name in ("prepared", "reviewed", "approved"):
                record = control.get(record_name)
                if isinstance(record, Mapping):
                    warnings.extend(
                        _unknown_fields(record, set(ControlRecord.model_fields), f"meta.document_control.{record_name}")
                    )
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


def _collect_table_unknowns(table: Mapping[str, Any], prefix: str) -> list[ValidationItem]:
    warnings = _unknown_fields(table, _model_input_fields(DeckTable), prefix)
    for field_name, model in (
        ("column_groups", TableColumnGroup),
        ("row_groups", TableRowGroup),
        ("cell_spans", TableCellSpan),
    ):
        items = table.get(field_name)
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, Mapping):
                    warnings.extend(_unknown_fields(item, _model_input_fields(model), f"{prefix}.{field_name}[{index}]"))
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
                            _model_input_fields(DeckTableCell),
                            f"{prefix}.rows[{row_index}][{col_index}]",
                        )
                    )
    return warnings


def _collect_architecture_unknowns(component: Mapping[str, Any], prefix: str) -> list[ValidationItem]:
    warnings: list[ValidationItem] = []
    nodes = component.get("nodes")
    if isinstance(nodes, list):
        for node_index, node in enumerate(nodes):
            if not isinstance(node, Mapping):
                continue
            node_prefix = f"{prefix}.nodes[{node_index}]"
            warnings.extend(_unknown_fields(node, _model_input_fields(ArchitectureNode), node_prefix))
            node_type = node.get("type")
            if isinstance(node_type, str) and node_type not in REGISTERED_ARCHITECTURE_NODE_TYPES:
                warnings.append(
                    _warning(
                        "W105",
                        f"{node_prefix}.type",
                        f'未知节点 type "{node_type}"，renderer 将回退 theme default 配色。',
                        "优先使用 primary、secondary、emphasis、data、job 或 module；自定义语义仅限人工确认的手工 IR。",
                    )
                )
            for field_name, model in (("position", DiagramPosition), ("size", DiagramSize)):
                value = node.get(field_name)
                if isinstance(value, Mapping):
                    warnings.extend(_unknown_fields(value, _model_input_fields(model), f"{node_prefix}.{field_name}"))
    for field_name, model in (("edges", ArchitectureEdge), ("groups", ArchitectureGroup)):
        items = component.get(field_name)
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, Mapping):
                    warnings.extend(_unknown_fields(item, _model_input_fields(model), f"{prefix}.{field_name}[{index}]"))
    manual_hints = component.get("manual_hints")
    if isinstance(manual_hints, Mapping):
        manual_prefix = f"{prefix}.manual_hints"
        warnings.extend(_unknown_fields(manual_hints, _model_input_fields(ArchitectureManualHints), manual_prefix))
        for field_name, model in (("node_positions", DiagramPosition), ("node_sizes", DiagramSize)):
            hints = manual_hints.get(field_name)
            if not isinstance(hints, Mapping):
                continue
            for node_id, hint in hints.items():
                if isinstance(hint, Mapping):
                    warnings.extend(_unknown_fields(hint, _model_input_fields(model), f"{manual_prefix}.{field_name}.{node_id}"))
    return warnings


def _collect_deck_component_unknowns(component: Mapping[str, Any], prefix: str) -> list[ValidationItem]:
    layout = str(component.get("layout"))
    model = DECK_SLIDE_MODELS.get(layout)
    if model is None:
        return []
    warnings = _unknown_fields(component, _model_input_fields(model), prefix)
    if layout == "table":
        table = component.get("table")
        if isinstance(table, Mapping):
            warnings.extend(_collect_table_unknowns(table, f"{prefix}.table"))
    elif layout == "architecture_diagram":
        warnings.extend(_collect_architecture_unknowns(component, prefix))
    elif layout == "title_bullets":
        bullets = component.get("bullets")
        if isinstance(bullets, list):
            for index, bullet in enumerate(bullets):
                if isinstance(bullet, Mapping):
                    warnings.extend(_unknown_fields(bullet, _model_input_fields(ListItem), f"{prefix}.bullets[{index}]"))
    elif layout == "cards":
        cards = component.get("cards")
        if isinstance(cards, list):
            for index, card in enumerate(cards):
                if isinstance(card, Mapping):
                    warnings.extend(_unknown_fields(card, _model_input_fields(Card), f"{prefix}.cards[{index}]"))
    elif layout == "two_column":
        for side in ("left", "right"):
            column = component.get(side)
            if not isinstance(column, Mapping):
                continue
            column_prefix = f"{prefix}.{side}"
            warnings.extend(_unknown_fields(column, _model_input_fields(ColumnContent), column_prefix))
            bullets = column.get("bullets")
            if isinstance(bullets, list):
                for index, bullet in enumerate(bullets):
                    if isinstance(bullet, Mapping):
                        warnings.extend(_unknown_fields(bullet, _model_input_fields(ListItem), f"{column_prefix}.bullets[{index}]"))
    elif layout == "chart":
        chart = component.get("chart")
        if isinstance(chart, Mapping):
            chart_prefix = f"{prefix}.chart"
            warnings.extend(_unknown_fields(chart, _model_input_fields(ChartSpec), chart_prefix))
            for field_name, model in (("series", ChartSeries), ("thresholds", ChartThreshold)):
                items = chart.get(field_name)
                if isinstance(items, list):
                    for index, item in enumerate(items):
                        if isinstance(item, Mapping):
                            warnings.extend(_unknown_fields(item, _model_input_fields(model), f"{chart_prefix}.{field_name}[{index}]"))
            side_table = chart.get("side_table")
            if isinstance(side_table, Mapping):
                warnings.extend(_unknown_fields(side_table, _model_input_fields(ChartSideTable), f"{chart_prefix}.side_table"))
    elif layout == "process_flow":
        steps = component.get("steps")
        if isinstance(steps, list):
            for index, step in enumerate(steps):
                if isinstance(step, Mapping):
                    warnings.extend(_unknown_fields(step, _model_input_fields(ProcessStep), f"{prefix}.steps[{index}]"))
    elif layout == "timeline":
        milestones = component.get("milestones")
        if isinstance(milestones, list):
            for index, milestone in enumerate(milestones):
                if isinstance(milestone, Mapping):
                    warnings.extend(_unknown_fields(milestone, _model_input_fields(TimelineMilestone), f"{prefix}.milestones[{index}]"))
    elif layout == "composite":
        regions = component.get("regions")
        if isinstance(regions, list):
            for region_index, region in enumerate(regions):
                if not isinstance(region, Mapping):
                    continue
                region_prefix = f"{prefix}.regions[{region_index}]"
                warnings.extend(_unknown_fields(region, _model_input_fields(CompositeRegion), region_prefix))
                components = region.get("components")
                if isinstance(components, list):
                    for component_index, nested_component in enumerate(components):
                        if isinstance(nested_component, Mapping):
                            warnings.extend(
                                _collect_deck_component_unknowns(
                                    nested_component,
                                    f"{region_prefix}.components[{component_index}]",
                                )
                            )
    return warnings


def _collect_deck_unknowns(data: Mapping[str, Any]) -> list[ValidationItem]:
    warnings = _unknown_fields(data, _model_input_fields(DeckIR))
    meta = data.get("meta")
    if isinstance(meta, Mapping):
        warnings.extend(_unknown_fields(meta, _model_input_fields(DeckIR.model_fields["meta"].annotation), "meta"))
    slides = data.get("slides")
    if isinstance(slides, list):
        for index, slide in enumerate(slides):
            if isinstance(slide, Mapping):
                warnings.extend(_collect_deck_component_unknowns(slide, f"slides[{index}]"))
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


def _strict_unknown_errors(warnings: list[ValidationItem], *, target: str) -> list[ValidationItem]:
    errors: list[ValidationItem] = []
    for warning in warnings:
        if warning.code not in {"W104", "W105"}:
            continue
        if target == "deck":
            code = "D005" if ".table" in warning.loc or ".side_table" in warning.loc else "D004"
        else:
            code = "E001"
        message = warning.message
        if warning.code == "W104":
            field_name = warning.loc.rsplit(".", 1)[-1]
            message = f'未知字段 "{field_name}" 不属于当前 IR Schema，模型输出不得携带 Schema 外字段。'
        errors.append(
            ValidationItem(
                code=code,
                level="Error",
                loc=warning.loc,
                message=message,
                suggestion=warning.suggestion or "删除该字段，或改为当前 Schema 中定义的字段名。",
            )
        )
    return errors


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


def validate_word_ir(
    raw: str | Mapping[str, Any], *, reject_unknown_fields: bool = False
) -> ValidationResult[WordIR]:
    data, parse_errors = _parse_raw(raw, "E001")
    if data is None:
        return ValidationResult(value=None, errors=parse_errors)
    warnings = _collect_word_unknowns(data)
    data, normalization_warnings, infos = _normalize_word_data(data)
    warnings.extend(normalization_warnings)
    try:
        value = WordIR.model_validate(data)
    except ValidationError as exc:
        return ValidationResult(value=None, errors=[_word_item(error) for error in exc.errors()], warnings=warnings, infos=infos)
    strict_errors = _strict_unknown_errors(warnings, target="word") if reject_unknown_fields else []
    if strict_errors:
        return ValidationResult(value=None, errors=strict_errors, warnings=warnings, infos=infos)
    return ValidationResult(value=value, warnings=warnings, infos=infos)


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


def validate_deck_ir(
    raw: str | Mapping[str, Any], *, reject_unknown_fields: bool = False
) -> ValidationResult[DeckIR]:
    data, parse_errors = _parse_raw(raw, "D001")
    if data is None:
        return ValidationResult(value=None, errors=parse_errors)
    data, migrated_from = migrate_deck_payload(data)
    warnings = _collect_deck_unknowns(data)
    if migrated_from is not None:
        warnings.append(
            _warning(
                "D004",
                "ir_version",
                f"DeckIR {migrated_from} 已在内存中兼容迁移到 1.9，并按 1.9 契约重新校验。",
                f"重新生成或序列化为 1.9 可消除该兼容提示；原始 {migrated_from} 文件不会被覆写。",
            )
        )
    data, normalization_warnings = _normalize_deck_data(data)
    warnings.extend(normalization_warnings)
    try:
        value = DeckIR.model_validate(data)
    except ValidationError as exc:
        return ValidationResult(value=None, errors=[_deck_item(error) for error in exc.errors()], warnings=warnings)
    strict_errors = _strict_unknown_errors(warnings, target="deck") if reject_unknown_fields else []
    if strict_errors:
        return ValidationResult(value=None, errors=strict_errors, warnings=warnings)
    return ValidationResult(value=value, warnings=warnings)
