from __future__ import annotations

import copy
from dataclasses import dataclass, field
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.generators.interface import IRTextGenerator
from app.generation.layout_policy import LAYOUT_SELECTION_RULES, detect_sequence_evidence, timeline_parts
from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.ir.errors import ValidationItem, ValidationResult
from app.ir.repair import repair_generated_text, repair_ir_text
from app.ir.shell import JsonExtractionError, extract_json_text, validate_deck_ir_text
from app.ir.validation import validate_deck_ir
from app.prompting.builder import Depth, build_prompt


OUTLINE_MARKER = "[Deck 大纲规划]"
CHUNK_MARKER = "[分段生成范围]"
DEFAULT_TARGET_PAGES: dict[Depth, int] = {"概览": 8, "标准": 11, "详细": 16}
CHUNK_SIZE = 4
FOCUSED_CONTEXT_CHARS = 10000
LayoutName = Literal[
    "cover",
    "agenda",
    "section",
    "title_bullets",
    "two_column",
    "table",
    "cards",
    "chart",
    "architecture_diagram",
    "process_flow",
    "timeline",
    "image",
    "conclusion",
    "composite",
]


class GenerationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: int | None = Field(default=None, ge=3, le=30)
    depth: Depth | None = None

    @property
    def enabled(self) -> bool:
        return self.pages is not None or self.depth is not None

    @property
    def effective_depth(self) -> Depth:
        return self.depth or "标准"

    @property
    def target_pages(self) -> int:
        return self.pages or DEFAULT_TARGET_PAGES[self.effective_depth]

    @property
    def segmented(self) -> bool:
        return self.effective_depth == "详细" or self.target_pages > 12


class OutlinePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1, le=30)
    layout: LayoutName
    title: str = Field(min_length=1)
    focus: str = Field(min_length=1)
    source_headings: list[str] = Field(default_factory=list, max_length=3)
    source_evidence: list[str] = Field(default_factory=list, max_length=3)
    selection_reason: str = Field(min_length=1)
    content_budget: int = Field(ge=1, le=3)


class DeckOutline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    pages: list[OutlinePage] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def validate_page_sequence(self) -> "DeckOutline":
        if [page.index for page in self.pages] != list(range(1, len(self.pages) + 1)):
            raise ValueError("outline page indexes must be contiguous from 1")
        if self.pages[0].layout != "cover":
            raise ValueError("outline first page must use cover")
        if self.pages[-1].layout != "conclusion":
            raise ValueError("outline last page must use conclusion")
        page_count = len(self.pages)
        layouts = [page.layout for page in self.pages]
        if page_count < 7 and "agenda" in layouts:
            raise ValueError("少于 7 页的大纲不得使用 agenda")
        if page_count < 10 and "section" in layouts:
            raise ValueError("少于 10 页的大纲不得使用 section")
        repeated = 1
        for previous, current in zip(layouts[1:-2], layouts[2:-1]):
            repeated = repeated + 1 if current == previous else 1
            if repeated >= 3:
                raise ValueError("正文不得连续 3 页使用同一 layout")
        return self


@dataclass
class DeckGenerationAttempt:
    validation: ValidationResult[DeckIR]
    raw_text: str
    prompts: dict[str, str]
    depth: Depth
    target_pages: int
    segmented: bool
    chunk_count: int
    repair_events: list[dict[str, Any]] = field(default_factory=list)

    def manifest(self) -> dict[str, Any]:
        return {
            "depth": self.depth,
            "target_pages": self.target_pages,
            "segmented": self.segmented,
            "chunk_count": self.chunk_count,
            "repair_events": self.repair_events,
        }


def generate_deck(
    document: DocumentIR,
    *,
    generator: IRTextGenerator,
    options: GenerationOptions,
    max_context_chars: int = 12000,
    max_output_chars: int = 6000,
) -> DeckGenerationAttempt:
    if not options.enabled:
        raise ValueError("generate_deck depth orchestration requires explicit options")
    if not options.segmented:
        return _generate_single(
            document,
            generator=generator,
            options=options,
            max_context_chars=max_context_chars,
            max_output_chars=max_output_chars,
        )
    return _generate_segmented(
        document,
        generator=generator,
        options=options,
        max_context_chars=max_context_chars,
        max_output_chars=max_output_chars,
    )


def build_outline_prompt(document: DocumentIR, options: GenerationOptions, *, max_context_chars: int) -> str:
    source_outline = [item.model_dump(mode="json") for item in document.content.outline]
    source_title = next(
        (str(item.get("text", "")).strip() for item in source_outline if str(item.get("text", "")).strip()),
        document.source.filename.rsplit(".", 1)[0],
    )
    sequence_evidence = detect_sequence_evidence(document.model_dump(mode="json"))
    source_evidence = _planning_evidence(document)
    planning = {
        "depth": options.effective_depth,
        "target_pages": options.target_pages,
        "source_filename": document.source.filename,
        "source_title": source_title,
        "source_outline": source_outline[:60],
        "source_evidence": source_evidence,
        "sequence_evidence": (
            {
                "layout": sequence_evidence.layout,
                "items": list(sequence_evidence.items),
                "labels": list(sequence_evidence.labels),
            }
            if sequence_evidence is not None
            else None
        ),
    }
    context = _outline_context(document, max_context_chars=max_context_chars)
    return (
        "[任务] 先规划完整 Deck 大纲，本轮不生成 DeckIR。只输出符合下方独立 Schema 的 JSON。\n"
        "[要求] 页数必须精确；第 1 页 cover、最后 1 页 conclusion；观点写进标题；每页 focus 只承载一个判断；"
        "source_headings 只能引用输入里的真实标题；source_evidence 只能摘取输入中的方法名、数据、权衡或条件；"
        "selection_reason 解释为何该内容适合当前 layout；content_budget 取 1-3，表示该页核心内容点上限。\n"
        "[版式节奏] 7 页以上才默认使用 agenda；10 页以上且输入存在至少两个一级章节时才使用 section；"
        "有足够内容关系时再增加版式变化；正文不得连续 3 页使用同一 layout。"
        f"{LAYOUT_SELECTION_RULES}"
        "只能使用 DeckIR 已登记的 layout，禁止输出 H01-H42 等外部参考编号。\n"
        f"{OUTLINE_MARKER}\n{json.dumps(planning, ensure_ascii=False, sort_keys=True)}\n"
        f"[大纲输入 DocumentIR 摘要]\n{context}\n"
        f"[独立大纲 Schema]\n{json.dumps(DeckOutline.model_json_schema(), ensure_ascii=False, sort_keys=True)}\n"
        "[输出纪律] 只输出一个完整 JSON 对象，不要解释、Markdown 围栏或 IR 字段。"
    )


def validate_outline_text(raw: str, *, expected_pages: int) -> ValidationResult[DeckOutline]:
    try:
        extracted = extract_json_text(raw)
        outline = DeckOutline.model_validate_json(extracted)
    except JsonExtractionError as exc:
        return ValidationResult(value=None, errors=[_outline_error("D001", "", f"大纲 JSON 剥壳失败: {exc}")])
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        return ValidationResult(
            value=None,
            errors=[_outline_error("D002", location, f"大纲结构不合法: {first.get('msg', 'validation failed')}")],
        )
    if len(outline.pages) != expected_pages:
        return ValidationResult(
            value=None,
            errors=[
                _outline_error(
                    "D006",
                    "pages",
                    f"大纲目标为 {expected_pages} 页，实际为 {len(outline.pages)} 页",
                )
            ],
        )
    return ValidationResult(value=outline)


def stub_outline_payload(planning: dict[str, Any]) -> dict[str, Any]:
    total = int(planning.get("target_pages", 8))
    title = str(planning.get("source_title") or "Stub 技术报告")
    source_outline = [item for item in planning.get("source_outline", []) if isinstance(item, dict)]
    headings = [str(item.get("text")) for item in source_outline if str(item.get("text", "")).strip()]
    top_level_headings = [item for item in source_outline if item.get("level") == 1]
    evidence_pool = [str(item).strip() for item in planning.get("source_evidence", []) if str(item).strip()]
    layout_cycle: list[LayoutName] = [
        "title_bullets",
        "two_column",
        "table",
        "cards",
    ]
    middle_layouts: list[LayoutName] = []
    if total >= 7:
        middle_layouts.append("agenda")
    if total >= 10 and len(top_level_headings) >= 2:
        middle_layouts.append("section")
    sequence = planning.get("sequence_evidence")
    if isinstance(sequence, dict) and sequence.get("layout") in {"process_flow", "timeline"}:
        middle_layouts.append(sequence["layout"])
    cycle_index = 0
    while len(middle_layouts) < total - 2:
        middle_layouts.append(layout_cycle[cycle_index % len(layout_cycle)])
        cycle_index += 1
    pages: list[dict[str, Any]] = []
    for index in range(1, total + 1):
        if index == 1:
            layout: LayoutName = "cover"
        elif index == total:
            layout = "conclusion"
        else:
            layout = middle_layouts[index - 2]
        source_heading = headings[(index - 2) % len(headings)] if headings and index > 1 else title
        source_evidence = evidence_pool[:3] or ([source_heading] if headings else [])
        if layout in {"process_flow", "timeline"} and isinstance(sequence, dict):
            source_evidence = [str(item) for item in sequence.get("items", [])[:3] if str(item).strip()]
            source_heading = source_evidence[0] if source_evidence else source_heading
        content_budget = 1 if layout == "cover" else 2 if layout in {"agenda", "section"} else 3
        pages.append(
            {
                "index": index,
                "layout": layout,
                "title": title if layout == "cover" else f"{source_heading}形成可复核结论",
                "focus": f"围绕{source_heading}给出方法、数据和适用条件",
                "source_headings": [source_heading] if headings else [],
                "source_evidence": source_evidence,
                "selection_reason": _stub_layout_reason(layout),
                "content_budget": content_budget,
            }
        )
    return {"title": title, "pages": pages}


def _planning_evidence(document: DocumentIR) -> list[str]:
    evidence: list[str] = []
    for block in document.content.blocks:
        payload = block.model_dump(mode="json")
        if payload.get("type") == "heading":
            continue
        values = _text_values(payload)
        text = " ".join(value.strip() for value in values if value.strip())
        if text and text not in evidence:
            evidence.append(text[:240])
        if len(evidence) >= 12:
            break
    return evidence


def _stub_layout_reason(layout: LayoutName) -> str:
    return {
        "cover": "封面建立汇报主题",
        "agenda": "目录概括长稿结构",
        "section": "章节页分隔多个一级主题",
        "title_bullets": "观点页承载结论与少量依据",
        "two_column": "双栏适合方法与依据对照",
        "table": "表格适合结构化比较",
        "cards": "卡片适合并列要素",
        "chart": "图表适合数值比较",
        "architecture_diagram": "架构图适合节点关系",
        "process_flow": "流程页适合线性步骤",
        "timeline": "时间线适合阶段演进",
        "image": "图文页保留证据位置",
        "conclusion": "结论页收束行动",
        "composite": "组合页适合两个半页组件联读",
    }[layout]


def stub_chunk_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    pages = chunk.get("outline_pages", [])
    title = str(chunk.get("deck_title") or "Stub 技术报告")
    slides = [_stub_slide(page, title=title, total_pages=int(chunk.get("global_target_pages", len(pages)))) for page in pages]
    return {
        "ir_type": "deck",
        "ir_version": "1.9",
        "meta": {"title": title, "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
        "slides": slides,
    }


def fit_stub_deck_pages(payload: dict[str, Any], target_pages: int) -> dict[str, Any]:
    fitted = copy.deepcopy(payload)
    slides = list(fitted.get("slides", []))
    conclusion = slides.pop() if slides and slides[-1].get("layout") == "conclusion" else None
    while len(slides) + (1 if conclusion else 0) < target_pages:
        index = len(slides) + 1
        slides.append(
            {
                "layout": "title_bullets",
                "title": f"第{index}项技术结论具备方法和数据支撑",
                "bullets": [
                    {"text": "具体方法：按输入结构提取并组织可复核内容", "level": 1},
                    {"text": "关键数据：保留原始材料中的指标和对比关系", "level": 1},
                    {"text": "适用条件：最终结论仍需结合原文人工复核", "level": 1},
                ],
            }
        )
    if conclusion is not None:
        slides = slides[: target_pages - 1] + [conclusion]
    else:
        slides = slides[:target_pages]
    fitted["slides"] = slides
    return fitted


def _generate_single(
    document: DocumentIR,
    *,
    generator: IRTextGenerator,
    options: GenerationOptions,
    max_context_chars: int,
    max_output_chars: int,
) -> DeckGenerationAttempt:
    prompt = build_prompt(
        kind="deck",
        context=document,
        max_context_chars=max_context_chars,
        max_output_chars=max_output_chars,
        depth=options.effective_depth,
        pages=options.target_pages,
    )
    raw = generator.generate(prompt, target="deck_ir")
    initial = _validate_deck_page_target(raw, options.target_pages)
    repair_events = _repair_event("deck", initial)
    validation = repair_ir_text(
        raw,
        target="deck_ir",
        generator=generator,
        expected_pages=options.target_pages,
    )
    return DeckGenerationAttempt(
        validation=validation,
        raw_text=raw,
        prompts={"deck.txt": prompt},
        depth=options.effective_depth,
        target_pages=options.target_pages,
        segmented=False,
        chunk_count=1,
        repair_events=repair_events,
    )


def _generate_segmented(
    document: DocumentIR,
    *,
    generator: IRTextGenerator,
    options: GenerationOptions,
    max_context_chars: int,
    max_output_chars: int,
) -> DeckGenerationAttempt:
    prompts: dict[str, str] = {}
    repair_events: list[dict[str, Any]] = []
    outline_prompt = build_outline_prompt(document, options, max_context_chars=max_context_chars)
    prompts["outline.txt"] = outline_prompt
    outline_raw = generator.generate(outline_prompt, target="analysis")
    initial_outline = validate_outline_text(outline_raw, expected_pages=options.target_pages)
    repair_events.extend(_repair_event("outline", initial_outline))
    outline_result = repair_generated_text(
        outline_raw,
        target="analysis",
        generator=generator,
        validator=lambda current: validate_outline_text(current, expected_pages=options.target_pages),
    )
    if not outline_result.ok or outline_result.value is None:
        return DeckGenerationAttempt(
            validation=_deck_failure(outline_result),
            raw_text=outline_raw,
            prompts=prompts,
            depth=options.effective_depth,
            target_pages=options.target_pages,
            segmented=True,
            chunk_count=0,
            repair_events=repair_events,
        )

    outline = outline_result.value
    decks: list[DeckIR] = []
    last_raw = outline_raw
    for chunk_index, start in enumerate(range(0, len(outline.pages), CHUNK_SIZE), start=1):
        pages = outline.pages[start : start + CHUNK_SIZE]
        focused_document = _focused_context(document, pages)
        prompt = _chunk_prompt(
            focused_document,
            outline,
            pages,
            options=options,
            max_context_chars=max_context_chars,
            max_output_chars=max_output_chars,
        )
        prompts[f"chunk-{chunk_index:02d}.txt"] = prompt
        raw = generator.generate(prompt, target="deck_ir")
        last_raw = raw
        initial_chunk = _validate_deck_page_target(raw, len(pages))
        repair_events.extend(_repair_event(f"chunk-{chunk_index:02d}", initial_chunk))
        chunk_result = repair_ir_text(
            raw,
            target="deck_ir",
            generator=generator,
            expected_pages=len(pages),
        )
        if not chunk_result.ok or chunk_result.value is None:
            return DeckGenerationAttempt(
                validation=chunk_result,
                raw_text=raw,
                prompts=prompts,
                depth=options.effective_depth,
                target_pages=options.target_pages,
                segmented=True,
                chunk_count=chunk_index,
                repair_events=repair_events,
            )
        decks.append(chunk_result.value)

    merged_payload = decks[0].model_dump(mode="json", by_alias=True)
    merged_payload["meta"]["title"] = outline.title
    merged_payload["slides"] = [
        slide.model_dump(mode="json", by_alias=True)
        for deck in decks
        for slide in deck.slides
    ]
    final_validation = validate_deck_ir(merged_payload)
    if final_validation.ok and final_validation.value is not None and len(final_validation.value.slides) != options.target_pages:
        final_validation = ValidationResult(
            value=None,
            errors=[_outline_error("D006", "slides", "合并后的 DeckIR 页数与目标不一致")],
        )
    final_raw = (
        final_validation.value.model_dump_json(indent=2, by_alias=True)
        if final_validation.ok and final_validation.value is not None
        else last_raw
    )
    return DeckGenerationAttempt(
        validation=final_validation,
        raw_text=final_raw,
        prompts=prompts,
        depth=options.effective_depth,
        target_pages=options.target_pages,
        segmented=True,
        chunk_count=len(decks),
        repair_events=repair_events,
    )


def _chunk_prompt(
    document: DocumentIR,
    outline: DeckOutline,
    pages: list[OutlinePage],
    *,
    options: GenerationOptions,
    max_context_chars: int,
    max_output_chars: int,
) -> str:
    base = build_prompt(
        kind="deck",
        context=document,
        max_context_chars=max_context_chars,
        max_output_chars=max_output_chars,
        depth=options.effective_depth,
        pages=len(pages),
    )
    chunk = {
        "deck_title": outline.title,
        "global_target_pages": options.target_pages,
        "chunk_start": pages[0].index,
        "chunk_end": pages[-1].index,
        "outline_pages": [page.model_dump(mode="json") for page in pages],
    }
    return (
        f"{base}\n{CHUNK_MARKER}\n{json.dumps(chunk, ensure_ascii=False, sort_keys=True)}\n"
        "[分段纪律] slides 只能包含上述页码范围对应的页面，数量必须与 outline_pages 完全一致；"
        "每页使用指定 layout/focus，并从 source_headings 对应原文提取具体方法、数据、权衡或条件。"
        "仍输出一个完整 DeckIR envelope；不要输出全局其他页，调用侧会按 index 合并并再次校验。"
    )


def _outline_context(document: DocumentIR, *, max_context_chars: int) -> str:
    payload = document.model_dump(mode="json")
    payload["source"]["parsed_at"] = "<normalized-for-determinism>"
    payload["warnings"] = _warning_summary(payload.get("warnings", []))
    content = payload["content"]
    if content.get("blocks"):
        compact_blocks = []
        for block in content["blocks"]:
            copy_block = dict(block)
            if copy_block.get("type") == "paragraph":
                copy_block["text"] = str(copy_block.get("text", ""))[:400]
            if copy_block.get("type") == "table":
                copy_block["rows"] = copy_block.get("rows", [])[:5]
            compact_blocks.append(copy_block)
        content["blocks"] = compact_blocks
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    while len(encoded) > max_context_chars:
        if content.get("blocks") and _drop_last_non_heading(content["blocks"]):
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            continue
        if content.get("slides"):
            content["slides"].pop()
        elif content.get("sheets"):
            content["sheets"].pop()
        else:
            break
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return encoded


def _drop_last_non_heading(blocks: list[dict[str, Any]]) -> bool:
    for index in range(len(blocks) - 1, -1, -1):
        if blocks[index].get("type") != "heading":
            del blocks[index]
            return True
    return False


def _focused_context(document: DocumentIR, pages: list[OutlinePage]) -> DocumentIR:
    if document.source.format not in {"md", "docx"}:
        return document
    if not any(page.source_headings for page in pages):
        return document
    payload = document.model_dump(mode="json")
    payload["warnings"] = _warning_summary(payload.get("warnings", []))
    blocks = payload["content"]["blocks"]
    page_budget = max(1000, FOCUSED_CONTEXT_CHARS // max(1, len(pages)))
    selected_indexes: set[int] = set()
    for page in pages:
        page_indexes: set[int] = set()
        for heading in page.source_headings:
            page_indexes.update(_section_indexes(blocks, heading))
        selected_indexes.update(_limit_section_indexes(blocks, page_indexes, max_chars=page_budget))
    if not selected_indexes:
        return document
    selected = [copy.deepcopy(blocks[index]) for index in sorted(selected_indexes)]
    for block in selected:
        if block.get("type") == "table":
            block["rows"] = block.get("rows", [])[:5]
    selected_headings = {
        str(block.get("text")) for block in selected if block.get("type") == "heading" and str(block.get("text", "")).strip()
    }
    payload["content"]["blocks"] = selected
    payload["content"]["outline"] = [
        item for item in payload["content"]["outline"] if item["text"] in selected_headings
    ]
    return DocumentIR.model_validate(payload)


def _section_indexes(blocks: list[dict[str, Any]], requested_heading: str) -> set[int]:
    start = next(
        (
            index
            for index, block in enumerate(blocks)
            if block.get("type") == "heading" and str(block.get("text")) == requested_heading
        ),
        None,
    )
    if start is None:
        return set()
    base_level = int(blocks[start].get("level", 1))
    end = len(blocks)
    for index in range(start + 1, len(blocks)):
        block = blocks[index]
        if block.get("type") == "heading" and int(block.get("level", 1)) <= base_level:
            end = index
            break
    return set(range(start, end))


def _limit_section_indexes(
    blocks: list[dict[str, Any]],
    indexes: set[int],
    *,
    max_chars: int,
) -> set[int]:
    if not indexes:
        return set()
    essentials = {index for index in indexes if blocks[index].get("type") == "heading"}
    selected = set(essentials)
    used = sum(_block_context_size(blocks[index]) for index in selected)
    candidates = sorted(
        (index for index in indexes if index not in selected),
        key=lambda index: (-_evidence_score(blocks[index]), index),
    )
    for index in candidates:
        size = _block_context_size(blocks[index])
        if selected and used + size > max_chars:
            continue
        selected.add(index)
        used += size
    return selected


def _block_context_size(block: dict[str, Any]) -> int:
    measured = block
    if block.get("type") == "table":
        measured = {**block, "rows": block.get("rows", [])[:5]}
    return len(json.dumps(measured, ensure_ascii=False, sort_keys=True))


def _evidence_score(block: dict[str, Any]) -> float:
    text = " ".join(_text_values(block))
    score = min(len(text), 500) / 100
    if block.get("type") == "table":
        score += 100
    if re.search(r"\d", text):
        score += 8
    score += 2 * len(
        re.findall(
            r"CNN|LSTM|edRVFL|WFRFT|dB|km|%|精度|误差|时延|模型|算法|参数|指标|结果|仿真|复杂度|权衡",
            text,
            flags=re.IGNORECASE,
        )
    )
    return score


def _warning_summary(warnings: list[str]) -> list[str]:
    if not warnings:
        return []
    return [f"focused generation context omitted {len(warnings)} parser warnings; see persisted document_ir.json"]


def _text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _text_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _text_values(item)]
    return []


def _validate_deck_page_target(raw: str, expected_pages: int) -> ValidationResult[DeckIR]:
    result = validate_deck_ir_text(raw)
    if not result.ok or result.value is None or len(result.value.slides) == expected_pages:
        return result
    return ValidationResult(
        value=None,
        errors=[
            ValidationItem(
                code="D006",
                level="Error",
                loc="slides",
                message=f"目标页数为 {expected_pages}，实际生成 {len(result.value.slides)} 页。",
                suggestion=f"把 slides 调整为恰好 {expected_pages} 页。",
            )
        ],
        warnings=result.warnings,
        infos=result.infos,
    )


def _repair_event(stage: str, result: ValidationResult[Any]) -> list[dict[str, Any]]:
    if result.ok:
        return []
    return [
        {
            "stage": stage,
            "initial_error_codes": [item.code for item in result.errors],
            "initial_messages": [item.message for item in result.errors],
        }
    ]


def _deck_failure(result: ValidationResult[Any]) -> ValidationResult[DeckIR]:
    return ValidationResult(value=None, errors=result.errors, warnings=result.warnings, infos=result.infos)


def _outline_error(code: str, loc: str, message: str) -> ValidationItem:
    return ValidationItem(
        code=code,
        level="Error",
        loc=loc,
        message=message,
        suggestion="按指定页数重建完整大纲或 DeckIR，不要续写截断残片。",
    )


def _stub_slide(page: dict[str, Any], *, title: str, total_pages: int) -> dict[str, Any]:
    layout = str(page.get("layout"))
    page_title = str(page.get("title") or page.get("focus") or title)
    focus = str(page.get("focus") or "内容待复核")
    evidence = [str(item) for item in page.get("source_evidence", []) if str(item).strip()]
    bullets = evidence or [focus]
    if layout == "cover":
        return {"layout": "cover", "title": title, "subtitle": "按所选深度生成的可编辑技术评审稿"}
    if layout == "agenda":
        return {"layout": "agenda", "items": ["技术背景与目标", "方案与关键数据", "结论与下一步"]}
    if layout == "section":
        return {"layout": "section", "index": max(1, int(page.get("index", 1)) - 1), "title": page_title}
    if layout == "two_column":
        return {
            "layout": "two_column",
            "title": page_title,
            "left": {"heading": "方法", "text": focus},
            "right": {"heading": "依据", "bullets": [{"text": item, "level": 1} for item in bullets[:3]]},
        }
    if layout == "table":
        return {
            "layout": "table",
            "title": page_title,
            "table": {
                "header": ["维度", "结论", "依据"],
                "rows": [["方法", focus, bullets[0]], ["条件", "按原文复核", bullets[-1]]],
            },
        }
    if layout == "cards":
        return {
            "layout": "cards",
            "title": page_title,
            "cards": [
                {"title": "方法", "desc": focus},
                {"title": "数据", "desc": bullets[0]},
                {"title": "条件", "desc": bullets[-1]},
            ],
        }
    if layout == "chart":
        return {
            "layout": "chart",
            "title": page_title,
            "chart": {"kind": "bar", "categories": ["方案A", "方案B"], "series": [{"name": "指标", "values": [1, 2]}]},
        }
    if layout == "architecture_diagram":
        return {
            "layout": "architecture_diagram",
            "title": page_title,
            "nodes": [
                {"id": "input", "text": "输入", "type": "primary"},
                {"id": "method", "text": focus, "type": "secondary"},
                {"id": "output", "text": "输出", "type": "data"},
            ],
            "edges": [{"from": "input", "to": "method"}, {"from": "method", "to": "output"}],
            "groups": [],
        }
    if layout == "process_flow":
        steps = bullets[:7]
        return {
            "layout": "process_flow",
            "title": page_title,
            "steps": [
                {"id": f"step-{index}", "title": item, "description": None}
                for index, item in enumerate(steps, start=1)
            ],
            "orientation": "horizontal",
        }
    if layout == "timeline":
        milestone_items = bullets[:8]
        return {
            "layout": "timeline",
            "title": page_title,
            "milestones": [
                {
                    "label": timeline_parts(item)[0],
                    "title": timeline_parts(item)[1],
                    "status": "planned",
                }
                for item in milestone_items
            ],
            "orientation": "horizontal",
        }
    if layout == "image":
        return {"layout": "image", "title": page_title, "placeholder": focus, "caption": bullets[0]}
    if layout == "conclusion":
        return {"layout": "conclusion", "title": page_title, "bullets": bullets[:3], "cta": "结合原文完成终审"}
    if layout == "composite":
        return {
            "layout": "composite",
            "title": page_title,
            "regions": [
                {
                    "slot": "left",
                    "components": [{
                        "layout": "title_bullets",
                        "title": "方法",
                        "bullets": [{"text": focus, "level": 1}],
                    }],
                },
                {
                    "slot": "right",
                    "components": [{
                        "layout": "cards",
                        "title": "依据",
                        "cards": [
                            {"title": "证据一", "desc": bullets[0]},
                            {"title": "证据二", "desc": bullets[-1]},
                        ],
                    }],
                },
            ],
        }
    return {
        "layout": "title_bullets",
        "title": page_title,
        "bullets": [{"text": f"{focus}：{item}", "level": 1} for item in bullets[:3]],
    }
