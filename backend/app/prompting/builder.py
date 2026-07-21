from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Literal

from app.generation.layout_policy import LAYOUT_SELECTION_RULES
from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.ir.schema_export import normalized_schema
from app.ir.word_ir import WordIR


Kind = Literal["word", "deck"]
Depth = Literal["概览", "标准", "详细"]
DEFAULT_MAX_OUTPUT_CHARS = 6000
SAMPLE_DIR = Path(__file__).resolve().parents[3] / "samples" / "ir"
TEMPLATE_DIR = Path(__file__).parent / "templates"
GENRE_TEMPLATE_DIR = TEMPLATE_DIR / "genres"
STYLE_EXAMPLE_PATH = TEMPLATE_DIR / "style_examples" / "huawei_technical.txt"
WORKFLOW_TEMPLATE_PATH = TEMPLATE_DIR / "three_stage_generation.txt"
DEFAULT_GENRES: dict[Kind, str] = {
    "word": "word_technical",
    "deck": "deck_review",
}
GENRE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
CONTEXT_WARNING_LIMIT = 2
CONTEXT_OUTLINE_LIMIT = 10
CONTEXT_CANDIDATE_LIMIT = 96
CONTEXT_TEXT_LIMIT = 360
CONTEXT_TABLE_ROW_LIMIT = 6
EVIDENCE_MEASUREMENT_PATTERN = re.compile(
    r"(?:\d+(?:[.,]\d+)*(?:\s*[:：/]\s*\d+)+|"
    r"[+-]?\d+(?:[.,]\d+)*\s*(?:%|dB|km|m|GHz|MHz|kHz|Hz|Gbps|Mbps|kbps|ms|"
    r"bit|组|层|次|路|个|倍))",
    re.IGNORECASE,
)
EVIDENCE_METHOD_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,}[A-Za-z0-9]*|[A-Za-z]{2,}(?:[-_/][A-Za-z0-9]+)+)\b|"
    r"(?:算法|模型|架构|协议|接口|网络|流程)",
)
EVIDENCE_TRADEOFF_PATTERN = re.compile(
    r"(?:相比|相较|对比|取舍|权衡|而非|代价|开销|受限|约束|不足|但|然而|因为|原因|"
    r"选择|优于|低于|高于|降低|提升|更快|更慢)",
)
EVIDENCE_CONDITION_PATTERN = re.compile(
    r"(?:条件下|适用于|适用条件|前提|风险|原文未提供|尚未|无法|资源|时延|算力)",
)
EVIDENCE_RESULT_PATTERN = re.compile(
    r"(?:指标|准确率|召回率|精确度|NMSE|数据集|迭代|学习率|吞吐|速率|带宽|"
    r"达到|不低于|不高于|低于|高于|验证)",
    re.IGNORECASE,
)
CAPTION_PATTERN = re.compile(r"^\s*(?:图|表)\s*\d+", re.IGNORECASE)
FEW_SHOT_FILES: dict[Kind, tuple[str, ...]] = {
    "word": ("word_valid_01_plain.json",),
    "deck": (
        "deck_few_shot_table_v19.json",
        "deck_few_shot_architecture_v19.json",
        "deck_few_shot_composite_v19.json",
    ),
}

TARGETS = {
    "word": {
        "label": "WordIR v1.1",
        "description": "可编辑 Word 文档",
        "model": WordIR,
    },
    "deck": {
        "label": "DeckIR v1.9",
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
    genre: str | None = None,
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
    context_json, truncation_notice, context_incomplete = _context_json(
        context,
        max_context_chars=max_context_chars,
    )
    template = _template_text()
    return template.format(
        target_label=target["label"],
        target_description=target["description"],
        contract_guide=_contract_guide(kind),
        field_quick_reference=_field_quick_reference(kind),
        content_rules=_content_rules(kind, depth=depth, pages=pages),
        generation_workflow=_generation_workflow(
            kind,
            genre=genre,
            context_incomplete=context_incomplete,
        ),
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
            "ir_type 固定为 word，ir_version 固定为 1.1，meta.title 必填且非空，blocks 至少 1 条。\n"
            "block.type 只能是 heading、paragraph、code_block、bullet_list、numbered_list、table、image_placeholder、page_break；"
            "heading.level 只能为 1-4；code_block.code 必填且必须保留原始换行与行首缩进；"
            "列表 items 至少 1 条；table 每行列数必须等于 header 列数。"
        )
    return (
        "顶层只能有 ir_type、ir_version、meta、slides。"
        "ir_type 固定为 deck，ir_version 固定为 1.9，meta.title 必填且非空，slides 至少 1 页。\n"
        "slides[].layout 只能是 cover、agenda、section、title_bullets、two_column、table、cards、chart、"
        "architecture_diagram、process_flow、timeline、image、conclusion、composite；每种 layout 只填写 Schema 为它定义的字段。\n"
        "agenda.items 为 2-8 条；title_bullets.bullets 至少 1 条；table.rows 每行列数等于 header；"
        "chart.series[].values 数量等于 categories；architecture_diagram 的 edge.from/to 必须引用已有 node.id；"
        "process_flow.steps 为 2-7 个且 id 唯一；timeline.milestones 为 2-8 个；"
        "chart.orientation=horizontal 只允许 kind=bar；cards.variant=kpi 时 title/desc/tag 分别表示指标名/数值/口径；"
        "architecture_diagram.nodes[].type 可使用 primary/secondary/emphasis/data/job/module；未知 type 使用主题 default 配色；"
        "composite.regions 必须恰含 left/right，components 为 1-3 块从上到下堆叠，首版仅允许 table/architecture_diagram/title_bullets/cards。"
    )


def _field_quick_reference(kind: Kind) -> str:
    if kind == "word":
        return "本目标为 WordIR；完整 Schema 是唯一准绳，不得添加 Schema 外字段。"
    return (
        "这份速查规则只划重点，不替代后面的完整 Schema；冲突时以完整 Schema 为准。\n"
        "1. table.col_widths 是各列的正数相对权重，渲染时归一化；不是英寸，总和不必为 1。\n"
        "2. 表格索引从 0 开始：column_groups[].start_col、row_groups[].start_row、conclusion_col、"
        "cell_spans[].row/col 都是 0 起始索引。span、rowspan、colspan 是覆盖数量，不是结束索引。\n"
        "3. architecture_diagram.nodes[].position/size 是架构图内容区的 0-1 比例：position 是节点中心，"
        "size 是宽高比例。type 决定主题色，只能用 primary、secondary、emphasis、data、job、module。\n"
        "4. chart.thresholds[].value 与 chart.series[].values 必须使用同一数值单位；chart.unit 只显示单位后缀，"
        "不换算数据。\n"
        "5. composite.regions 必须刚好有 left 与 right 各一栏；每栏 components 是从上到下的 1-3 个组件列表，"
        "仅可嵌入 table、architecture_diagram、title_bullets、cards。组件字段完全复用其原有 layout。"
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
        "- 版式选择：章节导航用 agenda/section；观点用 title_bullets；对比用 two_column/table；"
        "并列要素用 cards；数值趋势用 chart；图片说明用 image；收束用 conclusion。"
        f"{LAYOUT_SELECTION_RULES}\n"
        "- chart 的结论必须与 series/thresholds 一致；table 不得缺行或出现合并区冲突；"
        "architecture_diagram 不得有缺失节点或自环 edge。"
        " composite 仅用于两个需要同页联读且都能在半页内表达的组件，禁止用它把两页内容硬塞成一页。"
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
    examples: list[str] = []
    for index, filename in enumerate(FEW_SHOT_FILES[kind], start=1):
        path = SAMPLE_DIR / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        validated = TARGETS[kind]["model"].model_validate(payload)
        prompt_payload = validated.model_dump(mode="json") if kind == "word" else payload
        compact = json.dumps(prompt_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        examples.append(f"示例 {index}：{compact}")
    return "\n".join(examples)


def _generation_workflow(kind: Kind, *, genre: str | None, context_incomplete: bool) -> str:
    genre_name = genre or DEFAULT_GENRES[kind]
    if not GENRE_NAME_PATTERN.fullmatch(genre_name):
        raise ValueError("genre must use lowercase letters, numbers, underscores, or hyphens")
    genre_path = GENRE_TEMPLATE_DIR / f"{genre_name}.txt"
    if not genre_path.is_file():
        raise ValueError(f"genre template not found: {genre_name}")
    workflow = WORKFLOW_TEMPLATE_PATH.read_text(encoding="utf-8")
    return workflow.format(
        genre_skeleton=genre_path.read_text(encoding="utf-8").strip(),
        source_completeness_rule=_source_completeness_rule(context_incomplete),
        style_example=STYLE_EXAMPLE_PATH.read_text(encoding="utf-8").strip(),
    )


def _source_completeness_rule(context_incomplete: bool) -> str:
    if context_incomplete:
        return (
            "- 本次输入不是完整原文（未提供或已截断）：最终 JSON 中禁止出现“原文未提供”；"
            "没有明确缺失证据时只能删除该论点，或写“当前输入摘录未包含”。"
        )
    return "- 本次输入未截断：只有输入中确实没有且需要披露的关键事实，才可写“原文未提供”。"


def _context_json(context: DocumentIR | None, *, max_context_chars: int) -> tuple[str, str, bool]:
    if context is None:
        return "{}", "未提供输入 DocumentIR。", True
    payload = context.model_dump(mode="json")
    payload["source"]["parsed_at"] = "<normalized-for-determinism>"
    encoded = _encode(payload)
    if len(encoded) <= max_context_chars:
        return encoded, "未截断。", False
    payload = _truncate_context_payload(payload, max_context_chars=max_context_chars)
    encoded = _encode(payload)
    if len(encoded) > max_context_chars:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    notice = (
        f"已截断说明: 输入 DocumentIR 超过 {max_context_chars} 字符,已压缩解析告警和目录,"
        "并按事实密度优先保留方法、参数、指标、对比、取舍、适用条件和风险;请勿编造被截断内容。"
    )
    return encoded, notice, True


def _encode(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _truncate_context_payload(payload: dict, *, max_context_chars: int) -> dict:
    truncated = copy.deepcopy(payload)
    _bound_warnings(truncated)
    content = truncated.setdefault("content", {})
    blocks = content.get("blocks")
    sheets = content.get("sheets")
    slides = content.get("slides")

    _bound_outline(content)

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
        original_blocks = blocks
        content["blocks"] = []
        _fit_non_block_context(truncated, max_context_chars=max_context_chars)
        content["blocks"] = _select_evidence_blocks(
            truncated,
            original_blocks,
            max_context_chars=max_context_chars,
        )

    _fit_non_block_context(truncated, max_context_chars=max_context_chars)
    return truncated


def _bound_warnings(payload: dict) -> None:
    warnings = payload.get("warnings")
    if not isinstance(warnings, list):
        return
    bounded = [_truncate_text(str(warning), 180) for warning in warnings[:CONTEXT_WARNING_LIMIT]]
    remaining = len(warnings) - len(bounded)
    if remaining > 0:
        bounded.append(f"另有 {remaining} 条解析 warning 未展开。")
    payload["warnings"] = bounded


def _bound_outline(content: dict) -> None:
    outline = content.get("outline")
    if not isinstance(outline, list) or len(outline) <= CONTEXT_OUTLINE_LIMIT:
        return
    indexes = _evenly_spaced_indexes(len(outline), CONTEXT_OUTLINE_LIMIT)
    content["outline"] = [outline[index] for index in indexes]


def _evenly_spaced_indexes(length: int, limit: int) -> list[int]:
    if length <= limit:
        return list(range(length))
    return sorted({round(index * (length - 1) / (limit - 1)) for index in range(limit)})


def _select_evidence_blocks(
    payload: dict,
    blocks: list,
    *,
    max_context_chars: int,
) -> list:
    content = payload["content"]
    heading_for: dict[int, int | None] = {}
    latest_heading: int | None = None
    candidates: list[tuple[int, int]] = []
    compacted: dict[int, dict] = {}

    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        compacted[index] = _compact_block(block)
        if block.get("type") == "heading":
            latest_heading = index
            continue
        heading_for[index] = latest_heading
        candidates.append((_evidence_score(block), index))

    candidate_indexes = _prioritized_candidate_indexes(blocks, candidates)
    selected: set[int] = set()
    first_heading = next(
        (index for index, block in enumerate(blocks) if isinstance(block, dict) and block.get("type") == "heading"),
        None,
    )
    if first_heading is not None:
        selected.add(first_heading)

    for index in candidate_indexes[:CONTEXT_CANDIDATE_LIMIT]:
        additions = {index}
        heading_index = heading_for[index]
        if heading_index is not None:
            additions.add(heading_index)
        additions.update(_supporting_neighbor_indexes(blocks, index))
        trial_indexes = sorted(selected | additions)
        content["blocks"] = [compacted[item] for item in trial_indexes]
        if len(_encode(payload)) <= max_context_chars:
            selected.update(additions)

    selected_blocks = [compacted[index] for index in sorted(selected)]
    content["blocks"] = selected_blocks
    return selected_blocks


def _supporting_neighbor_indexes(blocks: list, index: int) -> set[int]:
    block = blocks[index]
    if not isinstance(block, dict):
        return set()
    block_type = block.get("type")
    neighbors: set[int] = set()
    if block_type == "table":
        for neighbor_index in range(index + 1, min(len(blocks), index + 3)):
            neighbor = blocks[neighbor_index]
            if not isinstance(neighbor, dict) or neighbor.get("type") == "heading":
                break
            if neighbor.get("type") in {"paragraph", "bullet_list", "numbered_list"}:
                neighbors.add(neighbor_index)
                break
        return neighbors
    if block_type not in {"paragraph", "bullet_list", "numbered_list"}:
        return neighbors
    for neighbor_index in range(index - 1, max(-1, index - 3), -1):
        neighbor = blocks[neighbor_index]
        if not isinstance(neighbor, dict) or neighbor.get("type") == "heading":
            break
        if neighbor.get("type") == "table":
            neighbors.add(neighbor_index)
            break
    return neighbors


def _prioritized_candidate_indexes(blocks: list, candidates: list[tuple[int, int]]) -> list[int]:
    ranked = sorted(candidates, key=lambda item: (-item[0], item[1]))
    ordered: list[int] = []
    seen: set[int] = set()

    def add(items: list[tuple[int, int]]) -> None:
        for _, index in items:
            if index not in seen:
                seen.add(index)
                ordered.append(index)

    executive_boundary = max(1, len(blocks) // 10)
    add([item for item in ranked if item[1] < executive_boundary and item[0] > 0][:4])

    segment_count = min(8, max(1, len(blocks) // 12))
    segments: list[list[tuple[int, int]]] = [[] for _ in range(segment_count)]
    for item in candidates:
        if item[0] <= 0:
            continue
        segment = min(segment_count - 1, item[1] * segment_count // max(1, len(blocks)))
        segments[segment].append(item)
    for segment in segments:
        segment.sort(key=lambda item: (-item[0], item[1]))
    for rank in range(3):
        add([segment[rank] for segment in segments if len(segment) > rank])

    categories: list[list[tuple[int, int]]] = [[], [], [], []]
    for item in ranked:
        block = blocks[item[1]]
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        if EVIDENCE_MEASUREMENT_PATTERN.search(text) or EVIDENCE_RESULT_PATTERN.search(text):
            categories[0].append(item)
        if EVIDENCE_TRADEOFF_PATTERN.search(text) or EVIDENCE_CONDITION_PATTERN.search(text):
            categories[1].append(item)
        if EVIDENCE_METHOD_PATTERN.search(text):
            categories[2].append(item)
        if block.get("type") == "table":
            categories[3].append(item)
    for rank in range(max((len(category) for category in categories), default=0)):
        add([category[rank] for category in categories if len(category) > rank])

    add(ranked)
    return ordered


def _compact_block(block: dict) -> dict:
    compacted = copy.deepcopy(block)
    block_type = compacted.get("type")
    if block_type in {"heading", "paragraph"}:
        compacted["text"] = _truncate_text(str(compacted.get("text", "")), CONTEXT_TEXT_LIMIT)
    elif block_type in {"bullet_list", "numbered_list"}:
        compacted["items"] = [
            {**item, "text": _truncate_text(str(item.get("text", "")), 240)}
            for item in compacted.get("items", [])[:8]
            if isinstance(item, dict)
        ]
    elif block_type == "table":
        rows = compacted.get("rows", [])
        ranked_rows = sorted(
            enumerate(rows),
            key=lambda item: (-_evidence_score_text(" ".join(str(cell) for cell in item[1])), item[0]),
        )[:CONTEXT_TABLE_ROW_LIMIT]
        compacted["rows"] = [
            [_truncate_text(str(cell), 180) for cell in rows[index]]
            for index in sorted(index for index, _ in ranked_rows)
        ]
        compacted["header"] = [_truncate_text(str(cell), 120) for cell in compacted.get("header", [])]
    return compacted


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head_length = limit * 2 // 3
    tail_length = limit - head_length - len("...[truncated]...")
    return f"{text[:head_length]}...[truncated]...{text[-tail_length:]}"


def _evidence_score(block: dict) -> int:
    block_type = block.get("type")
    text = _block_text(block)
    score = _evidence_score_text(text)
    if block_type == "table":
        score += 8
    elif block_type in {"bullet_list", "numbered_list"}:
        score += 2
    elif block_type == "image_placeholder":
        score -= 2
    elif block_type == "page_break":
        score -= 8
    if CAPTION_PATTERN.match(text):
        score -= 8
    return score


def _block_text(block: dict) -> str:
    block_type = block.get("type")
    if block_type in {"heading", "paragraph"}:
        return str(block.get("text", ""))
    if block_type in {"bullet_list", "numbered_list"}:
        return " ".join(str(item.get("text", "")) for item in block.get("items", []) if isinstance(item, dict))
    if block_type == "table":
        cells = [*block.get("header", [])]
        cells.extend(cell for row in block.get("rows", []) for cell in row)
        return " ".join(str(cell) for cell in cells)
    return " ".join(str(block.get(key, "")) for key in ("caption", "ref"))


def _evidence_score_text(text: str) -> int:
    measurements = min(4, len(EVIDENCE_MEASUREMENT_PATTERN.findall(text)))
    methods = min(4, len(EVIDENCE_METHOD_PATTERN.findall(text)))
    tradeoffs = min(4, len(EVIDENCE_TRADEOFF_PATTERN.findall(text)))
    conditions = min(3, len(EVIDENCE_CONDITION_PATTERN.findall(text)))
    results = min(4, len(EVIDENCE_RESULT_PATTERN.findall(text)))
    return measurements * 4 + methods * 2 + tradeoffs * 3 + conditions * 3 + results * 3


def _fit_non_block_context(payload: dict, *, max_context_chars: int) -> None:
    content = payload["content"]
    while len(_encode(payload)) > max_context_chars:
        warnings = payload.get("warnings")
        outline = content.get("outline")
        slides = content.get("slides")
        sheets = content.get("sheets")
        if isinstance(warnings, list) and warnings:
            warnings.pop()
            continue
        if isinstance(outline, list) and len(outline) > 1:
            outline.pop()
            continue
        if _drop_table_tail(content):
            continue
        if isinstance(slides, list) and _drop_slide_tail(slides):
            continue
        if isinstance(sheets, list) and _drop_sheet_tail(sheets):
            continue
        if isinstance(slides, list) and len(slides) > 1:
            slides.pop()
            continue
        if isinstance(sheets, list) and len(sheets) > 1:
            sheets.pop()
            continue
        break


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
    return (TEMPLATE_DIR / "ir_generation.txt").read_text(encoding="utf-8")
