from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.cli.parse import parse_file
from app.generators.stub import StubGenerator
from app.ir.deck_ir import DeckIR
from app.ir.word_ir import WordIR
from app.lint.placeholder import write_placeholder_report
from app.lint.pptx_lint import check_pptx, write_reports
from app.prompting.builder import build_prompt
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local stub end-to-end document generation demo.")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--target", choices=["word", "deck"], required=True)
    parser.add_argument("--generator", choices=["stub"], default="stub")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "demo")
    parser.add_argument("--lint", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    document_ir = parse_file(args.input_file)
    document_path = output_dir / "document_ir.json"
    document_path.write_text(document_ir.model_dump_json(indent=2) + "\n", encoding="utf-8")

    prompt = build_prompt(kind=args.target, context=document_ir)
    prompt_path = output_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    generator = StubGenerator()
    if args.target == "word":
        word_ir = WordIR.model_validate_json(generator.generate(prompt, target="word_ir"))
        artifact = render_word_ir(word_ir, output_dir / "word.docx")
        report = write_placeholder_report([artifact], output_dir)
    else:
        deck_ir = DeckIR.model_validate_json(generator.generate(prompt, target="deck_ir"))
        artifact = render_deck_ir(deck_ir, output_dir / "deck.pptx")
        if args.lint:
            report_obj = check_pptx(artifact, classification=deck_ir.meta.classification)
            report, _ = write_reports(report_obj, output_dir)
        else:
            report = write_placeholder_report([artifact], output_dir)
    print(f"document_ir: {document_path}")
    print(f"prompt: {prompt_path}")
    print(f"artifact: {artifact}")
    print(f"report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
