from __future__ import annotations

import sys
from pathlib import Path

from app.cli.errors import CliFailure, CodedArgumentParser, emit_cli_failure, io_failure
from app.assets.errors import AssetError
from app.assets.pipeline import load_asset_manifest
from app.ir.report import format_validation_result
from app.ir.shell import validate_deck_ir_text, validate_word_ir_text
from app.lint.pptx_lint import check_pptx
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir
from app.template.renderer import render_deck_ir_with_template


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Render validated IR into editable documents.")
    parser.add_argument("--type", choices=["word", "deck"], required=True)
    parser.add_argument("ir_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--template", type=Path, help="Optional .pptx template; only valid for deck rendering.")
    parser.add_argument("--asset-manifest", type=Path, help="Optional AssetManifest 1.0; only valid for deck rendering.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    failure_code = "E001" if args.type == "word" else "D001"
    if args.type == "word" and (args.template is not None or args.asset_manifest is not None):
        parser.error("--template and --asset-manifest are only supported with --type deck")
    try:
        raw = args.ir_path.read_text(encoding="utf-8")
    except Exception as exc:
        emit_cli_failure(io_failure(code=failure_code, loc="ir_path", operation="读取 IR", exc=exc))
        return 1

    if args.type == "word":
        result = validate_word_ir_text(raw)
        if not result.ok or result.value is None:
            print(format_validation_result(result), file=sys.stderr)
            return 1
        try:
            output = render_word_ir(result.value, args.output)
        except Exception as exc:
            emit_cli_failure(io_failure(code="E001", loc="output", operation="渲染或保存 DOCX", exc=exc))
            return 1
        print(output)
        return 0

    result = validate_deck_ir_text(raw)
    if not result.ok or result.value is None:
        print(format_validation_result(result), file=sys.stderr)
        return 1
    try:
        asset_registry = load_asset_manifest(args.asset_manifest) if args.asset_manifest is not None else None
        template_result = None
        if args.template is not None:
            template_result = render_deck_ir_with_template(
                result.value, args.template, args.output, asset_registry=asset_registry
            )
            output = template_result.artifact_path
        else:
            output = render_deck_ir(result.value, args.output, asset_registry=asset_registry)
        report = check_pptx(
            output,
            classification=result.value.meta.classification,
            template_profile=template_result.profile if template_result is not None else None,
        )
    except AssetError as exc:
        emit_cli_failure(
            CliFailure(
                code=exc.code,
                loc=exc.loc,
                message=exc.message,
                suggestion="检查 AssetManifest、资产文件哈希和 DeckIR image_ref 后重试。",
            )
        )
        return 1
    except Exception as exc:
        emit_cli_failure(io_failure(code="D001", loc="output", operation="渲染、保存或复检 PPTX", exc=exc))
        return 1
    if not report.summary["pass"]:
        for item in report.items:
            if item.level == "Error":
                slide = "-" if item.slide is None else str(item.slide)
                print(f"[{item.level}] {item.code} slide {slide}: {item.message}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
