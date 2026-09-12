from __future__ import annotations

import re
from pathlib import Path

from doc_agent.ir.schemas import DocumentBlock, DocumentIR
from doc_agent.parsers.base import BaseParser
from doc_agent.utils.text_utils import normalize_space


class MarkdownParser(BaseParser):
    def parse(self, path: str | Path) -> DocumentIR:
        source = Path(path)
        lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
        blocks: list[DocumentBlock] = []
        index = 0
        block_id = 1
        title: str | None = None

        while index < len(lines):
            line = lines[index].rstrip()
            stripped = line.strip()
            if not stripped:
                index += 1
                continue

            heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading:
                level = len(heading.group(1))
                text = normalize_space(heading.group(2))
                if title is None and level == 1:
                    title = text
                blocks.append(
                    DocumentBlock(
                        id=f"b{block_id}",
                        type="heading",
                        text=text,
                        level=level,
                    )
                )
                block_id += 1
                index += 1
                continue

            if self._is_bullet(stripped):
                items: list[str] = []
                while index < len(lines) and self._is_bullet(lines[index].strip()):
                    items.append(normalize_space(lines[index].strip()[2:]))
                    index += 1
                blocks.append(DocumentBlock(id=f"b{block_id}", type="bullet_list", items=items))
                block_id += 1
                continue

            if self._is_table_row(stripped):
                rows: list[list[str]] = []
                while index < len(lines) and self._is_table_row(lines[index].strip()):
                    row = lines[index].strip()
                    if not self._is_table_separator(row):
                        rows.append([normalize_space(cell) for cell in row.strip("|").split("|")])
                    index += 1
                if rows:
                    blocks.append(DocumentBlock(id=f"b{block_id}", type="table", rows=rows))
                    block_id += 1
                continue

            paragraph_lines = [stripped]
            index += 1
            while index < len(lines):
                candidate = lines[index].strip()
                if (
                    not candidate
                    or re.match(r"^(#{1,6})\s+(.+)$", candidate)
                    or self._is_bullet(candidate)
                    or self._is_table_row(candidate)
                ):
                    break
                paragraph_lines.append(candidate)
                index += 1
            blocks.append(
                DocumentBlock(
                    id=f"b{block_id}",
                    type="paragraph",
                    text=normalize_space(" ".join(paragraph_lines)),
                )
            )
            block_id += 1

        if title is None:
            for block in blocks:
                if block.text:
                    title = block.text
                    break

        return DocumentIR(
            source_file=str(source),
            source_type="md",
            title=title,
            blocks=blocks,
            meta={"parser": "markdown"},
        )

    @staticmethod
    def _is_bullet(line: str) -> bool:
        return len(line) > 2 and line[:2] in {"- ", "* "}

    @staticmethod
    def _is_table_row(line: str) -> bool:
        return line.startswith("|") and line.endswith("|") and line.count("|") >= 2

    @staticmethod
    def _is_table_separator(line: str) -> bool:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)
