from __future__ import annotations

from pathlib import Path

from app.assets.errors import AssetError
from app.assets.pipeline import normalize_assets
from app.cli.errors import CliFailure, CodedArgumentParser, emit_cli_failure


def build_parser() -> CodedArgumentParser:
    parser = CodedArgumentParser(description="Normalize local image assets and write AssetManifest 1.0.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        normalize_assets(args.files, args.output_dir, source_type="upload")
    except AssetError as exc:
        emit_cli_failure(
            CliFailure(
                code=exc.code,
                loc=exc.loc,
                message=exc.message,
                suggestion="确认图片格式、大小与来源路径符合资产安全限制后重试。",
            )
        )
        return 1
    print(args.output_dir / "asset_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
