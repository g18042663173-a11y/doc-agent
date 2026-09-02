from __future__ import annotations

from pathlib import Path


def ensure_parent(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def read_text_limited(path: str | Path, max_chars: int) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return text[:max_chars]
