from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCANNED_ROOTS = (ROOT / "backend", ROOT / "scripts")
SUBPROCESS_NAMES = {"run", "Popen", "check_output", "check_call"}


def test_all_subprocess_calls_pin_utf8_encoding() -> None:
    missing: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_subprocess_call(node):
                continue
            encoding = _keyword_string(node, "encoding")
            if encoding != "utf-8":
                rel = path.relative_to(ROOT)
                missing.append(f"{rel}:{node.lineno}")

    assert missing == []


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def _is_subprocess_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute):
        return (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr in SUBPROCESS_NAMES
        )
    return False


def _keyword_string(node: ast.Call, name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None
