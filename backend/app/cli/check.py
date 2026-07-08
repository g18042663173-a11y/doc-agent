from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.lint.pptx_lint import check_pptx, write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check generated or external document artifacts.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--classification", default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.file.suffix.lower() != ".pptx":
        print("only pptx lint is implemented in this milestone", file=sys.stderr)
        return 1
    report = check_pptx(args.file, classification=args.classification)
    json_path, md_path = write_reports(report, args.output_dir)
    print(json_path)
    print(md_path)
    return 0 if report.summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
