from __future__ import annotations

import os
from threading import Event
from typing import Literal, Protocol

from app.generators.stub import StubGenerator


GeneratorTarget = Literal["word_ir", "deck_ir", "analysis"]


class GeneratorCanceled(RuntimeError):
    """Raised when a generator call is aborted by job cancellation."""


class IRTextGenerator(Protocol):
    name: str

    def generate(
        self,
        prompt: str,
        *,
        target: GeneratorTarget,
        cancel_event: Event | None = None,
    ) -> str:
        """Return raw IR text; shell extraction and schema validation happen outside.

        ``cancel_event`` is a cooperative cancellation signal: generators should
        abort promptly (and kill child processes) when it is set.
        """


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
