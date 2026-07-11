from __future__ import annotations

from io import BytesIO
import json
import re
from pathlib import Path
from typing import Literal

from app.web import create_app


def test_web_upload_generates_deck_download_and_report(tmp_path: Path) -> None:
    app = create_app(work_dir=tmp_path)
    client = app.test_client()

    response = client.post(
        "/",
        data={
            "target": "deck",
            "input_file": (
                BytesIO("# 周报\n\n- 完成台账清理\n- 下周推进汇报材料\n".encode("utf-8")),
                "周报.md",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "合规检查报告" in html
    assert "Error" in html
    assert "Warning" in html
    assert "Info" in html

    download = client.get(_download_href(html))
    assert download.status_code == 200
    assert download.data[:2] == b"PK"
    assert "deck.pptx" in download.headers["Content-Disposition"]


def test_web_topic_generates_word_download_and_report(tmp_path: Path) -> None:
    app = create_app(work_dir=tmp_path)
    client = app.test_client()

    response = client.post(
        "/",
        data={"target": "word", "topic_text": "请生成一份项目周报，包含风险、进展和下周计划。"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "合规检查报告" in html
    assert "下载产物" in html

    download = client.get(_download_href(html))
    assert download.status_code == 200
    assert download.data[:2] == b"PK"
    assert "word.docx" in download.headers["Content-Disposition"]


def test_web_invalid_generated_ir_falls_back_to_manual_fix(tmp_path: Path) -> None:
    app = create_app(work_dir=tmp_path, generator=AlwaysInvalidGenerator())
    client = app.test_client()

    failed = client.post(
        "/",
        data={"target": "word", "topic_text": "生成一份需要人工修正兜底的周报。"},
    )

    assert failed.status_code == 200
    failed_html = failed.get_data(as_text=True)
    assert "IR 校验失败" in failed_html
    assert "name=\"manual_ir\"" in failed_html

    fixed = client.post(
        "/",
        data={
            "target": "word",
            "manual_ir": json.dumps(
                {
                    "ir_type": "word",
                    "ir_version": "1.0",
                    "meta": {"title": "人工修正周报", "classification": "内部公开"},
                    "blocks": [{"type": "paragraph", "text": "人工修正后的正文。"}],
                },
                ensure_ascii=False,
            ),
        },
    )

    assert fixed.status_code == 200
    download = client.get(_download_href(fixed.get_data(as_text=True)))
    assert download.status_code == 200
    assert download.data[:2] == b"PK"


class AlwaysInvalidGenerator:
    name = "invalid"

    def generate(self, prompt: str, *, target: Literal["word_ir", "deck_ir"]) -> str:
        _ = prompt
        if target == "word_ir":
            return '{"ir_type":"word","ir_version":"1.0","meta":{"title":"坏"},"blocks":[]}'
        return '{"ir_type":"deck","ir_version":"1.1","meta":{"title":"坏"},"slides":[]}'


def _download_href(html: str) -> str:
    match = re.search(r'href="(/download/[^"]+)"', html)
    assert match is not None
    return match.group(1)
