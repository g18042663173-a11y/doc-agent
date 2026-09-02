from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    BAR = "bar"
    COLUMN = "column"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"
    RADAR = "radar"
    DOUGHNUT = "doughnut"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    BUBBLE = "bubble"
    FUNNEL = "funnel"
    WATERFALL = "waterfall"
    STACKED_BAR = "stacked_bar"
    STACKED_COLUMN = "stacked_column"
    GROUPED_BAR = "grouped_bar"


class ChartData(BaseModel):
    labels: list[str]
    datasets: list[dict[str, Any]]


class ChartConfig(BaseModel):
    chart_type: ChartType
    title: str
    data: ChartData
    style_config: dict[str, Any] = Field(default_factory=dict)
    layout_config: dict[str, Any] = Field(default_factory=dict)


class ChartRecommendation(BaseModel):
    chart_type: ChartType
    confidence: float
    reason: str
    data_requirements: list[str]
    styling_tips: list[str]
