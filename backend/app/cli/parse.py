from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.parsers.docx_parser import parse_docx
from app.parsers.md_parser import parse_markdown
from app.parsers.pptx_parser import parse_pptx
from app.parsers.xlsx_parser import parse_xlsx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse input files into DocumentIR.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def parse_file(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".md":
        return parse_markdown(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".xlsx":
        return parse_xlsx(path)
    if suffix == ".pptx":
        return parse_pptx(path)
    raise ValueError(f"unsupported input format: {suffix}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document_ir = parse_file(args.file)
    except Exception as exc:
        print(f"parse failed: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document_ir.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
