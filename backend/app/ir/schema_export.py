from __future__ import annotations

import json
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.ir.word_ir import WordIR


SCHEMA_MODELS: dict[str, Type[BaseModel]] = {
    "word_ir": WordIR,
    "document_ir": DocumentIR,
    "deck_ir": DeckIR,
}


def normalized_schema(model: Type[BaseModel]) -> dict:
    encoded = json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True)
    return json.loads(encoded)


def export_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in SCHEMA_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(normalized_schema(model), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written
