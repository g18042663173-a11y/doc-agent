from __future__ import annotations

from pathlib import Path

from doc_agent.ir.schemas import DocumentIR
from doc_agent.parsers.docx_parser import DocxParser
from doc_agent.parsers.md_parser import MarkdownParser
from doc_agent.parsers.pptx_parser import PptxParser
from doc_agent.parsers.xlsx_parser import XlsxParser


class ParserRouter:
    def parse(self, path: str | Path) -> DocumentIR:
        source = Path(path)
        ext = source.suffix.lower()
        if ext == ".md":
            return MarkdownParser().parse(source)
        if ext == ".docx":
            return DocxParser().parse(source)
        if ext == ".pptx":
            return PptxParser().parse(source)
        if ext in {".xlsx", ".xlsm"}:
            return XlsxParser().parse(source)
        raise ValueError(f"Unsupported file type: {ext}")
