from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from doc_agent.config import Settings, normalize_llm_provider
from doc_agent.llm.base import BaseLLMClient
from doc_agent.utils.json_utils import extract_json_from_text


class LocalRelayLLMClient(BaseLLMClient):
    """HTTP adapter for a local model relay used by the main agent workflow."""

    def __init__(self, settings: Settings) -> None:
        if normalize_llm_provider(settings.llm_provider) != "local_relay":
            raise RuntimeError("LocalRelayLLMClient is only enabled for LLM_PROVIDER=local_relay")
        self.settings = settings
        self.endpoint = self._resolve_endpoint(settings.llm_base_url)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.settings.llm_model,
            "prompt": prompt,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.settings.llm_api_key and self.settings.llm_api_key != "EMPTY":
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        req = request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.llm_timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Local relay LLM request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Local relay LLM request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError("Local relay LLM request timed out") from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Local relay LLM response was not JSON") from exc
        return self._extract_json(data)

    @staticmethod
    def _resolve_endpoint(base_url: str) -> str:
        base = (base_url or "").rstrip("/")
        if not base:
            return "http://127.0.0.1:8765/v1/generate_json"
        if base.endswith("/generate_json") or base.endswith("/chat/completions"):
            return base
        return f"{base}/generate_json"

    @classmethod
    def _extract_json(cls, data: dict[str, Any]) -> dict[str, Any]:
        for key in ("json", "result", "data", "output"):
            value = data.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                return cls._extract_text_json(value)

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return cls._extract_text_json(message["content"])
                if isinstance(first.get("text"), str):
                    return cls._extract_text_json(first["text"])

        for key in ("content", "text", "response", "output_text"):
            value = data.get(key)
            if isinstance(value, str):
                return cls._extract_text_json(value)

        if any(key in data for key in ("deck_title", "slides", "title", "blocks")):
            return data

        raise RuntimeError("Local relay LLM response did not contain a JSON object payload")

    @staticmethod
    def _extract_text_json(text: str) -> dict[str, Any]:
        try:
            return extract_json_from_text(text)
        except ValueError as exc:
            raise RuntimeError("Local relay LLM text payload did not contain valid JSON") from exc
