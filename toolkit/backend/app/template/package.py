from __future__ import annotations

from dataclasses import dataclass
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile
from xml.etree import ElementTree

from lxml import etree as LxmlElementTree

from app.security.office_package import OfficePackageError, preflight_office_package


MAX_TEMPLATE_BYTES = 50 * 1024 * 1024
MAX_TEMPLATE_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_TEMPLATE_SLIDES = 200
MAX_TEMPLATE_SHAPES = 5000

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


@dataclass
class TemplateInputError(RuntimeError):
    code: str
    loc: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.loc}: {self.message}"


def validate_template_package(path: Path) -> dict:
    path = path.resolve()
    if path.suffix.lower() != ".pptx":
        raise TemplateInputError("E003", "template_file", "模板仅支持 .pptx 文件。")
    if not path.is_file():
        raise TemplateInputError("E003", "template_file", "模板文件不存在。")
    if path.stat().st_size > MAX_TEMPLATE_BYTES:
        raise TemplateInputError("E001", "template_file", "模板压缩包超过 50 MB 资源上限。")
    try:
        preflight_office_package(path, purpose="template")
    except OfficePackageError as exc:
        code = "E001" if exc.reason.endswith("_limit") else "E003"
        message = exc.message.replace("Office 包", "模板").replace("不安全活动部件", "不安全嵌入部件")
        raise TemplateInputError(code, "template_file", message) from exc
    try:
        with zipfile.ZipFile(path) as package:
            infos = package.infolist()
            names = [info.filename for info in infos]
            _validate_names(names)
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_TEMPLATE_UNCOMPRESSED_BYTES:
                raise TemplateInputError("E001", "template_file", "模板解包体积超过 500 MB 资源上限。")
            # Only real slide parts count: a name like ppt/slides/slideLayout1.xml
            # (non-standard writers) must not inflate the slide total.
            slide_count = sum(bool(re.fullmatch(r"ppt/slides/slide\d+\.xml", name)) for name in names)
            if slide_count < 1 or slide_count > MAX_TEMPLATE_SLIDES:
                raise TemplateInputError("E001", "template_file", "模板页数必须在 1-200 页之间。")
            external = _external_relationships(package)
            if external:
                raise TemplateInputError("E003", "template_file", f"模板包含外部关系: {external[0]}")
    except TemplateInputError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise TemplateInputError("E003", "template_file", f"模板不是有效的 PPTX 包: {exc}") from exc

    report = validate_pptx_package(path)
    if not report["pass"]:
        raise TemplateInputError("E003", "template_file", report["errors"][0])
    return report


def sanitize_template_hyperlinks(path: Path, output_path: Path) -> int:
    """Create a validated PPTX copy with only external hyperlinks removed.

    This is deliberately narrower than a general OOXML "repair" operation.
    External targets other than hyperlinks and all active content remain a hard
    failure, so a repair action cannot be used to smuggle an unsafe template
    through the authoritative validator.
    """
    path = Path(path).resolve()
    output_path = Path(output_path).resolve()
    if path.suffix.lower() != ".pptx" or output_path.suffix.lower() != ".pptx":
        raise TemplateInputError("E003", "template_file", "安全副本仅支持 .pptx 模板。")
    if not path.is_file():
        raise TemplateInputError("E003", "template_file", "模板文件不存在。")
    if path.stat().st_size > MAX_TEMPLATE_BYTES:
        raise TemplateInputError("E001", "template_file", "模板压缩包超过 50 MB 资源上限。")
    if path == output_path:
        raise TemplateInputError("E003", "template_file", "安全副本不能覆盖原模板。")
    if output_path.exists():
        raise TemplateInputError("E001", "template_file", "安全副本目标已存在，请选择其他保存位置。")

    try:
        source_report = preflight_office_package(path, purpose="source")
    except OfficePackageError as exc:
        code = "E001" if exc.reason.endswith("_limit") else "E003"
        message = exc.message.replace("Office 包", "模板").replace("不安全活动部件", "不安全嵌入部件")
        raise TemplateInputError(code, "template_file", message) from exc

    if source_report.office_kind != "pptx":
        raise TemplateInputError("E003", "template_file", "模板不是有效的 PPTX 包。")
    if source_report.active_parts:
        raise TemplateInputError("E003", "template_file", "模板包含不安全嵌入部件，不能自动清理。")
    if any("embedded chart workbook" in warning for warning in source_report.warnings):
        raise TemplateInputError("E003", "template_file", "模板的嵌入图表数据包含不安全关系，不能自动清理。")
    if not source_report.external_relationships:
        raise TemplateInputError("E003", "template_file", "模板没有可自动移除的外部超链接。")
    if any(not relationship.endswith(" (hyperlink)") for relationship in source_report.external_relationships):
        raise TemplateInputError("E003", "template_file", "安全副本仅支持移除外部超链接，其他外部关系仍需人工处理。")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="template-safe-",
        suffix=".pptx",
        dir=output_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        removed_relationships = _write_template_without_external_hyperlinks(path, temporary_path)
        if removed_relationships == 0:
            raise TemplateInputError("E003", "template_file", "模板没有可自动移除的外部超链接。")
        validate_template_package(temporary_path)
        temporary_path.replace(output_path)
        return removed_relationships
    except TemplateInputError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise TemplateInputError("E003", "template_file", "模板安全副本生成失败。") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_template_without_external_hyperlinks(source_path: Path, output_path: Path) -> int:
    with zipfile.ZipFile(source_path) as source:
        infos = source.infolist()
        names = {info.filename for info in infos}
        relation_updates: dict[str, bytes] = {}
        relationship_ids_by_part: dict[str, set[str]] = {}

        for info in infos:
            if not info.filename.endswith(".rels"):
                continue
            root = ElementTree.fromstring(source.read(info.filename))
            source_part = _relationship_source_part(info.filename)
            removals: list[ElementTree.Element] = []
            for relationship in root.findall(f"{{{REL_NS}}}Relationship"):
                if relationship.attrib.get("TargetMode") != "External":
                    continue
                if not _is_hyperlink_relationship(relationship):
                    raise TemplateInputError(
                        "E003",
                        "template_file",
                        "安全副本仅支持移除外部超链接，其他外部关系仍需人工处理。",
                    )
                relationship_id = relationship.attrib.get("Id", "")
                if not source_part or source_part not in names or not source_part.endswith(".xml") or not relationship_id:
                    raise TemplateInputError("E003", "template_file", "模板包含无法安全移除的外部超链接。")
                removals.append(relationship)
                relationship_ids_by_part.setdefault(source_part, set()).add(relationship_id)
            if removals:
                for relationship in removals:
                    root.remove(relationship)
                relation_updates[info.filename] = _serialize_xml(root)

        xml_updates = {
            part: _remove_hyperlink_references(source.read(part), part, relationship_ids)
            for part, relationship_ids in relationship_ids_by_part.items()
        }
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as target:
            for info in infos:
                data = relation_updates.get(info.filename, xml_updates.get(info.filename, source.read(info.filename)))
                target.writestr(info, data)
    return sum(len(ids) for ids in relationship_ids_by_part.values())


def _is_hyperlink_relationship(relationship: ElementTree.Element) -> bool:
    return relationship.attrib.get("Type", "").rsplit("/", 1)[-1].casefold() == "hyperlink"


def _remove_hyperlink_references(data: bytes, part: str, relationship_ids: set[str]) -> bytes:
    root = LxmlElementTree.fromstring(data)
    relationship_attribute = f"{{{OFFICE_REL_NS}}}id"
    for parent in root.iter():
        for child in list(parent):
            relationship_id = child.attrib.get(relationship_attribute)
            if relationship_id not in relationship_ids:
                continue
            if child.tag.rsplit("}", 1)[-1] not in {"hlinkClick", "hlinkHover"}:
                raise TemplateInputError(
                    "E003",
                    "template_file",
                    f"模板包含无法安全移除的外部超链接引用: {part}",
                )
            parent.remove(child)
    return LxmlElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _serialize_xml(root: ElementTree.Element) -> bytes:
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_pptx_package(path: Path) -> dict:
    errors: list[str] = []
    relationship_count = 0
    external_relationships = 0
    parsed_xml: dict[str, ElementTree.Element] = {}
    relationship_ids: dict[str, set[str]] = {}
    try:
        preflight_office_package(path, purpose="output")
    except OfficePackageError as exc:
        return {
            "report_version": "1.0",
            "pass": False,
            "part_count": 0,
            "relationship_count": 0,
            "external_relationship_count": 0,
            "errors": [exc.message],
        }
    try:
        with zipfile.ZipFile(path) as package:
            infos = package.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            try:
                _validate_names(names)
            except TemplateInputError as exc:
                errors.append(exc.message)
            required = {"[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml"}
            for missing in sorted(required - name_set):
                errors.append(f"缺少必要 OOXML 部件: {missing}")

            for name in names:
                if name.endswith((".xml", ".rels")):
                    try:
                        parsed_xml[name] = ElementTree.fromstring(package.read(name))
                    except ElementTree.ParseError as exc:
                        errors.append(f"XML 无法解析: {name}: {exc}")

            for rels_name in sorted(name for name in names if name.endswith(".rels")):
                try:
                    root = ElementTree.fromstring(package.read(rels_name))
                except ElementTree.ParseError:
                    continue
                source_part = _relationship_source_part(rels_name)
                relationship_ids[source_part] = {
                    relationship.attrib.get("Id", "")
                    for relationship in root.findall(f"{{{REL_NS}}}Relationship")
                    if relationship.attrib.get("Id")
                }
                for relationship in root.findall(f"{{{REL_NS}}}Relationship"):
                    relationship_count += 1
                    if relationship.attrib.get("TargetMode") == "External":
                        external_relationships += 1
                        continue
                    target = relationship.attrib.get("Target", "")
                    resolved = _resolve_relationship_target(source_part, target)
                    if not resolved or resolved not in name_set:
                        errors.append(f"关系目标不存在: {rels_name} -> {target}")

            _validate_xml_relationship_references(parsed_xml, relationship_ids, errors)

            if "[Content_Types].xml" in name_set:
                try:
                    _validate_content_types(package, name_set, errors)
                except ElementTree.ParseError:
                    pass
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"PPTX 包无法打开: {exc}")
        names = []
    return {
        "report_version": "1.0",
        "pass": not errors,
        "part_count": len(names),
        "relationship_count": relationship_count,
        "external_relationship_count": external_relationships,
        "errors": errors,
    }


def _validate_names(names: list[str]) -> None:
    if len(names) != len(set(names)):
        raise TemplateInputError("E003", "template_file", "PPTX 包包含重复部件名。")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise TemplateInputError("E003", "template_file", f"PPTX 包包含不安全路径: {name}")


def _external_relationships(package: zipfile.ZipFile) -> list[str]:
    external: list[str] = []
    for name in package.namelist():
        if not name.endswith(".rels"):
            continue
        root = ElementTree.fromstring(package.read(name))
        for relationship in root.findall(f"{{{REL_NS}}}Relationship"):
            if relationship.attrib.get("TargetMode") == "External":
                external.append(f"{name}:{relationship.attrib.get('Id', '?')}")
    return external


def _relationship_source_part(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return ""
    path = PurePosixPath(rels_name)
    if path.parent.name != "_rels" or not path.name.endswith(".rels"):
        return ""
    return (path.parent.parent / path.name.removesuffix(".rels")).as_posix()


def _resolve_relationship_target(source_part: str, target: str) -> str:
    target = target.split("#", 1)[0]
    if not target:
        return ""
    if target.startswith("/"):
        normalized = posixpath.normpath(target.lstrip("/"))
    else:
        normalized = posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))
    return "" if normalized == ".." or normalized.startswith("../") else normalized


def _validate_content_types(package: zipfile.ZipFile, names: set[str], errors: list[str]) -> None:
    root = ElementTree.fromstring(package.read("[Content_Types].xml"))
    defaults = {
        item.attrib.get("Extension", "").lower()
        for item in root.findall(f"{{{CONTENT_TYPES_NS}}}Default")
    }
    overrides = {
        item.attrib.get("PartName", "").lstrip("/")
        for item in root.findall(f"{{{CONTENT_TYPES_NS}}}Override")
    }
    for name in names:
        if name == "[Content_Types].xml" or name.endswith(".rels") or name.endswith("/"):
            continue
        extension = PurePosixPath(name).suffix.lstrip(".").lower()
        if name not in overrides and extension not in defaults:
            errors.append(f"部件缺少 Content Type: {name}")


def _validate_xml_relationship_references(
    parsed_xml: dict[str, ElementTree.Element],
    relationship_ids: dict[str, set[str]],
    errors: list[str],
) -> None:
    for part_name, root in parsed_xml.items():
        if not part_name.endswith(".xml"):
            continue
        known_ids = relationship_ids.get(part_name, set())
        for element in root.iter():
            local_name = element.tag.rsplit("}", 1)[-1]
            relationship_attributes = {
                attribute.rsplit("}", 1)[-1]: value
                for attribute, value in element.attrib.items()
                if attribute.startswith(f"{{{OFFICE_REL_NS}}}")
            }
            if local_name == "tags" and not relationship_attributes.get("id"):
                errors.append(f"关系元素缺少 r:id: {part_name} -> tags")
            for attribute_name, relationship_id in relationship_attributes.items():
                if not relationship_id:
                    continue
                if relationship_id not in known_ids:
                    errors.append(
                        f"XML 引用了不存在的关系: {part_name} -> {attribute_name}={relationship_id}"
                    )
