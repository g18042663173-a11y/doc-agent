from __future__ import annotations

from app.ir.errors import ValidationItem, ValidationResult


SUGGESTIONS = {
    "E001": "确认模型输出是一个完整 JSON 对象或单个 json 代码块。",
    "E002": "补齐 meta.title, 且标题不能为空白字符串。",
    "E003": "把 block.type 改为 heading、paragraph、bullet_list、numbered_list、table、image_placeholder 或 page_break。",
    "E004": "检查 table.header、rows 和 col_widths 的列数是否一致, 且表格不超过 100 行 x 12 列。",
    "E005": "将 heading.level 调整到 1-4。",
    "E006": "为 blocks 或列表 items 至少提供 1 条内容。",
    "D001": "确认模型输出是一个完整 JSON 对象或单个 json 代码块。",
    "D002": "补齐 meta.title, 且标题不能为空白字符串。",
    "D003": "把 slides[].layout 改为 DeckIR v1.6 允许的版式。",
    "D004": "补齐该 layout 的必填字段。",
    "D005": "检查表格页 header、rows、column_groups、row_groups、cell_spans 与 col_widths 是否越界或不规整, 且数据区不超过 12 行 x 8 列。",
    "D006": "减少 bullets 条数到该 layout 的上限。",
    "W101": "按 1、2、3、4 顺序组织标题层级,避免从 1 级直接跳到 3 级。",
    "W102": "删除空 paragraph,或填写实际正文。",
    "W103": "将超长段落或单元格拆分,控制单段 / 单元格在上限内。",
    "W104": "删除未知字段; 若确需保留, 先升级 IR 契约与 Schema。",
    "I201": "如需覆盖默认密级,显式填写 meta.classification。",
}


def format_validation_result(result: ValidationResult) -> str:
    if result.ok:
        return "PASS"

    lines: list[str] = []
    for item in result.errors + result.warnings + result.infos:
        lines.append(_format_item(item))
    return "\n".join(lines)


def _format_item(item: ValidationItem) -> str:
    loc = item.loc or "<root>"
    suggestion = item.suggestion or SUGGESTIONS.get(item.code, "按错误定位修正后重新校验。")
    return f"[{item.level}] {item.code} at {loc}: {item.message}\n建议: {suggestion}"
