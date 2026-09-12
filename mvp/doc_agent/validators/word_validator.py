from __future__ import annotations

from doc_agent.config import load_style_profile
from doc_agent.ir.schemas import WordBlockIR, WordIR
from doc_agent.utils.text_utils import truncate_text


class WordValidator:
    def __init__(self, style_profile: dict | None = None) -> None:
        self.style_profile = style_profile or load_style_profile()
        self.rules = self.style_profile.get("docx_rules", {})
        self.forbidden = self.style_profile.get("ppt_rules", {}).get("forbidden_phrases", [])

    def validate_and_fix(self, word: WordIR) -> tuple[WordIR, list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if not word.title.strip():
            word.title = "未命名文档"
            warnings.append("Word title was empty and has been filled")
        if not word.blocks:
            word.blocks.append(WordBlockIR(type="paragraph", text="输入文档已解析。"))
            warnings.append("Added fallback paragraph because WordIR had no blocks")

        max_paragraph_chars = int(self.rules.get("max_paragraph_chars", 500))
        for block in word.blocks:
            if block.type == "heading":
                block.level = min(max(block.level or 1, 1), 3)
                block.text = self._clean(block.text or "未命名章节")
            elif block.type == "paragraph":
                block.text = truncate_text(self._clean(block.text or ""), max_paragraph_chars)
            elif block.type == "bullet_list":
                block.items = [self._clean(item) for item in block.items if item.strip()]
                if not block.items:
                    warnings.append("Dropped empty bullet list")
            elif block.type == "table" and not (block.table_headers or block.table_rows):
                errors.append("WordIR table block is empty")
        return word, errors, warnings

    def _clean(self, text: str) -> str:
        value = text.strip()
        for phrase in self.forbidden:
            value = value.replace(phrase, "")
        return value.strip()
