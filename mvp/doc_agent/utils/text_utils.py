from __future__ import annotations

import re


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate_text(text: str | None, limit: int, fallback: str = "") -> str:
    value = normalize_space(text or fallback)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def first_non_empty(values: list[str], fallback: str) -> str:
    for value in values:
        cleaned = normalize_space(value)
        if cleaned:
            return cleaned
    return fallback
