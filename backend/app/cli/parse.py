from __future__ import annotations

import sys
from pathlib import Path

from app.cli.errors import CodedArgumentParser, emit_cli_failure, io_failure
from app.parsers.docx_parser import parse_docx
from app.parsers.errors import ParseFailure, unsupported_format, write_parse_failure_reports
from app.parsers.md_parser import parse_markdown
from app.parsers.pptx_parser import parse_pptx
from app.parsers.xlsx_parser import parse_xlsx


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Parse input files into DocumentIR.")
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
    raise unsupported_format(path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document_ir = parse_file(args.file)
    except ParseFailure as exc:
        return _emit_parse_failure(exc, args.output)
    except Exception as exc:
        failure = ParseFailure(
            code="E001",
            loc="source",
            message=f"无法读取或解析输入文件 {args.file.name}: {exc}",
            suggestion="确认文件存在、格式与扩展名一致且未损坏，然后重试。",
        )
        return _emit_parse_failure(failure, args.output)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document_ir.model_dump_json(indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        emit_cli_failure(io_failure(code="E001", loc="output", operation="写入 DocumentIR", exc=exc))
        return 1
    print(args.output)
    return 0


def _emit_parse_failure(failure: ParseFailure, output: Path) -> int:
    try:
        json_path, md_path = write_parse_failure_reports(failure, output)
    except Exception as exc:
        emit_cli_failure(io_failure(code=failure.code, loc="output", operation="写入解析失败报告", exc=exc))
        return 1
    print(f"[{failure.code}] {failure.message}", file=sys.stderr)
    print(f"report: {json_path}", file=sys.stderr)
    print(f"report: {md_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
