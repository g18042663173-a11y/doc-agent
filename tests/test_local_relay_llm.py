from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docx import Document

from doc_agent.config import Settings, normalize_llm_provider
from doc_agent.llm import LocalRelayLLMClient, get_llm_client
from doc_agent.llm.local_relay_client import request as relay_request
from doc_agent.workflow import run_generate


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_local_relay_provider_aliases() -> None:
    assert normalize_llm_provider("relay") == "local_relay"
    assert normalize_llm_provider("http_relay") == "local_relay"
    assert normalize_llm_provider("local_api") == "local_relay"
    assert normalize_llm_provider("local_gateway") == "local_relay"
    assert isinstance(get_llm_client(Settings(llm_provider="local_relay")), LocalRelayLLMClient)


def test_local_relay_client_posts_prompt_and_extracts_wrapped_json(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_urlopen(req, timeout):
        calls["url"] = req.full_url
        calls["timeout"] = timeout
        calls["auth"] = req.get_header("Authorization")
        calls["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse({"json": {"title": "Relay Word", "blocks": []}})

    monkeypatch.setattr(relay_request, "urlopen", fake_urlopen)
    client = LocalRelayLLMClient(
        Settings(
            llm_provider="local_relay",
            llm_base_url="http://127.0.0.1:8765/v1",
            llm_api_key="token",
            llm_model="glm-4.7",
            llm_timeout_seconds=9,
        )
    )

    result = client.generate_json("生成 WordIR")

    assert result["title"] == "Relay Word"
    assert calls["url"] == "http://127.0.0.1:8765/v1/generate_json"
    assert calls["timeout"] == 9
    assert calls["auth"] == "Bearer token"
    assert calls["body"]["prompt"] == "生成 WordIR"
    assert calls["body"]["model"] == "glm-4.7"


def test_local_relay_client_accepts_openai_like_response(monkeypatch) -> None:
    def fake_urlopen(req, timeout):
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"deck_title":"Relay Deck","slides":[]}',
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(relay_request, "urlopen", fake_urlopen)
    client = LocalRelayLLMClient(Settings(llm_provider="local_relay", llm_base_url="http://127.0.0.1:8765/v1/generate_json"))

    assert client.generate_json("生成 DeckIR") == {"deck_title": "Relay Deck", "slides": []}


def test_workflow_can_generate_docx_through_local_relay(tmp_path: Path, monkeypatch) -> None:
    def fake_urlopen(req, timeout):
        return _FakeResponse(
            {
                "json": {
                    "title": "Relay Agent Report",
                    "subtitle": "local relay",
                    "blocks": [
                        {"type": "heading", "text": "摘要", "level": 1},
                        {"type": "paragraph", "text": "主 Agent 已通过本地中转站生成 WordIR。"},
                    ],
                }
            }
        )

    monkeypatch.setattr(relay_request, "urlopen", fake_urlopen)
    source = tmp_path / "input.md"
    source.write_text("# Relay Agent\n\n这是一次本地中转站测试。", encoding="utf-8")

    output = run_generate(
        source,
        "docx",
        tmp_path / "relay.docx",
        settings=Settings(llm_provider="local_relay", llm_base_url="http://127.0.0.1:8765/v1"),
    )

    text = "\n".join(paragraph.text for paragraph in Document(str(output)).paragraphs)
    assert "Relay Agent Report" in text
    assert "主 Agent 已通过本地中转站生成 WordIR" in text
