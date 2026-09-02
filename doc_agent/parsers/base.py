from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from doc_agent.ir.schemas import DocumentIR


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: str | Path) -> DocumentIR:
        raise NotImplementedError
