from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.ir.common import ContractModel
from app.ir.word_ir import WordBlock


class DocumentSource(ContractModel):
    filename: str = Field(min_length=1)
    format: Literal["md", "docx", "xlsx", "pptx"]
    size_kb: float = Field(ge=0)
    parsed_at: str = Field(min_length=1)


class DocumentStats(ContractModel):
    headings: int = Field(default=0, ge=0)
    paragraphs: int = Field(default=0, ge=0)
    tables: int = Field(default=0, ge=0)
    images: int = Field(default=0, ge=0)


class OutlineItem(ContractModel):
    level: int = Field(ge=1, le=6)
    text: str = Field(min_length=1)


class ColumnStat(ContractModel):
    name: str
    type_guess: str | None = None
    non_empty_ratio: float | None = Field(default=None, ge=0, le=1)
    samples: list[str] = Field(default_factory=list, max_length=3)


class SheetSummary(ContractModel):
    name: str
    nrows: int = Field(ge=0)
    ncols: int = Field(ge=0)
    header_guess: list[str] = Field(default_factory=list)
    preview_rows: list[list[str]] = Field(default_factory=list)
    col_stats: list[ColumnStat] = Field(default_factory=list)
    formula_count: int = Field(default=0, ge=0)
    merged_count: int = Field(default=0, ge=0)
    truncated: bool = False


class SlideSummary(ContractModel):
    index: int = Field(ge=1)
    layout_name: str | None = None
    title: str | None = None
    bodies: list[str] = Field(default_factory=list)
    tables: list[dict] = Field(default_factory=list)
    notes: str | None = None
    shape_warnings: list[str] = Field(default_factory=list)


class DocumentContent(ContractModel):
    blocks: list[WordBlock] = Field(default_factory=list)
    outline: list[OutlineItem] = Field(default_factory=list)
    sheets: list[SheetSummary] = Field(default_factory=list)
    slides: list[SlideSummary] = Field(default_factory=list)


class DocumentIR(ContractModel):
    ir_type: Literal["document"]
    ir_version: Literal["1.0"]
    source: DocumentSource
    stats: DocumentStats
    warnings: list[str] = Field(default_factory=list)
    content: DocumentContent
