from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field


class DocumentBlock(BaseModel):
    id: str
    type: Literal["heading", "paragraph", "bullet_list", "table", "slide", "note", "image"]
    text: str | None = None
    level: int | None = None
    items: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class DocumentIR(BaseModel):
    source_file: str
    source_type: Literal["md", "docx", "pptx", "xlsx", "unknown"]
    title: str | None = None
    blocks: list[DocumentBlock] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


SlideLayout = Literal[
    "cover",
    "agenda",
    "section",
    "title_bullets",
    "two_column",
    "table",
    "cards",
    "chart",
    "image",
    "conclusion",
]
Importance = Literal["low", "medium", "high", "critical"]


class SourceRef(BaseModel):
    block_id: str | None = None
    source_file: str | None = None
    label: str | None = None
    excerpt: str | None = None


class CardIR(BaseModel):
    title: str
    body: str | None = None
    bullets: list[str] = Field(default_factory=list)
    importance: Importance = "medium"


class VisualIR(BaseModel):
    kind: Literal["image", "icon", "shape", "placeholder"] = "placeholder"
    title: str | None = None
    path: str | None = None
    alt_text: str | None = None
    caption: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ChartSeriesIR(BaseModel):
    name: str
    values: list[float] = Field(default_factory=list)


class ChartIR(BaseModel):
    chart_type: Literal["bar", "line", "pie", "table", "kpi"] = "bar"
    title: str | None = None
    labels: list[str] = Field(default_factory=list)
    series: list[ChartSeriesIR] = Field(default_factory=list)
    summary: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class FooterIR(BaseModel):
    text: str | None = None
    confidentiality: str | None = "HUAWEI CONFIDENTIAL"
    show_page_number: bool = True


class SlideIR(BaseModel):
    layout: SlideLayout
    title: str
    subtitle: str | None = None
    intent: str | None = None
    importance: Importance = "medium"
    source_refs: list[SourceRef] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    left_title: str | None = None
    left_bullets: list[str] = Field(default_factory=list)
    right_title: str | None = None
    right_bullets: list[str] = Field(default_factory=list)
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)
    cards: list[CardIR] = Field(default_factory=list)
    visuals: list[VisualIR] = Field(default_factory=list)
    chart: ChartIR | None = None
    footer: FooterIR | None = None
    confidentiality: str | None = None
    speaker_notes: str | None = None


class DeckIR(BaseModel):
    ir_version: str = "1.1"
    deck_title: str
    audience: str = "内部汇报"
    tone: str = "专业、克制、清晰"
    source_refs: list[SourceRef] = Field(default_factory=list)
    footer: FooterIR | None = None
    confidentiality: str | None = "HUAWEI CONFIDENTIAL"
    slides: list[SlideIR] = Field(default_factory=list)


class WordBlockIR(BaseModel):
    type: Literal["heading", "paragraph", "bullet_list", "table"]
    text: str | None = None
    level: int | None = None
    items: list[str] = Field(default_factory=list)
    table_headers: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)


class WordIR(BaseModel):
    title: str
    subtitle: str | None = None
    blocks: list[WordBlockIR] = Field(default_factory=list)


ModelT = TypeVar("ModelT", bound=BaseModel)


def load_json(path: str | Path, model: type[ModelT]) -> ModelT:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return model.model_validate(data)


def save_json(obj: BaseModel | dict[str, Any], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, BaseModel):
        data = obj.model_dump(mode="json")
    else:
        data = obj
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def to_pretty_json(obj: BaseModel | dict[str, Any]) -> str:
    if isinstance(obj, BaseModel):
        data = obj.model_dump(mode="json")
    else:
        data = obj
    return json.dumps(data, ensure_ascii=False, indent=2)
