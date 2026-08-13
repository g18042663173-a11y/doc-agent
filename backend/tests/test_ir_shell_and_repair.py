from __future__ import annotations

import json
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

VALID_DECK_JSON = """
{
  "ir_type": "deck",
  "ir_version": "1.9",
  "meta": {"title": "修复完成"},
  "slides": [{"layout": "cover", "title": "修复完成"}]
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


def test_extract_json_text_ignores_trailing_prose_unbalanced_brace() -> None:
    from app.ir.shell import extract_json_text

    raw = '{"value":"x"} 后续说明里有一个未闭合的花括号 {'

    assert extract_json_text(raw) == '{"value":"x"}'


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


class DeckRepairingGenerator:
    name = "deck-repairing"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str, *, target: str) -> str:
        assert target == "deck_ir"
        self.prompts.append(prompt)
        return VALID_DECK_JSON


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


@pytest.mark.parametrize(
    ("raw", "expected_code", "expected_loc"),
    [
        (
            '{"ir_type":"deck","ir_version":"1.9","meta":{"title":"拼写"},"slides":[{"layout":"cover","title":"拼写","subtitel":"错误"}]}',
            "D004",
            "slides[0].subtitel",
        ),
        (
            '{"ir_type":"deck","ir_version":"1.9","meta":{"title":"嵌套拼写"},"slides":[{"layout":"composite","title":"嵌套拼写","regions":[{"slot":"left","components":[{"layout":"table","title":"表","table":{"header":["项","值"],"rows":[["时延","18 ms"]],"colum_widths":[1,1]}}]},{"slot":"right","components":[{"layout":"title_bullets","title":"判断","bullets":[{"text":"可验证"}]}]}]}]}',
            "D005",
            "slides[0].regions[0].components[0].table.colum_widths",
        ),
        (
            '{"ir_type":"deck","ir_version":"1.9","meta":{"title":"类型拼写"},"slides":[{"layout":"architecture_diagram","title":"类型拼写","nodes":[{"id":"a","text":"模块","type":"moduel"}],"edges":[],"groups":[]}]}',
            "D004",
            "slides[0].nodes[0].type",
        ),
    ],
)
def test_repair_loop_retries_all_model_unknown_field_cases(
    raw: str, expected_code: str, expected_loc: str
) -> None:
    from app.ir.repair import repair_ir_text

    generator = DeckRepairingGenerator()
    result = repair_ir_text(raw, target="deck_ir", generator=generator, max_retries=1)

    assert result.ok
    assert len(generator.prompts) == 1
    assert expected_code in generator.prompts[0]
    assert expected_loc in generator.prompts[0]
    assert "未知字段" in generator.prompts[0] or "未知节点 type" in generator.prompts[0]


def test_stub_repair_rebuilds_deck_from_original_prompt_when_first_output_fails_page_target() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.repair import repair_ir_text

    document_payload = {
        "ir_type": "document",
        "ir_version": "1.2",
        "source": {"filename": "评审.md", "format": "md", "size_kb": 1.0, "parsed_at": "2026-01-01T00:00:00Z"},
        "stats": {"headings": 1, "paragraphs": 1, "tables": 0, "images": 0},
        "warnings": [],
        "content": {
            "outline": [{"level": 1, "text": "技术评审"}],
            "blocks": [{"type": "heading", "level": 1, "text": "技术评审"}],
        },
    }
    original_prompt = (
        "[任务] 生成 Deck。\n"
        "必须恰好生成 4 页。\n"
        "[输入 DocumentIR]\n"
        + json.dumps(document_payload, ensure_ascii=False)
        + "\n[输出纪律]\n"
    )

    class BrokenStubFirst:
        name = "broken-stub-first"

        def __init__(self) -> None:
            self.calls = 0

        def generate(self, prompt: str, *, target: str) -> str:
            self.calls += 1
            if self.calls == 1:
                return '{"ir_type":"deck","ir_version":"2.0","meta":{"title":"坏输出"},"slides":[{"layout":"cover","title":"坏输出"}]}'
            return StubGenerator().generate(prompt, target=target)

    generator = BrokenStubFirst()
    result = repair_ir_text(
        '{"ir_type":"deck","ir_version":"2.0","meta":{"title":"坏输出"},"slides":[{"layout":"cover","title":"坏输出"}]}',
        target="deck_ir",
        generator=generator,
        max_retries=2,
        expected_pages=4,
        original_prompt=original_prompt,
    )

    assert generator.calls == 2
    assert result.ok and result.value is not None
    assert len(result.value.slides) == 4
    assert result.value.meta.title == "技术评审"


def test_repair_loop_without_original_prompt_keeps_previous_behavior() -> None:
    from app.ir.repair import repair_ir_text

    generator = RepairingGenerator()
    result = repair_ir_text(
        '{"ir_type":"word","ir_version":"1.0","meta":{},"blocks":[]}',
        target="word_ir",
        generator=generator,
        max_retries=1,
    )

    assert result.ok
    assert "[原始生成提示]" not in generator.prompts[0]


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
