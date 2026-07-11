from __future__ import annotations

import os
from typing import Literal


class NgaGenerator:
    name = "nga"

    def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout_seconds: int = 60) -> None:
        self.base_url = base_url or os.environ.get("NGA_BASE_URL")
        self.token = token or os.environ.get("NGA_TOKEN")
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str, *, target: Literal["word_ir", "deck_ir", "analysis"]) -> str:
        if not self.base_url or not self.token:
            raise RuntimeError("NGA_BASE_URL and NGA_TOKEN must be set for NgaGenerator")
        raise NotImplementedError("NgaGenerator protocol is implemented inside the intranet integration point")
