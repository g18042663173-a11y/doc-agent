from __future__ import annotations

from pathlib import Path

from doc_agent.ir.schemas import DocumentIR
from doc_agent.parsers.base import BaseParser
from doc_agent.parsers.md_parser import MarkdownParser

try:
    from markitdown import MarkItDown
except ImportError:  # pragma: no cover - optional dependency
    MarkItDown = None


class MarkItDownParser(BaseParser):
    def parse(self, path: str | Path) -> DocumentIR:
        if MarkItDown is None:
            raise RuntimeError("markitdown is not installed; use ParserRouter lightweight parsers instead")
        source = Path(path)
        result = MarkItDown().convert(str(source))
        temp_md = source.with_suffix(source.suffix + ".markitdown.md")
        temp_md.write_text(result.text_content, encoding="utf-8")
        ir = MarkdownParser().parse(temp_md)
        ir.source_file = str(source)
        ir.meta["parser"] = "markitdown"
        try:
            temp_md.unlink()
        except OSError:
            pass
        return ir
