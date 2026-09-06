from __future__ import annotations

import math
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


class CodeBlock(ContractModel):
    type: Literal["code_block"]
    code: str = Field(min_length=1, description="保留原始换行和行首缩进的源码文本，不得按普通段落合并或 strip。")
    language: str | None = Field(default=None, description="可选语言标记，例如 c、cpp 或 python；仅供阅读与解析追溯。")

    @field_validator("code")
    @classmethod
    def code_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code must not be blank")
        return value

    @field_validator("language")
    @classmethod
    def language_not_blank(cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class BulletListBlock(ContractModel):
    type: Literal["bullet_list"]
    items: list[ListItem] = Field(min_length=1)


class NumberedListBlock(ContractModel):
    type: Literal["numbered_list"]
    items: list[ListItem] = Field(min_length=1)


class TableBlock(ContractModel):
    type: Literal["table"]
    header: list[str] = Field(min_length=1, max_length=12)
    rows: list[list[str]] = Field(min_length=1, max_length=100)
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
        if value is not None and any(not math.isfinite(width) or width <= 0 for width in value):
            raise ValueError("col_widths must be finite and positive")
        return value


class ImagePlaceholderBlock(ContractModel):
    type: Literal["image_placeholder"]
    ref: str | None = None
    caption: str | None = None


class PageBreakBlock(ContractModel):
    type: Literal["page_break"]
