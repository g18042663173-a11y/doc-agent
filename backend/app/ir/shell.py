from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.ir.errors import ValidationItem, ValidationResult
from app.ir.validation import validate_deck_ir, validate_document_ir, validate_word_ir


class JsonExtractionError(ValueError):
    pass


FENCED_JSON_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise JsonExtractionError("empty model output")

    fenced = FENCED_JSON_RE.search(text)
    if fenced:
        return fenced.group(1).strip()

    object_text = _first_balanced_object(text)
    if object_text is None:
        raise JsonExtractionError("no JSON object found")
    return object_text


def _first_balanced_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1].strip()
    return None


def _extract_error(code: str, raw: str, message: str) -> ValidationItem:
    preview = raw[:200].replace("\n", "\\n")
    return ValidationItem(
        code=code,
        level="Error",
        loc="",
        message=f"剥壳失败: {message}; 原文前 200 字: {preview}",
        suggestion="确认模型只输出一个 json 代码块,且 JSON 对象未被截断。",
    )


def validate_word_ir_text(raw: str | Mapping[str, Any]) -> ValidationResult:
    if isinstance(raw, Mapping):
        return validate_word_ir(raw)
    try:
        return validate_word_ir(extract_json_text(raw))
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_extract_error("E001", raw, str(exc))])


def validate_document_ir_text(raw: str | Mapping[str, Any]) -> ValidationResult:
    if isinstance(raw, Mapping):
        return validate_document_ir(raw)
    try:
        return validate_document_ir(extract_json_text(raw))
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_extract_error("E001", raw, str(exc))])


def validate_deck_ir_text(raw: str | Mapping[str, Any]) -> ValidationResult:
    if isinstance(raw, Mapping):
        return validate_deck_ir(raw)
    try:
        return validate_deck_ir(extract_json_text(raw))
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_extract_error("D001", raw, str(exc))])
