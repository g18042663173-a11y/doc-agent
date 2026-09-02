from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from doc_agent.config import Settings, get_settings
from doc_agent.ir.schemas import DocumentIR, WordIR, to_pretty_json
from doc_agent.llm import BaseLLMClient, get_llm_client
from doc_agent.utils.json_utils import render_template


PROMPT_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"


class WordPlanner:
    def __init__(self, llm_client: BaseLLMClient | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm_client = llm_client or get_llm_client(self.settings)

    def plan(self, document_ir: DocumentIR) -> WordIR:
        prompt = render_template(
            self._load_prompt("make_word_ir.md"),
            {"document_ir_json": document_ir.model_dump_json(ensure_ascii=False)},
        )
        raw = self.llm_client.generate_json(prompt)
        return self._validate_or_repair(raw)

    def _validate_or_repair(self, raw: dict[str, Any]) -> WordIR:
        try:
            return WordIR.model_validate(raw)
        except ValidationError as first_error:
            bad_json = to_pretty_json(raw)
            last_error: Exception = first_error
            for _ in range(self.settings.max_repair_attempts):
                repair_prompt = render_template(
                    self._load_prompt("repair_json.md"),
                    {"errors": str(last_error), "bad_json": bad_json},
                )
                raw = self.llm_client.generate_json(repair_prompt)
                try:
                    return WordIR.model_validate(raw)
                except ValidationError as exc:
                    last_error = exc
                    bad_json = to_pretty_json(raw)
            raise ValueError(f"WordIR validation failed after repair attempts: {last_error}") from last_error

    @staticmethod
    def _load_prompt(name: str) -> str:
        return (PROMPT_DIR / name).read_text(encoding="utf-8")
