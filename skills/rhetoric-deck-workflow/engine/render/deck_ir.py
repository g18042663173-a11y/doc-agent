from __future__ import annotations

from typing import Any

from engine.shared.common import RdwError, load_schema, validate


PATTERN_LABELS = {
    "capability_evidence": "能力与价值形成可核验闭环",
    "solution_selection": "对照结论明确支持方案选择",
    "method_walkthrough": "方法按顺序落到可执行步骤",
    "implementation_detail": "实现细节受组件与约束共同控制",
    "test_matrix": "测试矩阵覆盖验证重点",
    "issue_retro": "问题复盘形成分析与措施闭环",
    "phase_summary": "阶段投入转化为明确产出",
    "context_pain": "背景与痛点共同定义目标",
    "status_progress": "进展、风险与下一步保持一致",
    "struct_cover": "封面",
}


def build_deck_ir(skeleton: dict, content: dict, material: dict) -> dict:
    content_pages = {page["page_id"]: page for page in content["pages"]}
    has_struct_cover = any(page["page_pattern"] == "struct_cover" for page in skeleton["pages"])
    slides: list[dict[str, Any]] = []
    if not has_struct_cover:
        slides.append({"layout": "cover", "title": material["title"], "subtitle": "基于用户材料的修辞结构重组"})
    conclusion_values: list[str] = []
    for page in skeleton["pages"]:
        page_content = content_pages.get(page["page_id"])
        if page_content is None:
            continue
        values = _semantic_values(page, page_content)
        slide = _map_page(page, values, material["title"])
        slides.append(slide)
        conclusion_values.extend(_flat_values(values.get("conclusion.winner", [])))
        conclusion_values.extend(_flat_values(values.get("benefit.summary", [])))
        conclusion_values.extend(_flat_values(values.get("status.next", [])))
    if conclusion_values:
        slides.append({"layout": "conclusion", "title": "结论与下一步", "bullets": conclusion_values[:5]})
    deck = {
        "ir_type": "deck", "ir_version": "2.2",
        "meta": {"title": material["title"], "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
        "slides": slides,
    }
    try:
        validate(deck, load_schema("deck_ir.schema.json"), code="RD-E050", loc="deck_ir")
    except RdwError as exc:
        raise RdwError("RD-E050", exc.loc, f"DeckIR 映射未通过冻结契约: {exc.message}", "缩短或修正 FillContent，再重新 finalize。") from exc
    return deck


def _semantic_values(page: dict, content: dict) -> dict[str, list[str]]:
    slot_map = {slot["slot_id"]: slot for slot in page["slots"]}
    values: dict[str, list[str]] = {}
    for item in content["slots"]:
        if "value" not in item:
            continue
        value = item["value"] if isinstance(item["value"], list) else [item["value"]]
        values[slot_map[item["slot_id"]]["semantic"]] = value
    return values


def _map_page(page: dict, values: dict[str, list[str]], material_title: str) -> dict:
    pattern = page["page_pattern"]
    title = _first(values.get("page.title")) or PATTERN_LABELS[pattern]
    if pattern == "struct_cover":
        slide = {"layout": "cover", "title": title}
        subtitle = _first(values.get("page.subtitle"))
        if subtitle:
            slide["subtitle"] = subtitle
        return slide
    body = [(semantic, item) for semantic, items in values.items() if semantic != "page.title" for item in items]
    if pattern == "capability_evidence" and len(body) >= 2:
        return {"layout": "cards", "title": title, "cards": [{"title": _label(semantic), "desc": item} for semantic, item in body[:4]]}
    if pattern in {"solution_selection", "test_matrix", "issue_retro"}:
        rows = [[_label(semantic), item] for semantic, item in body[:12]] or [["材料", material_title]]
        return {"layout": "table", "title": title, "table": {"header": ["论证要素", "用户材料"], "rows": rows, "conclusion_col": 1}}
    if pattern == "method_walkthrough":
        steps = _flat_values(values.get("method.steps", []))
        if len(steps) >= 2:
            return {"layout": "process_flow", "title": title, "orientation": "horizontal", "steps": [{"id": f"step_{index}", "title": item} for index, item in enumerate(steps[:7], start=1)]}
    if pattern == "implementation_detail":
        nodes = _flat_values(values.get("implementation.flow", [])) + _flat_values(values.get("component.list", []))
        if len(nodes) >= 2:
            nodes = nodes[:8]
            return {
                "layout": "architecture_diagram", "title": title,
                "nodes": [{"id": f"node_{index}", "text": item, "type": "secondary"} for index, item in enumerate(nodes, start=1)],
                "edges": [{"from": f"node_{index}", "to": f"node_{index + 1}"} for index in range(1, len(nodes))],
                "groups": [],
            }
    if pattern == "phase_summary":
        labels = _flat_values(values.get("phase.labels", []))
        outputs = _flat_values(values.get("phase.output", []))
        milestones = []
        for index, item in enumerate(outputs[:8]):
            milestones.append({"label": labels[index] if index < len(labels) else f"阶段{index + 1}", "title": item, "status": "completed" if index < max(0, len(outputs) - 1) else "current"})
        if len(milestones) >= 2:
            return {"layout": "timeline", "title": title, "orientation": "horizontal", "milestones": milestones}
    if pattern == "status_progress":
        left = _flat_values(values.get("status.goal", [])) + _flat_values(values.get("status.progress", []))
        right = _flat_values(values.get("status.risk", [])) + _flat_values(values.get("status.next", []))
        return {
            "layout": "two_column", "title": title,
            "left": {"heading": "目标与进展", "bullets": _bullets(left[:7])},
            "right": {"heading": "风险与下一步", "bullets": _bullets(right[:7])},
        }
    items = [item for _, item in body[:7]] or [material_title]
    return {"layout": "title_bullets", "title": title, "bullets": _bullets(items)}


def _flat_values(values) -> list[str]:
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values if str(value).strip()]


def _first(values) -> str | None:
    flattened = _flat_values(values or [])
    return flattened[0] if flattened else None


def _bullets(values: list[str]) -> list[dict]:
    return [{"text": value, "level": 1} for value in values if value.strip()]


def _label(semantic: str) -> str:
    labels = {
        "benefit.metric": "量化收益", "capability.summary": "能力", "value.as_is": "现状", "value.to_be": "目标",
        "technical.point": "技术点", "option.a": "方案 A", "option.b": "方案 B", "comparison.dimensions": "对比维度",
        "conclusion.winner": "结论", "test.intent": "设计思路", "test.cases": "用例", "test.focus": "验证重点",
        "issue.problem": "问题", "issue.symptom": "现象", "issue.analysis": "分析", "issue.action": "措施",
    }
    return labels.get(semantic, semantic.replace("_", " ").replace(".", " / "))
