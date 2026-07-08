from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_render_deck_ir_p0_layouts_are_editable(tmp_path: Path) -> None:
    from app.ir.deck_ir import DeckIR
    from app.rendering.pptx_renderer import render_deck_ir

    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "Q3 业务汇报", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {"layout": "cover", "title": "Q3 业务汇报", "subtitle": "命令行文档工具链", "presenter": "张三"},
                {"layout": "agenda", "items": ["业务回顾", "关键进展", "风险与对策"]},
                {"layout": "section", "index": 1, "title": "关键进展"},
                {"layout": "title_bullets", "title": "主链路进展", "bullets": [{"text": "stub 模式可离线运行", "level": 1}]},
                {
                    "layout": "table",
                    "title": "风险清单",
                    "table": {
                        "header": ["风险", "等级"],
                        "rows": [["模型 JSON 不稳定", "中"]],
                    },
                },
            ],
        }
    )

    output = render_deck_ir(deck, tmp_path / "deck.pptx")
    prs = Presentation(str(output))
    all_text = "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if getattr(shape, "has_text_frame", False))

    assert len(prs.slides) == 5
    assert "Q3 业务汇报" in all_text
    assert "业务回顾" in all_text
    assert "关键进展" in all_text
    assert "stub 模式可离线运行" in all_text
    assert "HUAWEI CONFIDENTIAL" in all_text
    assert any(shape.has_table for shape in prs.slides[4].shapes)


def test_render_deck_ir_uses_16_by_9_page_size(tmp_path: Path) -> None:
    from app.ir.deck_ir import DeckIR
    from app.rendering.pptx_renderer import render_deck_ir

    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "尺寸"},
            "slides": [{"layout": "cover", "title": "尺寸"}],
        }
    )

    output = render_deck_ir(deck, tmp_path / "size.pptx")
    prs = Presentation(str(output))

    assert round(prs.slide_width / 914400, 3) == 13.333
    assert round(prs.slide_height / 914400, 1) == 7.5


def test_render_deck_ir_p1_layouts_and_downgrades(tmp_path: Path) -> None:
    from app.ir.deck_ir import DeckIR
    from app.rendering.pptx_renderer import render_deck_ir

    deck = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.1",
            "meta": {"title": "P1 版式"},
            "slides": [
                {
                    "layout": "two_column",
                    "title": "双栏对比",
                    "left": {"heading": "优势", "bullets": [{"text": "离线可测", "level": 1}]},
                    "right": {"heading": "风险", "text": "视觉终审仍需人工"},
                },
                {
                    "layout": "cards",
                    "title": "三大能力",
                    "cards": [
                        {"title": "解析", "desc": "多格式输入"},
                        {"title": "渲染", "desc": "可编辑产物"},
                    ],
                },
                {"layout": "conclusion", "title": "结论", "bullets": ["主链路继续推进"], "cta": "进入内网校准"},
                {
                    "layout": "chart",
                    "title": "趋势",
                    "chart": {"kind": "bar", "categories": ["W1"], "series": [{"name": "完成数", "values": [3]}]},
                },
                {"layout": "image", "title": "架构图", "placeholder": "黄区替换真图", "caption": "工具链架构"},
            ],
        }
    )

    output = render_deck_ir(deck, tmp_path / "p1.pptx")
    prs = Presentation(str(output))
    all_text = "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if getattr(shape, "has_text_frame", False))

    assert "双栏对比" in all_text
    assert "离线可测" in all_text
    assert "三大能力" in all_text
    assert "多格式输入" in all_text
    assert "主链路继续推进" in all_text
    assert "图表待内网 Skill / 后续版本生成" in all_text
    assert "图片占位" in all_text
