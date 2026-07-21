from __future__ import annotations

import copy
from typing import Annotated, Any, Literal, Union

from pydantic import Field, field_validator, model_validator

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
    non_empty,
)


class WordMeta(ContractModel):
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str | None = None
    classification: str = "内部公开"
    header_text: str | None = None
    footer_text: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


WordBlock = Annotated[
    Union[
        HeadingBlock,
        ParagraphBlock,
        CodeBlock,
        BulletListBlock,
        NumberedListBlock,
        TableBlock,
        ImagePlaceholderBlock,
        PageBreakBlock,
    ],
    Field(discriminator="type"),
]


def migrate_word_payload(value: Any, *, target_version: str = "1.1") -> tuple[Any, str | None]:
    if not isinstance(value, dict) or value.get("ir_version") != "1.0" or target_version != "1.1":
        return value, None
    migrated = copy.deepcopy(value)
    migrated["ir_version"] = "1.1"
    return migrated, "1.0"


class WordIR(ContractModel):
    ir_type: Literal["word"]
    ir_version: Literal["1.1"]
    meta: WordMeta
    blocks: list[WordBlock] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_payload(cls, value: Any) -> Any:
        migrated, _source_version = migrate_word_payload(value)
        return migrated

    @model_validator(mode="after")
    def validate_tables(self) -> "WordIR":
        for index, block in enumerate(self.blocks):
            if isinstance(block, TableBlock):
                expected_cols = len(block.header)
                if not block.rows:
                    raise ValueError(f"blocks[{index}].table rows must contain at least one data row")
                if len(block.header) > 12:
                    raise ValueError(f"blocks[{index}].header exceeds 12 columns")
                if any(len(row) != expected_cols for row in block.rows):
                    raise ValueError(f"blocks[{index}].rows must match header column count")
                if block.col_widths is not None and len(block.col_widths) != expected_cols:
                    raise ValueError(f"blocks[{index}].col_widths must match header column count")
            if isinstance(block, ImagePlaceholderBlock) and not block.ref and not block.caption:
                raise ValueError(f"blocks[{index}].image_placeholder requires ref or caption")
        return self
