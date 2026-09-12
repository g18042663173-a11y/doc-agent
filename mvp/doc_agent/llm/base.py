from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    @abstractmethod
    def generate_json(self, prompt: str) -> dict[str, Any]:
        raise NotImplementedError
