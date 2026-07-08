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
from app.lint.pptx_lint import check_pptx, write_reports
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


def main() -> int:
    export_schemas(ROOT / "backend" / "schemas")

    generator = StubGenerator()
    word = WordIR.model_validate_json(generator.generate("", target="word_ir"))
    deck = DeckIR.model_validate_json(generator.generate("", target="deck_ir"))

    output_dir = ROOT / "output"
    word_path = render_word_ir(word, output_dir / "c0_word.docx")
    deck_path = render_deck_ir(deck, output_dir / "c0_deck.pptx")
    report = check_pptx(deck_path, classification=deck.meta.classification)
    report_json, _ = write_reports(report, output_dir)

    print("C0 verify passed")
    print(f"schemas: {ROOT / 'backend' / 'schemas'}")
    print(f"artifacts: {word_path.name}, {deck_path.name}")
    print(f"report: {report_json.name}")
    return 0 if report.summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
