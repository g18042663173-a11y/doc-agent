from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "demo-recording"
DEMO_DIR = ROOT / "samples" / "demo"
LOG_DIR = DEMO_DIR / "logs"
SCREENSHOT_DIR = DEMO_DIR / "screenshots"


def main() -> int:
    for directory in (OUTPUT_DIR, LOG_DIR, SCREENSHOT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    commands = {
        "success_word": [
            sys.executable,
            "scripts/demo_e2e.py",
            "samples/input/需求说明.docx",
            "--target",
            "word",
            "--generator",
            "stub",
            "--output-dir",
            "output/demo-recording/word",
        ],
        "success_deck": [
            sys.executable,
            "scripts/demo_e2e.py",
            "samples/input/项目汇报.pptx",
            "--target",
            "deck",
            "--generator",
            "stub",
            "--lint",
            "--output-dir",
            "output/demo-recording/deck",
        ],
        "failure_deck": [
            sys.executable,
            "-m",
            "app.cli.render",
            "--type",
            "deck",
            "samples/ir/deck_invalid_d003_unknown_layout.json",
            "--output",
            "output/demo-recording/invalid.pptx",
        ],
    }
    results = {name: _run(command) for name, command in commands.items()}
    if results["success_word"]["returncode"] != 0 or results["success_deck"]["returncode"] != 0:
        raise SystemExit("success demo command failed")
    if results["failure_deck"]["returncode"] == 0 or "D003" not in results["failure_deck"]["stderr"]:
        raise SystemExit("failure demo did not expose D003")

    for name, result in results.items():
        log = _format_log(name, result)
        (LOG_DIR / f"{name}.txt").write_text(log, encoding="utf-8")

    success_text = "\n\n".join(
        _format_log(name, results[name]) for name in ("success_word", "success_deck")
    )
    failure_text = _format_log("failure_deck", results["failure_deck"])
    _render_text_screenshot("Stub chains: success", success_text, SCREENSHOT_DIR / "success.png")
    _render_text_screenshot("Structured failure: D003", failure_text, SCREENSHOT_DIR / "failure.png")

    steps = """# 演示录屏操作清单

1. 在仓库根目录运行 `python scripts/record_demo.py`。
2. 展示 `samples/demo/screenshots/success.png`,说明 Word/Deck 两条 stub 链路均为 0 退出。
3. 打开 `samples/output/word/word_valid_03_table.docx`,确认文本和表格可编辑。
4. 打开 `samples/output/deck/deck_valid_full.pptx`,确认文本、表格、图表和形状可编辑。
5. 展示 `samples/demo/screenshots/failure.png`,确认非法 DeckIR 在渲染前以 D003 阻断。
6. 展示 `samples/output/deck/deck_lint_violation_report/report.json`,确认人工注入的合规违规被命中。
7. Windows 上重复打开 Office 产物并录屏;Mac 截图不替代字体和观感终审。
"""
    (DEMO_DIR / "recording_steps.md").write_text(steps, encoding="utf-8")
    _write_manifest(results)
    print("demo evidence generated")
    return 0


def _run(command: list[str]) -> dict[str, object]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    backend = str(ROOT / "backend")
    env["PYTHONPATH"] = backend if not existing else f"{backend}{os.pathsep}{existing}"
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "command": [_normalize_path(value) for value in command],
        "returncode": completed.returncode,
        "stdout": _normalize_path(completed.stdout.strip()),
        "stderr": _normalize_path(completed.stderr.strip()),
    }


def _format_log(name: str, result: dict[str, object]) -> str:
    command = " ".join(str(value) for value in result["command"])
    return "\n".join(
        [
            f"CASE: {name}",
            f"COMMAND: {command}",
            f"RETURN CODE: {result['returncode']}",
            "STDOUT:",
            str(result["stdout"]) or "<empty>",
            "STDERR:",
            str(result["stderr"]) or "<empty>",
            "",
        ]
    )


def _normalize_path(value: str) -> str:
    return value.replace(sys.executable, "<PYTHON>").replace(str(ROOT), "<REPO>")


def _render_text_screenshot(title: str, text: str, path: Path) -> None:
    width, height = 1600, 900
    image = Image.new("RGB", (width, height), "#181A1F")
    draw = ImageDraw.Draw(image)
    title_font = _font(34)
    body_font = _font(24)
    draw.rectangle((0, 0, width, 70), fill="#C7000B")
    draw.text((28, 18), title, fill="#FFFFFF", font=title_font)
    y = 92
    lines: list[str] = []
    for source_line in text.splitlines():
        wrapped = textwrap.wrap(source_line, width=92, replace_whitespace=False) or [""]
        lines.extend(wrapped)
    for line in lines[:26]:
        color = "#F85948" if "RETURN CODE: 1" in line or "D003" in line else "#F2F2F2"
        draw.text((30, y), line, fill=color, font=body_font)
        y += 30
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _font(size: int):
    candidates = [
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _write_manifest(results: dict[str, dict[str, object]]) -> None:
    assets = sorted([*LOG_DIR.glob("*.txt"), *SCREENSHOT_DIR.glob("*.png")])
    payload = {
        "schema_version": 1,
        "cases": {
            name: {"returncode": result["returncode"], "command": result["command"]}
            for name, result in results.items()
        },
        "assets": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in assets
        ],
    }
    (DEMO_DIR / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
