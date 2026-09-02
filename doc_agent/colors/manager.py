from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from doc_agent.colors.models import ColorRecommendation, ColorScheme
from doc_agent.config import get_settings, load_style_profile


class ColorManager:
    def __init__(self, colors_dir: str | Path | None = None) -> None:
        self.colors_dir = Path(colors_dir) if colors_dir else get_settings().data_dir / "colors"
        self.colors_dir.mkdir(parents=True, exist_ok=True)
        self._load_system_schemes()

    def recommend_color_scheme(self, scenario: str) -> list[ColorRecommendation]:
        scenario_lower = scenario.lower()
        recommendations: list[ColorRecommendation] = []
        mapping = [
            ("business", ["报告", "商务", "汇报", "business", "report"], 0.9, ["business", "professional"]),
            ("tech", ["科技", "技术", "研发", "tech", "engineering"], 0.86, ["tech", "modern"]),
            ("education", ["培训", "教育", "课程", "education"], 0.82, ["education", "clear"]),
            ("creative", ["创意", "品牌", "营销", "creative", "brand"], 0.78, ["creative", "expressive"]),
        ]
        for category, keywords, confidence, tags in mapping:
            if any(keyword in scenario_lower for keyword in keywords):
                for scheme in self._get_schemes_by_category(category):
                    recommendations.append(
                        ColorRecommendation(
                            scheme_id=scheme.scheme_id,
                            confidence=confidence,
                            reason=f"适合{scenario}场景",
                            scenario_tags=tags,
                        )
                    )
        if not recommendations:
            recommendations = [
                ColorRecommendation(
                    scheme_id=scheme.scheme_id,
                    confidence=0.7,
                    reason="通用配色方案",
                    scenario_tags=["general"],
                )
                for scheme in self.list_schemes()
            ]
        return sorted(recommendations, key=lambda item: item.confidence, reverse=True)

    def create_custom_scheme(self, color_scheme: ColorScheme) -> ColorScheme:
        self._validate_scheme(color_scheme)
        color_scheme.is_system = False
        return self._save_scheme(color_scheme)

    def get_scheme(self, scheme_id: str) -> ColorScheme | None:
        scheme_file = self._scheme_path(scheme_id)
        if not scheme_file.exists():
            return None
        return ColorScheme.model_validate(json.loads(scheme_file.read_text(encoding="utf-8")))

    def list_schemes(self, category: str | None = None) -> list[ColorScheme]:
        schemes: list[ColorScheme] = []
        for scheme_file in sorted(self.colors_dir.glob("*.json")):
            scheme = ColorScheme.model_validate(json.loads(scheme_file.read_text(encoding="utf-8")))
            if category is None or scheme.category == category:
                schemes.append(scheme)
        return schemes

    def apply_scheme_to_style(self, scheme_id: str, base_style: dict | None = None) -> dict:
        scheme = self.get_scheme(scheme_id)
        if scheme is None:
            raise ValueError(f"Color scheme {scheme_id} not found")
        style = copy.deepcopy(base_style or load_style_profile())
        colors = style.setdefault("colors", {})
        colors.update(
            {
                "background": self._strip_hash(scheme.background_color),
                "title": self._strip_hash(scheme.text_color),
                "body": self._strip_hash(scheme.text_color),
                "primary": self._strip_hash(scheme.primary_color),
                "secondary": self._strip_hash(scheme.secondary_color),
                "accent": self._strip_hash(scheme.accent_color),
            }
        )
        return style

    def _load_system_schemes(self) -> None:
        schemes = [
            ColorScheme(
                scheme_id="business_blue",
                name="商务蓝",
                category="business",
                description="专业商务风格，适合报告和展示",
                primary_color="#2E86AB",
                secondary_color="#4A90E2",
                accent_color="#F18F01",
                background_color="#FFFFFF",
                text_color="#333333",
                additional_colors=["#50E3C2", "#B8E986"],
                is_system=True,
            ),
            ColorScheme(
                scheme_id="tech_green",
                name="科技绿",
                category="tech",
                description="现代技术风格，适合研发和产品说明",
                primary_color="#0F766E",
                secondary_color="#2563EB",
                accent_color="#F59E0B",
                background_color="#FFFFFF",
                text_color="#111827",
                additional_colors=["#14B8A6", "#60A5FA"],
                is_system=True,
            ),
            ColorScheme(
                scheme_id="education_purple",
                name="教学紫",
                category="education",
                description="清晰友好的培训和教学配色",
                primary_color="#6D28D9",
                secondary_color="#7C3AED",
                accent_color="#10B981",
                background_color="#FFFFFF",
                text_color="#1F2937",
                additional_colors=["#A78BFA", "#34D399"],
                is_system=True,
            ),
        ]
        for scheme in schemes:
            existing = self.get_scheme(scheme.scheme_id)
            if existing is None or existing.is_system:
                self._save_scheme(scheme)

    def _get_schemes_by_category(self, category: str) -> list[ColorScheme]:
        return [scheme for scheme in self.list_schemes() if scheme.category == category]

    def _validate_scheme(self, scheme: ColorScheme) -> None:
        for color in [
            scheme.primary_color,
            scheme.secondary_color,
            scheme.accent_color,
            scheme.background_color,
            scheme.text_color,
            *scheme.additional_colors,
        ]:
            self._validate_color_hex(color)

    @staticmethod
    def _validate_color_hex(hex_color: str) -> bool:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", hex_color):
            raise ValueError(f"Invalid color format: {hex_color}")
        return True

    def _save_scheme(self, scheme: ColorScheme) -> ColorScheme:
        self._validate_scheme(scheme)
        self._scheme_path(scheme.scheme_id).write_text(scheme.model_dump_json(indent=2), encoding="utf-8")
        return scheme

    def _scheme_path(self, scheme_id: str) -> Path:
        return self.colors_dir / f"{Path(scheme_id).name}.json"

    @staticmethod
    def _strip_hash(value: str) -> str:
        return value[1:] if value.startswith("#") else value
