from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.assets.contracts import AssetRecord
from app.assets.errors import AssetError


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    width: int
    height: int
    output_dir: Path


class ImageProvider(Protocol):
    def generate(self, request: ImageRequest) -> AssetRecord: ...


class DisabledImageProvider:
    def generate(self, request: ImageRequest) -> AssetRecord:
        raise AssetError("A006", "image_provider", "离线生产环境未启用 AI 生图服务。")
