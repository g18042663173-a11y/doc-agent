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


WORD_CLASSIFICATIONS = frozenset({"公开", "内部公开", "秘密", "机密", "绝密", "PUBLIC", "HUAWEI CONFIDENTIAL"})


class ControlRecord(ContractModel):
    name: str | None = Field(default=None, description="拟制、审核或批准人员姓名；为空时保留空白占位单元格。")
    date: str | None = Field(default=None, description="对应人员的日期；为空时保留空白占位单元格。")

    @field_validator("name", "date")
    @classmethod
    def optional_text_not_blank(cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class DocumentControl(ContractModel):
    product_name: str = Field(min_length=1, description="产品名称，渲染在文档控制信息表第一行。")
    document_name: str = Field(min_length=1, description="文档名称，通常与 meta.title 一致但可按正式名称单独填写。")
    classification: str | None = Field(
        default=None,
        description="文档头展示的密级；省略时使用 meta.classification，填写时必须与其一致。",
    )
    version: str = Field(min_length=1, description="文档版本号，例如 V1.0。")
    prepared: ControlRecord = Field(default_factory=ControlRecord, description="拟制人员与日期。")
    reviewed: ControlRecord = Field(default_factory=ControlRecord, description="审核人员与日期。")
    approved: ControlRecord = Field(default_factory=ControlRecord, description="批准人员与日期。")

    _product_name_not_blank = field_validator("product_name")(non_empty)
    _document_name_not_blank = field_validator("document_name")(non_empty)
    _version_not_blank = field_validator("version")(non_empty)


class WordMeta(ContractModel):
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str | None = None
    classification: str = Field(default="内部公开", description="页脚和文档头共用的受控密级文案。")
    header_text: str | None = None
    footer_text: str | None = None
    document_control: DocumentControl | None = Field(
        default=None,
        description="可选华为详设文档控制信息；存在时在正文前渲染产品/版本表和拟制审核批准表。",
    )

    _title_not_blank = field_validator("title")(non_empty)

    @field_validator("classification")
    @classmethod
    def classification_is_allowed(cls, value: str) -> str:
        value = non_empty(value)
        if value not in WORD_CLASSIFICATIONS:
            allowed = "、".join(sorted(WORD_CLASSIFICATIONS))
            raise ValueError(f"classification must be one of: {allowed}")
        return value


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


def migrate_word_payload(value: Any, *, target_version: str = "1.2") -> tuple[Any, str | None]:
    if not isinstance(value, dict) or value.get("ir_version") not in {"1.0", "1.1"} or target_version != "1.2":
        return value, None
    migrated = copy.deepcopy(value)
    source_version = migrated["ir_version"]
    migrated["ir_version"] = "1.2"
    return migrated, source_version


class WordIR(ContractModel):
    ir_type: Literal["word"]
    ir_version: Literal["1.2"]
    meta: WordMeta
    blocks: list[WordBlock] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_payload(cls, value: Any) -> Any:
        migrated, _source_version = migrate_word_payload(value)
        return migrated

    @model_validator(mode="after")
    def validate_tables(self) -> "WordIR":
        control = self.meta.document_control
        if control is not None and control.classification is not None and control.classification != self.meta.classification:
            raise ValueError("meta.document_control.classification must match meta.classification")
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
