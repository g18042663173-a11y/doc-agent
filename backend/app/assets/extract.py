from __future__ import annotations

from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from app.assets.errors import AssetError


OFFICE_MEDIA_PREFIXES = {
    ".docx": "word/media/",
    ".pptx": "ppt/media/",
    ".xlsx": "xl/media/",
}
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_EMBEDDED_IMAGE_BYTES = 20 * 1024 * 1024
MAX_EMBEDDED_IMAGES = 20
MAX_EMBEDDED_TOTAL_BYTES = 100 * 1024 * 1024
EXTRACT_CHUNK_BYTES = 1024 * 1024


def extract_office_image_files(package_path: Path, output_dir: Path) -> list[Path]:
    suffix = package_path.suffix.lower()
    prefix = OFFICE_MEDIA_PREFIXES.get(suffix)
    if prefix is None:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    total_bytes = 0
    try:
        with ZipFile(package_path) as archive:
            for member in archive.infolist():
                name = PurePosixPath(member.filename)
                normalized = name.as_posix()
                if name.is_absolute() or ".." in name.parts or not normalized.startswith(prefix):
                    continue
                if name.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES or member.is_dir():
                    continue
                if member.file_size > MAX_EMBEDDED_IMAGE_BYTES:
                    raise AssetError("A003", f"input_file:{normalized}", "嵌入图片超过 20 MB 限制。")
                if len(extracted) >= MAX_EMBEDDED_IMAGES:
                    raise AssetError("A003", "input_file", "输入文档中的图片超过 20 张限制。")
                if total_bytes + member.file_size > MAX_EMBEDDED_TOTAL_BYTES:
                    raise AssetError("A003", "input_file", "输入文档中的图片总大小超过 100 MB 限制。")
                target = output_dir / f"embedded-{len(extracted) + 1:03d}{name.suffix.lower()}"
                written = 0
                try:
                    with archive.open(member) as source, target.open("wb") as destination:
                        while chunk := source.read(EXTRACT_CHUNK_BYTES):
                            written += len(chunk)
                            if written > MAX_EMBEDDED_IMAGE_BYTES:
                                raise AssetError(
                                    "A003",
                                    f"input_file:{normalized}",
                                    "嵌入图片解包后超过 20 MB 限制。",
                                )
                            destination.write(chunk)
                except Exception:
                    target.unlink(missing_ok=True)
                    raise
                total_bytes += written
                extracted.append(target)
    except (BadZipFile, OSError, KeyError) as exc:
        raise AssetError("A002", "input_file", "无法安全读取 Office 文件中的图片资源。") from exc
    return extracted
