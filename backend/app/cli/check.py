from __future__ import annotations

from pathlib import Path

from app.cli.errors import CodedArgumentParser, emit_cli_failure, io_failure
from app.lint.docx_lint import DocxLintItem, DocxLintReport, check_docx, write_docx_reports
from app.lint.pptx_lint import PptxLintItem, PptxLintReport, check_pptx, write_reports


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Check generated or external document artifacts.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--classification", default=None)
    parser.add_argument("--theme", default="hw_v1", help="PPTX 主题名（hw_v1 / hw-report / hw-proposal / hw-academic）")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    suffix = args.file.suffix.lower()
    try:
        if suffix == ".pptx":
            try:
                report = check_pptx(args.file, classification=args.classification, theme_name=args.theme)
            except Exception as exc:
                report = PptxLintReport(
                    [
                        PptxLintItem(
                            code="E001",
                            level="Error",
                            slide=None,
                            message=f"PPTX 无法打开: {exc}",
                            suggestion="确认文件存在、是有效 .pptx 且扩展名与内容一致。",
                        )
                    ]
                )
            json_path, md_path = write_reports(report, args.output_dir)
        elif suffix == ".docx":
            report = check_docx(args.file, classification=args.classification)
            json_path, md_path = write_docx_reports(report, args.output_dir)
        else:
            report = DocxLintReport(
                [
                    DocxLintItem(
                        code="E003",
                        level="Error",
                        message=f"不支持的复检格式: {suffix or '<none>'}",
                        suggestion="仅支持 .pptx 或 .docx。",
                    )
                ]
            )
            json_path, md_path = write_docx_reports(report, args.output_dir)
    except Exception as exc:
        emit_cli_failure(io_failure(code="E001", loc="output_dir", operation="复检或写入报告", exc=exc))
        return 1
    print(json_path)
    print(md_path)
    return 0 if report.summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
