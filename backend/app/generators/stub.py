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
                    {"layout": "section", "index": 1, "title": "主链路"},
                    {
                        "layout": "title_bullets",
                        "title": "关键能力",
                        "bullets": [
                            {"text": "解析输入文件为 DocumentIR", "level": 1},
                            {"text": "stub 通道支持离线验收", "level": 1}
                        ]
                    },
                    {
                        "layout": "table",
                        "title": "验收信号",
                        "table": {
                            "header": ["环节", "状态"],
                            "rows": [["Schema", "冻结"], ["DOCX", "可渲染"], ["PPTX", "可渲染"]]
                        }
                    },
                    {"layout": "conclusion", "title": "结论", "bullets": ["主链路保持确定性"], "cta": "继续接入真实 generator"}
                ],
            }
        else:
            raise ValueError(f"unsupported target: {target}")

        return json.dumps(payload, ensure_ascii=False, indent=2)
