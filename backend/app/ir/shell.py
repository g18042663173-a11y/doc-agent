from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from app.ir.errors import ValidationItem, ValidationResult
from app.ir.validation import validate_deck_ir, validate_document_ir, validate_word_ir


class JsonExtractionError(ValueError):
    pass


FENCED_JSON_RE = re.compile(r"```(?:json|JSON)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*(?:\r?\n|$)", re.DOTALL)


def extract_json_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise JsonExtractionError("empty model output")

    fenced_blocks = list(FENCED_JSON_RE.finditer(text))
    if len(fenced_blocks) > 1:
        raise JsonExtractionError("multiple JSON objects found")
    if fenced_blocks:
        fenced = fenced_blocks[0]
        candidate = _single_json_object(fenced.group(1).strip())
        outside = f"{text[:fenced.start()]} {text[fenced.end():]}"
        outside_valid, _outside_invalid, _outside_truncated = _scan_json_objects(outside)
        # Mirrors _single_json_object: a complete fenced object wins over a stray
        # unbalanced brace (e.g. a '{' in the surrounding explanation). Only a
        # genuinely complete second JSON object outside the fence is ambiguous.
        if outside_valid:
            raise JsonExtractionError("multiple JSON objects found")
        return candidate
    return _single_json_object(text)


def _single_json_object(text: str) -> str:
    valid, invalid, truncated = _scan_json_objects(text)
    if len(valid) > 1:
        raise JsonExtractionError("multiple JSON objects found")
    if len(valid) == 1:
        # A single complete object wins over any trailing prose, including an
        # unbalanced brace in the surrounding explanation.
        return valid[0]
    if truncated:
        raise JsonExtractionError("truncated JSON object")
    if invalid:
        raise JsonExtractionError(f"invalid JSON object: {invalid[0]}")
    raise JsonExtractionError("no JSON object found")


def _scan_json_objects(text: str) -> tuple[list[str], list[str], bool]:
    valid: list[str] = []
    invalid: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if depth == 0:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue
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
            if depth == 0 and start is not None:
                candidate = text[start : index + 1].strip()
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    invalid.append(exc.msg)
                else:
                    if isinstance(parsed, dict):
                        valid.append(candidate)
                    else:
                        invalid.append("top-level JSON value must be an object")
                start = None
    return valid, invalid, depth > 0


def _extract_error(code: str, raw: str, message: str) -> ValidationItem:
    preview = raw[:200].replace("\n", "\\n")
    return ValidationItem(
        code=code,
        level="Error",
        loc="",
        message=f"剥壳失败: {message}; 原文前 200 字: {preview}",
        suggestion="确认模型只输出一个完整 JSON 对象,不要使用 Markdown 围栏,且对象未被截断或重复输出。",
    )


def validate_word_ir_text(
    raw: str | Mapping[str, Any], *, reject_unknown_fields: bool = False
) -> ValidationResult:
    if isinstance(raw, Mapping):
        return validate_word_ir(raw, reject_unknown_fields=reject_unknown_fields)
    try:
        return validate_word_ir(extract_json_text(raw), reject_unknown_fields=reject_unknown_fields)
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_extract_error("E001", raw, str(exc))])


def validate_document_ir_text(raw: str | Mapping[str, Any]) -> ValidationResult:
    if isinstance(raw, Mapping):
        return validate_document_ir(raw)
    try:
        return validate_document_ir(extract_json_text(raw))
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_extract_error("E001", raw, str(exc))])


def validate_deck_ir_text(
    raw: str | Mapping[str, Any], *, reject_unknown_fields: bool = False
) -> ValidationResult:
    if isinstance(raw, Mapping):
        return validate_deck_ir(raw, reject_unknown_fields=reject_unknown_fields)
    try:
        return validate_deck_ir(extract_json_text(raw), reject_unknown_fields=reject_unknown_fields)
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_extract_error("D001", raw, str(exc))])
