from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


def non_empty(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class ListItem(ContractModel):
    text: str = Field(min_length=1)
    level: Literal[1, 2] = 1

    _text_not_blank = field_validator("text")(non_empty)


class HeadingBlock(ContractModel):
    type: Literal["heading"]
    level: int = Field(ge=1, le=4)
    text: str = Field(min_length=1)

    _text_not_blank = field_validator("text")(non_empty)


class ParagraphBlock(ContractModel):
    type: Literal["paragraph"]
    text: str
    style: Literal["normal", "quote", "note"] = "normal"


class BulletListBlock(ContractModel):
    type: Literal["bullet_list"]
    items: list[ListItem] = Field(min_length=1)


class NumberedListBlock(ContractModel):
    type: Literal["numbered_list"]
    items: list[ListItem] = Field(min_length=1)


class TableBlock(ContractModel):
    type: Literal["table"]
    header: list[str] = Field(min_length=1, max_length=12)
    rows: list[list[str]] = Field(max_length=100)
    caption: str | None = None
    col_widths: list[float] | None = Field(
        default=None,
        description="各列的正数相对宽度权重；渲染时归一化到可用表宽，不是英寸或其它绝对单位。",
    )

    @field_validator("header")
    @classmethod
    def header_cells_not_blank(_cls, value: list[str]) -> list[str]:
        if any(not str(cell).strip() for cell in value):
            raise ValueError("table header cells must not be blank")
        return value

    @field_validator("rows")
    @classmethod
    def row_cells_as_strings(_cls, value: list[list[str]]) -> list[list[str]]:
        return [[str(cell) for cell in row] for row in value]

    @field_validator("col_widths")
    @classmethod
    def col_widths_positive(_cls, value: list[float] | None) -> list[float] | None:
        if value is not None and any(width <= 0 for width in value):
            raise ValueError("col_widths must be positive")
        return value


class ImagePlaceholderBlock(ContractModel):
    type: Literal["image_placeholder"]
    ref: str | None = None
    caption: str | None = None


class PageBreakBlock(ContractModel):
    type: Literal["page_break"]
