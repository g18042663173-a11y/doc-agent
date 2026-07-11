from __future__ import annotations

import os
from typing import Literal, Protocol

from app.generators.stub import StubGenerator


GeneratorTarget = Literal["word_ir", "deck_ir", "analysis"]


class IRTextGenerator(Protocol):
    name: str

    def generate(self, prompt: str, *, target: GeneratorTarget) -> str:
        """Return raw IR text; shell extraction and schema validation happen outside."""


def generator_from_name(name: str) -> IRTextGenerator:
    normalized = name.strip().lower()
    if normalized == "stub":
        return StubGenerator()
    if normalized == "nga":
        from app.generators.nga import NgaGenerator

        return NgaGenerator()
    if normalized == "codex":
        from app.generators.codex import CodexGenerator

        return CodexGenerator()
    raise ValueError(f"unsupported IR generator: {name}")


def default_ir_generator() -> IRTextGenerator:
    """Resolve an explicitly configured adapter while preserving stub as the unset default."""

    return generator_from_name(os.environ.get("IR_GENERATOR", "stub"))
