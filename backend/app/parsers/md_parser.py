from __future__ import annotations

import re
from pathlib import Path

from app.ir.document_ir import DocumentIR
from app.parsers.errors import ParseFailure, encoding_failure, parser_error_boundary
from app.parsers.source_metadata import deterministic_parsed_at
from app.parsers.text_limits import TextLimiter


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
UNORDERED_RE = re.compile(r"^(\s*)[-*]\s+(.+?)\s*$")
ORDERED_RE = re.compile(r"^(\s*)\d+[.)]\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
CODE_FENCE_RE = re.compile(r"^\s*```\s*([A-Za-z0-9_+-]*)\s*$")
MAX_MD_FILE_BYTES = 10 * 1024 * 1024


@parser_error_boundary
def parse_markdown(path: Path) -> DocumentIR:
    if path.stat().st_size > MAX_MD_FILE_BYTES:
        raise ParseFailure(
            code="E001",
            loc="source.resource",
            message="Markdown 文件超过 10 MB 资源上限。",
            suggestion="请拆分文件或移除低价值大段内容后重试。",
        )
    text, encoding_warning = _read_markdown_text(path)
    lines = text.splitlines()
    blocks: list[dict] = []
    outline: list[dict] = []
    warnings: list[str] = [encoding_warning] if encoding_warning else []
    limiter = TextLimiter(warnings)
    paragraph_buffer: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph_buffer:
            value = limiter.limit(
                " ".join(paragraph_buffer).strip(),
                loc=f"markdown paragraph {len(blocks) + 1}",
            )
            blocks.append({"type": "paragraph", "text": value})
            paragraph_buffer.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        code_fence = CODE_FENCE_RE.match(line)
        if code_fence:
            flush_paragraph()
            language = code_fence.group(1) or None
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not CODE_FENCE_RE.match(lines[index]):
                code_lines.append(lines[index])
                index += 1
            if index == len(lines):
                warnings.append("markdown code fence is not closed; remaining lines kept as code_block")
            else:
                index += 1
            if code_lines and any(line.strip() for line in code_lines):
                code = limiter.limit("\n".join(code_lines), loc=f"markdown code block {len(blocks) + 1}")
                block: dict[str, str] = {"type": "code_block", "code": code}
                if language:
                    block["language"] = language
                blocks.append(block)
            else:
                warnings.append("markdown empty code fence skipped")
            continue
        if not stripped:
            flush_paragraph()
            index += 1
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            text_value = limiter.limit(
                heading.group(2).strip(),
                loc=f"markdown heading line {index + 1}",
            )
            if not text_value:
                # Whitespace-only heading ("#   " or "#  " pasted from
                # Word) carries no content. Drop the line instead of emitting a
                # heading that violates the IR text min_length and fails the
                # whole file with E001.
                index += 1
                continue
            if level > 4:
                warnings.append(f"heading level {level} capped to 4: {text_value}")
                level = 4
            blocks.append({"type": "heading", "level": level, "text": text_value})
            outline.append({"level": level, "text": text_value})
            index += 1
            continue

        if _is_table_start(lines, index):
            flush_paragraph()
            table, consumed, truncated, malformed_rows = _parse_table(
                lines[index:],
                limiter=limiter,
                start_line=index + 1,
            )
            blocks.append(table)
            if truncated:
                warnings.append("W103: markdown table preview truncated to 20 rows")
            if malformed_rows:
                warnings.append(f"markdown malformed table rows skipped: {malformed_rows}")
            index += consumed
            continue

        unordered = UNORDERED_RE.match(line)
        ordered = ORDERED_RE.match(line)
        if unordered or ordered:
            flush_paragraph()
            list_block, consumed = _parse_list(
                lines[index:],
                ordered=ordered is not None,
                limiter=limiter,
                start_line=index + 1,
            )
            if list_block["items"]:
                blocks.append(list_block)
            index += consumed
            continue

        paragraph_buffer.append(stripped)
        index += 1

    flush_paragraph()

    table_count = sum(1 for block in blocks if block["type"] == "table")
    paragraph_count = sum(1 for block in blocks if block["type"] == "paragraph")
    return DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.2",
            "source": {
                "filename": path.name,
                "format": "md",
                "size_kb": round(path.stat().st_size / 1024, 2),
                "parsed_at": deterministic_parsed_at(path),
            },
            "stats": {
                "headings": len(outline),
                "paragraphs": paragraph_count,
                "tables": table_count,
                "images": 0,
            },
            "warnings": warnings,
            "content": {"blocks": blocks, "outline": outline},
        }
    )


def _is_table_start(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and "|" in lines[index] and TABLE_SEPARATOR_RE.match(lines[index + 1]) is not None


def _read_markdown_text(path: Path) -> tuple[str, str | None]:
    data = path.read_bytes()
    try:
        utf8_text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        utf8_text = None
    if utf8_text is not None and "\x00" not in utf8_text:
        return utf8_text, None
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16"), "markdown decoded as UTF-16"
    no_bom = _decode_utf16_without_bom(data)
    if no_bom is not None:
        return no_bom, "markdown decoded as UTF-16 (no BOM)"
    if utf8_text is not None:
        # UTF-8 "decoded" but produced embedded NULs (a UTF-16 no-BOM file
        # whose bytes are all valid UTF-8) and the UTF-16 pattern check did not
        # trigger; keep the bytes rather than degrading to gb18030.
        return utf8_text, "markdown decoded as UTF-8 with embedded NULs"
    try:
        return data.decode("gb18030"), "markdown decoded using gb18030 fallback"
    except UnicodeDecodeError as exc:
        raise encoding_failure(path) from exc


def _decode_utf16_without_bom(data: bytes) -> str | None:
    """Decode UTF-16 text that carries no BOM.

    UTF-16LE stores ASCII as ``<char>\\x00`` and UTF-16BE as ``\\x00<char>``,
    so the raw bytes show NULs on a regular interval while the decoded text has
    none. Without this, a UTF-16 no-BOM file is silently mis-decoded as UTF-8
    with embedded NULs or as gb18030 garbage. Only reached after a UTF-8 decode
    failure, so a genuine UTF-8 file can never trigger it.
    """
    window = data[:1024]
    if len(window) < 4:
        return None
    sample = min(len(window), 512)
    even_nul = sum(1 for index in range(0, sample, 2) if window[index] == 0)
    odd_nul = sum(1 for index in range(1, sample, 2) if window[index] == 0)
    pairs = sample // 2
    if pairs == 0:
        return None
    preferred = None
    if odd_nul > even_nul and odd_nul >= pairs * 0.4:
        preferred = "utf-16-le"
    elif even_nul > odd_nul and even_nul >= pairs * 0.4:
        preferred = "utf-16-be"
    if preferred is None:
        return None
    try:
        decoded = data.decode(preferred)
    except UnicodeDecodeError:
        return None
    # A real UTF-16 text has no NUL characters in its content; a non-UTF-16
    # file that happened to pass the byte pattern check is rejected here.
    if "\x00" in decoded:
        return None
    return decoded


def _parse_table(
    lines: list[str],
    *,
    limiter: TextLimiter,
    start_line: int,
) -> tuple[dict, int, bool, int]:
    header = _split_table_row(
        lines[0],
        limiter=limiter,
        loc=f"markdown table line {start_line}",
        warn_truncation=True,
    )
    header = [cell or f"Column {index}" for index, cell in enumerate(header, start=1)]
    rows: list[list[str]] = []
    consumed = 2
    truncated = False
    malformed_rows = 0
    while consumed < len(lines) and "|" in lines[consumed] and lines[consumed].strip():
        row_line = lines[consumed]
        if TABLE_SEPARATOR_RE.match(row_line):
            break
        if HEADING_RE.match(row_line) or CODE_FENCE_RE.match(row_line) or UNORDERED_RE.match(row_line) or ORDERED_RE.match(row_line):
            break
        row = _split_table_row(
            row_line,
            limiter=limiter,
            loc=f"markdown table line {start_line + consumed}",
        )
        if len(row) == len(header):
            if len(rows) < 20:
                rows.append(row)
            else:
                truncated = True
        else:
            malformed_rows += 1
        consumed += 1
    return {"type": "table", "header": header, "rows": rows}, consumed, truncated, malformed_rows


MAX_TABLE_COLUMNS = 12


def _split_table_row(line: str, *, limiter: TextLimiter, loc: str, warn_truncation: bool = False) -> list[str]:
    stripped = line.strip().strip("|")
    raw_cells = re.split(r"(?<!\\)\|", stripped)
    cells = [re.sub(r"\\([|\\])", r"\1", cell).strip() for cell in raw_cells]
    if warn_truncation and len(cells) > MAX_TABLE_COLUMNS:
        limiter.warnings.append(f"W103: markdown table {loc} truncated to 12 columns")
    return [
        limiter.limit(cell, loc=f"{loc} cell {index}")
        for index, cell in enumerate(cells[:MAX_TABLE_COLUMNS], start=1)
    ]


def _parse_list(
    lines: list[str],
    *,
    ordered: bool,
    limiter: TextLimiter,
    start_line: int,
) -> tuple[dict, int]:
    pattern = ORDERED_RE if ordered else UNORDERED_RE
    items: list[dict] = []
    consumed = 0
    while consumed < len(lines):
        match = pattern.match(lines[consumed])
        if match is None:
            break
        indent = len(match.group(1).replace("\t", "    "))
        level = 2 if indent >= 2 else 1
        text = limiter.limit(
            match.group(2).strip(),
            loc=f"markdown list item line {start_line + consumed}",
        )
        if not text:
            # Whitespace-only item ("-  ", "1.  " or "-  ") carries no
            # content. Drop the item instead of failing the whole file with a
            # ListItem.text min_length error.
            consumed += 1
            continue
        items.append({"text": text, "level": level})
        consumed += 1
    block_type = "numbered_list" if ordered else "bullet_list"
    return {"type": block_type, "items": items}, consumed
