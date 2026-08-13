"""Business-shaped corpus regression: parse determinism + stub end-to-end pipelines.

The corpus lives in samples/input/business/ and is generated deterministically by
scripts/make_business_samples.py. These are synthetic business-shaped files
(fictional, fully de-identified); samples/input/real/ remains the reserved place
for genuine de-identified corpus provided by the business side.

Covered per file:
1. parse determinism (two runs byte-identical) and structural sanity,
2. full stub word pipeline (parse -> prompt -> stub IR -> validate -> render -> lint),
3. full stub deck pipeline (same, plus visual plan and pptx lint).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.cli.parse import parse_file
from app.generators.interface import generator_from_name
from app.ir.deck_ir import DeckIR
from app.ir.repair import repair_ir_text
from app.ir.report import format_validation_result
from app.ir.word_ir import WordIR
from app.lint.docx_lint import check_docx
from app.lint.pptx_lint import check_pptx
from app.prompting.builder import build_prompt
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir
from app.visual.planner import build_visual_plan

ROOT = Path(__file__).resolve().parents[2]
BUSINESS_DIR = ROOT / "samples" / "input" / "business"

BUSINESS_FILES = sorted(
    path
    for path in BUSINESS_DIR.iterdir()
    if path.suffix.lower() in {".docx", ".xlsx", ".pptx"}
)

if not BUSINESS_FILES:  # pragma: no cover - fails loudly when corpus is missing
    raise AssertionError("business corpus missing; run scripts/make_business_samples.py")

EXPECTED_FORMAT = {".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx"}


@pytest.fixture(scope="module")
def stub_generator():
    return generator_from_name("stub")


@pytest.mark.parametrize("path", BUSINESS_FILES, ids=lambda p: p.name)
def test_business_parse_deterministic(path: Path) -> None:
    first = parse_file(path)
    second = parse_file(path)
    assert first.model_dump_json() == second.model_dump_json()
    assert first.source.format == EXPECTED_FORMAT[path.suffix.lower()]
    assert first.source.size_kb > 0
    assert first.stats.headings + first.stats.paragraphs + first.stats.tables > 0
    if path.suffix.lower() == ".docx":
        assert first.content.blocks
    elif path.suffix.lower() == ".xlsx":
        assert first.content.sheets
    else:
        assert first.content.slides


@pytest.mark.parametrize("path", BUSINESS_FILES, ids=lambda p: p.name)
def test_business_word_pipeline(path: Path, tmp_path: Path, stub_generator) -> None:
    document_ir = parse_file(path)
    prompt = build_prompt(
        kind="word",
        context=document_ir,
        max_context_chars=12000,
        max_output_chars=6000,
    )
    raw_ir = stub_generator.generate(prompt, target="word_ir")
    validation = repair_ir_text(raw_ir, target="word_ir", generator=stub_generator)
    assert validation.ok, format_validation_result(validation)
    word_ir = WordIR.model_validate(validation.value)
    artifact = render_word_ir(word_ir, tmp_path / "word.docx")
    assert artifact.exists() and artifact.stat().st_size > 0
    report = check_docx(artifact, classification=word_ir.meta.classification)
    assert report.summary["errors"] == 0, report.to_dict()


@pytest.mark.parametrize("path", BUSINESS_FILES, ids=lambda p: p.name)
def test_business_deck_pipeline(path: Path, tmp_path: Path, stub_generator) -> None:
    document_ir = parse_file(path)
    visual_plan = build_visual_plan(document_ir, None)
    prompt = build_prompt(
        kind="deck",
        context=document_ir,
        max_context_chars=12000,
        max_output_chars=6000,
        visual_plan=visual_plan,
    )
    raw_ir = stub_generator.generate(prompt, target="deck_ir")
    validation = repair_ir_text(raw_ir, target="deck_ir", generator=stub_generator)
    assert validation.ok, format_validation_result(validation)
    deck_ir = DeckIR.model_validate(validation.value)
    artifact = render_deck_ir(deck_ir, tmp_path / "deck.pptx")
    assert artifact.exists() and artifact.stat().st_size > 0
    report = check_pptx(
        artifact,
        classification=deck_ir.meta.classification,
        theme_name=deck_ir.meta.theme,
    )
    assert report.summary["errors"] == 0, report.to_dict()


def test_business_corpus_inventory() -> None:
    """The corpus must keep one file per format so coverage cannot silently shrink."""
    by_format = {fmt: 0 for fmt in ("docx", "xlsx", "pptx")}
    for path in BUSINESS_FILES:
        by_format[EXPECTED_FORMAT[path.suffix.lower()]] += 1
    assert by_format == {"docx": 3, "xlsx": 3, "pptx": 3}
