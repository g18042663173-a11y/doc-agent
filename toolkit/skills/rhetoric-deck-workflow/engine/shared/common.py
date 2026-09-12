from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from jsonschema import Draft202012Validator

from engine.shared.cli_errors import CliFailure, emit_cli_failure


SKILL_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RdwError(Exception):
    code: str
    loc: str
    message: str
    suggestion: str

    def __str__(self) -> str:
        return self.message


def emit_error(error: RdwError) -> None:
    emit_cli_failure(CliFailure(error.code, error.loc, error.message, error.suggestion))


def success(command: str, **payload: Any) -> dict[str, Any]:
    return {"ok": True, "command": command, **payload}


def read_json(path: Path, *, code: str, loc: str) -> Any:
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            raise RdwError(code, loc, "JSON 文件超过 10 MB 安全上限。", "缩小文件后重试。")
        return json.loads(path.read_text(encoding="utf-8"))
    except RdwError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RdwError(code, loc, f"无法读取有效 UTF-8 JSON: {exc}", "检查路径与 JSON 语法后重试。") from exc


def write_json(path: Path, value: Any, *, overwrite: bool = True) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", overwrite=overwrite)


def write_text(path: Path, value: str, *, overwrite: bool = True) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise RdwError("RD-E050", str(path), "目标文件已存在。", "改用新的输出目录或显式清理旧产物。")
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def validate(instance: Any, schema: dict, *, code: str, loc: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    error = errors[0]
    suffix = ".".join(str(part) for part in error.absolute_path)
    location = f"{loc}.{suffix}" if suffix else loc
    raise RdwError(code, location, error.message, "按错误字段与 Skill Schema 修正，不要绕过校验。")


def load_schema(name: str) -> dict:
    return read_json(SKILL_ROOT / "schemas" / name, code="RD-E999", loc=f"schemas/{name}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise RdwError("RD-E999", str(path), "拒绝操作工作目录之外的路径。", "使用当前工作目录内的明确路径。") from exc
    return resolved


def flatten_strings(value: Any, *, path: tuple[str | int, ...] = ()): 
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from flatten_strings(child, path=(*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from flatten_strings(child, path=(*path, index))


def jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)
