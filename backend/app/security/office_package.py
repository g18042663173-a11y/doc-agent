from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import posixpath
import re
from typing import Literal
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, ConfigDict


OfficePurpose = Literal["source", "template", "output"]
OfficeKind = Literal["docx", "xlsx", "pptx"]

MAX_SOURCE_COMPRESSED_BYTES = 100 * 1024 * 1024
MAX_TEMPLATE_COMPRESSED_BYTES = 50 * 1024 * 1024
MAX_OUTPUT_COMPRESSED_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_PACKAGE_PARTS = 10_000
MAX_PART_BYTES = 100 * 1024 * 1024
MIN_RATIO_GUARD_BYTES = 1 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PACKAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/package"

REQUIRED_PARTS: dict[OfficeKind, frozenset[str]] = {
    "docx": frozenset({"[Content_Types].xml", "_rels/.rels", "word/document.xml"}),
    "xlsx": frozenset({"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"}),
    "pptx": frozenset({"[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml"}),
}


class OfficePackageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_version: Literal["1.0"] = "1.0"
    purpose: OfficePurpose
    office_kind: OfficeKind
    compressed_bytes: int
    uncompressed_bytes: int
    part_count: int
    relationship_count: int
    active_parts: list[str]
    external_relationships: list[str]
    warnings: list[str]
    safe: bool = True


@dataclass
class OfficePackageError(Exception):
    reason: str
    loc: str
    message: str
    context: str | None = None

    def __str__(self) -> str:
        return self.message


def preflight_office_package(path: Path, *, purpose: OfficePurpose = "source") -> OfficePackageReport:
    path = Path(path)
    loc = "template_file" if purpose == "template" else "output" if purpose == "output" else "input_file"
    if not path.is_file():
        raise OfficePackageError("missing_file", loc, "Office 文件不存在或不可读取。")
    compressed_bytes = path.stat().st_size
    compressed_limit = {
        "source": MAX_SOURCE_COMPRESSED_BYTES,
        "template": MAX_TEMPLATE_COMPRESSED_BYTES,
        "output": MAX_OUTPUT_COMPRESSED_BYTES,
    }[purpose]
    if compressed_bytes > compressed_limit:
        raise OfficePackageError("compressed_size_limit", loc, "Office 压缩包超过资源上限。")

    try:
        with ZipFile(path) as package:
            infos = package.infolist()
            if not infos:
                raise OfficePackageError("corrupt_package", loc, "Office 压缩包不包含任何部件。")
            if len(infos) > MAX_PACKAGE_PARTS:
                raise OfficePackageError("part_count_limit", loc, "Office 压缩包部件数量超过 10000 个限制。")
            _validate_member_names(infos, loc)
            _validate_member_resources(infos, loc)
            names = {info.filename for info in infos}
            office_kind = _detect_office_kind(names, loc)
            expected = path.suffix.lower().lstrip(".")
            if expected != office_kind:
                raise OfficePackageError(
                    "extension_mismatch",
                    loc,
                    f"文件扩展名 .{expected or '<none>'} 与实际 {office_kind.upper()} 包不一致。",
                )
            _scan_xml_safety(package, infos, loc)
            relationship_count, external_relationships, internal_relationships = _relationship_summary(
                package, names, loc
            )
            chart_workbooks = _chart_workbook_parts(internal_relationships)
            nested_warnings = _validate_chart_workbooks(
                package,
                names,
                chart_workbooks,
                purpose=purpose,
                loc=loc,
            )
            active_parts = sorted(_active_parts(names, allowed=chart_workbooks), key=str.casefold)
            warnings: list[str] = []
            if active_parts:
                if purpose != "source":
                    active_part = active_parts[0]
                    reason = _active_reason(active_part)
                    context = _active_part_context(package, active_part)
                    raise OfficePackageError(
                        reason,
                        loc,
                        f"Office 包{context}包含不安全活动部件: {active_part}",
                        context=context,
                    )
                warnings.append(
                    f"active content ignored during source parsing: {len(active_parts)} part(s); binary not executed or copied"
                )
            if external_relationships:
                if purpose != "source":
                    raise OfficePackageError(
                        "external_relationship",
                        loc,
                        f"Office 包包含外部关系: {external_relationships[0]}",
                    )
                warnings.append(
                    f"external relationships ignored during source parsing: {len(external_relationships)}"
                )
            warnings.extend(nested_warnings)
            return OfficePackageReport(
                purpose=purpose,
                office_kind=office_kind,
                compressed_bytes=compressed_bytes,
                uncompressed_bytes=sum(info.file_size for info in infos),
                part_count=len(infos),
                relationship_count=relationship_count,
                active_parts=active_parts,
                external_relationships=external_relationships,
                warnings=warnings,
            )
    except OfficePackageError:
        raise
    except (BadZipFile, OSError, KeyError, ElementTree.ParseError) as exc:
        raise OfficePackageError("corrupt_package", loc, "Office 文件不是可安全读取的 OOXML 压缩包。") from exc


def _validate_member_names(infos, loc: str) -> None:
    seen: set[str] = set()
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        if not name or "\\" in name or "\x00" in name or path.is_absolute() or ".." in path.parts:
            raise OfficePackageError("unsafe_package_path", loc, f"Office 包包含不安全路径: {name}")
        normalized = name.casefold()
        if normalized in seen:
            raise OfficePackageError("duplicate_package_part", loc, f"Office 包包含重复部件: {name}")
        seen.add(normalized)
        if info.flag_bits & 0x1:
            raise OfficePackageError("encrypted_package", loc, "Office 包含加密 ZIP 部件，无法安全解析。")


def _validate_member_resources(infos, loc: str) -> None:
    uncompressed = sum(info.file_size for info in infos)
    if uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise OfficePackageError("uncompressed_size_limit", loc, "Office 解包体积超过 500 MB 限制。")
    for info in infos:
        if info.file_size > MAX_PART_BYTES:
            raise OfficePackageError("part_size_limit", loc, f"Office 部件超过 100 MB 限制: {info.filename}")
        if info.file_size < MIN_RATIO_GUARD_BYTES:
            continue
        ratio = float("inf") if info.compress_size == 0 else info.file_size / info.compress_size
        if ratio > MAX_COMPRESSION_RATIO:
            raise OfficePackageError(
                "suspicious_compression_ratio",
                loc,
                f"Office 部件 compression ratio 压缩率异常: {info.filename}",
            )


def _detect_office_kind(names: set[str], loc: str) -> OfficeKind:
    matches = [kind for kind, required in REQUIRED_PARTS.items() if required <= names]
    if len(matches) != 1:
        raise OfficePackageError("corrupt_package", loc, "Office 包缺少必需部件或类型不明确。")
    return matches[0]


# DTD/ENTITY declaration needles in every encoding the OOXML package may use.
# ECMA-376 allows UTF-16 parts; the declaration is then stored with interleaved
# null bytes and the ASCII-only scan above would miss it, letting a malicious
# DTD/ENTITY reach the downstream ElementTree parser.
_SAFE_SCAN_NEEDLES = (
    b"<!doctype",  # ASCII / UTF-8
    b"<!entity",  # ASCII / UTF-8
    b"<\x00!\x00d\x00o\x00c\x00t\x00y\x00p\x00e\x00",  # UTF-16LE <!doctype
    b"<\x00!\x00e\x00n\x00t\x00i\x00t\x00y\x00",  # UTF-16LE <!entity
    b"\x00<\x00!\x00d\x00o\x00c\x00t\x00y\x00p\x00e",  # UTF-16BE <!doctype
    b"\x00<\x00!\x00e\x00n\x00t\x00i\x00t\x00y",  # UTF-16BE <!entity
)


def _scan_xml_safety(package: ZipFile, infos, loc: str) -> None:
    needles = _SAFE_SCAN_NEEDLES
    carry_len = max(len(needle) for needle in needles) - 1
    for info in infos:
        if not (info.filename.lower().endswith(".xml") or info.filename.lower().endswith(".rels")):
            continue
        carry = b""
        with package.open(info) as stream:
            while chunk := stream.read(64 * 1024):
                lowered = (carry + chunk).lower()
                if any(needle in lowered for needle in needles):
                    raise OfficePackageError(
                        "unsafe_xml_declaration",
                        loc,
                        f"Office XML 包含禁止的 DTD/ENTITY 声明: {info.filename}",
                    )
                carry = lowered[-carry_len:]


def _relationship_summary(
    package: ZipFile,
    names: set[str],
    loc: str,
) -> tuple[int, list[str], list[tuple[str, str, str]]]:
    count = 0
    external: list[str] = []
    internal: list[tuple[str, str, str]] = []
    for name in sorted(names):
        if not name.endswith(".rels"):
            continue
        try:
            root = ElementTree.fromstring(package.read(name))
        except ElementTree.ParseError as exc:
            raise OfficePackageError("corrupt_package", loc, f"Office 关系 XML 损坏: {name}") from exc
        for relationship in root.findall(f"{{{REL_NS}}}Relationship"):
            count += 1
            if relationship.attrib.get("TargetMode") == "External":
                external.append(f"{name}:{relationship.attrib.get('Id', '?')}")
                continue
            source_part = _relationship_source_part(name)
            target = _resolve_relationship_target(source_part, relationship.attrib.get("Target", ""))
            internal.append((source_part, target, relationship.attrib.get("Type", "")))
    return count, external, internal


def _chart_workbook_parts(internal_relationships: list[tuple[str, str, str]]) -> set[str]:
    allowed: set[str] = set()
    for source, target, relationship_type in internal_relationships:
        if (
            re.fullmatch(r"ppt/charts/chart\d+\.xml", source, flags=re.IGNORECASE)
            and relationship_type == PACKAGE_REL_TYPE
            and re.fullmatch(r"ppt/embeddings/[^/]+\.xlsx", target, flags=re.IGNORECASE)
        ):
            allowed.add(target)
    return allowed


def _validate_chart_workbooks(
    package: ZipFile,
    names: set[str],
    chart_workbooks: set[str],
    *,
    purpose: OfficePurpose,
    loc: str,
) -> list[str]:
    warnings: list[str] = []
    for part in sorted(chart_workbooks, key=str.casefold):
        if part not in names:
            raise OfficePackageError(
                "corrupt_package",
                loc,
                f"PowerPoint 图表数据工作簿不存在: {part}",
            )
        try:
            with package.open(part) as stream, ZipFile(stream) as workbook:
                infos = workbook.infolist()
                if not infos:
                    raise OfficePackageError(
                        "corrupt_package",
                        loc,
                        f"PowerPoint 图表数据工作簿为空: {part}",
                    )
                _validate_member_names(infos, loc)
                _validate_member_resources(infos, loc)
                nested_names = {info.filename for info in infos}
                if _detect_office_kind(nested_names, loc) != "xlsx":
                    raise OfficePackageError(
                        "corrupt_package",
                        loc,
                        f"PowerPoint 图表数据部件不是有效 XLSX: {part}",
                    )
                _scan_xml_safety(workbook, infos, loc)
                _, nested_external, nested_internal = _relationship_summary(workbook, nested_names, loc)
                nested_active = _active_parts(nested_names)
                if nested_active:
                    if purpose != "source":
                        raise OfficePackageError(
                            _active_reason(nested_active[0]),
                            loc,
                            f"PowerPoint 图表数据工作簿包含不安全活动部件: {part}!/{nested_active[0]}",
                        )
                    warnings.append(
                        f"active content ignored in embedded chart workbook: {part}; "
                        f"{len(nested_active)} part(s)"
                    )
                if nested_external:
                    if purpose != "source":
                        raise OfficePackageError(
                            "external_relationship",
                            loc,
                            f"PowerPoint 图表数据工作簿包含外部关系: {part}!/{nested_external[0]}",
                        )
                    warnings.append(
                        f"external relationships ignored in embedded chart workbook: {part}; "
                        f"{len(nested_external)} relationship(s)"
                    )
                if _chart_workbook_parts(nested_internal):
                    raise OfficePackageError(
                        "unsafe_ole",
                        loc,
                        f"PowerPoint 图表数据工作簿包含嵌套嵌入部件: {part}",
                    )
        except OfficePackageError:
            raise
        except (BadZipFile, OSError, KeyError, ElementTree.ParseError) as exc:
            raise OfficePackageError(
                "corrupt_package",
                loc,
                f"PowerPoint 图表数据工作簿不是可安全读取的 XLSX: {part}",
            ) from exc
    return warnings


def _active_parts(names: set[str], *, allowed: set[str] | None = None) -> list[str]:
    allowed_casefold = {name.casefold() for name in (allowed or set())}
    return [
        name
        for name in names
        if not name.endswith("/")
        and name.casefold() not in allowed_casefold
        and (
            "vbaproject" in name.casefold()
            or "/activex/" in name.casefold()
            or "/embeddings/" in name.casefold()
            or "/oleobjects/" in name.casefold()
        )
    ]


def _active_reason(part: str) -> str:
    lowered = part.casefold()
    if "vbaproject" in lowered:
        return "unsafe_macro"
    if "/activex/" in lowered:
        return "unsafe_activex"
    return "unsafe_ole"


def _active_part_context(package: ZipFile, active_part: str) -> str:
    sources: list[str] = []
    for rels_name in package.namelist():
        if not rels_name.endswith(".rels"):
            continue
        root = ElementTree.fromstring(package.read(rels_name))
        source_part = _relationship_source_part(rels_name)
        for relationship in root.findall(f"{{{REL_NS}}}Relationship"):
            if relationship.attrib.get("TargetMode") == "External":
                continue
            target = relationship.attrib.get("Target", "")
            if _resolve_relationship_target(source_part, target).casefold() == active_part.casefold():
                sources.append(source_part)
    slide_numbers = sorted(
        {
            int(match.group(1))
            for source in sources
            if (match := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", source, flags=re.IGNORECASE))
        }
    )
    if slide_numbers:
        return f"第 {'、'.join(str(number) for number in slide_numbers)} 页"
    if sources:
        return f"的 {sorted(sources)[0]} 中"
    return "中"


def _relationship_source_part(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return ""
    path = PurePosixPath(rels_name)
    if path.parent.name != "_rels" or not path.name.endswith(".rels"):
        return ""
    return (path.parent.parent / path.name.removesuffix(".rels")).as_posix()


def _resolve_relationship_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))
