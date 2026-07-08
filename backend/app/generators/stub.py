from __future__ import annotations

import json
from typing import Literal


class StubGenerator:
    name = "stub"

    def generate(self, prompt: str, *, target: Literal["word_ir", "deck_ir"]) -> str:
        if target == "word_ir":
            payload = {
                "ir_type": "word",
                "ir_version": "1.0",
                "meta": {"title": "Stub 文档", "classification": "内部公开"},
                "blocks": [
                    {"type": "heading", "level": 1, "text": "Stub 输出"},
                    {"type": "paragraph", "text": "这是 C0 空链路的确定性 WordIR。"},
                ],
            }
        elif target == "deck_ir":
            payload = {
                "ir_type": "deck",
                "ir_version": "1.1",
                "meta": {"title": "Stub 演示", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
                "slides": [
                    {"layout": "cover", "title": "Stub 演示", "subtitle": "C0 空链路"},
                    {"layout": "agenda", "items": ["IR", "Schema", "Verify"]},
                ],
            }
        else:
            raise ValueError(f"unsupported target: {target}")

        return json.dumps(payload, ensure_ascii=False, indent=2)
