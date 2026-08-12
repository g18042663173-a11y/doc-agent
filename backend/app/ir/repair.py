from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol, TypeVar

from app.ir.errors import ValidationItem, ValidationResult
from app.ir.shell import validate_deck_ir_text, validate_word_ir_text


class RepairGenerator(Protocol):
    name: str

    def generate(self, prompt: str, *, target: str, cancel_event: Any | None = None) -> str:
        """Return raw IR text. Shell extraction and validation stay outside generators."""


Target = Literal["word_ir", "deck_ir"]
T = TypeVar("T")


def repair_generated_text(
    raw: str,
    *,
    target: str,
    generator: RepairGenerator,
    validator: Callable[[str], ValidationResult[T]],
    max_retries: int = 2,
    original_prompt: str | None = None,
    cancel_event: Any | None = None,
) -> ValidationResult[T]:
    current = raw
    result = validator(current)
    retries = 0
    while result.errors and retries < max_retries:
        if cancel_event is not None and cancel_event.is_set():
            break
        generate_kwargs = {} if cancel_event is None else {"cancel_event": cancel_event}
        current = generator.generate(
            _repair_prompt(current, result.errors, original_prompt=original_prompt),
            target=target,
            **generate_kwargs,
        )
        retries += 1
        result = validator(current)
    return result


def repair_ir_text(
    raw: str,
    *,
    target: Target,
    generator: RepairGenerator,
    max_retries: int = 2,
    expected_pages: int | None = None,
    original_prompt: str | None = None,
    cancel_event: Any | None = None,
) -> ValidationResult:
    return repair_generated_text(
        raw,
        target=target,
        generator=generator,
        validator=lambda current: _validate_with_page_target(current, target, expected_pages),
        max_retries=max_retries,
        original_prompt=original_prompt,
        cancel_event=cancel_event,
    )


def _validate(raw: str, target: Target) -> ValidationResult:
    if target == "word_ir":
        return validate_word_ir_text(raw, reject_unknown_fields=True)
    if target == "deck_ir":
        return validate_deck_ir_text(raw, reject_unknown_fields=True)
    raise ValueError(f"unsupported target: {target}")


def _validate_with_page_target(raw: str, target: Target, expected_pages: int | None) -> ValidationResult:
    result = _validate(raw, target)
    if target != "deck_ir" or expected_pages is None or not result.ok or result.value is None:
        return result
    actual_pages = len(result.value.slides)
    if actual_pages == expected_pages:
        return result
    return ValidationResult(
        value=None,
        errors=[
            ValidationItem(
                code="D006",
                level="Error",
                loc="slides",
                message=f"目标页数为 {expected_pages}，实际生成 {actual_pages} 页。",
                suggestion=f"返回完整 DeckIR，并把 slides 调整为恰好 {expected_pages} 页。",
            )
        ],
        warnings=result.warnings,
        infos=result.infos,
    )


def _repair_prompt(
    raw: str,
    errors: list[ValidationItem],
    *,
    original_prompt: str | None = None,
) -> str:
    error_lines = "\n".join(f"- {item.code} at {item.loc or '<root>'}: {item.message}" for item in errors[:8])
    preview = raw[:5000]
    preview_notice = "\n[原文已截到前 5000 字,请重建完整而更短的 IR。]" if len(raw) > len(preview) else ""
    parts = [
        "上一轮输出未通过 IR Schema 校验。\n"
        "只修正这些问题。只输出一个完整 JSON 对象，不要使用 Markdown 代码围栏，不要输出解释或第二个 JSON。\n"
        "若错误提示 truncated JSON object，请从头重建更短但完整的 IR，不要续写残片或猜补缺失事实。\n"
        "若错误提示 multiple JSON objects found，只保留一个符合目标 Schema 的对象。不要新增 Schema 之外的字段。\n"
        f"错误清单:\n{error_lines}",
    ]
    if original_prompt is not None:
        # Deterministic generators (stub) recover their context from the marker
        # sections of the original prompt; it must precede the raw preview so
        # the tool's own marker stays the first occurrence.
        parts.append("[原始生成提示]\n" + original_prompt)
    parts.append(f"待修正原文:\n{preview}{preview_notice}")
    return "\n".join(parts)
