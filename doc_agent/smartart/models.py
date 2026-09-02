from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SmartArtType(str, Enum):
    PROCESS = "process"
    HIERARCHY = "hierarchy"
    CYCLE = "cycle"
    RELATIONSHIP = "relationship"
    MATRIX = "matrix"
    PYRAMID = "pyramid"
    TIMELINE = "timeline"
    ORG_CHART = "org_chart"


class SmartArtNode(BaseModel):
    id: str
    text: str
    level: int = 0
    children: list["SmartArtNode"] = Field(default_factory=list)
    style: dict[str, Any] | None = None


class SmartArtConfig(BaseModel):
    smartart_type: SmartArtType
    style: str = "modern"
    primary_color: str = "#4472C4"
    secondary_color: str = "#ED7D31"
    background_color: str = "#FFFFFF"
    text_color: str = "#000000"
    font_family: str = "Microsoft YaHei"
    font_size: int = 11


SmartArtNode.model_rebuild()
