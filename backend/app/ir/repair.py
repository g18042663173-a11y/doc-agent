from __future__ import annotations

from typing import Literal, Protocol

from app.ir.errors import ValidationItem, ValidationResult
from app.ir.shell import validate_deck_ir_text, validate_word_ir_text


class RepairGenerator(Protocol):
    name: str

    def generate(self, prompt: str, *, target: str) -> str:
        """Return raw IR text. Shell extraction and validation stay outside generators."""


Target = Literal["word_ir", "deck_ir"]


def repair_ir_text(
    raw: str,
    *,
    target: Target,
    generator: RepairGenerator,
    max_retries: int = 2,
) -> ValidationResult:
    current = raw
    result = _validate(current, target)
    retries = 0
    while result.errors and retries < max_retries:
        current = generator.generate(_repair_prompt(current, result.errors), target=target)
        retries += 1
        result = _validate(current, target)
    return result


def _validate(raw: str, target: Target) -> ValidationResult:
    if target == "word_ir":
        return validate_word_ir_text(raw)
    if target == "deck_ir":
        return validate_deck_ir_text(raw)
    raise ValueError(f"unsupported target: {target}")


def _repair_prompt(raw: str, errors: list[ValidationItem]) -> str:
    error_lines = "\n".join(f"- {item.code} at {item.loc or '<root>'}: {item.message}" for item in errors)
    preview = raw[:12000]
    return (
        "上一轮输出未通过 IR Schema 校验。\n"
        "只修正这些问题、仍只输出一个 json 代码块; 不要新增 Schema 之外的字段。\n"
        f"错误清单:\n{error_lines}\n"
        f"待修正原文:\n{preview}"
    )
