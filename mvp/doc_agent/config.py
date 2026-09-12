from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at import time
    load_dotenv = None

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


DEFAULT_STYLE_PROFILE: dict[str, Any] = {
    "brand": {"name": "demo_company", "slide_size": "16:9", "logo_path": None},
    "fonts": {"zh": "Microsoft YaHei", "en": "Arial"},
    "colors": {
        "background": "FFFFFF",
        "title": "111827",
        "body": "374151",
        "muted": "6B7280",
        "primary": "1F4E79",
        "secondary": "5B9BD5",
        "accent": "C55A11",
        "white": "FFFFFF",
    },
    "ppt_rules": {
        "max_slides": 12,
        "min_slides": 5,
        "max_title_chars": 28,
        "max_bullets_per_slide": 5,
        "max_chars_per_bullet": 32,
        "allowed_layouts": [
            "cover",
            "agenda",
            "section",
            "title_bullets",
            "two_column",
            "table",
            "cards",
            "chart",
            "image",
            "conclusion",
        ],
        "forbidden_phrases": ["作为AI模型", "作为 AI 模型", "我不能", "无法提供"],
    },
    "docx_rules": {
        "heading_1_size": 18,
        "heading_2_size": 15,
        "heading_3_size": 13,
        "body_size": 11,
        "use_numbered_headings": True,
        "max_paragraph_chars": 500,
    },
}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "stub"
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "glm-4.7"
    llm_timeout_seconds: int = 120
    ppt_renderer: str = "stub"
    ppt_compliance_gate: str = "warn"
    use_langgraph: bool = False
    soffice_path: str | None = None
    pdftoppm_path: str | None = None
    default_target_slides: int = 8
    max_input_chars: int = 60000
    max_repair_attempts: int = 2
    style_profile: Path = PROJECT_ROOT / "doc_agent" / "styles" / "style_profile.yaml"
    template_pptx: Path = PROJECT_ROOT / "templates" / "company_template.pptx"
    reference_docx: Path = PROJECT_ROOT / "templates" / "reference.docx"
    data_dir: Path = PROJECT_ROOT / "data"
    output_dir: Path = PROJECT_ROOT / "outputs"
    log_dir: Path = PROJECT_ROOT / "data" / "logs"
    log_level: str = "INFO"
    save_debug_artifacts: bool = True


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _path_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default
    path = Path(raw)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def normalize_llm_provider(provider: str | None) -> str:
    value = (provider or "stub").strip().lower()
    aliases = {
        "mock": "stub",
        "local": "stub",
        "relay": "local_relay",
        "http_relay": "local_relay",
        "local_api": "local_relay",
        "local_gateway": "local_relay",
    }
    return aliases.get(value, value)


def normalize_ppt_renderer(renderer: str | None) -> str:
    value = (renderer or "stub").strip().lower()
    aliases = {
        "python_pptx": "stub",
        "python-pptx": "stub",
        "local": "stub",
    }
    return aliases.get(value, value)


def normalize_compliance_gate(gate: str | None) -> str:
    value = (gate or "warn").strip().lower()
    return value if value in {"off", "warn", "error"} else "warn"


def get_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)

    return Settings(
        llm_provider=normalize_llm_provider(os.getenv("LLM_PROVIDER", "stub")),
        llm_base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:8000/v1"),
        llm_api_key=os.getenv("LLM_API_KEY", "EMPTY"),
        llm_model=os.getenv("LLM_MODEL", "glm-4.7"),
        llm_timeout_seconds=_int_env("LLM_TIMEOUT_SECONDS", 120),
        ppt_renderer=normalize_ppt_renderer(os.getenv("PPT_RENDERER", "stub")),
        ppt_compliance_gate=normalize_compliance_gate(os.getenv("PPT_COMPLIANCE_GATE", "warn")),
        use_langgraph=_bool_env("USE_LANGGRAPH", False),
        soffice_path=os.getenv("SOFFICE_PATH") or None,
        pdftoppm_path=os.getenv("PDFTOPPM_PATH") or None,
        default_target_slides=_int_env("DEFAULT_TARGET_SLIDES", 8),
        max_input_chars=_int_env("MAX_INPUT_CHARS", 60000),
        max_repair_attempts=_int_env("MAX_REPAIR_ATTEMPTS", 2),
        style_profile=_path_env("STYLE_PROFILE", PROJECT_ROOT / "doc_agent" / "styles" / "style_profile.yaml"),
        template_pptx=_path_env("TEMPLATE_PPTX", PROJECT_ROOT / "templates" / "company_template.pptx"),
        reference_docx=_path_env("REFERENCE_DOCX", PROJECT_ROOT / "templates" / "reference.docx"),
        data_dir=_path_env("DATA_DIR", PROJECT_ROOT / "data"),
        output_dir=_path_env("OUTPUT_DIR", PROJECT_ROOT / "outputs"),
        log_dir=_path_env("LOG_DIR", PROJECT_ROOT / "data" / "logs"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        save_debug_artifacts=_bool_env("SAVE_DEBUG_ARTIFACTS", True),
    )


def load_style_profile(path: str | Path | None = None) -> dict[str, Any]:
    profile_path = Path(path) if path else get_settings().style_profile
    if not profile_path.is_absolute():
        profile_path = PROJECT_ROOT / profile_path
    if not profile_path.exists():
        return DEFAULT_STYLE_PROFILE.copy()

    loaded = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    merged = DEFAULT_STYLE_PROFILE.copy()
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged
