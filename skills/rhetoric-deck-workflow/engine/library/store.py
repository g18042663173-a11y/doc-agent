from __future__ import annotations

from copy import deepcopy
import re
from pathlib import Path

from engine.shared.common import RdwError, SKILL_ROOT, read_json, write_json
from engine.skeleton.contracts import validate_skeleton


ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


def list_patterns(tag: str | None = None) -> list[dict]:
    builtin = read_json(SKILL_ROOT / "library/builtin/deck_patterns.json", code="RD-E999", loc="library")
    results = [
        {"id": pattern_id, "source_kind": "builtin", **metadata}
        for pattern_id, metadata in builtin.items()
        if tag is None or tag in metadata.get("tags", [])
    ]
    imported = SKILL_ROOT / "library/imported"
    if imported.is_dir():
        for path in sorted(imported.glob("*.json")):
            entry = read_json(path, code="RD-E999", loc=str(path))
            if tag is None or tag in entry.get("library", {}).get("tags", []):
                results.append({"id": path.stem, "source_kind": "imported", **entry.get("library", {})})
    return results


def get_pattern(pattern_id: str) -> dict:
    imported = SKILL_ROOT / "library/imported" / f"{pattern_id}.json"
    if imported.is_file():
        value = read_json(imported, code="RD-E999", loc=str(imported))
        skeleton = value.get("skeleton", value)
        return validate_skeleton(skeleton)
    patterns = read_json(SKILL_ROOT / "library/builtin/deck_patterns.json", code="RD-E999", loc="library")
    if pattern_id not in patterns:
        raise RdwError("RD-E010", "pattern", f"写作思路不存在: {pattern_id}", "先运行 library list 查看可用 id。")
    templates = read_json(SKILL_ROOT / "library/builtin/page_patterns.json", code="RD-E999", loc="library")
    pages = []
    slot_counter = 1
    for index, page_pattern in enumerate(patterns[pattern_id]["pages"], start=1):
        template = templates[page_pattern]
        slots = []
        for semantic, slot_type, required in zip(template["semantics"], template["types"], template["required"]):
            slots.append(
                {
                    "slot_id": f"s{slot_counter}", "semantic": semantic, "type": slot_type,
                    "cardinality": {"min": 1, "max": 1 if slot_type in {"title", "subtitle", "conclusion", "metric", "caption"} else 7},
                    "capacity": {"chars_cjk": 36 if slot_type == "title" else 90, "lines": 2 if slot_type == "title" else 7},
                    "required": required, "shape_ref": None,
                }
            )
            slot_counter += 1
        diagram_type, groups, nodes, flow = template["diagram"]
        pages.append(
            {
                "page_id": f"p{index:02d}", "page_pattern": page_pattern, "argument_flow": template["argument_flow"], "confidence": 1.0,
                "structure": {"items": {"count": max(1, nodes), "expandable": True, "max": max(nodes, 7)}},
                "slots": slots, "emphasis": [],
                "diagram": {"type": diagram_type, "groups": groups, "nodes_per_group": nodes, "flow": flow, "annotations": 0, "labels": None},
                "structural_labels": {"_display": []},
            }
        )
    skeleton = {"format": "deck_skeleton", "version": "1.0", "source_kind": "builtin", "deck_pattern": pattern_id, "page_count": len(pages), "pages": pages}
    return validate_skeleton(skeleton)


def add_pattern(skeleton_path: Path, pattern_id: str, name: str, tags: list[str]) -> Path:
    if not ID_RE.fullmatch(pattern_id):
        raise RdwError("RD-E010", "id", "library id 只允许小写 ASCII、数字、下划线和连字符。", "使用如 team_review_v1 的 id。")
    target = SKILL_ROOT / "library/imported" / f"{pattern_id}.json"
    if target.exists():
        raise RdwError("RD-E050", "id", "同名导入骨架已存在。", "使用新的 id，或先显式执行 library rm。")
    skeleton = validate_skeleton(read_json(skeleton_path, code="RD-E010", loc="skeleton"))
    copied = deepcopy(skeleton)
    copied["source_kind"] = "imported"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json(target, {"library": {"name": name, "tags": tags}, "skeleton": copied}, overwrite=False)
    return target


def remove_pattern(pattern_id: str) -> Path:
    target = SKILL_ROOT / "library/imported" / f"{pattern_id}.json"
    if not target.is_file():
        raise RdwError("RD-E010", "id", "只能删除存在的 imported 写作思路。", "运行 library list 查看来源。")
    target.unlink()
    return target
