"""命名主题预设：三套主题加载/渲染/校验 + 入口白名单。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.generation.depth import GenerationOptions, generate_deck
from app.generators.stub import StubGenerator
from app.ir.document_ir import DocumentIR
from app.lint.pptx_lint import check_pptx
from app.prompting.builder import build_prompt
from app.rendering.theme import UnknownThemeError, load_theme, resolve_theme
from app.rendering.pptx_renderer import render_deck_ir

NAMED_THEMES = ["hw-report", "hw-proposal", "hw-academic"]


def _document() -> DocumentIR:
    return DocumentIR.model_validate(
        json.load(open("samples/ir/document_valid_01_md_summary.json", encoding="utf-8"))
    )


@pytest.mark.parametrize("name", NAMED_THEMES)
def test_named_themes_load_with_complete_structure(name: str) -> None:
    theme = load_theme(name)
    base = load_theme("hw_v1")
    required_keys = set(base.keys()) | {"style_guide"}
    assert set(theme.keys()) >= required_keys - {"style_guide"}
    assert theme["name"] == name
    assert theme["style_guide"], f"{name} must carry a style guide"


def test_theme_registry_whitelist() -> None:
    assert resolve_theme("hw_v1") == "hw_v1"
    assert resolve_theme("hw-report") == "hw-report"
    with pytest.raises(UnknownThemeError):
        resolve_theme("not-a-theme")


@pytest.mark.parametrize(
    "malicious",
    [
        "../secret",
        "../../etc/passwd",
        "..\\..\\windows\\win.ini",
        "themes/../hw_v1",
        "hw_v1/../../hw-report",
    ],
)
def test_load_theme_rejects_path_traversal(malicious: str) -> None:
    """Theme names must resolve through the registry, never touch the filesystem
    outside the themes directory (path-traversal / arbitrary .json read)."""
    with pytest.raises(UnknownThemeError):
        load_theme(malicious)


@pytest.mark.parametrize("name", NAMED_THEMES)
def test_generate_deck_overrides_meta_theme(name: str) -> None:
    attempt = generate_deck(
        _document(),
        generator=StubGenerator(),
        options=GenerationOptions(depth="概览", theme=name),
    )
    assert attempt.validation.ok
    assert attempt.validation.value.meta.theme == name
    assert f'"theme": "{name}"' in attempt.raw_text


def test_default_theme_remains_hw_v1() -> None:
    attempt = generate_deck(
        _document(),
        generator=StubGenerator(),
        options=GenerationOptions(depth="概览"),
    )
    assert attempt.validation.value.meta.theme == "hw_v1"


def test_named_theme_renders_pptx(name: str = "hw-academic") -> None:
    attempt = generate_deck(
        _document(),
        generator=StubGenerator(),
        options=GenerationOptions(depth="概览", theme=name),
    )
    deck = attempt.validation.value
    path = render_deck_ir(deck, Path("output") / f"theme-{name}-test.pptx")
    assert path.exists()
    assert path.stat().st_size > 0


def test_named_theme_lint_uses_own_palette() -> None:
    """主题色板差异（如 hw-academic 的 #1F4E79 锚点）不应被复检误报为色板外颜色。"""
    attempt = generate_deck(
        _document(),
        generator=StubGenerator(),
        options=GenerationOptions(depth="概览", theme="hw-academic"),
    )
    deck = attempt.validation.value
    path = render_deck_ir(deck, Path("output") / "theme-hw-academic-lint-test.pptx")
    report = check_pptx(path, classification=deck.meta.classification, theme_name=deck.meta.theme)
    off_palette = [item for item in report.items if item.code == "HW-W02" and "1F4E79" in item.message]
    assert not off_palette


@pytest.mark.parametrize("name", NAMED_THEMES)
def test_prompt_injects_theme_style_guide(name: str) -> None:
    prompt = build_prompt(kind="deck", context=_document(), depth="标准", pages=11, theme=name)
    assert f"[主题风格 {name}]" in prompt


def test_default_prompt_has_no_theme_section() -> None:
    prompt = build_prompt(kind="deck", context=_document(), depth="标准", pages=11)
    assert "[主题风格" not in prompt


def test_prompt_unknown_theme_has_no_style_guide_section() -> None:
    """Unknown/traversal theme names must not inject any file content into the prompt."""
    prompt = build_prompt(kind="deck", context=_document(), depth="标准", pages=11, theme="../secret")
    assert "[主题风格" not in prompt
    assert "style_guide" not in prompt


def test_generation_options_rejects_bad_theme() -> None:
    with pytest.raises(ValidationError):
        GenerationOptions(depth="概览", theme="x" * 65)
