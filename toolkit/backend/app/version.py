from __future__ import annotations

from pathlib import Path
import re


_VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"


def _read_product_version() -> str:
    version = _VERSION_FILE.read_text(encoding="utf-8").strip()
    if not _VERSION_PATTERN.fullmatch(version):
        raise RuntimeError(f"invalid product version in {_VERSION_FILE}")
    return version


APP_VERSION = _read_product_version()
