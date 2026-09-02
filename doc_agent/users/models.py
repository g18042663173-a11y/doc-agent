from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from doc_agent.config import normalize_llm_provider, normalize_ppt_renderer


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserConfig(BaseModel):
    user_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_name: str
    nga_endpoint: str
    auth_token: str
    llm_provider: str = "nga"
    llm_model: str = "glm-4.7"
    ppt_renderer: str = "stub"
    default_template: str | None = None
    default_color_scheme: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    last_used: datetime = Field(default_factory=utc_now)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_provider_aliases(self) -> "UserConfig":
        self.llm_provider = normalize_llm_provider(self.llm_provider)
        self.ppt_renderer = normalize_ppt_renderer(self.ppt_renderer)
        return self
