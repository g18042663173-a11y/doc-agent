from __future__ import annotations

import re
from pathlib import Path

from engine.fit.scoring import ROLE_TERMS
from engine.shared.common import SKILL_ROOT, read_json, write_json
from engine.skeleton.contracts import validate_skeleton


PATTERN_FLOW = {
    "capability_evidence": "quantify_columns_compare",
    "solution_selection": "options_compare_conclude",
    "method_walkthrough": "steps_compare_benefit",
    "implementation_detail": "flow_components_constraints",
    "test_matrix": "intent_matrix_emphasis",
    "issue_retro": "problem_symptom_analysis_action",
    "phase_summary": "phase_input_output",
    "context_pain": "context_pain_goal",
    "status_progress": "goal_progress_risk_next",
    "struct_cover": "cover_title_subtitle",
}
OMIT_RE = re.compile(
    r"(目录|目次|谢谢|致谢|结束|再见|agenda|contents|thank\s*you|q\s*&\s*a)",
    re.IGNORECASE,
)


def write_skeleton_draft(pack: Path, pages: list[tuple[str, list[dict]]], skipped_pages: list[dict]) -> Path | None:
    skipped = {item["page_id"] for item in skipped_pages}
    vocabulary = set(read_json(SKILL_ROOT / "library/label_vocab.json", code="RD-E999", loc="label_vocab"))
    drafted = []
    for index, (page_id, elements) in enumerate(pages, start=1):
        candidates = _text_candidates(elements)
        blob = "\n".join(item["text"] for item in candidates)
        drafted.append(_draft_page(page_id, index, candidates, blob, vocabulary))
    if not drafted:
        return None
    skeleton = {
        "format": "deck_skeleton",
        "version": "2.0",
        "source_kind": "extracted",
        "page_policy": "preserve",
        "deck_pattern": "review_solution",
        "page_count": len(drafted),
        "pages": drafted,
    }
    validate_skeleton(skeleton, source_text="\n".join(
        item.get("text") or ""
        for _, elements in pages
        for item in elements
    ))
    path = pack / "skeleton_draft.json"
    write_json(path, skeleton)
    return path


def _text_candidates(elements: list[dict]) -> list[dict]:
    results = []
    for item in elements:
        text = (item.get("text") or "").strip()
        if (not text and item.get("kind") != "chart") or not item.get("shape_ref"):
            continue
        kind = item.get("kind") or "shape"
        if kind not in {"table_cell", "smartart_node", "chart", "shared_text"}:
            kind = "shape"
        results.append(
            {
                "shape_ref": item["shape_ref"],
                "kind": kind,
                "text": text,
                "chars": len(text),
                "bbox": item.get("bbox") or {},
                "paragraphs": item.get("paragraphs") or [],
            }
        )
    return results


def _is_omit_page(blob: str) -> bool:
    compact = re.sub(r"\s+", "", blob)
    return bool(OMIT_RE.search(blob)) and len(compact) <= 24


def _draft_page(page_id: str, source_index: int, candidates: list[dict], blob: str, vocabulary: set[str]) -> dict:
    pattern = _guess_pattern(blob, source_index, candidates)
    title_ref = _title_ref(candidates)
    node_index = 0
    cell_index = 0
    body_index = 0
    slots = []
    for candidate in candidates:
        slot_id = f"s{len(slots) + 1}"
        kind = candidate["kind"]
        chars = max(8, min(120, candidate["chars"] or 8))
        lines = max(1, min(12, len(candidate["paragraphs"]) or (2 if candidate["chars"] > 24 else 1)))
        if kind == "shared_text":
            semantic = f"shared.caption_{len(slots) + 1}"
            slot_type = "caption"
        elif kind == "chart":
            semantic = f"evidence.chart_{len(slots) + 1}"
            slot_type = "chart"
        elif kind == "table_cell":
            row_col = candidate["shape_ref"].partition(".cell_")[2] or f"{cell_index}_0"
            semantic = f"issue.cell_{row_col}" if pattern == "issue_retro" else f"body.cell_{row_col}"
            slot_type = "table_cell"
            cell_index += 1
        elif kind == "smartart_node":
            node_index += 1
            semantic = f"method.node_{node_index}"
            slot_type = "node_label"
        elif candidate["shape_ref"] == title_ref:
            semantic = "page.title"
            slot_type = "title"
        else:
            body_index += 1
            slot_type, semantic = _body_type(candidate, body_index, pattern, title_ref is not None)
        slots.append(
            {
                "slot_id": slot_id,
                "semantic": semantic,
                "type": slot_type,
                "cardinality": {"min": 1, "max": 1 if slot_type != "bullet_list" else 6},
                "capacity": {"chars_cjk": chars, "lines": lines if slot_type != "bullet_list" else max(lines, 6)},
                "required": True,
                "shape_ref": candidate["shape_ref"],
            }
        )
    node_count = sum(1 for item in candidates if item["kind"] == "smartart_node")
    return {
        "page_id": page_id,
        "page_pattern": pattern,
        "argument_flow": PATTERN_FLOW[pattern],
        "confidence": 0.6,
        "structure": {"items": {"count": max(1, len(slots)), "expandable": False, "max": max(1, len(slots))}},
        "slots": slots,
        "emphasis": [],
        "diagram": {
            "type": "linear_flow" if node_count else "none",
            "groups": 1 if node_count else 0,
            "nodes_per_group": min(20, node_count),
            "flow": "left_right" if node_count else "none",
            "annotations": 0,
            "labels": None,
        },
        "structural_labels": {"_display": _display_labels(blob, vocabulary)},
    }


def _guess_pattern(blob: str, source_index: int, candidates: list[dict]) -> str:
    if source_index == 1:
        return "struct_cover"
    folded = blob.casefold()
    scores = {name: sum(1 for term in terms if term.casefold() in folded) for name, terms in ROLE_TERMS.items()}
    best = max(scores, key=scores.get)
    if source_index == 1 and len(candidates) <= 4 and scores.get("struct_cover", 0) == scores[best]:
        return "struct_cover"
    if source_index == 1 and len(candidates) <= 3 and scores[best] == 0:
        return "struct_cover"
    if scores[best] == 0:
        if any(item["kind"] == "table_cell" for item in candidates):
            return "issue_retro"
        if any(item["kind"] == "smartart_node" for item in candidates):
            return "method_walkthrough"
        return "context_pain"
    return best


def _title_ref(candidates: list[dict]) -> str | None:
    shapes = [item for item in candidates if item["kind"] == "shape"]
    if not shapes:
        return None
    def title_rank(item):
        sizes = [run.get("font_size_pt") or 0 for p in item.get("paragraphs", []) for run in p.get("runs", [])]
        return (-max(sizes, default=0), int(item["bbox"].get("top") or 0), -item["chars"])
    return min(shapes, key=title_rank)["shape_ref"]


def _body_type(candidate: dict, body_index: int, pattern: str, has_title: bool) -> tuple[str, str]:
    top = int(candidate["bbox"].get("top") or 0)
    height = int(candidate["bbox"].get("height") or 0)
    chars = candidate["chars"]
    if has_title and body_index == 1 and top < 3_200_000 and chars <= 40 and height < 800_000:
        return "subtitle", "page.subtitle"
    if chars <= 18 and height < 600_000:
        return "caption", f"body.slot_{body_index}"
    return "bullet_list", f"body.slot_{body_index}"


def _display_labels(blob: str, vocabulary: set[str]) -> list[str]:
    labels = []
    for label in vocabulary:
        if 1 <= len(label) <= 6 and blob.count(label) >= 2 and label not in labels:
            labels.append(label)
        if len(labels) >= 8:
            break
    return labels
