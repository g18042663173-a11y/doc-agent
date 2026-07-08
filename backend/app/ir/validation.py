from __future__ import annotations

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
    CardsSlide,
    ChartSlide,
    ConclusionSlide,
    CoverSlide,
    DeckIR,
    ImageSlide,
    SectionSlide,
    TableSlide,
    TitleBulletsSlide,
    TwoColumnSlide,
)
from app.ir.document_ir import DocumentIR
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.word_ir import WordIR, WordMeta


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
            warnings.extend(_unknown_fields(slide, set(model.model_fields), f"slides[{index}]"))
    return warnings


def _collect_document_unknowns(data: Mapping[str, Any]) -> list[ValidationItem]:
    return _unknown_fields(data, set(DocumentIR.model_fields))


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
    elif "table" in loc or "rows" in loc or "header" in loc:
        code = "D005"
    elif "bullets" in loc:
        code = "D006"
    elif error_type == "missing":
        code = "D004"
    else:
        code = "D004"

    return ValidationItem(code=code, level="Error", loc=loc, message=message)


def validate_word_ir(raw: str | Mapping[str, Any]) -> ValidationResult[WordIR]:
    data, parse_errors = _parse_raw(raw, "E001")
    if data is None:
        return ValidationResult(value=None, errors=parse_errors)
    warnings = _collect_word_unknowns(data)
    try:
        return ValidationResult(value=WordIR.model_validate(data), warnings=warnings)
    except ValidationError as exc:
        return ValidationResult(value=None, errors=[_word_item(error) for error in exc.errors()], warnings=warnings)


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
    try:
        return ValidationResult(value=DeckIR.model_validate(data), warnings=warnings)
    except ValidationError as exc:
        return ValidationResult(value=None, errors=[_deck_item(error) for error in exc.errors()], warnings=warnings)
