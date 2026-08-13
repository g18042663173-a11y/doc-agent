from __future__ import annotations

from hashlib import sha256
import json

from app.ir.deck_ir import DeckIR
from app.template.contracts import (
    TemplatePlan,
    TemplateProfile,
    TemplateReplacement,
    TemplateScoreDetails,
    TemplateSlidePlan,
    TemplateSlideProfile,
    TemplateWarning,
)
from app.template.text_fit import font_is_available
from app.template.theme import select_template_fonts


REPLACEABLE_LAYOUTS = {"cover", "agenda", "section", "title_bullets", "two_column", "conclusion"}
COMPATIBLE_ROLES = {
    "cover": {"cover": 40, "section": 22},
    "agenda": {"agenda": 40, "title_bullets": 25, "generic": 15},
    "section": {"section": 40, "closing": 25, "cover": 20},
    "title_bullets": {"title_bullets": 40, "generic": 30, "cards": 22},
    "two_column": {"two_column": 40, "cards": 25, "generic": 18},
    "table": {"table": 40, "title_bullets": 20, "generic": 18},
    "chart": {"chart": 40, "two_column": 22, "generic": 18},
    "cards": {"cards": 40, "two_column": 25, "generic": 18},
    "timeline": {"timeline": 40, "title_bullets": 20, "generic": 18},
    "conclusion": {"conclusion": 40, "closing": 35, "title_bullets": 20, "generic": 18},
    "architecture_diagram": {"two_column": 20, "generic": 18},
    "process_flow": {"timeline": 25, "generic": 18},
    "image": {"two_column": 20, "generic": 18},
    "composite": {"two_column": 25, "generic": 18},
}


def build_template_plan(deck: DeckIR, profile: TemplateProfile) -> TemplatePlan:
    use_counts: dict[str, int] = {}
    slide_plans: list[TemplateSlidePlan] = []
    warnings = _font_substitution_warnings(profile)
    for output_index, slide in enumerate(deck.slides, start=1):
        required = _required_content(slide)
        candidates = [
            _candidate(slide.layout, required, candidate, use_counts.get(candidate.prototype_id, 0))
            for candidate in profile.slides
        ]
        best_profile, details, replacements = max(
            candidates,
            key=lambda candidate: (candidate[1].total, -candidate[0].index),
        )
        score = max(0, details.total)
        use_prototype = slide.layout in REPLACEABLE_LAYOUTS and best_profile.safe_to_clone and score >= 70
        slide_warnings: list[TemplateWarning] = []
        strategy = "prototype_replace" if use_prototype else "master_redraw"
        if not use_prototype:
            warning = TemplateWarning(
                code="W201",
                loc=f"slides[{output_index - 1}].template",
                message=(
                    f"模板原型 {best_profile.prototype_id} 不满足安全文本替换阈值，"
                    "已在同一模板母版/主题下重绘。"
                ),
            )
            slide_warnings.append(warning)
            warnings.append(warning)
            replacements = []
        else:
            use_counts[best_profile.prototype_id] = use_counts.get(best_profile.prototype_id, 0) + 1
            essential_count = sum(1 for _role, _source, _text, essential in required if essential)
            if len(replacements) < essential_count:
                # Prototype replacement would silently drop unmatched essential
                # content (e.g. an 8-item agenda against a 5-slot prototype).
                # Render from the master instead so no deck content is lost.
                unmatched = essential_count - len(replacements)
                use_counts[best_profile.prototype_id] = max(
                    0, use_counts[best_profile.prototype_id] - 1
                )
                replacements = []
                strategy = "master_redraw"
                warning = TemplateWarning(
                    code="W201",
                    loc=f"slides[{output_index - 1}].template",
                    message=(
                        f"模板原型 {best_profile.prototype_id} 无法容纳全部必需内容"
                        f"（未匹配 {unmatched} 项），已在同一模板母版/主题下重绘以保留完整内容。"
                    ),
                )
                slide_warnings.append(warning)
                warnings.append(warning)
        slide_plans.append(
            TemplateSlidePlan(
                output_index=output_index,
                deck_layout=slide.layout,
                strategy=strategy,
                prototype_id=best_profile.prototype_id,
                prototype_index=best_profile.index,
                score=score,
                score_details=details,
                selection_reason=(
                    f"role={details.role}/40, slots={details.slots}/25, "
                    f"capacity={details.capacity}/25, safety={details.safety}/10, "
                    f"reuse_penalty={details.reuse_penalty}"
                ),
                replacements=replacements,
                warnings=slide_warnings,
            )
        )
    profile_payload = json.dumps(
        profile.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return TemplatePlan(
        plan_version="1.1",
        template_sha256=profile.source.sha256,
        profile_sha256=sha256(profile_payload.encode("utf-8")).hexdigest(),
        deck_ir_version=deck.ir_version,
        slides=slide_plans,
        warnings=warnings,
    )


def _font_substitution_warnings(profile: TemplateProfile) -> list[TemplateWarning]:
    _major, minor, substitutions = select_template_fonts(profile)
    warnings = [
        TemplateWarning(
            code="W202",
            loc=loc,
            message=f"模板字体 {source} 在当前系统不可用，已替代为 {replacement}。",
        )
        for loc, source, replacement in substitutions
    ]
    theme_sources = {source for _loc, source, _replacement in substitutions}
    missing_shape_fonts: dict[str, tuple[str, int]] = {}
    for slide_index, slide in enumerate(profile.slides):
        for shape_index, shape in enumerate(slide.shapes):
            font_name = shape.style.font_name if shape.style is not None else None
            if (
                not font_name
                or font_name.startswith("+")
                or font_name in theme_sources
                or font_is_available(font_name)
            ):
                continue
            loc = f"template.slides[{slide_index}].shapes[{shape_index}].style.font_name"
            first_loc, count = missing_shape_fonts.get(font_name, (loc, 0))
            missing_shape_fonts[font_name] = (first_loc, count + 1)
    warnings.extend(
        TemplateWarning(
            code="W202",
            loc=loc,
            message=f"模板字体 {font_name} 在当前系统不可用，已替代为 {minor}（影响 {count} 个形状）。",
        )
        for font_name, (loc, count) in sorted(missing_shape_fonts.items())
    )
    return warnings


def _candidate(
    deck_layout: str,
    required: list[tuple[str, str, str, bool]],
    candidate: TemplateSlideProfile,
    reuse_count: int,
) -> tuple[TemplateSlideProfile, TemplateScoreDetails, list[TemplateReplacement]]:
    role_score = COMPATIBLE_ROLES.get(deck_layout, {}).get(candidate.role, 0)
    available = [shape for shape in candidate.shapes if shape.role not in {"brand", "footer", "decorative"}]
    matched = _match_replacements(required, available)
    slots_score = round(25 * len(matched) / max(len(required), 1))
    required_chars = sum(len(text) for _role, _source, text, _essential in required)
    matched_shape_ids = {replacement.shape_id for replacement in matched}
    available_chars = sum(
        shape.capacity.char_capacity
        for shape in available
        if shape.capacity is not None and shape.shape_id in matched_shape_ids
    )
    if required_chars == 0:
        capacity_score = 25
    elif available_chars >= required_chars:
        capacity_score = 25
    else:
        capacity_score = round(25 * available_chars / required_chars)
    safety_score = 10 if candidate.safe_to_clone else 0
    reuse_penalty = min(reuse_count * 5, 15)
    details = TemplateScoreDetails(
        role=role_score,
        slots=slots_score,
        capacity=capacity_score,
        safety=safety_score,
        reuse_penalty=reuse_penalty,
    )
    return candidate, details, matched


def _match_replacements(required, available) -> list[TemplateReplacement]:
    remaining = list(available)
    replacements: list[TemplateReplacement] = []
    aliases = {
        "subtitle": ("subtitle", "section_label", "body"),
        "section_label": ("section_label", "subtitle", "body"),
        "agenda_item": ("agenda_item", "body", "content_slot"),
        "body": ("body", "agenda_item", "content_slot", "unknown"),
        "title": ("title",),
    }
    for role, source_path, _text, _essential in required:
        match = next((shape for shape in remaining if shape.role in aliases.get(role, (role,))), None)
        if match is None:
            continue
        remaining.remove(match)
        replacements.append(TemplateReplacement(shape_id=match.shape_id, role=role, source_path=source_path))
    return replacements


def _required_content(slide) -> list[tuple[str, str, str, bool]]:
    """Return (role, source_path, text, essential) content items for a slide.

    ``essential`` marks content whose loss would be a data-integrity problem
    (title, body, agenda items); optional metadata like a cover's presenter or
    date is still matched to a template slot when one exists, but its absence
    from the prototype must not force a master_redraw fallback.
    """
    layout = slide.layout
    if layout == "cover":
        values: list[tuple[str, str, str, bool]] = [("title", "title", slide.title, True)]
        if slide.subtitle:
            values.append(("subtitle", "subtitle", slide.subtitle, True))
        if slide.presenter:
            values.append(("body", "presenter", slide.presenter, False))
        if slide.date:
            values.append(("body", "date", slide.date, False))
        return values
    if layout == "agenda":
        return [("agenda_item", f"items[{index}]", item, True) for index, item in enumerate(slide.items)]
    if layout == "section":
        values = [("title", "title", slide.title, True)]
        if slide.subtitle:
            values.append(("subtitle", "subtitle", slide.subtitle, True))
        if slide.index:
            values.append(("body", "index", str(slide.index), False))
        return values
    if layout == "title_bullets":
        return [("title", "title", slide.title, True), ("body", "bullets", "\n".join(item.text for item in slide.bullets), True)]
    if layout == "two_column":
        left = _column_text(slide.left)
        right = _column_text(slide.right)
        return [("title", "title", slide.title, True), ("body", "left", left, True), ("body", "right", right, True)]
    if layout == "conclusion":
        values = [("title", "title", slide.title, True)]
        if slide.bullets:
            values.append(("body", "bullets", "\n".join(slide.bullets), True))
        if slide.cta:
            values.append(("body", "cta", slide.cta, True))
        return values
    title = getattr(slide, "title", layout)
    return [("title", "title", title, True)]


def _column_text(column) -> str:
    parts: list[str] = []
    if column.heading:
        parts.append(column.heading)
    if column.text:
        parts.append(column.text)
    parts.extend(item.text for item in column.bullets)
    return "\n".join(parts)
