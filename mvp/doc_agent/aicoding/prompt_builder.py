from __future__ import annotations

import json
from typing import Literal

from doc_agent.ir.schemas import DeckIR, DocumentIR, WordIR


class AICodingPromptBuilder:
    def build(self, document_ir: DocumentIR, target: Literal["docx", "pptx"], slides: int = 8) -> str:
        if target == "docx":
            schema = WordIR.model_json_schema()
            task = "请根据输入文档生成 WordIR，用于渲染格式稳定的 Word 文档。"
            extra_rules = [
                "blocks 至少包含 1 个 heading 和 2 个 paragraph，必要时可包含 bullet_list 或 table。",
                "heading 的 level 只能使用 1、2、3，不要跳级。",
                "table 使用 table_headers 和 table_rows，不要输出 Markdown 表格。",
            ]
        else:
            schema = DeckIR.model_json_schema()
            task = f"请根据输入文档生成 DeckIR，用于渲染 {slides} 页左右的 PPTX。"
            extra_rules = [
                f"slides 建议接近 {slides} 页，优先使用 cover、agenda、title_bullets、two_column、table、conclusion。",
                "每页标题要短，正文 bullets 要可直接放进 PPT。",
                "如输入包含 Excel 表格，请优先提炼结论，不要逐行复述。",
            ]

        rules = [
            "只输出一个 JSON 对象，不要输出 Markdown、解释文字或代码围栏。",
            "必须严格匹配下面的 JSON Schema。",
            "不要输出“作为 AI 模型”等无关表述。",
            "中文内容使用专业、克制、内部汇报风格。",
            *extra_rules,
        ]
        return "\n".join(
            [
                "# AICoding 结构化生成任务",
                "",
                task,
                "",
                "## 输出规则",
                *[f"- {rule}" for rule in rules],
                "",
                "## JSON Schema",
                json.dumps(schema, ensure_ascii=False, indent=2),
                "",
                "## 输入 DocumentIR",
                document_ir.model_dump_json(ensure_ascii=False, indent=2),
                "",
                "请现在输出最终 JSON 对象。",
            ]
        )
