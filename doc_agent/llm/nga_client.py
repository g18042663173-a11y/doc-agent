from __future__ import annotations

from typing import Any

from doc_agent.config import Settings
from doc_agent.llm.base import BaseLLMClient


class NGAClient(BaseLLMClient):
    """Internal-network adapter placeholder for GLM-4.7 through NGA."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_json(self, prompt: str) -> dict[str, Any]:
        raise RuntimeError(
            "NGAClient is an internal-network adapter placeholder. "
            "Use LLM_PROVIDER=stub outside the intranet, or implement NGAClient.generate_json "
            "after the real NGA request contract is available."
        )
