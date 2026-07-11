from __future__ import annotations

from dataclasses import dataclass, field


MAX_OFFICE_TEXT_CHARS = 2000


@dataclass
class TextLimiter:
    warnings: list[str]
    max_chars: int = MAX_OFFICE_TEXT_CHARS
    _reported_locations: set[str] = field(default_factory=set)

    def limit(self, value: str, *, loc: str) -> str:
        if len(value) <= self.max_chars:
            return value
        if loc not in self._reported_locations:
            self.warnings.append(
                f"W103: {loc} text truncated from {len(value)} to {self.max_chars} characters"
            )
            self._reported_locations.add(loc)
        return value[: self.max_chars]
