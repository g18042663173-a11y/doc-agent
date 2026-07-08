from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, field_validator, model_validator

from app.ir.common import ContractModel, ListItem, non_empty


class DeckMeta(ContractModel):
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str | None = None
    date: str | None = None
    classification: str = "HUAWEI CONFIDENTIAL"
    theme: str = "hw_v1"

    _title_not_blank = field_validator("title")(non_empty)


class CoverSlide(ContractModel):
    layout: Literal["cover"]
    title: str = Field(min_length=1)
    subtitle: str | None = None
    presenter: str | None = None
    date: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


class AgendaSlide(ContractModel):
    layout: Literal["agenda"]
    items: list[str] = Field(min_length=2, max_length=8)


class SectionSlide(ContractModel):
    layout: Literal["section"]
    index: int = Field(ge=1)
    title: str = Field(min_length=1)
    subtitle: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


class TitleBulletsSlide(ContractModel):
    layout: Literal["title_bullets"]
    title: str = Field(min_length=1)
    bullets: list[ListItem] = Field(min_length=1, max_length=7)

    _title_not_blank = field_validator("title")(non_empty)


class ColumnContent(ContractModel):
    heading: str | None = None
    bullets: list[ListItem] = Field(default_factory=list, max_length=7)
    text: str | None = None


class TwoColumnSlide(ContractModel):
    layout: Literal["two_column"]
    title: str = Field(min_length=1)
    left: ColumnContent
    right: ColumnContent

    _title_not_blank = field_validator("title")(non_empty)


class DeckTable(ContractModel):
    header: list[str] = Field(min_length=1, max_length=8)
    rows: list[list[str]] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_rows(self) -> "DeckTable":
        expected_cols = len(self.header)
        if any(len(row) != expected_cols for row in self.rows):
            raise ValueError("rows must match header column count")
        return self


class TableSlide(ContractModel):
    layout: Literal["table"]
    title: str = Field(min_length=1)
    table: DeckTable

    _title_not_blank = field_validator("title")(non_empty)


class Card(ContractModel):
    title: str = Field(min_length=1)
    desc: str = Field(min_length=1)
    tag: str | None = None


class CardsSlide(ContractModel):
    layout: Literal["cards"]
    title: str = Field(min_length=1)
    cards: list[Card] = Field(min_length=2, max_length=4)

    _title_not_blank = field_validator("title")(non_empty)


class ChartSeries(ContractModel):
    name: str
    values: list[float]


class ChartSpec(ContractModel):
    kind: Literal["bar", "line", "pie"]
    categories: list[str] = Field(min_length=1)
    series: list[ChartSeries] = Field(min_length=1)


class ChartSlide(ContractModel):
    layout: Literal["chart"]
    title: str = Field(min_length=1)
    chart: ChartSpec

    _title_not_blank = field_validator("title")(non_empty)


class ImageSlide(ContractModel):
    layout: Literal["image"]
    title: str = Field(min_length=1)
    image_ref: str | None = None
    placeholder: str | None = None
    caption: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


class ConclusionSlide(ContractModel):
    layout: Literal["conclusion"]
    title: str = Field(min_length=1)
    bullets: list[str] = Field(default_factory=list, max_length=5)
    cta: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


DeckSlide = Annotated[
    Union[
        CoverSlide,
        AgendaSlide,
        SectionSlide,
        TitleBulletsSlide,
        TwoColumnSlide,
        TableSlide,
        CardsSlide,
        ChartSlide,
        ImageSlide,
        ConclusionSlide,
    ],
    Field(discriminator="layout"),
]


class DeckIR(ContractModel):
    ir_type: Literal["deck"]
    ir_version: Literal["1.1"]
    meta: DeckMeta
    slides: list[DeckSlide] = Field(min_length=1, max_length=30)
