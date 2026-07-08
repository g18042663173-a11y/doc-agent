from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.generators.stub import StubGenerator
from app.ir.deck_ir import DeckIR
from app.ir.schema_export import export_schemas
from app.ir.word_ir import WordIR
from app.lint.placeholder import write_placeholder_report
from app.rendering.placeholder import render_placeholder
from app.rendering.docx_renderer import render_word_ir


def main() -> int:
    export_schemas(ROOT / "backend" / "schemas")

    generator = StubGenerator()
    word = WordIR.model_validate_json(generator.generate("", target="word_ir"))
    deck = DeckIR.model_validate_json(generator.generate("", target="deck_ir"))

    output_dir = ROOT / "output"
    rendered = [
        render_word_ir(word, output_dir / "c0_word.docx"),
        render_placeholder(deck, output_dir),
    ]
    report = write_placeholder_report(rendered, output_dir)

    print("C0 verify passed")
    print(f"schemas: {ROOT / 'backend' / 'schemas'}")
    print(f"placeholders: {', '.join(path.name for path in rendered)}")
    print(f"report: {report.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
