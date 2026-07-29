from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COLOR_RE = re.compile(r"^[0-9A-F]{6}$")


class TemplateContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateSource(TemplateContractModel):
    filename: str = Field(min_length=1)
    sha256: str
    bytes: int = Field(ge=1)

    @field_validator("filename")
    @classmethod
    def filename_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("filename must not be blank")
        return value

    @field_validator("sha256")
    @classmethod
    def sha256_is_lower_hex(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class TemplateTheme(TemplateContractModel):
    major_fonts: list[str] = Field(default_factory=list)
    minor_fonts: list[str] = Field(default_factory=list)
    colors: dict[str, str] = Field(default_factory=dict)

    @field_validator("major_fonts", "minor_fonts")
    @classmethod
    def fonts_are_unique_and_non_blank(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("font names must not be blank")
        return list(dict.fromkeys(normalized))

    @field_validator("colors")
    @classmethod
    def colors_are_rgb_hex(cls, value: dict[str, str]) -> dict[str, str]:
        normalized = {str(key): str(color).lstrip("#").upper() for key, color in value.items()}
        if any(not COLOR_RE.fullmatch(color) for color in normalized.values()):
            raise ValueError("template colors must be six-digit RGB hex values")
        return normalized


class TemplateTextStyle(TemplateContractModel):
    font_name: str | None = None
    font_size_pt: float | None = Field(default=None, gt=0, le=400)
    bold: bool | None = None
    color_hex: str | None = None
    alignment: str | None = None

    @field_validator("color_hex")
    @classmethod
    def color_is_rgb_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lstrip("#").upper()
        if not COLOR_RE.fullmatch(normalized):
            raise ValueError("color_hex must be a six-digit RGB value")
        return normalized


class TemplateCapacity(TemplateContractModel):
    char_capacity: int = Field(ge=0)
    line_capacity: int = Field(ge=0)
    list_item_capacity: int = Field(ge=0)


TemplateShapeKind = Literal["text", "placeholder", "shape", "image", "table", "chart", "group"]
TemplateShapeRole = Literal[
    "title",
    "subtitle",
    "body",
    "agenda_item",
    "section_label",
    "footer",
    "brand",
    "decorative",
    "content_slot",
    "unknown",
]


class TemplateShapeProfile(TemplateContractModel):
    shape_id: int = Field(ge=1)
    name: str = Field(min_length=1)
    kind: TemplateShapeKind
    role: TemplateShapeRole
    left_ratio: float = Field(ge=-2, le=3)
    top_ratio: float = Field(ge=-2, le=3)
    width_ratio: float = Field(ge=0, le=3)
    height_ratio: float = Field(ge=0, le=3)
    text_preview: str | None = None
    style: TemplateTextStyle | None = None
    fill_color_hex: str | None = None
    line_color_hex: str | None = None
    capacity: TemplateCapacity | None = None
    relationship_ids: list[str] = Field(default_factory=list)

    @field_validator("fill_color_hex", "line_color_hex")
    @classmethod
    def shape_colors_are_rgb_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lstrip("#").upper()
        if not COLOR_RE.fullmatch(normalized):
            raise ValueError("shape colors must be six-digit RGB values")
        return normalized


class TemplateRelationship(TemplateContractModel):
    relationship_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    external: bool = False


TemplateSlideRole = Literal[
    "cover",
    "agenda",
    "section",
    "title_bullets",
    "two_column",
    "table",
    "chart",
    "cards",
    "timeline",
    "conclusion",
    "closing",
    "generic",
]


class TemplateSlideProfile(TemplateContractModel):
    index: int = Field(ge=1)
    prototype_id: str = Field(pattern=r"^slide-[0-9]{3}$")
    role: TemplateSlideRole
    layout_name: str | None = None
    master_name: str | None = None
    safe_to_clone: bool
    exclusion_reasons: list[str] = Field(default_factory=list)
    has_transition: bool = False
    has_timing: bool = False
    notes_present: bool = False
    relationships: list[TemplateRelationship] = Field(default_factory=list)
    shapes: list[TemplateShapeProfile] = Field(default_factory=list)

    @model_validator(mode="after")
    def unsafe_slide_has_reason(self) -> "TemplateSlideProfile":
        if not self.safe_to_clone and not self.exclusion_reasons:
            raise ValueError("unsafe template slides must record an exclusion reason")
        return self


class TemplateProfile(TemplateContractModel):
    profile_version: Literal["1.0"]
    source: TemplateSource
    slide_width_in: float = Field(gt=0, le=100)
    slide_height_in: float = Field(gt=0, le=100)
    theme: TemplateTheme
    slides: list[TemplateSlideProfile] = Field(min_length=1, max_length=200)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def slide_indices_and_ids_are_unique(self) -> "TemplateProfile":
        indices = [slide.index for slide in self.slides]
        identifiers = [slide.prototype_id for slide in self.slides]
        if len(indices) != len(set(indices)) or len(identifiers) != len(set(identifiers)):
            raise ValueError("template slide indices and prototype ids must be unique")
        return self


class TemplateWarning(TemplateContractModel):
    code: Literal["W201", "W202"]
    loc: str = Field(min_length=1)
    message: str = Field(min_length=1)


class TemplateReplacement(TemplateContractModel):
    shape_id: int = Field(ge=1)
    role: TemplateShapeRole
    source_path: str = Field(min_length=1)


class TemplateScoreDetails(TemplateContractModel):
    role: int = Field(ge=0, le=40)
    slots: int = Field(ge=0, le=25)
    capacity: int = Field(ge=0, le=25)
    safety: int = Field(ge=0, le=10)
    reuse_penalty: int = Field(ge=0, le=15)

    @property
    def total(self) -> int:
        return self.role + self.slots + self.capacity + self.safety - self.reuse_penalty


TemplateStrategy = Literal["prototype_replace", "master_redraw"]


class TemplateSlidePlan(TemplateContractModel):
    output_index: int = Field(ge=1)
    deck_layout: str = Field(min_length=1)
    strategy: TemplateStrategy
    prototype_id: str | None = Field(default=None, pattern=r"^slide-[0-9]{3}$")
    prototype_index: int | None = Field(default=None, ge=1)
    score: int = Field(ge=0, le=100)
    score_details: TemplateScoreDetails
    selection_reason: str = Field(min_length=1)
    replacements: list[TemplateReplacement] = Field(default_factory=list)
    warnings: list[TemplateWarning] = Field(default_factory=list)

    @model_validator(mode="after")
    def score_and_prototype_are_consistent(self) -> "TemplateSlidePlan":
        if self.score != max(0, self.score_details.total):
            raise ValueError("template slide score must match score_details")
        if self.strategy == "prototype_replace" and (self.prototype_id is None or self.prototype_index is None):
            raise ValueError("prototype_replace requires prototype id and index")
        return self


class TemplatePlan(TemplateContractModel):
    plan_version: Literal["1.1"]
    template_sha256: str
    profile_sha256: str
    deck_ir_version: Literal["2.0"]
    slides: list[TemplateSlidePlan] = Field(min_length=1, max_length=30)
    warnings: list[TemplateWarning] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_plan(cls, value):
        if isinstance(value, dict) and value.get("plan_version") == "1.0":
            value = dict(value)
            value["plan_version"] = "1.1"
            if value.get("deck_ir_version") == "1.9":
                value["deck_ir_version"] = "2.0"
        return value

    @field_validator("template_sha256", "profile_sha256")
    @classmethod
    def hashes_are_lower_hex(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("hash must be 64 lowercase hexadecimal characters")
        return value


TemplateReplacementAction = Literal["replaced", "cleared", "preserved", "master_redraw", "image_replaced"]


class TemplateReplacementAuditShape(TemplateContractModel):
    """A privacy-safe record of one template text-shape decision."""

    shape_id: int = Field(ge=1)
    role: TemplateShapeRole
    action: TemplateReplacementAction
    source_path: str | None = None
    expected_text_sha256: str | None = None
    rendered_text_sha256: str | None = None
    text_fit: bool | None = None
    reason: str | None = None
    asset_id: str | None = None
    asset_sha256: str | None = None
    image_fit: Literal["contain", "cover"] | None = None
    crop_left: float | None = Field(default=None, ge=0, le=1)
    crop_top: float | None = Field(default=None, ge=0, le=1)
    crop_right: float | None = Field(default=None, ge=0, le=1)
    crop_bottom: float | None = Field(default=None, ge=0, le=1)
    focal_x: float | None = Field(default=None, ge=0, le=1)
    focal_y: float | None = Field(default=None, ge=0, le=1)

    @field_validator("expected_text_sha256", "rendered_text_sha256", "asset_sha256")
    @classmethod
    def optional_hashes_are_lower_hex(cls, value: str | None) -> str | None:
        if value is not None and not SHA256_RE.fullmatch(value):
            raise ValueError("hash must be 64 lowercase hexadecimal characters")
        return value


class TemplateReplacementAuditSlide(TemplateContractModel):
    output_index: int = Field(ge=1)
    prototype_id: str = Field(pattern=r"^slide-[0-9]{3}$")
    strategy: TemplateStrategy
    planned_shapes_exist: bool
    unused_text_cleared: bool
    no_placeholder_residue: bool
    text_fit: bool
    shapes: list[TemplateReplacementAuditShape] = Field(default_factory=list)


class TemplateReplacementAudit(TemplateContractModel):
    audit_version: Literal["1.1"]
    template_sha256: str
    plan_sha256: str
    slides: list[TemplateReplacementAuditSlide] = Field(min_length=1)
    warnings: list[TemplateWarning] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_audit(cls, value):
        if isinstance(value, dict) and value.get("audit_version") == "1.0":
            value = dict(value)
            value["audit_version"] = "1.1"
        return value

    @field_validator("template_sha256", "plan_sha256")
    @classmethod
    def hashes_are_lower_hex(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("hash must be 64 lowercase hexadecimal characters")
        return value

    @model_validator(mode="after")
    def output_indices_are_unique(self) -> "TemplateReplacementAudit":
        indices = [slide.output_index for slide in self.slides]
        if len(indices) != len(set(indices)):
            raise ValueError("replacement audit output indices must be unique")
        return self

def template_schema_documents() -> dict[str, dict]:
    models = {
        "template_profile": TemplateProfile,
        "template_plan": TemplatePlan,
        "template_replacement_audit": TemplateReplacementAudit,
    }
    return {
        name: json.loads(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True))
        for name, model in models.items()
    }


def write_template_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, schema in template_schema_documents().items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written
