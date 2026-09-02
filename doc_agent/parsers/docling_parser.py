from __future__ import annotations

from pathlib import Path

from doc_agent.ir.schemas import DocumentIR
from doc_agent.parsers.base import BaseParser

try:
    from docling.document_converter import DocumentConverter
except ImportError:  # pragma: no cover - optional dependency
    DocumentConverter = None


class DoclingParser(BaseParser):
    def parse(self, path: str | Path) -> DocumentIR:
        if DocumentConverter is None:
            raise RuntimeError("docling is not installed; use ParserRouter lightweight parsers instead")
        raise NotImplementedError("DoclingParser adapter is reserved for the enhanced parser path")
