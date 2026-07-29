from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
import json
from pathlib import Path
from typing import Callable, TypeVar

from app.ir.errors import ValidationItem


T = TypeVar("T")


@dataclass
class ParseFailure(Exception):
    code: str
    message: str
    loc: str = "source"
    suggestion: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def as_item(self) -> ValidationItem:
        return ValidationItem(
            code=self.code,
            level="Error",
            loc=self.loc,
            message=self.message,
            suggestion=self.suggestion,
        )


def parser_error_boundary(parser: Callable[[Path], T]) -> Callable[[Path], T]:
    @wraps(parser)
    def wrapped(path: Path) -> T:
        try:
            return parser(path)
        except ParseFailure:
            raise
        except Exception as exc:
            raise _read_failure(path, exc) from exc

    return wrapped


def unsupported_format(path: Path) -> ParseFailure:
    suffix = path.suffix.lower() or "<none>"
    return ParseFailure(
        code="E003",
        loc="source.format",
        message=f"不支持的输入文件格式: {suffix}",
        suggestion="仅支持 .md、.docx、.xlsx、.pptx。",
    )


def encoding_failure(path: Path) -> ParseFailure:
    return ParseFailure(
        code="E001",
        loc="source.encoding",
        message=f"无法识别文本文件编码: {path.name}",
        suggestion="将文件转换为 UTF-8，或确认其为完整的 GBK/GB18030 文本后重试。",
    )


def write_parse_failure_reports(failure: ParseFailure, output_path: Path) -> tuple[Path, Path]:
    item = failure.as_item()
    payload = {
        "summary": {"errors": 1, "warnings": 0, "infos": 0, "pass": False},
        "items": [
            {
                "code": item.code,
                "level": item.level,
                "loc": item.loc,
                "message": item.message,
                "suggestion": item.suggestion,
            }
        ],
    }
    json_path = output_path.with_suffix(".report.json")
    md_path = output_path.with_suffix(".report.md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# 输入解析报告",
                "",
                "- Errors: 1",
                "- Warnings: 0",
                "- Infos: 0",
                "- Pass: False",
                "",
                f"## {item.code} ({item.level})",
                f"- Location: {item.loc}",
                f"- Message: {item.message}",
                f"- Suggestion: {item.suggestion or ''}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def _read_failure(path: Path, exc: Exception) -> ParseFailure:
    return ParseFailure(
        code="E001",
        loc="source",
        message=f"无法读取或解析输入文件 {path.name}: {exc}",
        suggestion="确认文件存在、格式与扩展名一致且未损坏，然后重试。",
    )
