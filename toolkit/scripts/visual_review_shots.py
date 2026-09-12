"""开发专用：截取工作台 UI 多状态截图，供视觉审阅使用。

用法：.venv\\Scripts\\python.exe scripts/visual_review_shots.py [--output-dir DIR]
不进入交付物；仅产出 PNG 到 output/visual-review/。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.generators.stub import StubGenerator
from app.web_api import create_api_app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "visual-review")
    parser.add_argument("--channel", default="chrome")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    workspace = output_dir / "jobs"
    app = create_api_app(work_dir=workspace, generator=StubGenerator())
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/static/index.html"

    fixture = output_dir / "fixture.md"
    fixture.write_text(
        "# 智能制造产线升级方案\n\n## 项目背景\n\n- 产线自动化率不足\n- 数据采集分散\n\n## 目标\n\n1. 自动化率提升至 85%\n2. 建立统一数据平台\n\n## 里程碑\n\n| 阶段 | 时间 | 交付 |\n| --- | --- | --- |\n| 一期 | Q1 | 试点产线 |\n| 二期 | Q2 | 全面推广 |\n",
        encoding="utf-8",
    )

    shots: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=args.channel)

        def snap(page, name: str, full: bool = True) -> None:
            path = output_dir / f"{name}.png"
            page.screenshot(path=str(path), full_page=full)
            shots.append(path.name)
            print(f"shot: {path.name}")

        # --- 桌面 1440 ---
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(base, wait_until="networkidle")
        page.get_by_test_id("service-status").get_by_text("本地服务").wait_for(timeout=5000)
        snap(page, "01-desktop-empty")

        page.get_by_test_id("input-file").set_input_files(str(fixture))
        page.wait_for_timeout(300)
        snap(page, "02-desktop-file")

        # 分析面板
        page.get_by_test_id("analyze-button").click()
        page.wait_for_timeout(1200)
        snap(page, "03-desktop-analysis")

        # 生成成功（标准 PPT）
        page.get_by_test_id("generate-button").click()
        page.locator('[data-testid="result-panel"].result--success').wait_for(state="visible", timeout=30000)
        page.wait_for_timeout(400)
        snap(page, "04-desktop-success")

        # 设置面板展开
        page.get_by_test_id("generator-settings").locator("summary").click()
        page.wait_for_timeout(200)
        snap(page, "05-desktop-settings")

        # HTTP 传输方式（显示全部字段）
        page.get_by_test_id("nga-transport").select_option("http")
        page.wait_for_timeout(200)
        snap(page, "06-desktop-settings-http")
        page.get_by_test_id("nga-transport").select_option("cli")

        # 主题选择下拉（学术版色板）
        page.locator("#themeSelect").select_option("hw-academic")
        page.wait_for_timeout(200)
        snap(page, "07-desktop-theme-academic", full=False)
        page.locator("#themeSelect").select_option("hw_v1")

        # 进度状态（触发一次生成并立即截图）
        page.get_by_test_id("generate-button").click()
        page.get_by_test_id("progress-panel").wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(120)
        snap(page, "08-desktop-progress", full=False)
        page.locator('[data-testid="result-panel"].result--success').wait_for(state="visible", timeout=30000)

        # Word 类型（主题/深度禁用态）
        page.get_by_test_id("type-word").click()
        page.wait_for_timeout(200)
        snap(page, "11-desktop-word-mode", full=False)
        page.get_by_test_id("type-deck").click()

        # 失败诊断视觉（DOM 注入，仅审样式）
        page.evaluate("""() => {
          const panel = document.getElementById('resultPanel');
          panel.className = 'section result result--error is-visible';
          document.getElementById('resultTitle').textContent = '生成失败';
          document.getElementById('resultDetail').textContent = '第 1 页：模板包含不安全的 OLE 嵌入对象。';
          const diag = document.getElementById('failureDiagnostic');
          diag.hidden = false;
          document.getElementById('failureCode').textContent = 'E003';
          document.getElementById('failureStage').textContent = '定位：template_file';
          document.getElementById('failureSuggestion').textContent = '请在 PowerPoint 中删除嵌入对象，或替换为 PNG 图片后重新上传。';
          document.getElementById('failureSupport').textContent = '如仍无法解决，请下载失败报告并联系支持。';
          const link = document.getElementById('failureReportLink');
          link.hidden = false; link.href = '#';
          panel.scrollIntoView({ block: 'center' });
        }""")
        page.wait_for_timeout(200)
        snap(page, "12-desktop-failure", full=False)
        page.close()

        # --- 浅色模式 ---
        light = browser.new_page(viewport={"width": 1440, "height": 900})
        light.goto(base, wait_until="networkidle")
        light.get_by_test_id("service-status").get_by_text("本地服务").wait_for(timeout=5000)
        light.get_by_test_id("theme-toggle").click()
        light.wait_for_timeout(300)
        snap(light, "13-desktop-light")
        light.close()

        # --- 移动 390 ---
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(base, wait_until="networkidle")
        mobile.get_by_test_id("service-status").get_by_text("本地服务").wait_for(timeout=5000)
        snap(mobile, "09-mobile-empty")
        mobile.get_by_test_id("input-file").set_input_files(str(fixture))
        mobile.wait_for_timeout(300)
        mobile.get_by_test_id("generator-settings").locator("summary").click()
        mobile.wait_for_timeout(200)
        snap(mobile, "10-mobile-file-settings")
        mobile.close()

        browser.close()

    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    print(f"done: {len(shots)} shots -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
