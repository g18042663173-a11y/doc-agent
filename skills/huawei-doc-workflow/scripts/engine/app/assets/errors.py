from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetError(Exception):
    code: str
    loc: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} {self.loc}: {self.message}"
