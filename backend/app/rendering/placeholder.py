from __future__ import annotations

from pathlib import Path

from app.ir.deck_ir import DeckIR
from app.ir.word_ir import WordIR


def render_placeholder(ir: WordIR | DeckIR, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "word" if isinstance(ir, WordIR) else "deck"
    path = output_dir / f"c0_{suffix}.placeholder.json"
    path.write_text(ir.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
