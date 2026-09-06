"""Check explicit source references; report semantic review separately."""
from __future__ import annotations

import math


def audit_evidence(content: dict, material: dict) -> dict:
    index = {item["id"]: item for item in material.get("evidence", [])}
    issues = []
    slots = []
    for page in content["pages"]:
        for slot in page["slots"]:
            loc = f"{page['page_id']}.{slot['slot_id']}"
            refs = slot.get("evidence_refs", [])
            if slot.get("status") == "missing":
                issues.append({"loc": loc, "kind": "missing", "message": slot["reason"]})
            elif not refs or any(ref not in index or not index[ref]["text"].strip() for ref in refs):
                issues.append({"loc": loc, "kind": "invalid_reference", "message": "每个填充槽必须引用存在且非空的材料证据。"})
            value = slot.get("value")
            if isinstance(value, dict):
                for series in value["series"]:
                    if any(not math.isfinite(number) for number in series["values"]):
                        issues.append({"loc": loc, "kind": "invalid_number", "message": "图表不允许 NaN 或无穷数。"})
            slots.append({"loc": loc, "evidence_refs": refs, "derivation": slot.get("derivation"),
                          "source_locations": [{k: index[ref][k] for k in ("source_name", "source_sha256", "page", "block") if k in index[ref]} for ref in refs if ref in index]})
    return {"format": "rdw_evidence_audit", "version": "2.0", "pass": not issues,
            "issues": issues, "slots": slots, "semantic_review": "required",
            "material_warnings": material.get("warnings", []),
            "note": "引用有效仅证明可追溯；改写含义、实验口径及派生计算须独立复核。"}
