from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_build_prompt_is_deterministic_and_contains_schema() -> None:
    from app.parsers.md_parser import parse_markdown
    from app.prompting.builder import build_prompt

    context = parse_markdown(ROOT / "samples" / "input" / "quarterly_report.md")

    first = build_prompt(kind="word", context=context)
    second = build_prompt(kind="word", context=context)

    assert first == second
    assert "WordIR v1.2" in first
    assert '"ir_type"' in first
    assert "[输入 DocumentIR]" in first
    assert "Q3 业务汇报" in first
    assert "document_control" in first
    assert "帧头接口模块详细设计" in first


def test_build_prompt_truncates_context_and_declares_it() -> None:
    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "huge.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-08T00:00:00Z"},
            "stats": {"headings": 0, "paragraphs": 1, "tables": 0, "images": 0},
            "warnings": [],
            "content": {"blocks": [{"type": "paragraph", "text": "长文本" * 500}], "outline": []},
        }
    )

    prompt = build_prompt(kind="deck", context=context, max_context_chars=300)
    context_json = prompt.split("[输入 DocumentIR]", 1)[1].split("[字符估算]", 1)[0].strip()

    assert "DeckIR v2.1" in prompt
    assert "已截断说明" in prompt
    assert "最终 JSON 中禁止出现“原文未提供”" in prompt
    assert len(context_json) <= 300


def test_build_prompt_truncates_context_as_valid_json_by_priority() -> None:
    import json

    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "huge.md", "format": "md", "size_kb": 1, "parsed_at": "2026-07-08T00:00:00Z"},
            "stats": {"headings": 1, "paragraphs": 30, "tables": 1, "images": 0},
            "warnings": [],
            "content": {
                "blocks": [
                    {"type": "heading", "level": 1, "text": "关键标题"},
                    *[{"type": "paragraph", "text": f"次要段落 {index} " + "长文本" * 80} for index in range(30)],
                    {"type": "table", "header": ["A", "B"], "rows": [[f"R{row}A", f"R{row}B"] for row in range(20)]},
                ],
                "outline": [{"level": 1, "text": "关键标题"}],
            },
        }
    )

    prompt = build_prompt(kind="word", context=context, max_context_chars=900)
    context_json = prompt.split("[输入 DocumentIR]", 1)[1].split("[字符估算]", 1)[0].strip()
    payload = json.loads(context_json)

    assert payload["content"]["outline"] == [{"level": 1, "text": "关键标题"}]
    assert len(json.dumps(payload, ensure_ascii=False)) <= 900
    assert "按事实密度优先保留" in prompt


def test_build_prompt_truncation_prioritizes_method_metric_and_tradeoff_evidence() -> None:
    import json

    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {
                "filename": "超长技术报告.docx",
                "format": "docx",
                "size_kb": 2048,
                "parsed_at": "2026-07-17T00:00:00Z",
            },
            "stats": {"headings": 60, "paragraphs": 84, "tables": 1, "images": 20},
            "warnings": [
                f"解析诊断 {index}: " + "嵌入对象路径 " * 80
                for index in range(40)
            ],
            "content": {
                "outline": [
                    {"level": 2, "text": f"第 {index} 节常规背景"}
                    for index in range(60)
                ],
                "blocks": [
                    {"type": "heading", "level": 1, "text": "技术方案"},
                    *[
                        {
                            "type": "paragraph",
                            "text": f"背景材料 {index}：介绍研究范围和一般情况。" + "常规说明" * 20,
                        }
                        for index in range(80)
                    ],
                    {"type": "heading", "level": 2, "text": "预测方法与训练参数"},
                    {
                        "type": "paragraph",
                        "text": (
                            "方法采用 CNN-LSTM：四层卷积提取空间特征，两层 LSTM 建模时序；"
                            "数据集 20,000 组，训练/测试/验证比例 8:1:1，迭代 600 次，学习率 0.001。"
                        ),
                    },
                    {"type": "heading", "level": 2, "text": "性能对比"},
                    {
                        "type": "paragraph",
                        "text": (
                            "AR-SiamFDSC 全局准确率为 98.38%；在 JNR 0 dB 条件下，"
                            "相对 CNN 基线提高 3.83%。"
                        ),
                    },
                    {"type": "heading", "level": 2, "text": "方案取舍"},
                    {
                        "type": "paragraph",
                        "text": (
                            "星上算力受限时选择 edRVFL 而非 CNN-LSTM，因为 edRVFL 无需反向传播、"
                            "训练开销更低且响应更快；其量化精度对比原文未提供，需作为风险保留。"
                        ),
                    },
                    {
                        "type": "table",
                        "header": ["对象", "指标", "结果"],
                        "rows": [
                            ["LEO 信道预测", "轨道高度/NMSE", "1000 km / -10 dB"],
                            ["地面验证", "带宽/速率", "100 MHz / 800 Mbps"],
                        ],
                    },
                ],
            },
        }
    )

    prompt = build_prompt(kind="deck", context=context, max_context_chars=4200)
    context_json = prompt.split("[输入 DocumentIR]", 1)[1].split("[字符估算]", 1)[0].strip()
    payload = json.loads(context_json)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)

    assert len(encoded) <= 4200
    assert len(payload["warnings"]) <= 5
    assert len(payload["content"]["outline"]) <= 18
    retained = json.dumps(payload["content"]["blocks"], ensure_ascii=False)
    assert "CNN-LSTM" in retained and "20,000" in retained and "8:1:1" in retained
    assert "98.38%" in retained and "3.83%" in retained and "JNR 0 dB" in retained
    assert "edRVFL" in retained and "训练开销更低" in retained and "原文未提供" in retained
    assert "1000 km / -10 dB" in retained and "100 MHz / 800 Mbps" in retained
    assert "背景材料 79" not in retained


def test_three_stage_workflow_is_adjacent_to_input_facts_for_recency() -> None:
    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None)

    context_index = prompt.index("[输入 DocumentIR]")
    workflow_index = prompt.index("[三阶段内容生成]")
    final_check_index = prompt.index("[最后自检]")
    assert context_index < workflow_index < final_check_index


def test_build_deck_prompt_contains_weak_model_rules_and_few_shot() -> None:
    import json

    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None, max_output_chars=6000)

    assert "只输出一个完整的 JSON 对象" in prompt
    assert "不要使用 Markdown 代码围栏" in prompt
    assert "必须以 { 开始、以 } 结束" in prompt
    assert "观点在标题" in prompt
    assert "每页最多 3 个内容点" in prompt
    assert "title_bullets" in prompt and "architecture_diagram" in prompt
    assert "目标 JSON 总长度不得超过 6000 个字符" in prompt
    assert "内容过长时按主题拆成多页" in prompt
    assert "优先组织为 8-10 页技术评审稿" in prompt
    assert "[正例 few-shot]" in prompt
    assert '"ir_type":"deck"' in prompt
    assert prompt.index("[字段速查规则]") < prompt.index("[完整目标 Schema，以此为最终准绳]")
    for phrase in (
        "相对权重",
        "总和不必为 1",
        "span、rowspan、colspan 是覆盖数量",
        "primary、secondary、emphasis、data、job、module",
        "thresholds[].value 与 chart.series[].values 必须使用同一数值单位",
        "components 是从上到下的 1-3 个组件列表",
    ):
        assert phrase in prompt
    from app.ir.deck_ir import DeckIR

    for filename in (
        "deck_few_shot_table_v19.json",
        "deck_few_shot_architecture_v19.json",
        "deck_few_shot_composite_v19.json",
    ):
        sample = json.loads((ROOT / "samples" / "ir" / filename).read_text(encoding="utf-8"))
        compact_sample = json.dumps(
            DeckIR.model_validate(sample).model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        assert compact_sample in prompt
        assert '"ir_version":"2.1"' in compact_sample
    assert "est_chars=2" in prompt
    assert "```" not in prompt


def test_prompt_uses_silent_fact_skeleton_draft_workflow_with_anti_ai_rules() -> None:
    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None)

    assert "[三阶段内容生成]" in prompt
    assert "第1阶段：抽取事实" in prompt
    assert "方法/模型名称" in prompt
    assert "关键参数" in prompt
    assert "数据与指标" in prompt
    assert "对比对象" in prompt
    assert "取舍/权衡" in prompt
    assert "适用条件" in prompt
    assert "原文未提供" in prompt
    assert "禁止写完整句子" in prompt
    assert "第2阶段：排文体骨架" in prompt
    assert "第3阶段：成文" in prompt
    assert "阶段1和阶段2只在内部完成" in prompt
    assert "不得把事实表或骨架写成 Schema 外字段" in prompt
    for phrase in ("先进的", "有效的", "良好的", "显著的", "充分体现", "奠定基础", "具有重要意义"):
        assert phrase in prompt
    assert "每个论点必须挂一个具体支撑" in prompt
    assert "为什么这么选" in prompt
    assert "能用数据或对比表达的优先建表" in prompt
    assert "截断摘录不等于原文缺失" in prompt
    assert "当前输入摘录未包含" in prompt
    assert "输入摘录中有明确缺失证据" in prompt
    assert "文件名或正文明确标注“公开”" in prompt
    assert "PUBLIC" in prompt


def test_truncation_keeps_adjacent_parameter_table_with_selected_conclusion() -> None:
    import json

    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {
                "filename": "公开训练报告.docx",
                "format": "docx",
                "size_kb": 128,
                "parsed_at": "2026-07-17T00:00:00Z",
            },
            "stats": {"headings": 2, "paragraphs": 31, "tables": 1, "images": 0},
            "warnings": ["诊断信息 " * 200],
            "content": {
                "outline": [{"level": 1, "text": "训练分析"}],
                "blocks": [
                    {"type": "heading", "level": 1, "text": "背景"},
                    *[
                        {
                            "type": "paragraph",
                            "text": f"对比样本 {index}：模型 M{index} 在 10 dB 条件下准确率为 90%。",
                        }
                        for index in range(30)
                    ],
                    {"type": "heading", "level": 1, "text": "训练分析"},
                    {
                        "type": "table",
                        "header": ["项目", "设置值"],
                        "rows": [
                            ["训练世代", "100"],
                            ["早停的忍耐度", "20"],
                            ["早停的最低门限", "0"],
                            ["批尺寸", "16"],
                        ],
                    },
                    {
                        "type": "paragraph",
                        "text": "验证集损失在第13世代最小，第15世代后振荡上升，因此采用早停终止训练。",
                    },
                ],
            },
        }
    )

    prompt = build_prompt(kind="deck", context=context, max_context_chars=2300)
    context_json = prompt.split("[输入 DocumentIR]", 1)[1].split("[字符估算]", 1)[0].strip()
    retained = json.loads(context_json)["content"]["blocks"]
    retained_text = json.dumps(retained, ensure_ascii=False)

    assert "第13世代最小" in retained_text
    assert "早停的忍耐度" in retained_text and '"20"' in retained_text
    assert "早停的最低门限" in retained_text and '"0"' in retained_text


def test_default_genre_templates_define_deck_and_word_skeletons() -> None:
    from app.prompting.builder import build_prompt

    deck = build_prompt(kind="deck", context=None)
    word = build_prompt(kind="word", context=None)

    assert "技术方案评审稿" in deck
    assert "问题/现状 → 方案（挂具体方法） → 数据支撑 → 结论" in deck
    assert "观点提到标题" in deck
    assert "two_column 每栏最多 3 条" in deck
    assert "全页最多 6 条" in deck
    assert "architecture_diagram 最多 4 个节点、4 条边" in deck
    assert "技术方案文档" in word
    assert "概述 → 方案设计（模块/接口/数据流/关键算法） → 关键取舍与风险 → 结论" in word


def test_deck_prompt_defines_chart_selection_quality_rules() -> None:
    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None)

    assert "长类目标签优先使用 kind=bar 且 orientation=horizontal" in prompt
    assert "单系列图表设置 legend_position=none" in prompt
    assert "pie 仅用于 2-6 个非负类别" in prompt
    assert "时间序列折线至少提供两个数据点" in prompt


def test_genre_template_is_file_configurable_without_builder_code_change(tmp_path: Path, monkeypatch) -> None:
    import app.prompting.builder as builder

    genre_dir = tmp_path / "genres"
    genre_dir.mkdir()
    (genre_dir / "decision_memo.txt").write_text(
        "决策备忘录：候选方案 → 证据 → 取舍 → 决策。",
        encoding="utf-8",
    )
    monkeypatch.setattr(builder, "GENRE_TEMPLATE_DIR", genre_dir)

    prompt = builder.build_prompt(kind="deck", context=None, genre="decision_memo")

    assert "决策备忘录：候选方案 → 证据 → 取舍 → 决策。" in prompt
    with pytest.raises(ValueError, match="genre"):
        builder.build_prompt(kind="deck", context=None, genre="../escape")


def test_prompt_has_replaceable_huawei_style_example_slot() -> None:
    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="word", context=None)

    assert "[文体范例插槽]" in prompt
    assert "面向实现" in prompt
    assert "重技术细节、轻背景铺垫" in prompt
    assert "陈述事实与权衡" in prompt
    assert "真实华为详设/概设" in prompt
    assert "替换模板文件即可升级" in prompt


def test_build_prompt_output_budget_controls_page_and_block_limits() -> None:
    from app.prompting.builder import build_prompt

    small_deck = build_prompt(kind="deck", context=None, max_output_chars=4000)
    large_deck = build_prompt(kind="deck", context=None, max_output_chars=8000)
    small_word = build_prompt(kind="word", context=None, max_output_chars=4000)

    assert "最多 5 页" in small_deck
    assert "最多 10 页" in large_deck
    assert "优先组织为 8-10 页技术评审稿" not in small_deck
    assert "优先组织为 8-10 页技术评审稿" in large_deck
    assert "最多 13 个 blocks" in small_word


def test_stub_channel_accepts_hardened_prompt_and_returns_valid_ir() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.prompting.builder import build_prompt

    prompt = build_prompt(kind="deck", context=None, max_output_chars=6000)
    raw = StubGenerator().generate(prompt, target="deck_ir")

    deck = DeckIR.model_validate_json(raw)
    assert "严格字段结构" in prompt
    assert "最多 8 页" in prompt
    assert deck.ir_type == "deck"


def test_prompt_normalizes_volatile_parse_timestamp() -> None:
    from app.ir.document_ir import DocumentIR
    from app.prompting.builder import build_prompt

    base = {
        "ir_type": "document",
        "ir_version": "1.1",
        "source": {"filename": "same.md", "format": "md", "size_kb": 1},
        "stats": {},
        "content": {"blocks": [{"type": "paragraph", "text": "同一内容"}]},
    }
    first = DocumentIR.model_validate({**base, "source": {**base["source"], "parsed_at": "2026-07-10T01:00:00Z"}})
    second = DocumentIR.model_validate({**base, "source": {**base["source"], "parsed_at": "2026-07-10T02:00:00Z"}})

    assert build_prompt(kind="word", context=first) == build_prompt(kind="word", context=second)
    assert "<normalized-for-determinism>" in build_prompt(kind="word", context=first)


def test_stub_output_changes_with_document_content_and_preserves_primary_fact() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.word_ir import WordIR
    from app.parsers.md_parser import parse_markdown
    from app.prompting.builder import build_prompt

    generator = StubGenerator()
    first_context = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_01.md")
    second_context = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_02.md")
    first_prompt = build_prompt(kind="word", context=first_context)
    second_prompt = build_prompt(kind="word", context=second_context)

    first_word_raw = generator.generate(first_prompt, target="word_ir")
    second_word_raw = generator.generate(second_prompt, target="word_ir")
    first_deck_raw = generator.generate(build_prompt(kind="deck", context=first_context), target="deck_ir")
    second_deck_raw = generator.generate(build_prompt(kind="deck", context=second_context), target="deck_ir")

    WordIR.model_validate_json(first_word_raw)
    WordIR.model_validate_json(second_word_raw)
    DeckIR.model_validate_json(first_deck_raw)
    DeckIR.model_validate_json(second_deck_raw)
    assert first_word_raw != second_word_raw
    assert first_deck_raw != second_deck_raw
    assert "Markdown 样例 1" in first_word_raw and "Markdown 样例 1" in first_deck_raw
    assert "Markdown 样例 2" in second_word_raw and "Markdown 样例 2" in second_deck_raw


def test_stub_maps_each_document_format_in_process() -> None:
    from app.cli.parse import parse_file
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.word_ir import WordIR
    from app.prompting.builder import build_prompt

    samples = {
        "md_sample_01.md": "Markdown 样例 1",
        "docx_sample_01.docx": "DOCX 样例 1",
        "xlsx_sample_01.xlsx": "台账1",
        "pptx_sample_01.pptx": "PPTX 样例 1",
    }
    generator = StubGenerator()
    for sample_name, marker in samples.items():
        context = parse_file(ROOT / "samples" / "input" / "parser_samples" / sample_name)
        word = WordIR.model_validate_json(generator.generate(build_prompt(kind="word", context=context), target="word_ir"))
        deck = DeckIR.model_validate_json(generator.generate(build_prompt(kind="deck", context=context), target="deck_ir"))

        assert marker in word.model_dump_json()
        assert marker in deck.model_dump_json()
        assert any(block.type == "table" for block in word.blocks)
        assert any(slide.layout == "table" for slide in deck.slides)


def test_stub_handles_image_page_break_empty_sheet_and_dirty_prompt_edges() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.document_ir import DocumentIR
    from app.ir.word_ir import WordIR
    from app.prompting.builder import build_prompt

    context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "图片说明.docx", "format": "docx", "size_kb": 1, "parsed_at": "now"},
            "stats": {"images": 1},
            "content": {
                "blocks": [
                    {"type": "heading", "level": 1, "text": "图片说明"},
                    {"type": "image_placeholder", "caption": "图1: 架构"},
                    {"type": "page_break"},
                ]
            },
        }
    )
    empty_sheet_context = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {"filename": "空台账.xlsx", "format": "xlsx", "size_kb": 1, "parsed_at": "now"},
            "stats": {"tables": 1},
            "content": {"sheets": [{"name": "空表", "nrows": 0, "ncols": 0}]},
        }
    )
    generator = StubGenerator()

    word = WordIR.model_validate_json(generator.generate(build_prompt(kind="word", context=context), target="word_ir"))
    empty_sheet_word = WordIR.model_validate_json(
        generator.generate(build_prompt(kind="word", context=empty_sheet_context), target="word_ir")
    )
    fallback = WordIR.model_validate_json(generator.generate("[输入 DocumentIR]\n{broken", target="word_ir"))

    assert [block.type for block in word.blocks] == ["heading", "image_placeholder"]
    assert [block.type for block in empty_sheet_word.blocks] == ["heading", "paragraph"]
    assert fallback.meta.title == "Stub 文档"
    with pytest.raises(ValueError, match="unsupported target"):
        generator.generate("", target="unsupported")  # type: ignore[arg-type]


def test_deck_prompt_optional_depth_rules_keep_default_path_deterministic() -> None:
    from app.parsers.md_parser import parse_markdown
    from app.prompting.builder import build_prompt

    context = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_01.md")
    legacy = build_prompt(kind="deck", context=context)
    standard = build_prompt(kind="deck", context=context, depth="标准")
    detailed = build_prompt(kind="deck", context=context, depth="详细", pages=16)

    assert hashlib.sha256(legacy.encode("utf-8")).hexdigest() == (
        "9ebf411c97146080f27203eb934b955759c83c3d3e0afc0c2b2a41f7705cd445"
    )
    from app.generators.stub import StubGenerator

    legacy_raw = StubGenerator().generate(legacy, target="deck_ir")
    assert hashlib.sha256(legacy_raw.encode("utf-8")).hexdigest() == (
        "d78bfadb23c35e0b6366d9ea376d6edb3be4e806f5d8f0653771e99693f65b89"
    )
    assert "[生成深度与目标页数]" not in legacy
    assert "结论句 + 1个关键支撑" in standard
    assert "10-12 页" in standard
    assert "必须恰好生成 16 页" in detailed
    assert "结论 + 具体方法/架构名称 + 关键数据/指标 + 必要的权衡或适用条件" in detailed
    assert "CNN-LSTM" in detailed and "1000km LEO" in detailed and "NMSE -10dB" in detailed
    assert "严禁标题党" in detailed


def test_deck_prompt_declares_page_plan_rhythm_and_registered_layout_boundary() -> None:
    from app.generation.depth import GenerationOptions, build_outline_prompt
    from app.parsers.md_parser import parse_markdown

    document = parse_markdown(ROOT / "samples" / "input" / "parser_samples" / "md_sample_01.md")
    prompt = build_outline_prompt(document, GenerationOptions(depth="标准", pages=10), max_context_chars=12000)

    for field in ("source_evidence", "selection_reason", "content_budget"):
        assert field in prompt
    assert "有足够内容关系时再增加版式变化" in prompt
    assert "不为增加版式数量强行套版" in prompt
    assert "不得连续 3 页" in prompt
    assert "H01-H42" in prompt and "禁止" in prompt
    assert "10 页以上" in prompt and "section" in prompt
