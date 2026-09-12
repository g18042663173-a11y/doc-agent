from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _assessment_module():
    path = ROOT / "experiments" / "html2pptx" / "assessment.py"
    spec = importlib.util.spec_from_file_location("html2pptx_assessment", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _benchmark_module():
    path = ROOT / "scripts" / "html2pptx_benchmark.py"
    spec = importlib.util.spec_from_file_location("html2pptx_benchmark", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _engine(*, hard_pass: bool, score: int, visual_review: str = "approved") -> dict:
    return {
        "hard_gates": {
            "schema_valid": hard_pass,
            "package_valid": hard_pass,
            "lint_clean": hard_pass,
            "no_layout_issues": hard_pass,
            "office_opened": hard_pass,
            "native_editability": hard_pass,
        },
        "scores": {
            "visual_hierarchy": score,
            "chinese_typography": score,
            "template_fidelity": score,
            "deployment_reliability": score,
        },
        "visual_review": visual_review,
    }


def test_assessment_keeps_python_when_html_fails_a_template_hard_gate() -> None:
    module = _assessment_module()
    report = module.assess_engines(
        [
            {"name": "standard", "template_case": False, "python": _engine(hard_pass=True, score=4), "html": _engine(hard_pass=True, score=5)},
            {"name": "hit-template", "template_case": True, "python": _engine(hard_pass=True, score=4), "html": _engine(hard_pass=False, score=5)},
        ]
    )

    assert report["recommendation"] == "keep_python"
    assert report["html"]["hard_gate_pass"] is False


def test_assessment_requires_15_percent_advantage_and_human_visual_evidence() -> None:
    module = _assessment_module()
    cases = [
        {"name": "standard", "template_case": False, "python": _engine(hard_pass=True, score=4), "html": _engine(hard_pass=True, score=5)},
        {"name": "template", "template_case": True, "python": _engine(hard_pass=True, score=4), "html": _engine(hard_pass=True, score=5)},
    ]

    candidate = module.assess_engines(cases)
    pending = module.assess_engines([{**case, "html": {**case["html"], "visual_review": "pending"}} for case in cases])

    assert candidate["recommendation"] == "candidate_for_review"
    assert candidate["html_score_advantage"] >= 0.15
    assert pending["recommendation"] == "expand_html_experiment"


@pytest.mark.skipif(
    shutil.which("node") is None or not (ROOT / "experiments" / "html2pptx" / "node_modules" / "pptxgenjs").exists(),
    reason="isolated Node experiment dependencies are not installed",
)
def test_isolated_html_benchmark_uses_validated_deck_ir_and_keeps_python_default(tmp_path: Path) -> None:
    module = _benchmark_module()
    args = module.build_parser().parse_args(
        [
            "--deck-ir",
            str(ROOT / "samples" / "ir" / "deck_engine_benchmark_core.json"),
            "--output-dir",
            str(tmp_path / "benchmark"),
            "--skip-office",
        ]
    )

    result = module.run_benchmark(args)

    assert result["production_engine"] == "python-pptx"
    assert result["recommendation"] == "expand_html_experiment"
    assert (tmp_path / "benchmark" / "deck_engine_benchmark_core" / "python" / "deck.pptx").is_file()
    assert (tmp_path / "benchmark" / "deck_engine_benchmark_core" / "html" / "deck.pptx").is_file()
    case = result["cases"][0]
    assert len(case["python"]["artifact_sha256"]) == 64
    assert len(case["html"]["artifact_sha256"]) == 64
    assert case["html"]["hard_gates"]["no_layout_issues"] is True
    assert case["html"]["html_render"]["slides"][0]["html_validation"]["body_overflow"] is False
    assert len(case["html"]["html_render"]["slides"][0]["html_sha256"]) == 64
    assert result["engine_versions"]["python_pptx"]
    assert result["engine_versions"]["html_pptxgenjs"] == "4.0.1"
