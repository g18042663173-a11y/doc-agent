from __future__ import annotations

from typing import Any

from doc_agent.config import Settings, normalize_llm_provider
from doc_agent.llm.base import BaseLLMClient
from doc_agent.utils.json_utils import extract_json_from_text


class OpenAICompatibleLLMClient(BaseLLMClient):
    def __init__(self, settings: Settings) -> None:
        if normalize_llm_provider(settings.llm_provider) != "openai_compatible":
            raise RuntimeError("OpenAICompatibleLLMClient is only enabled for legacy LLM_PROVIDER=openai_compatible")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is required for openai_compatible mode") from exc

        self.settings = settings
        self.client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )

    def generate_json(self, prompt: str) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": "You output strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover - external call
            raise RuntimeError(f"OpenAI-compatible LLM request failed: {exc}") from exc

        content = response.choices[0].message.content or ""
        try:
            return extract_json_from_text(content)
        except ValueError as exc:
            raise RuntimeError("OpenAI-compatible LLM response did not contain valid JSON") from exc
