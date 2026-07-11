from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Literal

from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.ir.schema_export import normalized_schema
from app.ir.word_ir import WordIR


Kind = Literal["word", "deck"]
Depth = Literal["概览", "标准", "详细"]
DEFAULT_MAX_OUTPUT_CHARS = 6000
SAMPLE_DIR = Path(__file__).resolve().parents[3] / "samples" / "ir"
FEW_SHOT_FILES: dict[Kind, str] = {
    "word": "word_valid_01_plain.json",
    "deck": "deck_valid_01_minimal.json",
}

TARGETS = {
    "word": {
        "label": "WordIR v1.0",
        "description": "可编辑 Word 文档",
        "model": WordIR,
    },
    "deck": {
        "label": "DeckIR v1.4",
        "description": "华为风格 PPTX 演示文稿",
        "model": DeckIR,
    },
}


def build_prompt(
    *,
    kind: Kind,
    context: DocumentIR | None,
    max_context_chars: int = 12000,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    depth: Depth | None = None,
    pages: int | None = None,
) -> str:
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive")
    if max_output_chars < 2000:
        raise ValueError("max_output_chars must be at least 2000")
    if kind != "deck" and (depth is not None or pages is not None):
        raise ValueError("depth/pages are only supported for deck prompts")
    if pages is not None and not 3 <= pages <= 30:
        raise ValueError("pages must be between 3 and 30")
    target = TARGETS[kind]
    schema_json = json.dumps(normalized_schema(target["model"]), ensure_ascii=False, sort_keys=True, indent=2)
    context_json, truncation_notice = _context_json(context, max_context_chars=max_context_chars)
    template = _template_text()
    return template.format(
        target_label=target["label"],
        target_description=target["description"],
        contract_guide=_contract_guide(kind),
        content_rules=_content_rules(kind, depth=depth, pages=pages),
        output_plan=_output_plan(kind, max_output_chars, depth=depth, pages=pages),
        few_shot=_few_shot(kind),
        schema_json=schema_json,
        context_json=context_json,
        context_est_chars=len(context_json),
        truncation_notice=truncation_notice,
    )


def _contract_guide(kind: Kind) -> str:
    if kind == "word":
        return (
            "顶层只能有 ir_type、ir_version、meta、blocks。"
            "ir_type 固定为 word，ir_version 固定为 1.0，meta.title 必填且非空，blocks 至少 1 条。\n"
            "block.type 只能是 heading、paragraph、bullet_list、numbered_list、table、image_placeholder、page_break；"
            "heading.level 只能为 1-4；列表 items 至少 1 条；table 每行列数必须等于 header 列数。"
        )
    return (
        "顶层只能有 ir_type、ir_version、meta、slides。"
        "ir_type 固定为 deck，ir_version 固定为 1.4，meta.title 必填且非空，slides 至少 1 页。\n"
        "slides[].layout 只能是 cover、agenda、section、title_bullets、two_column、table、cards、chart、"
        "architecture_diagram、image、conclusion；每种 layout 只填写 Schema 为它定义的字段。\n"
        "agenda.items 为 2-8 条；title_bullets.bullets 至少 1 条；table.rows 每行列数等于 header；"
        "chart.series[].values 数量等于 categories；architecture_diagram 的 edge.from/to 必须引用已有 node.id。"
    )


def _content_rules(kind: Kind, *, depth: Depth | None = None, pages: int | None = None) -> str:
    if kind == "word":
        return (
            "- 标题层级连续，不从 1 级直接跳到 3/4 级。\n"
            "- 一段只表达一个主题；长内容拆成多个 heading + paragraph，不把整篇材料塞进一个 paragraph。\n"
            "- 表格必须有数据行；图片占位必须至少给 ref 或 caption；不得编造输入中没有的事实。"
        )
    legacy = (
        "- 观点在标题：除 cover、agenda、section 外，title 应写结论或判断，不只写“背景/分析/数据”等栏目名。\n"
        "- 每页只表达一个观点，每页最多 3 个内容点；材料过多时拆页，不缩成长段。\n"
        "- 版式选择：顺序用 agenda/section；观点用 title_bullets；对比用 two_column/table；"
        "并列要素用 cards；数值趋势用 chart；节点关系用 architecture_diagram；图片说明用 image；收束用 conclusion。\n"
        "- chart 的结论必须与 series/thresholds 一致；table 不得缺行或出现合并区冲突；"
        "architecture_diagram 不得有缺失节点或自环 edge。"
    )
    if depth is None and pages is None:
        return legacy
    effective_depth: Depth = depth or "标准"
    depth_rules = {
        "概览": (
            "概览（约 8 页）：每个要点是结论句；只保留核心结论和关键指标；"
            "版式以 title_bullets、table、conclusion 为主。"
        ),
        "标准": (
            "标准（10-12 页）：每个要点 = 结论句 + 1个关键支撑（具体方法名或数据）；"
            "保留 section、table、architecture_diagram、two_column。"
        ),
        "详细": (
            "详细（14-18 页）：每个要点 = 结论 + 具体方法/架构名称 + 关键数据/指标 + 必要的权衡或适用条件；"
            "技术点必须展开到讲得清怎么做、数据多少，不能停在结论句。"
            "例如信道预测要点应在原文有依据时写明 CNN-LSTM/edRVFL、1000km LEO、NMSE -10dB 及选型原因；"
            "相关数据能建表或对比时优先使用 table。"
        ),
    }[effective_depth]
    page_rule = f"必须恰好生成 {pages} 页。" if pages is not None else "按所选档位的页数区间组织。"
    return (
        f"{legacy}\n[生成深度与目标页数]\n- 当前档位：{effective_depth}。{page_rule}\n- {depth_rules}\n"
        "- 所有档位都严禁标题党：每个要点必须有具体内容，不能只有小标题；"
        "能用数据或对比表达的优先建表；继续坚持观点写进标题。"
    )


def _output_plan(
    kind: Kind,
    max_output_chars: int,
    *,
    depth: Depth | None = None,
    pages: int | None = None,
) -> str:
    if kind == "deck":
        if depth is not None or pages is not None:
            effective_depth: Depth = depth or "标准"
            ranges = {"概览": "约 8 页", "标准": "10-12 页", "详细": "14-18 页"}
            target = f"必须恰好生成 {pages} 页" if pages is not None else f"目标为 {ranges[effective_depth]}"
            return (
                f"当前为 {effective_depth}档，{target}。单次模型输出不得超过 {max_output_chars} 个字符；"
                "若由调用侧按大纲分批生成，本次只输出指定批次的完整 DeckIR，不得输出其他页。"
                "任何情况下都不能输出半个 JSON；预算不足时压缩措辞，但不得删除方法名、关键数据或必要权衡。"
            )
        page_limit = max(3, min(10, max_output_chars // 700))
        page_target = "" if page_limit < 8 else "对于章节足够的长技术材料，优先组织为 8-10 页技术评审稿；不得用重复或空泛内容凑页数。"
        return (
            f"目标 JSON 总长度不得超过 {max_output_chars} 个字符，最多 {page_limit} 页。"
            "内容过长时按主题拆成多页，但仍须遵守总页数和总字符预算；优先保留结论、依据、风险和行动，"
            f"删除低价值细节。{page_target}绝不能因达到上限而输出半个 JSON。"
        )
    block_limit = max(8, min(24, max_output_chars // 300))
    return (
        f"目标 JSON 总长度不得超过 {max_output_chars} 个字符，最多 {block_limit} 个 blocks。"
        "长材料按章节分段，每段保持短小；优先保留标题、结论、关键依据和表格摘要，删除低价值明细。"
        "绝不能因达到上限而输出半个 JSON。"
    )


def _few_shot(kind: Kind) -> str:
    path = SAMPLE_DIR / FEW_SHOT_FILES[kind]
    payload = json.loads(path.read_text(encoding="utf-8"))
    TARGETS[kind]["model"].model_validate(payload)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _context_json(context: DocumentIR | None, *, max_context_chars: int) -> tuple[str, str]:
    if context is None:
        return "{}", "未提供输入 DocumentIR。"
    payload = context.model_dump(mode="json")
    payload["source"]["parsed_at"] = "<normalized-for-determinism>"
    encoded = _encode(payload)
    if len(encoded) <= max_context_chars:
        return encoded, "未截断。"
    payload = _truncate_context_payload(payload, max_context_chars=max_context_chars)
    encoded = _encode(payload)
    notice = f"已截断说明: 输入 DocumentIR 超过 {max_context_chars} 字符,已按优先级丢弃预览尾行、次要段落和低价值明细;请勿编造被截断内容。"
    return encoded, notice


def _encode(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _truncate_context_payload(payload: dict, *, max_context_chars: int) -> dict:
    truncated = copy.deepcopy(payload)
    content = truncated.setdefault("content", {})
    blocks = content.get("blocks")
    sheets = content.get("sheets")
    slides = content.get("slides")

    if isinstance(sheets, list):
        for sheet in sheets:
            if isinstance(sheet, dict):
                sheet["preview_rows"] = sheet.get("preview_rows", [])[:8]
                for stat in sheet.get("col_stats", []):
                    if isinstance(stat, dict):
                        stat["samples"] = stat.get("samples", [])[:1]
    if isinstance(slides, list):
        for slide in slides:
            if isinstance(slide, dict):
                slide["bodies"] = slide.get("bodies", [])[:6]
                slide["tables"] = _truncate_tables(slide.get("tables", []), max_rows=5)
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "table":
                block["rows"] = block.get("rows", [])[:8]

    while len(_encode(truncated)) > max_context_chars:
        if _drop_table_tail(content):
            continue
        if _shrink_long_paragraph(content):
            continue
        if _drop_secondary_block(content):
            continue
        if isinstance(slides, list) and _drop_slide_tail(slides):
            continue
        if isinstance(sheets, list) and _drop_sheet_tail(sheets):
            continue
        content["blocks"] = []
        content["sheets"] = []
        content["slides"] = []
        break
    return truncated


def _truncate_tables(tables: list, *, max_rows: int) -> list:
    truncated = []
    for table in tables:
        if isinstance(table, dict):
            copy_table = dict(table)
            copy_table["rows"] = copy_table.get("rows", [])[:max_rows]
            truncated.append(copy_table)
    return truncated


def _drop_table_tail(content: dict) -> bool:
    for block in reversed(content.get("blocks", [])):
        if isinstance(block, dict) and block.get("type") == "table" and block.get("rows"):
            block["rows"].pop()
            return True
    for sheet in reversed(content.get("sheets", [])):
        if isinstance(sheet, dict) and sheet.get("preview_rows"):
            sheet["preview_rows"].pop()
            return True
    for slide in reversed(content.get("slides", [])):
        if not isinstance(slide, dict):
            continue
        for table in reversed(slide.get("tables", [])):
            if isinstance(table, dict) and table.get("rows"):
                table["rows"].pop()
                return True
    return False


def _shrink_long_paragraph(content: dict) -> bool:
    for block in reversed(content.get("blocks", [])):
        if isinstance(block, dict) and block.get("type") == "paragraph" and len(str(block.get("text", ""))) > 160:
            block["text"] = str(block["text"])[:120] + "...[truncated]"
            return True
    for slide in reversed(content.get("slides", [])):
        if isinstance(slide, dict):
            for index, body in enumerate(slide.get("bodies", [])):
                if len(str(body)) > 160:
                    slide["bodies"][index] = str(body)[:120] + "...[truncated]"
                    return True
    return False


def _drop_secondary_block(content: dict) -> bool:
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        return False
    for index in range(len(blocks) - 1, -1, -1):
        block = blocks[index]
        if isinstance(block, dict) and block.get("type") not in {"heading", "table"}:
            del blocks[index]
            return True
    return False


def _drop_slide_tail(slides: list) -> bool:
    for slide in reversed(slides):
        if isinstance(slide, dict) and slide.get("bodies"):
            slide["bodies"].pop()
            return True
    return False


def _drop_sheet_tail(sheets: list) -> bool:
    for sheet in reversed(sheets):
        if isinstance(sheet, dict) and sheet.get("col_stats"):
            sheet["col_stats"].pop()
            return True
    return False


def _template_text() -> str:
    return (Path(__file__).parent / "templates" / "ir_generation.txt").read_text(encoding="utf-8")
