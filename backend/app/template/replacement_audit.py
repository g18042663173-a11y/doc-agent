"""Privacy-safe verification evidence for template text replacement."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from app.ir.deck_ir import DeckIR
from app.assets.pipeline import AssetRegistry
from app.template.contracts import (
    TemplatePlan,
    TemplateProfile,
    TemplateReplacementAudit,
    TemplateReplacementAuditShape,
    TemplateReplacementAuditSlide,
)


def build_template_replacement_audit(
    deck: DeckIR,
    profile: TemplateProfile,
    plan: TemplatePlan,
    presentation,
    asset_registry: AssetRegistry | None = None,
) -> TemplateReplacementAudit:
    """Describe applied replacements without serializing source or generated text."""

    if len(deck.slides) != len(plan.slides) or len(deck.slides) != len(presentation.slides):
        raise ValueError("replacement audit requires one rendered slide per DeckIR slide")

    audit_slides: list[TemplateReplacementAuditSlide] = []
    for output_index, (deck_slide, slide_plan, rendered_slide) in enumerate(
        zip(deck.slides, plan.slides, presentation.slides), start=1
    ):
        profile_slide = profile.slides[(slide_plan.prototype_index or 1) - 1]
        shape_by_id = {shape.shape_id: shape for shape in _iter_shapes(rendered_slide.shapes)}
        planned = {replacement.shape_id: replacement for replacement in slide_plan.replacements}
        shapes: list[TemplateReplacementAuditShape] = []
        planned_shapes_exist = True
        unused_text_cleared = True

        if slide_plan.strategy == "prototype_replace":
            for shape_profile in profile_slide.shapes:
                if shape_profile.kind not in {"text", "placeholder"}:
                    continue
                shape = shape_by_id.get(shape_profile.shape_id)
                replacement = planned.get(shape_profile.shape_id)
                if shape is None:
                    planned_shapes_exist = False
                    shapes.append(
                        TemplateReplacementAuditShape(
                            shape_id=shape_profile.shape_id,
                            role=shape_profile.role,
                            action="replaced" if replacement else "cleared",
                            source_path=replacement.source_path if replacement else None,
                            text_fit=False,
                            reason="rendered_shape_missing",
                        )
                    )
                    continue

                rendered_text = _shape_text(shape)
                if replacement is not None:
                    expected = _source_text(deck_slide, replacement.source_path)
                    matches_expected = rendered_text == expected
                    shapes.append(
                        TemplateReplacementAuditShape(
                            shape_id=shape_profile.shape_id,
                            role=shape_profile.role,
                            action="replaced",
                            source_path=replacement.source_path,
                            expected_text_sha256=_text_hash(expected),
                            rendered_text_sha256=_text_hash(rendered_text),
                            text_fit=matches_expected,
                            reason=None if matches_expected else "rendered_text_differs_from_plan",
                        )
                    )
                    if not matches_expected:
                        unused_text_cleared = False
                elif shape_profile.role == "brand":
                    shapes.append(
                        TemplateReplacementAuditShape(
                            shape_id=shape_profile.shape_id,
                            role=shape_profile.role,
                            action="preserved",
                            rendered_text_sha256=_text_hash(rendered_text),
                        )
                    )
                else:
                    cleared = not rendered_text.strip()
                    shapes.append(
                        TemplateReplacementAuditShape(
                            shape_id=shape_profile.shape_id,
                            role=shape_profile.role,
                            action="cleared",
                            rendered_text_sha256=_text_hash(rendered_text),
                            text_fit=cleared,
                            reason=None if cleared else "unused_template_text_remains",
                        )
                    )
                    unused_text_cleared = unused_text_cleared and cleared
        else:
            shapes.append(
                TemplateReplacementAuditShape(
                    shape_id=1,
                    role="decorative",
                    action="master_redraw",
                    reason="template_plan_master_redraw",
                )
            )
        if asset_registry is not None:
            for spec in _image_specs(deck_slide):
                picture = next(
                    (
                        shape
                        for shape in _iter_shapes(rendered_slide.shapes)
                        if getattr(shape, "name", "") == f"HW_ASSET_IMAGE:{spec.image_ref}"
                    ),
                    None,
                )
                if picture is None:
                    planned_shapes_exist = False
                    continue
                record = asset_registry.record(spec.image_ref)
                shapes.append(
                    TemplateReplacementAuditShape(
                        shape_id=picture.shape_id,
                        role="content_slot",
                        action="image_replaced",
                        source_path="image_ref",
                        asset_id=record.asset_id,
                        asset_sha256=record.normalized_sha256,
                        image_fit=spec.fit,
                        crop_left=float(getattr(picture, "crop_left", 0)),
                        crop_top=float(getattr(picture, "crop_top", 0)),
                        crop_right=float(getattr(picture, "crop_right", 0)),
                        crop_bottom=float(getattr(picture, "crop_bottom", 0)),
                        focal_x=spec.focal_x,
                        focal_y=spec.focal_y,
                        text_fit=True,
                    )
                )

        no_placeholder_residue = slide_plan.strategy == "master_redraw" or unused_text_cleared
        audit_slides.append(
            TemplateReplacementAuditSlide(
                output_index=output_index,
                prototype_id=profile_slide.prototype_id,
                strategy=slide_plan.strategy,
                planned_shapes_exist=planned_shapes_exist,
                unused_text_cleared=unused_text_cleared,
                no_placeholder_residue=no_placeholder_residue,
                text_fit=slide_plan.strategy == "master_redraw" or all(
                    item.text_fit is not False for item in shapes
                ),
                shapes=shapes,
            )
        )

    return TemplateReplacementAudit(
        audit_version="1.1",
        template_sha256=profile.source.sha256,
        plan_sha256=_plan_hash(plan),
        slides=audit_slides,
        warnings=plan.warnings,
    )


def write_template_replacement_audit(audit: TemplateReplacementAudit, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def _plan_hash(plan: TemplatePlan) -> str:
    payload = json.dumps(
        plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _text_hash(value: str) -> str | None:
    if not value:
        return None
    return sha256(value.encode("utf-8")).hexdigest()


def _shape_text(shape) -> str:
    if not getattr(shape, "has_text_frame", False):
        return ""
    return "\n".join(paragraph.text for paragraph in shape.text_frame.paragraphs).strip()


def _iter_shapes(shapes):
    for shape in shapes:
        if "GROUP" in str(getattr(shape, "shape_type", "")) and hasattr(shape, "shapes"):
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def _source_text(slide, source_path: str) -> str:
    if source_path == "title":
        return slide.title
    if source_path == "subtitle":
        return slide.subtitle or ""
    if source_path.startswith("items["):
        index = int(source_path.removeprefix("items[").removesuffix("]"))
        return slide.items[index]
    if source_path == "bullets":
        return "\n".join(f"• {getattr(item, 'text', item)}" for item in slide.bullets)
    if source_path == "left":
        return _column_text(slide.left)
    if source_path == "right":
        return _column_text(slide.right)
    if source_path == "cta":
        return slide.cta or ""
    raise ValueError(f"unknown template replacement source: {source_path}")


def _image_specs(slide):
    if slide.layout == "image" and slide.image_ref:
        return [slide]
    if slide.layout == "image_text":
        return [slide.image]
    if slide.layout == "image_grid":
        return list(slide.images)
    return []


def _column_text(column) -> str:
    values: list[str] = []
    if column.heading:
        values.append(column.heading)
    if column.text:
        values.append(column.text)
    values.extend(f"• {item.text}" for item in column.bullets)
    return "\n".join(values)
