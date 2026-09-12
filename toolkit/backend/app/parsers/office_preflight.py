from __future__ import annotations

from pathlib import Path

from app.parsers.errors import ParseFailure
from app.security.office_package import OfficePackageError, preflight_office_package


FORMAT_OR_SAFETY_REASONS = {
    "extension_mismatch",
    "unsafe_package_path",
    "duplicate_package_part",
    "encrypted_package",
    "unsafe_xml_declaration",
}


def preflight_source_office(path: Path) -> list[str]:
    try:
        report = preflight_office_package(path, purpose="source")
    except OfficePackageError as exc:
        code = "E003" if exc.reason in FORMAT_OR_SAFETY_REASONS else "E001"
        raise ParseFailure(
            code=code,
            loc="source.resource",
            message=exc.message,
            suggestion="请确认文件来源可信、扩展名与实际格式一致，并使用 Office 重新另存后重试。",
        ) from exc
    return list(report.warnings)
