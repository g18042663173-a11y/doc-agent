from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class ValidationItem:
    code: str
    level: str
    loc: str
    message: str
    suggestion: str | None = None


@dataclass(frozen=True)
class ValidationResult(Generic[T]):
    value: T | None
    errors: list[ValidationItem] = field(default_factory=list)
    warnings: list[ValidationItem] = field(default_factory=list)
    infos: list[ValidationItem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.value is not None and not self.errors
