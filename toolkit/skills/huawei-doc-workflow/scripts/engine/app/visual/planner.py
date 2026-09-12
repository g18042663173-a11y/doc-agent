from __future__ import annotations

import re

from app.assets.contracts import AssetManifest
from app.generation.layout_policy import detect_sequence_evidence
from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.visual.contracts import VisualOpportunity, VisualPlan, VisualSelection, VisualSelectionAudit


RULES = (
    ("architecture_diagram", None, re.compile(r"架构|模块|接口|依赖|拓扑|系统关系"), 0.88, "实体关系适合架构图"),
    ("infographic_funnel", None, re.compile(r"漏斗|转化|筛选|收敛|淘汰"), 0.86, "阶段递减适合漏斗图"),
    ("infographic_quadrant", None, re.compile(r"影响.*难度|难度.*影响|价值.*成本|优先级象限"), 0.86, "双维定位适合象限图"),
    ("infographic_cycle", None, re.compile(r"闭环|循环|持续改进|迭代周期"), 0.84, "闭环过程适合循环图"),
    ("infographic_matrix", None, re.compile(r"矩阵|交叉分类|优先级分类"), 0.82, "交叉分类适合矩阵"),
    ("process_flow", None, re.compile(r"流程|步骤|首先|然后|最后|阶段"), 0.78, "线性步骤适合流程图"),
)


def build_visual_plan(document: DocumentIR, assets: AssetManifest | None = None) -> VisualPlan:
    text, evidence = _document_text(document)
    candidates: list[tuple[str, str | None, float, str, list[str], list[str]]] = []
    sequence = detect_sequence_evidence(document.model_dump(mode="json"))
    if sequence is not None:
        reason = "明确时间节点适合时间线" if sequence.layout == "timeline" else "顺序步骤适合流程图"
        candidates.append((sequence.layout, None, 0.9, reason, list(sequence.items), []))
    for layout, chart_kind, pattern, confidence, reason in RULES:
        if layout == "process_flow" and sequence is not None:
            continue
        match = pattern.search(text)
        if match:
            candidates.append((layout, chart_kind, confidence, reason, _matching_evidence(evidence, pattern), []))
    table_candidate = _table_visual(document)
    if table_candidate is not None:
        candidates.append(table_candidate)
    if assets and assets.assets:
        selected = [asset.asset_id for asset in assets.assets[:4]]
        layout = "image_text" if len(selected) == 1 else "image_grid"
        candidates.append((layout, None, 0.9, "存在已验证图片资产，可用于证据型图文表达", [], selected))
    opportunities = [
        VisualOpportunity(
            visual_id=f"visual-{index:03d}",
            recommended_layout=layout,
            chart_kind=chart_kind,
            confidence=confidence,
            reason=reason,
            evidence_refs=evidence_refs,
            asset_ids=asset_ids,
        )
        for index, (layout, chart_kind, confidence, reason, evidence_refs, asset_ids) in enumerate(
            _deduplicate(candidates)[:12], start=1
        )
    ]
    return VisualPlan(visual_plan_version="1.0", source_filename=document.source.filename, opportunities=opportunities)


def audit_visual_selection(plan: VisualPlan, deck: DeckIR) -> VisualSelectionAudit:
    selections: list[VisualSelection] = []
    for opportunity in plan.opportunities:
        expected_layout = opportunity.recommended_layout
        if expected_layout.startswith("infographic_"):
            expected_kind = expected_layout.removeprefix("infographic_")
            indices = [
                index
                for index, slide in enumerate(deck.slides, start=1)
                if slide.layout == "infographic" and slide.infographic.kind == expected_kind
            ]
        elif expected_layout == "chart":
            indices = [
                index
                for index, slide in enumerate(deck.slides, start=1)
                if slide.layout == "chart" and slide.chart.kind == opportunity.chart_kind
            ]
        else:
            indices = [index for index, slide in enumerate(deck.slides, start=1) if slide.layout == expected_layout]
        selections.append(
            VisualSelection(
                visual_id=opportunity.visual_id,
                recommended_layout=opportunity.recommended_layout,
                selected=bool(indices),
                slide_indices=indices,
                reason="DeckIR 采用了该推荐" if indices else "DeckIR 保留其它经 Schema 校验的表达，不强制配图",
            )
        )
    return VisualSelectionAudit(audit_version="1.0", selections=selections)


def _document_text(document: DocumentIR) -> tuple[str, list[str]]:
    evidence: list[str] = []
    for item in document.content.outline:
        evidence.append(item.text)
    for block in document.content.blocks:
        payload = block.model_dump(mode="json")
        if isinstance(payload.get("text"), str):
            evidence.append(payload["text"])
        evidence.extend(str(item.get("text", "")) for item in payload.get("items", []) if isinstance(item, dict))
    for slide in document.content.slides:
        evidence.extend([slide.title or "", *slide.bodies, slide.notes or ""])
    evidence = [item.strip() for item in evidence if item and item.strip()]
    return "\n".join(evidence), evidence


def _matching_evidence(evidence: list[str], pattern: re.Pattern[str]) -> list[str]:
    return [item[:160] for item in evidence if pattern.search(item)][:4]


def _table_visual(document: DocumentIR):
    headers: list[str] = []
    rows: list[list[str]] = []
    for block in document.content.blocks:
        if getattr(block, "type", None) == "table":
            headers, rows = list(block.header), [list(row) for row in block.rows]
            break
    if not headers and document.content.sheets:
        sheet = document.content.sheets[0]
        headers, rows = list(sheet.header_guess), [list(row) for row in sheet.preview_rows]
    if not headers or len(rows) < 2:
        return None
    header_text = " ".join(headers)
    if re.search(r"时间|日期|月份|季度|年度|年|月", header_text):
        return ("chart", "line", 0.9, "时间序列表格适合折线图", headers[:4], [])
    if re.search(r"占比|比例|份额", header_text) and 2 <= len(rows) <= 6:
        return ("chart", "pie", 0.82, "2-6 个非负占比类别适合饼图", headers[:4], [])
    return ("chart", "bar", 0.8, "类目数值比较适合柱图", headers[:4], [])


def _deduplicate(candidates):
    seen: set[tuple[str, str | None]] = set()
    result = []
    for candidate in candidates:
        key = (candidate[0], candidate[1])
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result
