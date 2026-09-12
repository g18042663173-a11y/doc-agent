from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


VisualLayout = Literal[
    "chart",
    "architecture_diagram",
    "process_flow",
    "timeline",
    "infographic_funnel",
    "infographic_quadrant",
    "infographic_cycle",
    "infographic_matrix",
    "image_text",
    "image_grid",
    "text_only",
]


class VisualContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VisualOpportunity(VisualContractModel):
    visual_id: str = Field(pattern=r"^visual-[0-9]{3}$")
    recommended_layout: VisualLayout
    chart_kind: Literal["bar", "line", "pie", "scatter", "combo"] | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list, max_length=8)
    asset_ids: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def chart_kind_matches_layout(self) -> "VisualOpportunity":
        if (self.recommended_layout == "chart") != (self.chart_kind is not None):
            raise ValueError("chart_kind is required only for chart recommendations")
        if self.recommended_layout.startswith("image_") and not self.asset_ids:
            raise ValueError("image recommendations require asset ids")
        return self


class VisualPlan(VisualContractModel):
    visual_plan_version: Literal["1.0"]
    source_filename: str = Field(min_length=1)
    opportunities: list[VisualOpportunity] = Field(default_factory=list, max_length=12)


class VisualSelection(VisualContractModel):
    visual_id: str = Field(pattern=r"^visual-[0-9]{3}$")
    recommended_layout: VisualLayout
    selected: bool
    slide_indices: list[int] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class VisualSelectionAudit(VisualContractModel):
    audit_version: Literal["1.0"]
    selections: list[VisualSelection] = Field(default_factory=list)


def visual_schema_documents() -> dict[str, dict]:
    models = {"visual_plan": VisualPlan, "visual_selection_audit": VisualSelectionAudit}
    return {
        name: json.loads(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True))
        for name, model in models.items()
    }


def write_visual_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, schema in visual_schema_documents().items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
