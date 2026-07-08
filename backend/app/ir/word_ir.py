from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from app.ir.common import (
    BulletListBlock,
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
        BulletListBlock,
        NumberedListBlock,
        TableBlock,
        ImagePlaceholderBlock,
        PageBreakBlock,
    ],
    Field(discriminator="type"),
]


class WordIR(ContractModel):
    ir_type: Literal["word"]
    ir_version: Literal["1.0"]
    meta: WordMeta
    blocks: list[WordBlock] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tables(self) -> "WordIR":
        for index, block in enumerate(self.blocks):
            if isinstance(block, TableBlock):
                expected_cols = len(block.header)
                if len(block.header) > 12:
                    raise ValueError(f"blocks[{index}].header exceeds 12 columns")
                if any(len(row) != expected_cols for row in block.rows):
                    raise ValueError(f"blocks[{index}].rows must match header column count")
                if block.col_widths is not None and len(block.col_widths) != expected_cols:
                    raise ValueError(f"blocks[{index}].col_widths must match header column count")
        return self
