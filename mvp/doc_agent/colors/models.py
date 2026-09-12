from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ColorScheme(BaseModel):
    scheme_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    category: str
    description: str | None = None
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str
    text_color: str
    additional_colors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    is_system: bool = False


class ColorRecommendation(BaseModel):
    scheme_id: str
    confidence: float
    reason: str
    scenario_tags: list[str]
