from __future__ import annotations

import copy
from typing import Annotated, Any, Literal, Union

from pydantic import ConfigDict, Field, model_validator

from app.ir.common import (
    BulletListBlock,
    CodeBlock,
    ContractModel,
    HeadingBlock,
    ImagePlaceholderBlock,
    NumberedListBlock,
    PageBreakBlock,
    ParagraphBlock,
    TableBlock,
)


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


PreviewRow = Annotated[list[str], Field(max_length=15)]


class SheetSummary(ContractModel):
    name: str
    nrows: int = Field(ge=0)
    ncols: int = Field(ge=0)
    header_guess: list[str] = Field(default_factory=list)
    preview_rows: list[PreviewRow] = Field(default_factory=list, max_length=20)
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


class DocumentTableBlock(TableBlock):
    rows: list[list[str]] = Field(max_length=20)


DocumentBlock = Annotated[
    Union[
        HeadingBlock,
        ParagraphBlock,
        CodeBlock,
        BulletListBlock,
        NumberedListBlock,
        DocumentTableBlock,
        ImagePlaceholderBlock,
        PageBreakBlock,
    ],
    Field(discriminator="type"),
]


class DocumentContent(ContractModel):
    blocks: list[DocumentBlock] = Field(default_factory=list)
    outline: list[OutlineItem] = Field(default_factory=list)
    sheets: list[SheetSummary] = Field(default_factory=list)
    slides: list[SlideSummary] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_table_previews(self) -> "DocumentContent":
        for index, block in enumerate(self.blocks):
            if not isinstance(block, DocumentTableBlock):
                continue
            expected_cols = len(block.header)
            if any(len(row) != expected_cols for row in block.rows):
                raise ValueError(f"blocks[{index}].rows must match header column count")
        return self


class DocumentIR(ContractModel):
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "source": {
                                "properties": {"format": {"enum": ["md", "docx"]}},
                                "required": ["format"],
                            }
                        },
                        "required": ["source"],
                    },
                    "then": {
                        "properties": {
                            "content": {
                                "properties": {
                                    "sheets": {"maxItems": 0},
                                    "slides": {"maxItems": 0},
                                }
                            }
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "source": {
                                "properties": {"format": {"const": "xlsx"}},
                                "required": ["format"],
                            }
                        },
                        "required": ["source"],
                    },
                    "then": {
                        "properties": {
                            "content": {
                                "properties": {
                                    "blocks": {"maxItems": 0},
                                    "outline": {"maxItems": 0},
                                    "slides": {"maxItems": 0},
                                }
                            }
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "source": {
                                "properties": {"format": {"const": "pptx"}},
                                "required": ["format"],
                            }
                        },
                        "required": ["source"],
                    },
                    "then": {
                        "properties": {
                            "content": {
                                "properties": {
                                    "blocks": {"maxItems": 0},
                                    "outline": {"maxItems": 0},
                                    "sheets": {"maxItems": 0},
                                }
                            }
                        }
                    },
                },
            ]
        },
    )

    ir_type: Literal["document"]
    ir_version: Literal["1.2"]
    source: DocumentSource
    stats: DocumentStats
    warnings: list[str] = Field(default_factory=list)
    content: DocumentContent

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict) or value.get("ir_version") not in {"1.0", "1.1"}:
            return value
        source_version = value["ir_version"]
        migrated = copy.deepcopy(value)
        migrated["ir_version"] = "1.2"
        warnings = list(migrated.get("warnings") or [])
        migration_warning = f"DocumentIR {source_version} 已兼容迁移到 1.2，并按 1.2 约束重新校验。"
        if migration_warning not in warnings:
            warnings.append(migration_warning)
        migrated["warnings"] = warnings
        return migrated

    @model_validator(mode="after")
    def validate_content_matches_format(self) -> "DocumentIR":
        populated = {
            "blocks": bool(self.content.blocks),
            "outline": bool(self.content.outline),
            "sheets": bool(self.content.sheets),
            "slides": bool(self.content.slides),
        }
        allowed = {
            "md": {"blocks", "outline"},
            "docx": {"blocks", "outline"},
            "xlsx": {"sheets"},
            "pptx": {"slides"},
        }[self.source.format]
        invalid = [name for name, has_items in populated.items() if has_items and name not in allowed]
        if invalid:
            joined = ", ".join(f"content.{name}" for name in invalid)
            raise ValueError(f"source.format={self.source.format} does not allow populated {joined}")
        return self
