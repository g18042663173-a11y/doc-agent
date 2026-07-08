from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.ir.schema_export import normalized_schema
from app.ir.word_ir import WordIR


Kind = Literal["word", "deck"]

TARGETS = {
    "word": {
        "label": "WordIR v1.0",
        "description": "可编辑 Word 文档",
        "model": WordIR,
    },
    "deck": {
        "label": "DeckIR v1.1",
        "description": "华为风格 PPTX 演示文稿",
        "model": DeckIR,
    },
}


def build_prompt(*, kind: Kind, context: DocumentIR | None, max_context_chars: int = 12000) -> str:
    target = TARGETS[kind]
    schema_json = json.dumps(normalized_schema(target["model"]), ensure_ascii=False, sort_keys=True, indent=2)
    context_json, truncation_notice = _context_json(context, max_context_chars=max_context_chars)
    template = _template_text()
    return template.format(
        target_label=target["label"],
        target_description=target["description"],
        schema_json=schema_json,
        context_json=context_json,
        truncation_notice=truncation_notice,
    )


def _context_json(context: DocumentIR | None, *, max_context_chars: int) -> tuple[str, str]:
    if context is None:
        return "{}", "未提供输入 DocumentIR。"
    encoded = json.dumps(context.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    if len(encoded) <= max_context_chars:
        return encoded, "未截断。"
    truncated = encoded[:max_context_chars].rstrip()
    notice = f"已截断说明: 输入 DocumentIR 超过 {max_context_chars} 字符,已按确定性字符上限截断;请勿编造被截断内容。"
    return truncated, notice


def _template_text() -> str:
    return (Path(__file__).parent / "templates" / "ir_generation.txt").read_text(encoding="utf-8")
