from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import sys


@dataclass(frozen=True)
class CliFailure:
    code: str
    loc: str
    message: str
    suggestion: str

    def payload(self) -> dict:
        item = {"level": "Error", **asdict(self)}
        return {
            "summary": {"errors": 1, "warnings": 0, "infos": 0, "pass": False},
            "items": [item],
        }


def emit_cli_failure(failure: CliFailure) -> None:
    print(json.dumps(failure.payload(), ensure_ascii=False), file=sys.stderr)


class CodedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_cli_failure(
            CliFailure(
                code="E001",
                loc="arguments",
                message=f"命令行参数无效: {message}",
                suggestion="运行命令并加 --help 查看完整参数说明。",
            )
        )
        raise SystemExit(2)


def io_failure(*, code: str, loc: str, operation: str, exc: Exception) -> CliFailure:
    return CliFailure(
        code=code,
        loc=loc,
        message=f"{operation}失败: {exc}",
        suggestion="确认路径存在、文件格式正确且当前用户具有读写权限，然后重试。",
    )
