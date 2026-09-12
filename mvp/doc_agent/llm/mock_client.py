from __future__ import annotations

import re
from typing import Any

from doc_agent.ir.schemas import CardIR, ChartIR, ChartSeriesIR, DeckIR, DocumentIR, SlideIR, VisualIR, WordBlockIR, WordIR
from doc_agent.llm.base import BaseLLMClient
from doc_agent.utils.json_utils import extract_json_from_text
from doc_agent.utils.text_utils import first_non_empty, normalize_space, truncate_text


class MockLLMClient(BaseLLMClient):
    def generate_json(self, prompt: str) -> dict[str, Any]:
        document = self._document_from_prompt(prompt)
        if "WordIR" in prompt or "word_ir" in prompt or "DOCX" in prompt:
            return self._word_ir(document).model_dump(mode="json")
        target_slide_count = self._target_slide_count(prompt)
        return self._deck_ir(document, target_slide_count).model_dump(mode="json")

    def _document_from_prompt(self, prompt: str) -> DocumentIR:
        try:
            data = extract_json_from_text(prompt)
            if "source_file" in data and "blocks" in data:
                return DocumentIR.model_validate(data)
        except Exception:
            pass
        return DocumentIR(source_file="unknown", source_type="unknown", title="未命名文档")

    @staticmethod
    def _target_slide_count(prompt: str) -> int:
        match = re.search(r"目标页数\s*[:：]?\s*(\d+)", prompt)
        if not match:
            return 6
        return min(max(int(match.group(1)), 5), 12)

    def _deck_ir(self, document: DocumentIR, target_slide_count: int) -> DeckIR:
        title = truncate_text(document.title, 28, "未命名文档")
        topics = self._topics(document)
        bullets = [truncate_text(topic, 32) for topic in topics[:5]] or ["信息已整理", "结构可复用", "输出可编辑"]

        slides: list[SlideIR] = [
            SlideIR(layout="cover", title=title, subtitle="内部汇报"),
            SlideIR(layout="agenda", title="目录", bullets=bullets[:5]),
            SlideIR(layout="section", title="核心方案"),
        ]

        content_slots = max(target_slide_count - 4, 1)
        for slot in range(content_slots):
            if slot == 0:
                slides.append(
                    SlideIR(
                        layout="title_bullets",
                        title=self._content_title(topics, slot, "方案重点"),
                        bullets=bullets[:5],
                    )
                )
            elif slot == 1:
                slides.append(
                    SlideIR(
                        layout="two_column",
                        title=self._content_title(topics, slot, "能力拆解"),
                        left_title="输入侧",
                        left_bullets=bullets[:3],
                        right_title="输出侧",
                        right_bullets=(bullets[2:5] or bullets[:3]),
                    )
                )
            elif target_slide_count >= 8 and slot % 4 == 2:
                slides.append(
                    SlideIR(
                        layout="cards",
                        title=self._content_title(topics, slot, "关键卡片"),
                        cards=[CardIR(title=item, body="来自输入文档的结构化要点") for item in bullets[:3]],
                        bullets=bullets[:3],
                    )
                )
            elif target_slide_count >= 8 and slot % 4 == 3:
                labels = [f"项{i + 1}" for i, _ in enumerate(bullets[:4] or ["内容"])]
                slides.append(
                    SlideIR(
                        layout="chart",
                        title=self._content_title(topics, slot, "指标概览"),
                        chart=ChartIR(
                            chart_type="bar",
                            labels=labels,
                            series=[ChartSeriesIR(name="指标", values=[float(i + 1) for i in range(len(labels))])],
                            summary="占位图表用于验证 DeckIR v1.1 基础渲染。",
                        ),
                    )
                )
            elif target_slide_count >= 10 and slot % 5 == 4:
                slides.append(
                    SlideIR(
                        layout="image",
                        title=self._content_title(topics, slot, "视觉说明"),
                        visuals=[VisualIR(kind="placeholder", title="图片占位", alt_text="根据输入内容预留图片区域")],
                    )
                )
            else:
                slides.append(
                    SlideIR(
                        layout="table",
                        title=self._content_title(topics, slot, "模块状态"),
                        table_headers=["模块", "说明"],
                        table_rows=[[f"模块 {i + 1}", item] for i, item in enumerate(bullets[:4])],
                    )
                )

        slides.append(
            SlideIR(
                layout="conclusion",
                title="结论",
                bullets=bullets[:3] or ["默认本地运行", "结构清晰", "便于集成"],
            )
        )
        return DeckIR(deck_title=title, slides=slides[:target_slide_count])

    def _word_ir(self, document: DocumentIR) -> WordIR:
        title = document.title or "未命名文档"
        topics = self._topics(document)
        bullets = topics[:5] or ["输入解析", "结构规划", "文件渲染"]
        blocks = [
            WordBlockIR(type="heading", text="摘要", level=1),
            WordBlockIR(type="paragraph", text=self._summary(document)),
            WordBlockIR(type="heading", text="主要内容", level=1),
            WordBlockIR(type="bullet_list", items=bullets),
            WordBlockIR(type="heading", text="实施建议", level=1),
            WordBlockIR(type="paragraph", text="建议先在 stub 模式完成本地验证，再接入公司内网模型与模板。"),
        ]
        table = self._first_table(document)
        if table:
            blocks.append(
                WordBlockIR(
                    type="table",
                    table_headers=table[0],
                    table_rows=table[1:],
                )
            )
        return WordIR(title=title, subtitle="自动生成报告", blocks=blocks)

    @staticmethod
    def _topics(document: DocumentIR) -> list[str]:
        topics: list[str] = []
        for block in document.blocks:
            if block.type == "heading" and block.text:
                topics.append(block.text)
            elif block.type == "bullet_list":
                topics.extend(block.items)
            elif block.type == "paragraph" and block.text:
                topics.append(block.text)
            elif block.type == "slide" and block.text:
                topics.extend([line for line in block.text.splitlines() if line.strip()])
        cleaned: list[str] = []
        for topic in topics:
            value = normalize_space(topic)
            if value and value not in cleaned:
                cleaned.append(value)
        return cleaned

    @staticmethod
    def _content_title(topics: list[str], slot: int, fallback: str) -> str:
        return truncate_text(first_non_empty(topics[slot + 1 : slot + 3], fallback), 28, fallback)

    @staticmethod
    def _summary(document: DocumentIR) -> str:
        paragraphs = [block.text or "" for block in document.blocks if block.type in {"paragraph", "slide"}]
        return truncate_text(first_non_empty(paragraphs, "输入文档已解析为结构化内容。"), 500)

    @staticmethod
    def _first_table(document: DocumentIR) -> list[list[str]] | None:
        for block in document.blocks:
            if block.type == "table" and block.rows:
                return block.rows
        return None
