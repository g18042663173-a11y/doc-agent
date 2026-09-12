from __future__ import annotations

from doc_agent.config import load_style_profile
from doc_agent.ir.schemas import CardIR, ChartIR, ChartSeriesIR, DeckIR, SlideIR, VisualIR
from doc_agent.utils.text_utils import truncate_text


class DeckValidator:
    def __init__(self, style_profile: dict | None = None) -> None:
        self.style_profile = style_profile or load_style_profile()
        self.rules = self.style_profile.get("ppt_rules", {})

    def validate_and_fix(self, deck: DeckIR) -> tuple[DeckIR, list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if not deck.deck_title.strip():
            deck.deck_title = "未命名文档"
            warnings.append("Deck title was empty and has been filled")

        max_slides = int(self.rules.get("max_slides", 12))
        min_slides = int(self.rules.get("min_slides", 5))
        allowed = set(self.rules.get("allowed_layouts", []))
        max_title_chars = int(self.rules.get("max_title_chars", 28))
        max_bullets = int(self.rules.get("max_bullets_per_slide", 5))
        max_bullet_chars = int(self.rules.get("max_chars_per_bullet", 32))
        forbidden = self.rules.get("forbidden_phrases", [])

        if not deck.slides:
            errors.append("DeckIR has no slides")
            return deck, errors, warnings

        if len(deck.slides) > max_slides:
            deck.slides = deck.slides[:max_slides]
            warnings.append(f"Slides trimmed to max_slides={max_slides}")

        while len(deck.slides) < min_slides:
            deck.slides.append(SlideIR(layout="conclusion", title="结论", bullets=["内容已整理"]))
            warnings.append(f"Added fallback slide to satisfy min_slides={min_slides}")

        for slide in deck.slides:
            if allowed and slide.layout not in allowed:
                errors.append(f"Unsupported layout: {slide.layout}")
            slide.title = truncate_text(self._remove_forbidden(slide.title, forbidden), max_title_chars, "未命名章节")
            slide.bullets = [
                truncate_text(self._remove_forbidden(item, forbidden), max_bullet_chars)
                for item in slide.bullets[:max_bullets]
                if item.strip()
            ]
            slide.left_bullets = [
                truncate_text(self._remove_forbidden(item, forbidden), max_bullet_chars)
                for item in slide.left_bullets[:max_bullets]
                if item.strip()
            ]
            slide.right_bullets = [
                truncate_text(self._remove_forbidden(item, forbidden), max_bullet_chars)
                for item in slide.right_bullets[:max_bullets]
                if item.strip()
            ]
            slide.table_headers = slide.table_headers[:5]
            slide.table_rows = [row[:5] for row in slide.table_rows[:6]]
            slide.cards = [
                CardIR(
                    title=truncate_text(self._remove_forbidden(card.title, forbidden), max_title_chars, "要点"),
                    body=truncate_text(self._remove_forbidden(card.body, forbidden), max_bullet_chars * 2) if card.body else None,
                    bullets=[
                        truncate_text(self._remove_forbidden(item, forbidden), max_bullet_chars)
                        for item in card.bullets[:max_bullets]
                        if item.strip()
                    ],
                    importance=card.importance,
                )
                for card in slide.cards[:4]
            ]
            slide.visuals = [
                VisualIR(
                    kind=visual.kind,
                    title=truncate_text(self._remove_forbidden(visual.title, forbidden), max_title_chars) if visual.title else None,
                    path=visual.path,
                    alt_text=truncate_text(self._remove_forbidden(visual.alt_text, forbidden), max_bullet_chars * 2) if visual.alt_text else None,
                    caption=truncate_text(self._remove_forbidden(visual.caption, forbidden), max_bullet_chars) if visual.caption else None,
                    meta=visual.meta,
                )
                for visual in slide.visuals[:2]
            ]
            if slide.chart:
                slide.chart = ChartIR(
                    chart_type=slide.chart.chart_type,
                    title=truncate_text(self._remove_forbidden(slide.chart.title, forbidden), max_title_chars) if slide.chart.title else None,
                    labels=[truncate_text(label, 14) for label in slide.chart.labels[:8]],
                    series=[
                        ChartSeriesIR(name=truncate_text(series.name, 16, "系列"), values=series.values[:8])
                        for series in slide.chart.series[:3]
                    ],
                    summary=truncate_text(self._remove_forbidden(slide.chart.summary, forbidden), max_bullet_chars * 2) if slide.chart.summary else None,
                    meta=slide.chart.meta,
                )
            if slide.layout == "cards" and not slide.cards:
                slide.cards = [CardIR(title=item) for item in (slide.bullets[:3] or ["内容已整理"])]
            if slide.layout == "image" and not slide.visuals:
                slide.visuals = [VisualIR(kind="placeholder", title=slide.title, alt_text="图片占位")]
            if slide.layout == "chart" and slide.chart is None:
                labels = [f"项{i + 1}" for i, _ in enumerate(slide.bullets[:4] or ["内容"])]
                slide.chart = ChartIR(
                    chart_type="bar",
                    title=slide.title,
                    labels=labels,
                    series=[ChartSeriesIR(name="指标", values=[float(index + 1) for index in range(len(labels))])],
                    summary="根据输入内容生成的占位图表",
                )

        return deck, errors, warnings

    @staticmethod
    def _remove_forbidden(text: str | None, forbidden: list[str]) -> str:
        value = text or ""
        for phrase in forbidden:
            value = value.replace(phrase, "")
        return value.strip()
