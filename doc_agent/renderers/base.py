from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseRenderer(ABC):
    @abstractmethod
    def render(self, ir: dict[str, Any], output_path: str | Path) -> Path:
        raise NotImplementedError
