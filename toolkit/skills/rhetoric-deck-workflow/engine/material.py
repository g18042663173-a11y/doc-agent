from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree

from engine.security.office_package import OfficePackageError, preflight_office_package
from engine.shared.chrome import extract_classification
from engine.shared.common import RdwError


TEXT_LIMIT = 2 * 1024 * 1024
XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)


def parse_material(paths: list[Path]) -> dict:
    if not paths:
        raise RdwError("RD-E020", "material", "至少需要一份用户素材。", "使用一个或多个 --material 文件。")
    documents = []
    combined: list[str] = []
    evidence = []
    warnings = []
    for raw_path in paths:
        path = raw_path.resolve()
        if not path.is_file():
            raise RdwError("RD-E020", "material", f"素材不存在: {path}", "检查路径后重试。")
        suffix = path.suffix.casefold()
        document_id = f"d{len(documents) + 1:02d}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        units = []
        if suffix in {".md", ".txt"}:
            text = _read_text(path)
        elif suffix == ".json":
            try:
                value = json.loads(_read_text(path))
            except json.JSONDecodeError as exc:
                raise RdwError("RD-E020", "material", f"素材 JSON 无效: {exc}", "修正 JSON 后重试。") from exc
            text = "\n".join(_json_strings(value))
        elif suffix in {".docx", ".xlsx", ".pptx"}:
            try:
                report = preflight_office_package(path, purpose="source")
            except OfficePackageError as exc:
                raise RdwError("RD-E020", "material", exc.message, "使用安全、未损坏的 Office 素材。") from exc
            if report.office_kind != suffix.lstrip("."):
                raise RdwError("RD-E020", "material", "素材扩展名与 Office 包类型不一致。", "更正文件扩展名。")
            text = _office_text(path, suffix)
        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader
                if path.stat().st_size > 100 * 1024 * 1024:
                    raise ValueError("PDF 超过 100 MB")
                reader = PdfReader(path)
                if reader.is_encrypted:
                    raise ValueError("加密 PDF 不支持")
                if len(reader.pages) > 500:
                    raise ValueError("PDF 超过 500 页")
                for index, page in enumerate(reader.pages, 1):
                    page_text = _normalize(page.extract_text() or "")
                    if not page_text:
                        warnings.append({"document": document_id, "page": index, "code": "RD-W010", "message": "无可提取文字，可能是扫描页，必须单独复核。"})
                    units.append({"id": f"{document_id}:p{index:04d}", "page": index, "text": page_text})
                text = "\n\n".join(unit["text"] for unit in units)
            except Exception as exc:
                raise RdwError("RD-E020", "material.pdf", f"PDF 提取失败: {type(exc).__name__}: {exc}", "提供未加密 PDF；扫描页需提供经核对的文字材料。") from exc
        else:
            raise RdwError("RD-E020", "material", f"不支持素材格式: {suffix}", "使用 md/txt/json/docx/xlsx/pptx/pdf。")
        normalized = _normalize(text)
        if not normalized:
            raise RdwError("RD-E020", "material", f"素材没有可提取文本: {path.name}", "提供含可编辑文本的素材。")
        if len(normalized) > TEXT_LIMIT:
            raise RdwError("RD-E020", "material", "提取文字超过 2 MB。", "拆分材料，避免静默截断。")
        if not units:
            units = [{"id": f"{document_id}:b{index:04d}", "block": index, "text": block}
                     for index, block in enumerate(re.split(r"\n\s*\n", normalized), 1) if block.strip()]
        evidence.extend({**unit, "document_id": document_id, "source_name": path.name, "source_sha256": digest} for unit in units)
        documents.append({"id": document_id, "name": path.name, "kind": suffix.lstrip("."), "sha256": digest, "text": normalized})
        combined.append(normalized)
    raw_text = "\n\n".join(combined)
    lines = [line.strip("#-* \t") for line in raw_text.splitlines() if line.strip("#-* \t")]
    title = lines[0][:100] if lines else "用户材料演示"
    return {
        "format": "rdw_material", "version": "2.0", "title": title,
        "classification": extract_classification(raw_text),
        "documents": documents, "raw_text": raw_text,
        "evidence": evidence, "warnings": warnings,
        "stats": {"characters": len(raw_text), "lines": len(lines), "numbers": len(re.findall(r"\d+(?:\.\d+)?%?", raw_text))},
    }


def _read_text(path: Path) -> str:
    try:
        if path.stat().st_size > TEXT_LIMIT:
            raise RdwError("RD-E020", "material", "文本素材超过 2 MB 上限。", "拆分或精简素材。")
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise RdwError("RD-E020", "material", "文本素材必须使用 UTF-8。", "转换编码后重试。") from exc


def _office_text(path: Path, suffix: str) -> str:
    with ZipFile(path) as package:
        names = set(package.namelist())
        if suffix == ".docx":
            targets = [name for name in names if name == "word/document.xml" or name.startswith("word/header") or name.startswith("word/footer")]
        elif suffix == ".pptx":
            targets = [name for name in names if re.fullmatch(r"ppt/(slides|notesSlides)/[^/]+\.xml", name)]
        else:
            targets = [name for name in names if name == "xl/sharedStrings.xml" or re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
        fragments: list[str] = []
        for name in sorted(targets):
            root = etree.fromstring(package.read(name), parser=XML_PARSER)
            local_names = {"t"} if suffix in {".docx", ".pptx"} else {"t", "v"}
            for element in root.iter():
                if etree.QName(element).localname in local_names and element.text:
                    fragments.append(element.text)
        return "\n".join(fragments)


def _json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _json_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _json_strings(child)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield str(value)


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()
