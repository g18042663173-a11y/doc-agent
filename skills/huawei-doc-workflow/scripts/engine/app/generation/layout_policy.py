from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


LAYOUT_SELECTION_RULES = (
    "先判断内容关系再选择版式，不为增加版式数量强行套版。"
    "顺序步骤仅在原文存在 2-7 个编号步骤，或流程/步骤/工作流/实施路径标题及对应条目时使用 process_flow；"
    "时间线仅在原文存在至少两个不同年份、季度、月份、上下半年或明确里程碑时间标签时使用 timeline；"
    "同时满足时，有明确时间标签优先 timeline，否则使用 process_flow；"
    "分支或任意节点关系使用 architecture_diagram。"
    "精确 Gantt 所需的开始/结束日期、持续时间或依赖关系当前无法表达，不得用 timeline 冒充。"
)

_PROCESS_HEADING_RE = re.compile(r"流程|步骤|工作流|实施路径")
_TIME_TOKEN_RE = re.compile(
    r"(?:20\d{2}(?:\s+Q[1-4]|年|[-/.]\d{1,2}(?:月)?)?|"
    r"Q[1-4]|[一二三四]季度|(?:1[0-2]|[1-9])月|上半年|下半年|"
    r"里程碑\s*M?[一二三四五六七八九十\d]+|M\d+(?=\s*(?:里程碑|阶段|规划|计划|目标|发布)))",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SequenceEvidence:
    layout: str
    items: tuple[str, ...]
    labels: tuple[str, ...] = ()


def detect_sequence_evidence(document: Mapping[str, Any] | None) -> SequenceEvidence | None:
    if not isinstance(document, Mapping):
        return None
    records = _content_records(document)
    timeline = _timeline_evidence(records)
    if timeline is not None:
        return timeline
    return _process_evidence(document)


def timeline_parts(text: str) -> tuple[str, str]:
    match = _TIME_TOKEN_RE.search(text)
    if match is None:
        return "阶段", text
    label = match.group(0)
    title = (text[: match.start()] + text[match.end() :]).strip(" ：:，,-") or text
    return label, title


def _timeline_evidence(records: list[str]) -> SequenceEvidence | None:
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text in records:
        match = _TIME_TOKEN_RE.search(text)
        if match is None:
            continue
        normalized = match.group(0).upper().replace(" ", "")
        if normalized in seen:
            continue
        seen.add(normalized)
        selected.append((match.group(0), text))
        if len(selected) >= 8:
            break
    if len(selected) < 2:
        return None
    return SequenceEvidence(
        layout="timeline",
        items=tuple(text for _label, text in selected),
        labels=tuple(label for label, _text in selected),
    )


def _process_evidence(document: Mapping[str, Any]) -> SequenceEvidence | None:
    blocks = document.get("content", {}).get("blocks", [])
    if not isinstance(blocks, list):
        return None
    previous_heading = ""
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        block_type = block.get("type")
        if block_type == "heading":
            previous_heading = _clean_text(block.get("text"))
            continue
        if block_type not in {"numbered_list", "bullet_list"}:
            continue
        items = tuple(
            text
            for item in block.get("items", [])
            if isinstance(item, Mapping) and (text := _clean_text(item.get("text")))
        )
        explicit_numbered = block_type == "numbered_list"
        headed_process = bool(_PROCESS_HEADING_RE.search(previous_heading))
        if 2 <= len(items) <= 7 and (explicit_numbered or headed_process):
            return SequenceEvidence(layout="process_flow", items=items)
    return None


def _content_records(document: Mapping[str, Any]) -> list[str]:
    content = document.get("content", {})
    records: list[str] = []
    for block in content.get("blocks", []):
        if not isinstance(block, Mapping):
            continue
        if block.get("type") in {"heading", "paragraph"}:
            text = _clean_text(block.get("text"))
            if text:
                records.append(text)
        elif block.get("type") in {"bullet_list", "numbered_list"}:
            records.extend(
                text
                for item in block.get("items", [])
                if isinstance(item, Mapping) and (text := _clean_text(item.get("text")))
            )
    for slide in content.get("slides", []):
        if not isinstance(slide, Mapping):
            continue
        for value in [slide.get("title"), *slide.get("bodies", [])]:
            text = _clean_text(value)
            if text:
                records.append(text)
    for sheet in content.get("sheets", []):
        if not isinstance(sheet, Mapping):
            continue
        for row in sheet.get("preview_rows", [])[:20]:
            if not isinstance(row, list):
                continue
            text = " ".join(filter(None, (_clean_text(value) for value in row)))
            if text:
                records.append(text)
    return records


def _clean_text(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""
