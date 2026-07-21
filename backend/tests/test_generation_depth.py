from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PY_ENV = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}


def _document_payload() -> dict:
    return {
        "ir_type": "document",
        "ir_version": "1.2",
        "source": {
            "filename": "技术报告.docx",
            "format": "docx",
            "size_kb": 12.5,
            "parsed_at": "2026-07-11T00:00:00Z",
        },
        "stats": {"headings": 2, "paragraphs": 1, "tables": 1, "images": 0},
        "warnings": [],
        "content": {
            "outline": [
                {"level": 1, "text": "技术报告"},
                {"level": 3, "text": "链路指标"},
            ],
            "blocks": [
                {"type": "heading", "level": 1, "text": "技术报告"},
                {"type": "paragraph", "text": "采用预测模型完成链路评估"},
                {"type": "table", "header": ["指标", "结果"], "rows": [["NMSE", "-10dB"]]},
            ],
        },
    }


def test_measure_document_uses_parser_counts_depth_tables_and_content_chars() -> None:
    from app.generation.analysis import measure_document
    from app.ir.document_ir import DocumentIR

    metrics = measure_document(DocumentIR.model_validate(_document_payload()))

    assert metrics.title_count == 2
    assert metrics.max_heading_depth == 3
    assert metrics.table_count == 1
    assert metrics.character_count == len("技术报告采用预测模型完成链路评估指标结果NMSE-10dB")


def test_analysis_validation_rejects_model_that_changes_measured_facts() -> None:
    from app.generation.analysis import AnalysisMetrics, validate_analysis_text

    expected = AnalysisMetrics(title_count=8, max_heading_depth=3, table_count=2, character_count=5200)
    raw = json.dumps(
        {
            "analysis_version": "1.0",
            "source_filename": "技术报告.docx",
            "metrics": {
                "title_count": 3,
                "max_heading_depth": 2,
                "table_count": 0,
                "character_count": 100,
            },
            "tiers": [
                {"depth": "概览", "min_pages": 6, "max_pages": 8, "coverage": "核心结论"},
                {"depth": "标准", "min_pages": 10, "max_pages": 12, "coverage": "主要章节"},
                {"depth": "详细", "min_pages": 14, "max_pages": 18, "coverage": "方法、数据和权衡"},
            ],
            "recommended_depth": "标准",
            "recommended_reason": "标题较多。",
        },
        ensure_ascii=False,
    )

    result = validate_analysis_text(raw, expected_metrics=expected)

    assert not result.ok
    assert result.errors[0].code == "D004"
    assert "实测" in result.errors[0].message


def test_analyze_cli_stub_prints_recommendation_and_only_writes_analysis(tmp_path: Path) -> None:
    output = tmp_path / "analysis.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/analyze.py",
            "samples/input/parser_samples/docx_sample_01.docx",
            "--generator",
            "stub",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["analysis_version"] == "1.0"
    assert payload["metrics"]["title_count"] >= 1
    assert [tier["depth"] for tier in payload["tiers"]] == ["概览", "标准", "详细"]
    assert "文件规模摘要" in result.stdout
    assert "概览" in result.stdout and "标准" in result.stdout and "详细" in result.stdout
    assert "推荐" in result.stdout
    assert sorted(path.name for path in tmp_path.iterdir()) == ["analysis.json"]


def test_generation_options_use_standard_when_only_pages_are_given() -> None:
    from app.generation.depth import GenerationOptions

    options = GenerationOptions(pages=9)

    assert options.enabled
    assert options.effective_depth == "标准"
    assert options.target_pages == 9
    assert GenerationOptions().enabled is False


def test_generate_cli_standard_and_detailed_stub_use_expected_page_counts(tmp_path: Path) -> None:
    outputs: dict[str, Path] = {}
    for depth, expected_pages in (("标准", 11), ("详细", 16)):
        output_dir = tmp_path / depth
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate.py",
                "samples/input/parser_samples/docx_sample_01.docx",
                "--generator",
                "stub",
                "--depth",
                depth,
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=PY_ENV,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        deck = json.loads((output_dir / "deck_ir.json").read_text(encoding="utf-8"))
        manifest = json.loads((output_dir / "generation_manifest.json").read_text(encoding="utf-8"))
        assert len(deck["slides"]) == expected_pages
        assert manifest["depth"] == depth
        assert manifest["target_pages"] == expected_pages
        outputs[depth] = output_dir

    assert json.loads((outputs["标准"] / "generation_manifest.json").read_text(encoding="utf-8"))["segmented"] is False
    detailed_manifest = json.loads(
        (outputs["详细"] / "generation_manifest.json").read_text(encoding="utf-8")
    )
    assert detailed_manifest["segmented"] is True
    assert detailed_manifest["chunk_count"] >= 3
    assert (outputs["详细"] / "prompts" / "outline.txt").exists()


def test_generate_cli_pages_override_depth_default_target(tmp_path: Path) -> None:
    output_dir = tmp_path / "nine-pages"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/generate.py",
            "samples/input/parser_samples/md_sample_01.md",
            "--generator",
            "stub",
            "--depth",
            "概览",
            "--pages",
            "9",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        env=PY_ENV,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    deck = json.loads((output_dir / "deck_ir.json").read_text(encoding="utf-8"))
    assert len(deck["slides"]) == 9


def test_generate_cli_without_depth_matches_existing_demo_output(tmp_path: Path) -> None:
    source = "samples/input/parser_samples/md_sample_01.md"
    generated_dir = tmp_path / "generate"
    demo_dir = tmp_path / "demo"
    commands = [
        [sys.executable, "scripts/generate.py", source, "--generator", "stub", "--output-dir", str(generated_dir)],
        [
            sys.executable,
            "scripts/demo_e2e.py",
            source,
            "--target",
            "deck",
            "--generator",
            "stub",
            "--output-dir",
            str(demo_dir),
        ],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=PY_ENV,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    assert (generated_dir / "prompt.txt").read_bytes() == (demo_dir / "prompt.txt").read_bytes()
    assert (generated_dir / "raw_ir.txt").read_bytes() == (demo_dir / "raw_ir.txt").read_bytes()
    assert (generated_dir / "deck_ir.json").read_bytes() == (demo_dir / "deck_ir.json").read_bytes()
    assert not (generated_dir / "generation_manifest.json").exists()


def test_detailed_generation_repairs_truncated_outline_and_wrong_chunk_page_count() -> None:
    from app.generation.depth import (
        CHUNK_MARKER,
        OUTLINE_MARKER,
        GenerationOptions,
        generate_deck,
        stub_chunk_payload,
        stub_outline_payload,
    )
    from app.generators.stub import _json_after_marker
    from app.ir.document_ir import DocumentIR

    document = DocumentIR.model_validate(_document_payload())

    class DirtyGenerator:
        name = "dirty"

        def __init__(self) -> None:
            self.planning: dict | None = None
            self.pending_chunk: dict | None = None
            self.outline_repaired = False
            self.chunk_repaired = False

        def generate(self, prompt: str, *, target: str) -> str:
            if target == "analysis" and OUTLINE_MARKER in prompt:
                self.planning = _json_after_marker(prompt, OUTLINE_MARKER)
                return '{"title":"截断大纲","pages":['
            if target == "analysis":
                self.outline_repaired = True
                return json.dumps(stub_outline_payload(self.planning or {}), ensure_ascii=False)
            if CHUNK_MARKER in prompt:
                self.pending_chunk = _json_after_marker(prompt, CHUNK_MARKER)
                payload = stub_chunk_payload(self.pending_chunk or {})
                if not self.chunk_repaired:
                    payload["slides"] = payload["slides"][:-1]
                    return json.dumps(payload, ensure_ascii=False)
                return json.dumps(payload, ensure_ascii=False)
            self.chunk_repaired = True
            return json.dumps(stub_chunk_payload(self.pending_chunk or {}), ensure_ascii=False)

    generator = DirtyGenerator()
    attempt = generate_deck(
        document,
        generator=generator,  # type: ignore[arg-type]
        options=GenerationOptions(depth="详细", pages=8),
    )

    assert attempt.validation.ok
    assert attempt.validation.value is not None
    assert len(attempt.validation.value.slides) == 8
    assert generator.outline_repaired
    assert generator.chunk_repaired
    assert {event["stage"] for event in attempt.repair_events} == {"outline", "chunk-01"}
    assert attempt.repair_events[0]["initial_error_codes"] == ["D001"]
    assert attempt.repair_events[1]["initial_error_codes"] == ["D006"]


def test_detailed_stub_generation_uses_outline_text_as_title_and_preserves_facts() -> None:
    from app.generation.depth import GenerationOptions, generate_deck
    from app.generators.stub import StubGenerator
    from app.ir.document_ir import DocumentIR

    attempt = generate_deck(
        DocumentIR.model_validate(_document_payload()),
        generator=StubGenerator(),
        options=GenerationOptions(depth="详细", pages=8),
    )

    assert attempt.validation.ok and attempt.validation.value is not None
    deck = attempt.validation.value
    serialized = deck.model_dump_json()
    assert deck.meta.title == "技术报告"
    assert deck.slides[0].title == "技术报告"
    assert "{'level':" not in serialized
    assert "NMSE" in serialized and "-10dB" in serialized


def test_detailed_focus_keeps_nested_section_evidence_and_excludes_next_peer_section() -> None:
    from app.generation.depth import OutlinePage, _focused_context
    from app.ir.document_ir import DocumentIR

    payload = _document_payload()
    payload["stats"] = {"headings": 4, "paragraphs": 4, "tables": 1, "images": 0}
    payload["warnings"] = ["long parser diagnostic " + "x" * 500 for _ in range(20)]
    payload["content"] = {
        "outline": [
            {"level": 1, "text": "方案A"},
            {"level": 2, "text": "模型设计"},
            {"level": 3, "text": "性能结果"},
            {"level": 1, "text": "方案B"},
        ],
        "blocks": [
            {"type": "heading", "level": 1, "text": "方案A"},
            {"type": "paragraph", "text": "总体采用CNN-LSTM。"},
            {"type": "heading", "level": 2, "text": "模型设计"},
            {"type": "paragraph", "text": "CNN提取局部特征，LSTM建模时序依赖。"},
            {"type": "heading", "level": 3, "text": "性能结果"},
            {"type": "table", "header": ["指标", "结果"], "rows": [["NMSE", "-10dB"]]},
            {"type": "heading", "level": 1, "text": "方案B"},
            {"type": "paragraph", "text": "不应进入方案A上下文。"},
        ],
    }
    document = DocumentIR.model_validate(payload)
    page = OutlinePage(
        index=4,
        layout="title_bullets",
        title="方案A具备方法与数据支撑",
        focus="展开方案A",
        source_headings=["方案A"],
        source_evidence=["CNN-LSTM", "NMSE -10dB"],
        selection_reason="观点页展开方法与数据",
        content_budget=3,
    )

    focused = _focused_context(document, [page])
    text = focused.model_dump_json()

    assert "CNN提取局部特征" in text
    assert "NMSE" in text and "-10dB" in text
    assert "方案B" not in text
    assert "不应进入方案A上下文" not in text
    assert focused.warnings == [
        "focused generation context omitted 20 parser warnings; see persisted document_ir.json"
    ]


def test_outline_requires_page_plan_semantics_and_rejects_repetitive_body() -> None:
    from app.generation.depth import validate_outline_text

    pages = [
        {
            "index": 1,
            "layout": "cover",
            "title": "方案结论",
            "focus": "建立评审目标",
            "source_headings": ["技术报告"],
            "source_evidence": ["技术报告"],
            "selection_reason": "封面建立主题",
            "content_budget": 1,
        },
        *[
            {
                "index": index,
                "layout": "title_bullets",
                "title": f"第{index}项判断",
                "focus": "说明一个判断",
                "source_headings": ["链路指标"],
                "source_evidence": ["NMSE -10dB"],
                "selection_reason": "观点页承载结论与依据",
                "content_budget": 3,
            }
            for index in range(2, 8)
        ],
        {
            "index": 8,
            "layout": "conclusion",
            "title": "结论可复核",
            "focus": "收束结论",
            "source_headings": ["技术报告"],
            "source_evidence": ["NMSE -10dB"],
            "selection_reason": "结论页汇总行动",
            "content_budget": 3,
        },
    ]

    result = validate_outline_text(json.dumps({"title": "方案", "pages": pages}, ensure_ascii=False), expected_pages=8)

    assert not result.ok
    assert result.errors[0].code == "D002"
    assert "连续 3 页" in result.errors[0].message


def test_stub_outline_applies_page_rhythm_and_records_selection_evidence() -> None:
    from app.generation.depth import stub_outline_payload

    short = stub_outline_payload(
        {
            "target_pages": 6,
            "source_title": "技术报告",
            "source_outline": [{"level": 1, "text": "技术报告"}],
        }
    )
    standard = stub_outline_payload(
        {
            "target_pages": 10,
            "source_title": "技术报告",
            "source_outline": [
                {"level": 1, "text": "方案设计"},
                {"level": 2, "text": "链路指标"},
                {"level": 1, "text": "验证结论"},
            ],
        }
    )

    assert "agenda" not in {page["layout"] for page in short["pages"]}
    assert "section" not in {page["layout"] for page in short["pages"]}
    assert standard["pages"][1]["layout"] == "agenda"
    assert "section" in {page["layout"] for page in standard["pages"]}
    assert {"process_flow", "timeline"}.isdisjoint({page["layout"] for page in standard["pages"]})
    assert all(
        {"layout", "focus", "source_evidence", "selection_reason", "content_budget"} <= set(page)
        for page in standard["pages"]
    )
    assert all(1 <= page["content_budget"] <= 3 for page in standard["pages"])


def test_stub_selects_sequence_layout_only_with_source_evidence() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    def deck_for(blocks: list[dict]) -> DeckIR:
        payload = _document_payload()
        payload["content"]["blocks"] = blocks
        payload["content"]["outline"] = [{"level": 1, "text": "实施计划"}]
        document = DocumentIR.model_validate(payload)
        raw = StubGenerator().generate(build_prompt(kind="deck", context=document), target="deck_ir")
        return DeckIR.model_validate_json(raw)

    neutral = deck_for([{"type": "paragraph", "text": "方案具备明确指标和验证结论。"}])
    process = deck_for(
        [
            {"type": "heading", "level": 1, "text": "实施步骤"},
            {
                "type": "numbered_list",
                "items": [
                    {"text": "准备样例", "level": 1},
                    {"text": "执行验证", "level": 1},
                    {"text": "完成复核", "level": 1},
                ],
            },
        ]
    )
    timeline = deck_for(
        [
            {"type": "paragraph", "text": "2026 Q1 冻结基线。"},
            {"type": "paragraph", "text": "2026 Q2 完成验证。"},
            {"type": "paragraph", "text": "2026 Q3 进入交付。"},
        ]
    )

    assert {"process_flow", "timeline"}.isdisjoint({slide.layout for slide in neutral.slides})
    assert "process_flow" in {slide.layout for slide in process.slides}
    assert "timeline" not in {slide.layout for slide in process.slides}
    assert "timeline" in {slide.layout for slide in timeline.slides}
    assert "process_flow" not in {slide.layout for slide in timeline.slides}
    assert "准备样例" in process.model_dump_json()
    assert "2026 Q2" in timeline.model_dump_json()


def test_outline_rejects_agenda_before_seven_pages_and_section_before_ten() -> None:
    from app.generation.depth import DeckOutline
    from pydantic import ValidationError

    def page(index: int, layout: str) -> dict:
        return {
            "index": index,
            "layout": layout,
            "title": f"第{index}页形成判断",
            "focus": "单一判断",
            "source_headings": [],
            "source_evidence": [],
            "selection_reason": "匹配内容结构",
            "content_budget": 2,
        }

    with pytest.raises(ValidationError, match="agenda"):
        DeckOutline.model_validate(
            {"title": "短稿", "pages": [page(1, "cover"), page(2, "agenda"), page(3, "conclusion")]}
        )

    with pytest.raises(ValidationError, match="section"):
        DeckOutline.model_validate(
            {
                "title": "九页稿",
                "pages": [
                    page(1, "cover"),
                    page(2, "agenda"),
                    page(3, "section"),
                    page(4, "title_bullets"),
                    page(5, "two_column"),
                    page(6, "table"),
                    page(7, "cards"),
                    page(8, "chart"),
                    page(9, "conclusion"),
                ],
            }
        )
