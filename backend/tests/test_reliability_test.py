from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def test_reliability_entrypoint_writes_json_junit_and_html(tmp_path: Path) -> None:
    output_dir = tmp_path / "qa"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/reliability_test.py",
            "--skip-verify",
            "--pytest-target",
            "backend/tests/test_web_api_static.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["pass"] is True
    assert report["summary"]["tests"] == 1
    assert report["gates"][0]["name"] == "pytest"
    assert (output_dir / "pytest-junit.xml").is_file()
    assert "可靠性测试报告：通过" in (output_dir / "index.html").read_text(encoding="utf-8")


def test_visual_diff_passes_identical_images_and_rejects_a_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    Image.new("RGB", (12, 12), "white").save(baseline / "slide1.png")
    Image.new("RGB", (12, 12), "white").save(candidate / "slide1.png")
    output = tmp_path / "visual-pass.json"

    passed = subprocess.run(
        [
            sys.executable,
            "scripts/visual_diff.py",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert passed.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["pass"] is True
    Image.new("RGB", (12, 12), "black").save(candidate / "slide1.png")
    failed = subprocess.run(
        [
            sys.executable,
            "scripts/visual_diff.py",
            "--baseline",
            str(baseline),
            "--candidate",
            str(candidate),
            "--output",
            str(tmp_path / "visual-fail.json"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert failed.returncode == 1


def test_reliability_junit_reader_counts_failure_elements(tmp_path: Path) -> None:
    module = _load_reliability_module()
    junit = tmp_path / "failure.xml"
    junit.write_text(
        '<testsuites><testsuite><testcase classname="suite" name="case"><failure message="D001 invalid" /></testcase></testsuite></testsuites>',
        encoding="utf-8",
    )

    result = module._read_junit(junit)
    public = module._safe_failures(result["failures"])

    assert result["failed"] == 1
    assert public == [{"name": "suite::case", "kind": "failure", "error_codes": ["D001"]}]


def test_reliability_environment_prepends_discovered_graphviz(monkeypatch, tmp_path: Path) -> None:
    module = _load_reliability_module()
    graphviz_bin = tmp_path / "graphviz" / "bin"
    graphviz_bin.mkdir(parents=True)
    monkeypatch.setattr(module, "_graphviz_runtime_bin", lambda: graphviz_bin)
    monkeypatch.setenv("PATH", "existing-path")

    environment = module._test_environment()

    assert environment["PATH"].split(os.pathsep)[0] == str(graphviz_bin)


def _load_reliability_module():
    path = ROOT / "scripts" / "reliability_test.py"
    spec = importlib.util.spec_from_file_location("reliability_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
