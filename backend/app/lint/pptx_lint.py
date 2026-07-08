from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from pptx import Presentation

from app.rendering.theme import load_theme


@dataclass(frozen=True)
class PptxLintItem:
    code: str
    level: str
    slide: int | None
    message: str
    suggestion: str


@dataclass(frozen=True)
class PptxLintReport:
    items: list[PptxLintItem]

    @property
    def summary(self) -> dict[str, Any]:
        errors = sum(1 for item in self.items if item.level == "Error")
        warnings = sum(1 for item in self.items if item.level == "Warning")
        infos = sum(1 for item in self.items if item.level == "Info")
        return {"errors": errors, "warnings": warnings, "infos": infos, "pass": errors == 0}

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "items": [
                {
                    "code": item.code,
                    "level": item.level,
                    "slide": item.slide,
                    "message": item.message,
                    "suggestion": item.suggestion,
                }
                for item in self.items
            ],
        }


def check_pptx(path: Path, *, classification: str | None = None, theme_name: str = "hw_v1") -> PptxLintReport:
    theme = load_theme(theme_name)
    expected_classification = classification or theme["footer"]["default_classification"]
    prs = Presentation(str(path))
    items: list[PptxLintItem] = []

    if len(prs.slides) > theme["constraints"]["max_slides"]:
        items.append(
            PptxLintItem(
                code="HW-W05",
                level="Warning",
                slide=None,
                message=f"总页数 {len(prs.slides)} 超过 {theme['constraints']['max_slides']}。",
                suggestion="拆分演示或合并低价值页面。",
            )
        )

    for slide_index, slide in enumerate(prs.slides, start=1):
        text_shapes = [shape for shape in slide.shapes if getattr(shape, "has_text_frame", False)]
        slide_text = "\n".join(shape.text for shape in text_shapes)
        if expected_classification not in slide_text:
            items.append(_item("HW-E01", "Error", slide_index, "页脚缺少密级文案。", "在页脚区写入 meta.classification。"))

        xml = slide.element.xml
        if "<p:transition" in xml or "<p:timing" in xml:
            items.append(_item("HW-E03", "Error", slide_index, "存在动画或切换效果。", "移除 transition / timing XML 节点。"))

        items.extend(_font_items(slide, slide_index, theme))
        items.extend(_table_items(slide, slide_index, theme))
        items.extend(_bullet_items(text_shapes, slide_index, theme))
        items.extend(_layout_items(text_shapes, slide_index, prs, theme))

    return PptxLintReport(items)


def write_reports(report: PptxLintReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    md_path = output_dir / "report.md"
    payload = report.to_dict()
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_lines = [
        "# PPTX 合规检查报告",
        "",
        f"- Errors: {payload['summary']['errors']}",
        f"- Warnings: {payload['summary']['warnings']}",
        f"- Infos: {payload['summary']['infos']}",
        f"- Pass: {payload['summary']['pass']}",
        "",
    ]
    for item in report.items:
        slide = "-" if item.slide is None else str(item.slide)
        md_lines.append(f"## {item.code} ({item.level})")
        md_lines.append(f"- Slide: {slide}")
        md_lines.append(f"- Message: {item.message}")
        md_lines.append(f"- Suggestion: {item.suggestion}")
        md_lines.append("")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path


def _font_items(slide, slide_index: int, theme: dict) -> list[PptxLintItem]:
    items: list[PptxLintItem] = []
    whitelist = set(theme["fonts"]["whitelist"])
    minimum = theme["font_sizes_pt"]["minimum"]
    palette = {value.upper() for value in theme["colors"].values()}
    for shape in slide.shapes:
        if not getattr(shape, "has_text_frame", False):
            continue
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                if run.font.name and run.font.name not in whitelist:
                    items.append(_item("HW-E02", "Error", slide_index, f"字体不在白名单: {run.font.name}", "改用主题字体白名单。"))
                if run.font.size and run.font.size.pt < minimum:
                    items.append(_item("HW-W01", "Warning", slide_index, f"字号 {run.font.size.pt:.1f}pt 小于下限。", "提高到 10.5pt 以上。"))
                if run.font.color.type is not None and getattr(run.font.color, "rgb", None):
                    color = f"#{run.font.color.rgb}".upper()
                    if color not in palette:
                        items.append(_item("HW-W02", "Warning", slide_index, f"颜色 {color} 不在主题色板。", "改用 hw_theme.json 色板。"))
    return items


def _table_items(slide, slide_index: int, theme: dict) -> list[PptxLintItem]:
    items: list[PptxLintItem] = []
    max_rows = theme["constraints"]["max_table_rows"]
    max_cols = theme["constraints"]["max_table_cols"]
    for shape in slide.shapes:
        if getattr(shape, "has_table", False):
            rows = len(shape.table.rows)
            cols = len(shape.table.columns)
            if rows > max_rows or cols > max_cols:
                items.append(_item("HW-W04", "Warning", slide_index, f"表格尺寸 {rows}x{cols} 超过 {max_rows}x{max_cols}。", "拆分表格或减少列。"))
    return items


def _bullet_items(text_shapes: list, slide_index: int, theme: dict) -> list[PptxLintItem]:
    bullet_lines = []
    for shape in text_shapes:
        for line in shape.text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("•", "-", "–")):
                bullet_lines.append(stripped)
    too_many = len(bullet_lines) > theme["constraints"]["max_bullets_per_slide"]
    too_long = any(len(line) > theme["constraints"]["max_bullet_chars"] for line in bullet_lines)
    if too_many or too_long:
        return [_item("HW-W03", "Warning", slide_index, "单页要点过多或单条过长。", "控制在 7 条以内且单条不超过 60 字。")]
    return []


def _layout_items(text_shapes: list, slide_index: int, prs, theme: dict) -> list[PptxLintItem]:
    items: list[PptxLintItem] = []
    width = prs.slide_width
    height = prs.slide_height
    min_margin = int(theme["grid"]["min_edge_margin_in"] * 914400)
    for shape in text_shapes:
        if shape.left < min_margin or shape.top < 0:
            items.append(_item("HW-W07", "Warning", slide_index, "元素过近页边。", "按主题页边距重新排布。"))
            break
        if shape.left + shape.width > width - min_margin or shape.top + shape.height > height:
            items.append(_item("HW-W07", "Warning", slide_index, "元素超出版心或过近页边。", "按主题页边距重新排布。"))
            break
    return items


def _item(code: str, level: str, slide: int | None, message: str, suggestion: str) -> PptxLintItem:
    return PptxLintItem(code=code, level=level, slide=slide, message=message, suggestion=suggestion)
