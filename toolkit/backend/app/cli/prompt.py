from __future__ import annotations

from pathlib import Path

from app.cli.errors import CodedArgumentParser, emit_cli_failure, io_failure
from app.ir.document_ir import DocumentIR
from app.prompting.builder import build_prompt


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Build deterministic IR generation prompts.")
    parser.add_argument("--kind", choices=["word", "deck"], required=True)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-context-chars", type=int, default=12000)
    parser.add_argument("--max-output-chars", type=int, default=6000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        context = None
        if args.context is not None:
            context = DocumentIR.model_validate_json(args.context.read_text(encoding="utf-8"))
        prompt = build_prompt(
            kind=args.kind,
            context=context,
            max_context_chars=args.max_context_chars,
            max_output_chars=args.max_output_chars,
        )
    except Exception as exc:
        emit_cli_failure(io_failure(code="E001", loc="context", operation="读取上下文或组装 Prompt", exc=exc))
        return 1
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(prompt, encoding="utf-8")
    except Exception as exc:
        emit_cli_failure(io_failure(code="E001", loc="output", operation="写入 Prompt", exc=exc))
        return 1
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
