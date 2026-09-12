from __future__ import annotations

import re
import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class AssetContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetRecord(AssetContractModel):
    asset_id: str = Field(pattern=ASSET_ID_RE.pattern)
    source_type: Literal["upload", "document", "local_whitelist", "generated"]
    source_filename: str = Field(min_length=1, max_length=255)
    original_media_type: Literal["image/png", "image/jpeg", "image/webp"]
    media_type: Literal["image/png"] = "image/png"
    original_sha256: str
    normalized_sha256: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    pixel_count: int = Field(ge=1)
    bytes: int = Field(ge=1)
    relative_path: str = Field(min_length=1)
    has_alpha: bool
    exif_orientation_applied: bool
    metadata_removed: bool
    animated: bool = False
    label: str | None = None
    alt: str | None = None
    credit: str | None = None

    @field_validator("original_sha256", "normalized_sha256")
    @classmethod
    def hashes_are_lower_hex(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("hash must be 64 lowercase hexadecimal characters")
        return value

    @field_validator("source_filename", "label", "alt", "credit")
    @classmethod
    def text_is_trimmed(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value

    @field_validator("relative_path")
    @classmethod
    def path_is_safe_relative_posix(cls, value: str) -> str:
        if "\\" in value:
            raise ValueError("relative_path must use POSIX separators")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("relative_path must stay inside the manifest directory")
        return path.as_posix()

    @model_validator(mode="after")
    def dimensions_are_consistent(self) -> "AssetRecord":
        if self.pixel_count != self.width * self.height:
            raise ValueError("pixel_count must equal width * height")
        if self.animated:
            raise ValueError("animated images are not supported")
        return self


class AssetManifest(AssetContractModel):
    manifest_version: Literal["1.0"]
    assets: list[AssetRecord] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def identifiers_and_paths_are_unique(self) -> "AssetManifest":
        ids = [asset.asset_id for asset in self.assets]
        paths = [asset.relative_path.casefold() for asset in self.assets]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ValueError("asset ids and relative paths must be unique")
        return self


class AssetUsage(AssetContractModel):
    slide: int = Field(ge=1)
    asset_id: str = Field(pattern=ASSET_ID_RE.pattern)
    normalized_sha256: str
    fit: Literal["contain", "cover"]
    left_in: float = Field(ge=0)
    top_in: float = Field(ge=0)
    width_in: float = Field(gt=0)
    height_in: float = Field(gt=0)
    crop_left: float = Field(default=0, ge=0, le=1)
    crop_top: float = Field(default=0, ge=0, le=1)
    crop_right: float = Field(default=0, ge=0, le=1)
    crop_bottom: float = Field(default=0, ge=0, le=1)
    effective_dpi: float = Field(gt=0)

    _hash_valid = field_validator("normalized_sha256")(AssetRecord.hashes_are_lower_hex.__func__)


class AssetUsageAudit(AssetContractModel):
    audit_version: Literal["1.0"]
    usages: list[AssetUsage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def asset_schema_documents() -> dict[str, dict]:
    models = {"asset_manifest": AssetManifest, "asset_usage_audit": AssetUsageAudit}
    return {
        name: json.loads(json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True))
        for name, model in models.items()
    }


def write_asset_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, schema in asset_schema_documents().items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written
