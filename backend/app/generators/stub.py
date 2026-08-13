from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Literal

from app.generation.analysis import ANALYSIS_MARKER, stub_analysis_payload
from app.generation.layout_policy import detect_sequence_evidence, timeline_parts


CONTEXT_MARKER = "[输入 DocumentIR]"
VISUAL_PLAN_MARKER = "[VisualPlan 1.0]"


def _coerce_int(value: Any, *, default: int = 1, low: int | None = None, high: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if low is not None:
        result = max(low, result)
    if high is not None:
        result = min(high, result)
    return result


class StubGenerator:
    name = "stub"

    def generate(
        self,
        prompt: str,
        *,
        target: Literal["word_ir", "deck_ir", "analysis"],
        cancel_event: Any | None = None,
    ) -> str:
        if target == "analysis":
            from app.generation.depth import OUTLINE_MARKER, stub_outline_payload

            planning = _json_after_marker(prompt, OUTLINE_MARKER, side="pre", required_keys=frozenset({"target_pages"}))
            if planning is not None:
                return json.dumps(stub_outline_payload(planning), ensure_ascii=False, indent=2)
            measured = _json_after_marker(prompt, ANALYSIS_MARKER, side="pre", required_keys=frozenset({"metrics"}))
            if measured is None:
                raise ValueError(
                    "analysis prompt is missing measured parser data "
                    "(no `[分析实测数据]` marker with a metrics payload found)"
                )
            return json.dumps(stub_analysis_payload(measured), ensure_ascii=False, indent=2)
        context = _extract_document_context(prompt)
        if target == "word_ir":
            payload = _word_payload(context)
        elif target == "deck_ir":
            from app.generation.depth import CHUNK_MARKER, fit_stub_deck_pages, stub_chunk_payload

            chunk = _json_after_marker(prompt, CHUNK_MARKER, side="post")
            if chunk is not None:
                payload = stub_chunk_payload(chunk)
            else:
                payload = _deck_payload(context)
                visual_plan = _json_after_marker(prompt, VISUAL_PLAN_MARKER, side="post")
                _apply_visual_plan_to_deck_payload(payload, visual_plan)
                page_match = re.search(r"必须恰好生成\s*(\d+)\s*页", prompt)
                if page_match is not None:
                    payload = fit_stub_deck_pages(payload, int(page_match.group(1)))
        else:
            raise ValueError(f"unsupported target: {target}")
        return json.dumps(payload, ensure_ascii=False, indent=2)


def _json_after_marker(
    prompt: str,
    marker: str,
    *,
    side: Literal["pre", "post"] = "post",
    required_keys: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    # Markers injected BEFORE user-controlled content ("pre", e.g. the document
    # context that follows the marker) must be found with `find`: the tool's
    # occurrence is always first, so user content echoing the marker text
    # cannot hijack the parse. Markers appended AFTER all user content ("post",
    # e.g. chunk ranges) are unique at the tail, where `rfind` is correct.
    marker_index = prompt.find(marker) if side == "pre" else prompt.rfind(marker)
    if marker_index < 0:
        return None
    remainder = prompt[marker_index + len(marker) :].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(remainder)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if required_keys and not required_keys.issubset(payload):
        return None
    return payload


def _extract_document_context(prompt: str) -> dict[str, Any] | None:
    payload = _json_after_marker(
        prompt,
        CONTEXT_MARKER,
        side="pre",
        required_keys=frozenset({"ir_type", "source"}),
    )
    if payload is None or payload.get("ir_type") != "document":
        return None
    return payload


def _word_payload(context: dict[str, Any] | None) -> dict[str, Any]:
    title = _document_title(context, fallback="Stub 文档")
    blocks = _word_blocks(context)
    if not blocks:
        blocks = [
            {"type": "heading", "level": 1, "text": "内容摘要"},
            {"type": "paragraph", "text": "当前输入没有可映射正文，已生成可编辑的确定性占位内容。"},
        ]
    return {
        "ir_type": "word",
        "ir_version": "1.2",
        "meta": {"title": title, "classification": "内部公开"},
        "blocks": blocks,
    }


def _word_blocks(context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if context is None:
        return []
    content = context.get("content", {})
    source_format = context.get("source", {}).get("format")
    if source_format in {"md", "docx"}:
        return _copy_document_blocks(content.get("blocks", []))
    if source_format == "xlsx":
        return _sheet_word_blocks(content.get("sheets", []))
    if source_format == "pptx":
        return _slide_word_blocks(content.get("slides", []))
    return []


def _copy_document_blocks(blocks: Any) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    if not isinstance(blocks, list):
        return copied
    for block in blocks[:24]:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "heading":
            text = _text(block.get("text"))
            if text:
                copied.append({"type": "heading", "level": _coerce_int(block.get("level", 1), low=1, high=4), "text": text})
        elif block_type == "paragraph":
            text = _text(block.get("text"), max_chars=1000)
            if text:
                copied.append({"type": "paragraph", "text": text, "style": block.get("style", "normal")})
        elif block_type == "code_block":
            code = block.get("code")
            if isinstance(code, str) and code.strip():
                copied_block = {"type": "code_block", "code": code}
                language = block.get("language")
                if isinstance(language, str) and language.strip():
                    copied_block["language"] = language.strip()
                copied.append(copied_block)
        elif block_type in {"bullet_list", "numbered_list"}:
            items = _list_items(block.get("items"))
            if items:
                copied.append({"type": block_type, "items": items})
        elif block_type == "table":
            table = _normalize_table(block)
            if table is not None:
                copied.append({"type": "table", **table})
        elif block_type == "image_placeholder":
            ref = _text(block.get("ref"))
            caption = _text(block.get("caption"))
            if ref or caption:
                copied.append({"type": "image_placeholder", "ref": ref or None, "caption": caption or None})
        elif block_type == "page_break" and copied:
            copied.append({"type": "page_break"})
    while copied and copied[-1].get("type") == "page_break":
        copied.pop()
    return copied


def _sheet_word_blocks(sheets: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if not isinstance(sheets, list):
        return blocks
    for sheet in sheets[:6]:
        if not isinstance(sheet, dict):
            continue
        name = _text(sheet.get("name"), fallback="工作表")
        blocks.append({"type": "heading", "level": 1, "text": name})
        table = _normalize_sheet_table(sheet, max_columns=12)
        if table is not None:
            blocks.append({"type": "table", **table})
        else:
            blocks.append(
                {
                    "type": "paragraph",
                    "text": f"该工作表共 {sheet.get('nrows', 0)} 行、{sheet.get('ncols', 0)} 列，当前没有可用预览数据。",
                }
            )
    return blocks


def _slide_word_blocks(slides: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if not isinstance(slides, list):
        return blocks
    for slide in slides[:12]:
        if not isinstance(slide, dict):
            continue
        title = _text(slide.get("title"), fallback=f"第 {slide.get('index', len(blocks) + 1)} 页")
        blocks.append({"type": "heading", "level": 1, "text": title})
        for body in slide.get("bodies", [])[:6]:
            body_text = _text(body, max_chars=1000)
            if body_text and body_text != title:
                blocks.append({"type": "paragraph", "text": body_text})
        for table_payload in slide.get("tables", [])[:2]:
            table = _normalize_table(table_payload)
            if table is not None:
                blocks.append({"type": "table", **table})
        notes = _text(slide.get("notes"), max_chars=1000)
        if notes:
            blocks.append({"type": "paragraph", "text": f"演讲备注: {notes}"})
    return blocks


def _deck_payload(context: dict[str, Any] | None) -> dict[str, Any]:
    title = _document_title(context, fallback="Stub 演示")
    facts = _content_facts(context)
    if not facts:
        facts = ["输入内容已进入确定性生成链路", "产物可继续人工编辑和复检"]
    agenda = _agenda_items(context, title)
    table = _first_table(context, max_columns=8)
    sequence = detect_sequence_evidence(context)
    format_name = _text((context or {}).get("source", {}).get("format"), fallback="topic").upper()
    stats = (context or {}).get("stats", {})
    scale = (
        f"标题 {stats.get('headings', 0)}、段落 {stats.get('paragraphs', 0)}、"
        f"表格 {stats.get('tables', 0)}、图片 {stats.get('images', 0)}"
    )
    slides: list[dict[str, Any]] = [
        {"layout": "cover", "title": title, "subtitle": f"{format_name} 输入的确定性结构化摘要"},
        {"layout": "agenda", "items": agenda},
    ]
    for chunk_index in range(0, len(facts), 3):
        chunk = facts[chunk_index : chunk_index + 3]
        slides.append(
            {
                "layout": "title_bullets",
                "title": (
                    f"{title}的关键信息已完成结构化提取"
                    if chunk_index == 0
                    else f"{title}的关键内容可继续逐项复核"
                ),
                "bullets": [{"text": fact, "level": 1} for fact in chunk],
            }
        )
    if table is not None:
        slides.append({"layout": "table", "title": "关键数据可按原始预览复核", "table": table})
    else:
        slides.append(
            {
                "layout": "two_column",
                "title": "输入结构与核心内容可以分栏复核",
                "left": {"heading": "来源", "text": f"格式: {format_name}\n文件: {_source_filename(context)}"},
                "right": {"heading": "摘要", "text": facts[0]},
            }
        )
    if sequence is not None and sequence.layout == "process_flow":
        slides.append(
            {
                "layout": "process_flow",
                "title": "原文步骤形成可顺序执行的流程",
                "steps": [
                    {"id": f"step-{index}", "title": item}
                    for index, item in enumerate(sequence.items, start=1)
                ],
            }
        )
    elif sequence is not None and sequence.layout == "timeline":
        slides.append(
            {
                "layout": "timeline",
                "title": "原文时间节点形成连续里程碑",
                "milestones": [
                    {"label": timeline_parts(item)[0], "title": timeline_parts(item)[1], "status": "planned"}
                    for item in sequence.items
                ],
            }
        )
    if len(slides) < 11:
        slides.append(
            {
                "layout": "cards",
                "title": "输入来源和内容规模均保留可追溯依据",
                "cards": [
                    {"title": "来源格式", "desc": format_name, "tag": "SOURCE"},
                    {"title": "内容规模", "desc": scale, "tag": "STATS"},
                ],
            }
        )
    slides.append(
        {
            "layout": "conclusion",
            "title": f"{title}已形成可编辑输出骨架",
            "bullets": facts[:2],
            "cta": "请结合原始材料完成人工内容终审",
        }
    )
    return {
        "ir_type": "deck",
        "ir_version": "2.1",
        "meta": {"title": title, "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
        "slides": slides,
    }


def _apply_visual_plan_to_deck_payload(payload: dict[str, Any], visual_plan: dict[str, Any] | None) -> None:
    if not visual_plan:
        return
    from app.generation.depth import _stub_slide

    opportunities = [item for item in visual_plan.get("opportunities", []) if isinstance(item, dict)]
    for opportunity in opportunities:
        recommended = str(opportunity.get("recommended_layout", ""))
        page: dict[str, Any] = {
            "title": "输入证据采用可编辑视觉表达",
            "focus": str(opportunity.get("reason") or "按视觉计划组织内容"),
            "source_evidence": list(opportunity.get("evidence_refs", []))[:3],
            "asset_ids": list(opportunity.get("asset_ids", []))[:4],
        }
        if recommended.startswith("infographic_"):
            page["layout"] = "infographic"
            page["visual_kind"] = recommended.removeprefix("infographic_")
        elif recommended in {"image_text", "image_grid", "architecture_diagram", "process_flow", "timeline"}:
            page["layout"] = recommended
        elif recommended == "chart":
            page["layout"] = "chart"
            page["visual_kind"] = opportunity.get("chart_kind")
        else:
            continue
        slide = _stub_slide(page, title=payload["meta"]["title"], total_pages=len(payload["slides"]) + 1)
        payload["slides"].insert(max(len(payload["slides"]) - 1, 0), slide)
        return


def _document_title(context: dict[str, Any] | None, *, fallback: str) -> str:
    if context is None:
        return fallback
    content = context.get("content", {})
    for outline in content.get("outline", []):
        if isinstance(outline, dict) and _coerce_int(outline.get("level", 1)) == 1:
            value = _text(outline.get("text"))
            if value:
                return value
    for slide in content.get("slides", []):
        if isinstance(slide, dict):
            value = _text(slide.get("title"))
            if value:
                return value
    for sheet in content.get("sheets", []):
        if isinstance(sheet, dict):
            value = _text(sheet.get("name"))
            if value:
                return value
    filename = _source_filename(context)
    if filename:
        return Path(filename).stem or fallback
    return fallback


def _source_filename(context: dict[str, Any] | None) -> str:
    if context is None:
        return "未提供文件"
    return _text(context.get("source", {}).get("filename"), fallback="未提供文件")


def _content_facts(context: dict[str, Any] | None) -> list[str]:
    if context is None:
        return []
    content = context.get("content", {})
    candidates: list[str] = []
    for block in content.get("blocks", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") in {"heading", "paragraph"}:
            candidates.append(_text(block.get("text")))
        elif block.get("type") in {"bullet_list", "numbered_list"}:
            candidates.extend(_text(item.get("text")) for item in block.get("items", []) if isinstance(item, dict))
    for sheet in content.get("sheets", []):
        if not isinstance(sheet, dict):
            continue
        candidates.append(_text(sheet.get("name")))
        candidates.extend(_text(value) for value in sheet.get("header_guess", []))
        preview = sheet.get("preview_rows", [])
        if isinstance(preview, list):
            for row in preview:
                if isinstance(row, list):
                    candidates.extend(_text(value) for value in row)
    for slide in content.get("slides", []):
        if not isinstance(slide, dict):
            continue
        candidates.append(_text(slide.get("title")))
        candidates.extend(_text(body) for body in slide.get("bodies", []))
        candidates.append(_text(slide.get("notes")))
    return _unique_texts(candidates, max_items=24, max_chars=60)


def _agenda_items(context: dict[str, Any] | None, title: str) -> list[str]:
    if context is None:
        return ["内容摘要", "结论与行动"]
    content = context.get("content", {})
    candidates = [
        _text(item.get("text"))
        for item in content.get("outline", [])
        if isinstance(item, dict) and _text(item.get("text")) != title
    ]
    candidates.extend(_text(sheet.get("name")) for sheet in content.get("sheets", []) if isinstance(sheet, dict))
    candidates.extend(
        _text(slide.get("title"))
        for slide in content.get("slides", [])
        if isinstance(slide, dict) and _text(slide.get("title")) != title
    )
    items = _unique_texts(candidates, max_items=6, max_chars=24)
    for fallback in ("内容摘要", "关键数据", "结论与行动"):
        if len(items) >= 2:
            break
        if fallback not in items:
            items.append(fallback)
    return items[:8]


def _first_table(context: dict[str, Any] | None, *, max_columns: int) -> dict[str, Any] | None:
    if context is None:
        return None
    content = context.get("content", {})
    for block in content.get("blocks", []):
        if isinstance(block, dict) and block.get("type") == "table":
            table = _normalize_table(block, max_columns=max_columns)
            if table is not None:
                return table
    for sheet in content.get("sheets", []):
        if isinstance(sheet, dict):
            table = _normalize_sheet_table(sheet, max_columns=max_columns)
            if table is not None:
                return table
    for slide in content.get("slides", []):
        if not isinstance(slide, dict):
            continue
        for payload in slide.get("tables", []):
            table = _normalize_table(payload, max_columns=max_columns)
            if table is not None:
                return table
    return None


def _normalize_sheet_table(sheet: dict[str, Any], *, max_columns: int) -> dict[str, Any] | None:
    preview = sheet.get("preview_rows", [])
    if not isinstance(preview, list):
        return None
    header = sheet.get("header_guess") or (preview[0] if preview else [])
    payload = {"header": header, "rows": preview}
    return _normalize_table(payload, max_columns=max_columns)


def _normalize_table(payload: Any, *, max_columns: int = 12) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    raw_header = payload.get("header", [])
    raw_rows = payload.get("rows", [])
    if not isinstance(raw_header, list) or not isinstance(raw_rows, list):
        return None
    header = [(_text(value, max_chars=40) or f"列{index + 1}") for index, value in enumerate(raw_header[:max_columns])]
    if not header:
        return None
    rows: list[list[str]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, list) or len(raw_row) < len(header):
            continue
        row = [_text(value, max_chars=80) for value in raw_row[: len(header)]]
        if row == header and not rows:
            continue
        rows.append(row)
        if len(rows) >= 12:
            break
    if not rows:
        return None
    return {"header": header, "rows": rows}


def _list_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = _text(item.get("text"), max_chars=500)
        if text:
            normalized.append({"text": text, "level": _coerce_int(item.get("level", 1), low=1, high=2)})
    return normalized


def _unique_texts(values: list[str], *, max_items: int, max_chars: int) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _text(value, max_chars=max_chars)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
        if len(unique) >= max_items:
            break
    return unique


def _text(value: Any, *, fallback: str = "", max_chars: int = 120) -> str:
    if value is None:
        return fallback
    normalized = " ".join(str(value).split())
    if not normalized:
        return fallback
    if len(normalized) > max_chars:
        return normalized[: max_chars - 3] + "..."
    return normalized
