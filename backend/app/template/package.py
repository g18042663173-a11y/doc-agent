from __future__ import annotations

from dataclasses import dataclass
import posixpath
from pathlib import Path, PurePosixPath
import re
import zipfile
from xml.etree import ElementTree

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
            slide_count = sum(name.startswith("ppt/slides/slide") and name.endswith(".xml") for name in names)
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


def _unsafe_part_context(package: zipfile.ZipFile, unsafe_part: str) -> str:
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
            if _resolve_relationship_target(source_part, target).casefold() == unsafe_part.casefold():
                sources.append(source_part)
    slide_numbers = sorted(
        {
            int(match.group(1))
            for source in sources
            if (match := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", source, flags=re.IGNORECASE))
        }
    )
    if slide_numbers:
        pages = "、".join(str(number) for number in slide_numbers)
        return f"第 {pages} 页"
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
