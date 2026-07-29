from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import html
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ElementTree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "output" / "qa"
ERROR_CODE_PATTERN = re.compile(r"\b(?:[ED]\d{3}|HW-[EWI]\d{2})\b")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the deterministic reliability gate and write QA artifacts.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--pytest-target",
        action="append",
        dest="pytest_targets",
        help="Pytest path to include; repeat to select multiple paths. Defaults to backend/tests.",
    )
    parser.add_argument("--skip-verify", action="store_true", help="Skip scripts/verify.py for a focused local run.")
    parser.add_argument("--ui", action="store_true", help="Run the optional Playwright workbench test.")
    parser.add_argument("--real-model", action="store_true", help="Run explicit Codex generator smoke tests.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    junit_path = output_dir / "pytest-junit.xml"
    gates: list[dict[str, Any]] = []

    if not args.skip_verify:
        gates.append(_run_gate("offline_verify", [sys.executable, "scripts/verify.py"]))

    targets = args.pytest_targets or ["backend/tests"]
    gates.append(
        _run_gate(
            "pytest",
            [sys.executable, "-m", "pytest", *targets, "-q", f"--junitxml={junit_path}"],
        )
    )

    if args.ui:
        gates.append(
            _run_gate(
                "workbench_ui",
                [sys.executable, "scripts/test_workbench_ui.py", "--output-dir", str(output_dir / "workbench-ui")],
            )
        )

    if args.real_model:
        gates.extend(_run_real_model_smoke(output_dir))

    junit = _read_junit(junit_path)
    failures = _safe_failures(junit["failures"])
    code_counts = Counter(code for failure in junit["failures"] for code in ERROR_CODE_PATTERN.findall(failure["message"]))
    gate_failed = any(gate["status"] == "failed" for gate in gates)
    report = {
        "qa_report_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "offline_release_gate": True,
        },
        "summary": {
            "pass": not gate_failed,
            "tests": junit["tests"],
            "passed": junit["passed"],
            "failed": junit["failed"],
            "skipped": junit["skipped"],
        },
        "gates": gates,
        "failures": failures,
        "error_code_counts": dict(sorted(code_counts.items())),
        "artifacts": {
            "junit": junit_path.name if junit_path.exists() else None,
            "html": "index.html",
        },
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(_render_html(report), encoding="utf-8")
    print(f"qa report: {report_path}")
    print(f"qa dashboard: {output_dir / 'index.html'}")
    return 1 if gate_failed else 0


def _run_gate(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_test_environment(),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "status": "passed" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "command": _display_command(command),
    }


def _run_real_model_smoke(output_dir: Path) -> list[dict[str, Any]]:
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("CODEX_GENERATOR_TRANSPORT")):
        return [
            {
                "name": "real_model",
                "status": "failed",
                "return_code": 2,
                "command": "not run",
                "reason": "未检测到 OPENAI_API_KEY 或 CODEX_GENERATOR_TRANSPORT，拒绝执行真实模型测试。",
            }
        ]

    sample = ROOT / "samples" / "input" / "parser_samples" / "md_sample_01.md"
    gates = []
    for target in ("word", "deck"):
        command = [
            sys.executable,
            "scripts/demo_e2e.py",
            str(sample),
            "--target",
            target,
            "--generator",
            "codex",
            "--output-dir",
            str(output_dir / "real-model" / target),
        ]
        if target == "deck":
            command.append("--lint")
        gates.append(_run_gate(f"real_model_{target}", command))
    return gates


def _test_environment() -> dict[str, str]:
    environment = os.environ.copy()
    backend = str(ROOT / "backend")
    previous = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = backend if not previous else f"{backend}{os.pathsep}{previous}"
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _read_junit(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"tests": 0, "passed": 0, "failed": 1, "skipped": 0, "failures": [{"name": "pytest-junit", "message": "JUnit 报告未生成。"}]}
    root = ElementTree.parse(path).getroot()
    cases = list(root.iter("testcase"))
    failures = []
    skipped = 0
    for case in cases:
        problem = case.find("failure")
        kind = "failure"
        if problem is None:
            problem = case.find("error")
            kind = "error"
        if case.find("skipped") is not None:
            skipped += 1
        if problem is not None:
            failures.append(
                {
                    "name": f"{case.get('classname', '')}::{case.get('name', '')}".strip(":"),
                    "message": _safe_text(problem.get("message") or problem.text or "测试失败"),
                    "kind": kind,
                }
            )
    failed = len(failures)
    return {
        "tests": len(cases),
        "passed": max(0, len(cases) - failed - skipped),
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def _safe_failures(failures: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "name": _safe_text(item["name"], limit=240),
            "kind": item.get("kind", "failure"),
            "error_codes": sorted(set(ERROR_CODE_PATTERN.findall(item["message"]))),
        }
        for item in failures
    ]


def _safe_text(value: str, *, limit: int = 500) -> str:
    return " ".join(value.replace("\x00", "").split())[:limit]


def _display_command(command: list[str]) -> str:
    return " ".join("<configured>" if "API_KEY" in item else item for item in command)


def _render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    gate_rows = "".join(
        f"<tr><td>{html.escape(gate['name'])}</td><td class=\"{html.escape(gate['status'])}\">{html.escape(gate['status'])}</td><td>{gate['return_code']}</td></tr>"
        for gate in report["gates"]
    )
    failure_rows = "".join(
        f"<tr><td>{html.escape(item['name'])}</td><td>{html.escape(item['kind'])}</td><td>{html.escape(', '.join(item['error_codes']) or '无错误码')}</td></tr>"
        for item in report["failures"]
    ) or "<tr><td colspan=\"3\">无失败用例</td></tr>"
    codes = ", ".join(f"{html.escape(code)}: {count}" for code, count in report["error_code_counts"].items()) or "无"
    outcome = "通过" if summary["pass"] else "失败"
    return f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>可靠性测试报告</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;margin:32px;color:#1f1f1f}}table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #d9d9d9;padding:8px;text-align:left}}th{{background:#f5f5f5}}.passed{{color:#18794e;font-weight:700}}.failed{{color:#b42318;font-weight:700}}</style></head>
<body><h1>可靠性测试报告：{outcome}</h1><p>生成时间：{html.escape(report['generated_at'])}</p>
<p>测试：{summary['tests']}，通过：{summary['passed']}，失败：{summary['failed']}，跳过：{summary['skipped']}</p>
<h2>门禁</h2><table><tr><th>名称</th><th>状态</th><th>退出码</th></tr>{gate_rows}</table>
<h2>错误码分布</h2><p>{codes}</p><h2>失败用例</h2><table><tr><th>用例</th><th>类型</th><th>错误码</th></tr>{failure_rows}</table>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
