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
    """Resolve the workbench's default generator at startup.

    Priority: explicit ``IR_GENERATOR`` override > configured AI credentials
    (``OPENAI_API_KEY`` enables the opencode-go codex adapter) > stub. A machine
    with credentials therefore defaults to real AI generation; an unconfigured
    machine still works offline via the deterministic stub. The per-job
    GeneratorManager may later switch to an explicitly enabled NGA config.
    """

    explicit = os.environ.get("IR_GENERATOR")
    if explicit:
        return generator_from_name(explicit)
    if os.environ.get("OPENAI_API_KEY"):
        return generator_from_name("codex")
    return generator_from_name("stub")
