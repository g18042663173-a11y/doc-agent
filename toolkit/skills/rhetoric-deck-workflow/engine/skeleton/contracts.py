from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from engine.shared.common import RdwError, SKILL_ROOT, load_schema, read_json, validate


CJK_RE = re.compile(r"[\u3400-\u9fff]")
UPPER_TERM_RE = re.compile(r"[A-Z]{2,}")


def validate_skeleton(skeleton: dict, *, source_text: str | None = None) -> dict:
    if skeleton.get("version") == "1.0":
        validate(skeleton, load_schema("deck_skeleton.v1.schema.json"), code="RD-E010", loc="skeleton")
        skeleton = deepcopy(skeleton)
        skeleton.update(version="2.0", page_policy="preserve")
    validate(skeleton, load_schema("deck_skeleton.schema.json"), code="RD-E010", loc="skeleton")
    if skeleton["page_count"] != len(skeleton["pages"]):
        raise RdwError("RD-E010", "skeleton.page_count", "page_count 与 pages 长度不一致。", "更新 page_count 使其等于实际页面数。")
    page_ids: set[str] = set()
    for page_index, page in enumerate(skeleton["pages"]):
        page_loc = f"skeleton.pages.{page_index}"
        if page["page_id"] in page_ids:
            raise RdwError("RD-E010", f"{page_loc}.page_id", "page_id 重复。", "为每页使用唯一 page_id。")
        page_ids.add(page["page_id"])
        slot_ids: set[str] = set()
        semantics = {slot["semantic"] for slot in page["slots"]}
        for slot_index, slot in enumerate(page["slots"]):
            if slot["slot_id"] in slot_ids:
                raise RdwError("RD-E010", f"{page_loc}.slots.{slot_index}.slot_id", "同页 slot_id 重复。", "为同一页每个槽位使用唯一 slot_id。")
            slot_ids.add(slot["slot_id"])
            if slot["cardinality"]["min"] > slot["cardinality"]["max"]:
                raise RdwError("RD-E010", f"{page_loc}.slots.{slot_index}.cardinality", "min 不能大于 max。", "修正槽位基数范围。")
        for emphasis_index, rule in enumerate(page["emphasis"]):
            if rule["applies_to"] not in semantics:
                raise RdwError("RD-E010", f"{page_loc}.emphasis.{emphasis_index}.applies_to", "强调规则未引用本页槽位 semantic。", "改为本页已有 semantic。")
    _assert_no_cjk_outside_display(skeleton)
    if source_text is not None:
        _validate_display_labels(skeleton, source_text)
    return skeleton


def _assert_no_cjk_outside_display(value: Any, path: tuple[str | int, ...] = ()) -> None:
    if isinstance(value, str):
        if len(path) >= 2 and path[-2] == "_display":
            return
        if CJK_RE.search(value):
            loc = ".".join(map(str, path))
            raise RdwError("RD-E011", f"skeleton.{loc}", "骨架在结构标签白名单之外含中文原文。", "改用受控枚举或小写 ASCII semantic。")
    elif isinstance(value, dict):
        for key, child in value.items():
            _assert_no_cjk_outside_display(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_cjk_outside_display(child, (*path, index))


def _validate_display_labels(skeleton: dict, source_text: str) -> None:
    vocabulary = set(read_json(SKILL_ROOT / "library/label_vocab.json", code="RD-E999", loc="label_vocab"))
    for page_index, page in enumerate(skeleton["pages"]):
        for label_index, label in enumerate(page["structural_labels"].get("_display", [])):
            loc = f"skeleton.pages.{page_index}.structural_labels._display.{label_index}"
            if label not in vocabulary or any(char.isdigit() for char in label) or UPPER_TERM_RE.search(label):
                raise RdwError("RD-E011", loc, f"结构标签未通过受控词表: {label}", "删除该标签，改用英文 semantic；本版本不提供交互确认。")
            if source_text.count(label) < 2:
                raise RdwError("RD-E011", loc, f"结构标签在源件中重复不足 2 次: {label}", "删除该标签或确认它确为重复结构表头。")


def compile_fill_schema(skeleton: dict, accepted_page_ids: set[str]) -> dict:
    generic = load_schema("fill_content.schema.json")
    page_variants: list[dict] = []
    for page in skeleton["pages"]:
        if page["page_id"] not in accepted_page_ids:
            continue
        slot_variants = []
        for slot in page["slots"]:
            value_schema = ({"$ref": "#/$defs/chart"} if slot["type"] == "chart" else
                {"oneOf": [{"type": "string", "minLength": 1, "pattern": "\\S"}, {"type": "array", "minItems": 1, "maxItems": slot["cardinality"]["max"], "items": {"type": "string", "minLength": 1, "pattern": "\\S"}}]})
            slot_variants.append(
                {
                    "oneOf": [
                        {
                            "type": "object", "additionalProperties": False,
                            "required": ["slot_id", "value"],
                            "properties": {
                                "slot_id": {"const": slot["slot_id"]},
                                "value": value_schema,
                                "evidence_refs": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 128}},
                                "derivation": {"type": "string", "minLength": 1, "maxLength": 2000},
                            },
                        },
                        {
                            "type": "object", "additionalProperties": False,
                            "required": ["slot_id", "status", "reason"],
                            "properties": {"slot_id": {"const": slot["slot_id"]}, "status": {"const": "missing"}, "reason": {"type": "string", "minLength": 1, "maxLength": 500}},
                        },
                    ]
                }
            )
        page_variants.append(
            {
                "type": "object", "additionalProperties": False, "required": ["page_id", "slots"],
                "properties": {
                    "page_id": {"const": page["page_id"]},
                    "slots": {"type": "array", "minItems": len(page["slots"]), "maxItems": len(page["slots"]), "items": {"oneOf": slot_variants} if slot_variants else False},
                },
            }
        )
    schema = deepcopy(generic)
    schema["properties"]["pages"]["items"] = {"oneOf": page_variants}
    schema["properties"]["pages"]["maxItems"] = max(1, len(page_variants))
    schema["properties"]["pages"]["minItems"] = len(page_variants)
    return schema


def validate_fill_content(content: dict, schema: dict, skeleton: dict, accepted_page_ids: set[str]) -> dict:
    if content.get("version") == "1.0":
        content = deepcopy(content)
        content["version"] = "2.0"
    validate(content, schema, code="RD-E030", loc="content")
    expected_order = [p["page_id"] for p in skeleton["pages"]]
    actual_order = [p["page_id"] for p in content["pages"]]
    if actual_order != expected_order or accepted_page_ids != set(expected_order):
        raise RdwError("RD-E030", "content.pages", "页面集合或顺序不完整。", "逐页填充全部计划页，不能删页或跳过低分页。")
    page_map = {page["page_id"]: page for page in skeleton["pages"]}
    seen_pages: set[str] = set()
    for page_index, page_content in enumerate(content["pages"]):
        page_id = page_content["page_id"]
        if page_id in seen_pages:
            raise RdwError("RD-E030", f"content.pages.{page_index}.page_id", "同一 page_id 重复。", "每页只提交一次。")
        seen_pages.add(page_id)
        if page_id not in accepted_page_ids:
            raise RdwError("RD-E030", f"content.pages.{page_index}.page_id", "该页不在完整源页清单内。", "重新生成完整计划并逐页填充。")
        slot_map = {slot["slot_id"]: slot for slot in page_map[page_id]["slots"]}
        seen_slots: set[str] = set()
        for slot_index, item in enumerate(page_content["slots"]):
            slot_id = item["slot_id"]
            if slot_id in seen_slots:
                raise RdwError("RD-E030", f"content.pages.{page_index}.slots.{slot_index}.slot_id", "slot_id 重复。", "每个槽位只提交一次。")
            seen_slots.add(slot_id)
            if "value" in item:
                if isinstance(item["value"], dict):
                    chart = item["value"]
                    if slot_map[slot_id]["type"] != "chart" or any(len(s["values"]) != len(chart["categories"]) for s in chart["series"]):
                        raise RdwError("RD-E030", f"content.pages.{page_index}.slots.{slot_index}", "图表类目和系列数值长度不一致。", "每个系列须覆盖全部类目。")
                    continue
                values = item["value"] if isinstance(item["value"], list) else [item["value"]]
                slot = slot_map[slot_id]
                if not slot["cardinality"]["min"] <= len(values) <= slot["cardinality"]["max"]:
                    raise RdwError("RD-E030", f"content.pages.{page_index}.slots.{slot_index}.value", "值数量超出槽位 cardinality。", "按槽位 min/max 调整条目数。")
        missing_required = [slot["slot_id"] for slot in page_map[page_id]["slots"] if slot["slot_id"] not in seen_slots]
        if missing_required:
            raise RdwError("RD-E030", f"content.pages.{page_index}.slots", f"必填槽位未声明: {', '.join(missing_required)}", "填写 value，或显式返回 status: missing 与原因。")
    return content
