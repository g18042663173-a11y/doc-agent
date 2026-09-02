from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TemplateCategory(str, Enum):
    BUSINESS = "business"
    TECH = "tech"
    EDUCATION = "education"
    CREATIVE = "creative"


class TemplateLayout(BaseModel):
    layout_id: str
    name: str
    description: str
    slide_masters: list[str]
    default_layouts: dict[str, str]
    custom_settings: dict[str, Any] = Field(default_factory=dict)


class TemplateConfig(BaseModel):
    template_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    category: TemplateCategory
    description: str
    thumbnail: str | None = None
    preview: str | None = None
    file_path: str
    layout_config: TemplateLayout
    color_scheme: str | None = None
    font_config: dict[str, Any] = Field(default_factory=dict)
    custom_settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_system: bool = False
