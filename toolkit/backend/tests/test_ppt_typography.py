from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _fit(texts: list[str], *, width: float, height: float):
    from app.rendering.typography import fit_text_stack

    return fit_text_stack(
        texts,
        [16, 14, 12, 10.5],
        width_in=width,
        height_in=height,
        line_spacing=1.3,
        item_gap_in=0.222222,
        baseline_pt=8,
        horizontal_margin_in=0.1,
        vertical_margin_in=0.04,
    )


def test_fit_text_stack_keeps_sparse_body_at_sixteen_points() -> None:
    fit = _fit(["• 短要点一", "• 短要点二", "• 短要点三"], width=12.2, height=4.77)

    assert fit.font_size_pt == 16
    assert fit.overflow is False
    assert fit.item_heights_in == (4 / 9, 4 / 9, 4 / 9)


def test_fit_text_stack_steps_down_deterministically() -> None:
    fourteen = _fit(["中" * 60] * 7, width=12.2, height=4.77)
    twelve = _fit(["中" * 50] * 4, width=5.083, height=3.0)

    assert fourteen.font_size_pt == 14
    assert fourteen.overflow is False
    assert twelve.font_size_pt == 12
    assert twelve.overflow is False


def test_fit_text_stack_reports_floor_overflow_without_dropping_items() -> None:
    from app.rendering.typography import constrained_stack_heights

    fit = _fit(["中" * 50] * 4, width=5.083, height=2.5)
    constrained = constrained_stack_heights(fit, height_in=2.5, item_gap_in=0.222222)

    assert fit.font_size_pt == 10.5
    assert fit.overflow is True
    assert len(constrained) == 4
    assert sum(constrained) + 0.222222 * 3 <= 2.5 + 1e-6
