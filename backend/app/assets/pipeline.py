from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Literal
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import ValidationError

from app.assets.contracts import AssetManifest, AssetRecord, AssetUsage, AssetUsageAudit
from app.assets.errors import AssetError


SourceType = Literal["upload", "document", "local_whitelist", "generated"]
MEDIA_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
SUFFIX_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}


@dataclass(frozen=True)
class AssetLimits:
    max_bytes_per_image: int = 20 * 1024 * 1024
    max_total_bytes: int = 100 * 1024 * 1024
    max_assets: int = 20
    max_pixels_per_image: int = 40_000_000


@dataclass
class AssetRegistry:
    manifest: AssetManifest
    base_dir: Path
    usages: list[AssetUsage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def record(self, asset_id: str) -> AssetRecord:
        for record in self.manifest.assets:
            if record.asset_id == asset_id:
                return record
        raise AssetError("A005", f"asset[{asset_id}]", "DeckIR 引用了不存在的图片资产。")

    def resolve(self, asset_id: str) -> Path:
        record = self.record(asset_id)
        root = self.base_dir.resolve()
        path = (root / Path(record.relative_path)).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise AssetError("A006", f"asset[{asset_id}]", "资产路径越出清单目录。") from exc
        if not path.is_file():
            raise AssetError("A005", f"asset[{asset_id}]", "图片资产文件不存在。")
        return path

    def add_usage(self, usage: AssetUsage) -> None:
        self.usages.append(usage)

    def write_usage_audit(self, path: Path) -> Path:
        audit = AssetUsageAudit(audit_version="1.0", usages=self.usages, warnings=self.warnings)
        path.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def normalize_assets(
    files: Iterable[Path],
    output_dir: Path,
    *,
    source_type: SourceType = "upload",
    limits: AssetLimits | None = None,
    allowed_roots: Iterable[Path] | None = None,
    append: bool = False,
) -> AssetManifest:
    limits = limits or AssetLimits()
    paths = [Path(path) for path in files]
    existing: list[AssetRecord] = []
    manifest_path = output_dir / "asset_manifest.json"
    if append and manifest_path.is_file():
        existing = load_asset_manifest(manifest_path).manifest.assets
    if len(paths) + len(existing) > limits.max_assets:
        raise AssetError("A003", "asset_files", f"图片数量超过 {limits.max_assets} 张限制。")
    existing_bytes = sum(record.bytes for record in existing)
    total = sum(path.stat().st_size for path in paths if path.is_file())
    if total + existing_bytes > limits.max_total_bytes:
        raise AssetError("A003", "asset_files", "图片总大小超过 100 MB 限制。")
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir = output_dir / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    roots = [root.resolve() for root in allowed_roots or []]
    records: list[AssetRecord] = list(existing)
    seen_original_hashes: set[str] = {record.original_sha256 for record in existing}
    normalized_total = existing_bytes
    for index, source in enumerate(paths):
        source = source.resolve()
        loc = f"asset_files[{index}]"
        if source_type == "local_whitelist" and not any(_is_relative_to(source, root) for root in roots):
            raise AssetError("A006", loc, "本地图片不在允许的白名单目录中。")
        if source.is_file() and _sha256_file(source) in seen_original_hashes:
            continue
        record = _normalize_one(source, normalized_dir, source_type=source_type, limits=limits, loc=loc)
        if normalized_total + record.bytes > limits.max_total_bytes:
            (output_dir / record.relative_path).unlink(missing_ok=True)
            raise AssetError("A003", "asset_files", "规范化图片总大小超过 100 MB 限制。")
        normalized_total += record.bytes
        seen_original_hashes.add(record.original_sha256)
        records.append(record)
    manifest = AssetManifest(manifest_version="1.0", assets=records)
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def _normalize_one(source: Path, normalized_dir: Path, *, source_type: SourceType, limits: AssetLimits, loc: str) -> AssetRecord:
    if not source.is_file():
        raise AssetError("A002", loc, "图片文件不存在或不可读取。")
    suffix = source.suffix.lower()
    if suffix not in SUFFIX_FORMATS:
        raise AssetError("A001", loc, "图片只支持 PNG、JPEG 或 WebP。")
    original_bytes = source.stat().st_size
    if original_bytes > limits.max_bytes_per_image:
        raise AssetError("A003", loc, "单张图片超过 20 MB 限制。")
    original_hash = _sha256_file(source)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as opened:
                opened.load()
                detected = (opened.format or "").upper()
                if detected != SUFFIX_FORMATS[suffix]:
                    raise AssetError("A001", loc, "图片扩展名与实际编码格式不一致。")
                if detected not in MEDIA_TYPES:
                    raise AssetError("A001", loc, "图片实际编码不受支持。")
                if bool(getattr(opened, "is_animated", False)) or int(getattr(opened, "n_frames", 1)) != 1:
                    raise AssetError("A001", loc, "不支持动画图片。")
                width, height = opened.size
                pixels = width * height
                if pixels > limits.max_pixels_per_image:
                    raise AssetError("A003", loc, "图片像素总量超过 40MP 限制。")
                orientation = int(opened.getexif().get(274, 1) or 1)
                image = ImageOps.exif_transpose(opened)
                has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                asset_id = f"asset-{original_hash[:12]}"
                relative_path = f"normalized/{asset_id}.png"
                destination = normalized_dir / f"{asset_id}.png"
                image.save(destination, format="PNG", optimize=False)
    except AssetError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise AssetError("A002", loc, "图片无法安全解码。") from exc
    normalized_bytes = destination.stat().st_size
    return AssetRecord(
        asset_id=asset_id,
        source_type=source_type,
        source_filename=source.name,
        original_media_type=MEDIA_TYPES[detected],
        original_sha256=original_hash,
        normalized_sha256=_sha256_file(destination),
        width=image.width,
        height=image.height,
        pixel_count=image.width * image.height,
        bytes=normalized_bytes,
        relative_path=relative_path,
        has_alpha=has_alpha,
        exif_orientation_applied=orientation not in {0, 1},
        metadata_removed=True,
        animated=False,
    )


def load_asset_manifest(path: Path) -> AssetRegistry:
    path = path.resolve()
    try:
        manifest = AssetManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise AssetError("A002", "asset_manifest", "资产清单无法读取或未通过契约校验。") from exc
    registry = AssetRegistry(manifest=manifest, base_dir=path.parent)
    for record in manifest.assets:
        asset_path = registry.resolve(record.asset_id)
        if _sha256_file(asset_path) != record.normalized_sha256:
            raise AssetError("A006", f"asset[{record.asset_id}]", "图片文件哈希与资产清单不一致。")
    return registry


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
