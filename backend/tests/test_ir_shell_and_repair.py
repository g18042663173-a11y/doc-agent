from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


VALID_WORD_JSON = """
{
  "ir_type": "word",
  "ir_version": "1.0",
  "meta": {"title": "剥壳测试"},
  "blocks": [{"type": "paragraph", "text": "正文"}]
}
""".strip()


def test_extract_json_text_accepts_pure_json() -> None:
    from app.ir.shell import extract_json_text

    assert extract_json_text(VALID_WORD_JSON) == VALID_WORD_JSON


def test_extract_json_text_accepts_fenced_json_block() -> None:
    from app.ir.shell import extract_json_text

    raw = f"说明文字\n```json\n{VALID_WORD_JSON}\n```\n后续解释"

    assert extract_json_text(raw) == VALID_WORD_JSON


def test_extract_json_text_accepts_mixed_explanation_with_object() -> None:
    from app.ir.shell import extract_json_text

    raw = f"我将输出如下 IR:\n{VALID_WORD_JSON}\n请保存。"

    assert extract_json_text(raw) == VALID_WORD_JSON


def test_validate_word_ir_text_maps_extract_failure_to_e001() -> None:
    from app.ir.shell import validate_word_ir_text

    result = validate_word_ir_text("没有任何 JSON")

    assert result.value is None
    assert result.errors[0].code == "E001"


def test_validate_deck_ir_text_maps_extract_failure_to_d001() -> None:
    from app.ir.shell import validate_deck_ir_text

    result = validate_deck_ir_text("没有任何 JSON")

    assert result.value is None
    assert result.errors[0].code == "D001"


def test_validate_word_ir_text_validates_fenced_json() -> None:
    from app.ir.shell import validate_word_ir_text

    result = validate_word_ir_text(f"```json\n{VALID_WORD_JSON}\n```")

    assert result.ok
    assert result.value is not None
    assert result.value.meta.title == "剥壳测试"


@pytest.mark.parametrize(
    "raw",
    [
        '{"ir_type":"word","ir_version":"1.0","meta":{"title":"截断"}',
        '```json\n{"ir_type":"word","ir_version":"1.0","meta":{"title":"截断"}\n```',
        '```json\n{"ir_type":"word","ir_version":"1.0","meta":{"title":"截断"}',
    ],
)
def test_validate_word_ir_text_reports_truncated_json_without_crashing(raw: str) -> None:
    from app.ir.shell import validate_word_ir_text

    result = validate_word_ir_text(raw)

    assert result.value is None
    assert result.errors[0].code == "E001"
    assert "truncated JSON object" in result.errors[0].message


def test_validate_deck_ir_text_rejects_multiple_json_objects_as_ambiguous() -> None:
    from app.ir.shell import validate_deck_ir_text

    raw = '{"ir_type":"deck"}\n{"ir_type":"deck"}'
    result = validate_deck_ir_text(raw)

    assert result.value is None
    assert result.errors[0].code == "D001"
    assert "multiple JSON objects found" in result.errors[0].message


def test_extract_json_text_ignores_braces_inside_strings() -> None:
    from app.ir.shell import extract_json_text

    raw = '说明: {not json}\n{"value":"正文里的 { 与 } 不影响边界"}'

    assert extract_json_text(raw) == '{"value":"正文里的 { 与 } 不影响边界"}'


class RepairingGenerator:
    name = "repairing"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, target: str) -> str:
        self.prompts.append(prompt)
        return VALID_WORD_JSON


class BrokenGenerator:
    name = "broken"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, target: str) -> str:
        self.prompts.append(prompt)
        return '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}'


def test_repair_loop_retries_with_error_codes_until_valid() -> None:
    from app.ir.repair import repair_ir_text

    generator = RepairingGenerator()
    result = repair_ir_text(
        '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}',
        target="word_ir",
        generator=generator,
        max_retries=2,
    )

    assert result.ok
    assert len(generator.prompts) == 1
    assert "E002" in generator.prompts[0]
    assert "只修正这些问题" in generator.prompts[0]


def test_repair_loop_stops_after_max_retries() -> None:
    from app.ir.repair import repair_ir_text

    generator = BrokenGenerator()
    result = repair_ir_text(
        '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}',
        target="word_ir",
        generator=generator,
        max_retries=2,
    )

    assert result.value is None
    assert result.errors[0].code == "E002"
    assert len(generator.prompts) == 2


def test_repair_loop_rebuilds_truncated_output_with_compact_bare_json_prompt() -> None:
    from app.ir.repair import repair_ir_text

    generator = RepairingGenerator()
    result = repair_ir_text(
        '{"ir_type":"word","ir_version":"1.0","meta":{"title":"截断"}',
        target="word_ir",
        generator=generator,
        max_retries=2,
    )

    assert result.ok
    assert len(generator.prompts) == 1
    assert "E001" in generator.prompts[0]
    assert "truncated JSON object" in generator.prompts[0]
    assert "只输出一个完整 JSON 对象" in generator.prompts[0]
    assert "不要使用 Markdown 代码围栏" in generator.prompts[0]
    assert len(generator.prompts[0]) < 8000
