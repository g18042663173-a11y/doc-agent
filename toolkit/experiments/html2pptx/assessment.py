"""Decision rules for the isolated HTML/PptxGenJS engine experiment."""

from __future__ import annotations

from typing import Any


HARD_GATES = (
    "schema_valid",
    "package_valid",
    "lint_clean",
    "no_layout_issues",
    "office_opened",
    "native_editability",
)
SCORE_FIELDS = (
    "visual_hierarchy",
    "chinese_typography",
    "template_fidelity",
    "deployment_reliability",
)


def assess_engines(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a reproducible recommendation; never change the production engine."""

    summaries = {name: _summary(cases, name) for name in ("python", "html")}
    python_score = summaries["python"]["mean_score"]
    html_score = summaries["html"]["mean_score"]
    advantage = 0.0 if python_score <= 0 else round((html_score - python_score) / python_score, 4)
    all_visual_evidence = all(
        case["python"].get("visual_review") == "approved"
        and case["html"].get("visual_review") == "approved"
        for case in cases
    )
    template_cases = [case for case in cases if case.get("template_case")]
    html_template_ok = bool(template_cases) and all(
        all(case["html"].get("hard_gates", {}).get(gate) is True for gate in HARD_GATES)
        for case in template_cases
    )
    if not summaries["html"]["hard_gate_pass"]:
        recommendation = "keep_python"
        reason = "html_hard_gate_failed"
    elif not all_visual_evidence:
        recommendation = "expand_html_experiment"
        reason = "visual_review_pending"
    elif advantage >= 0.15 and html_template_ok:
        recommendation = "candidate_for_review"
        reason = "html_passed_all_gates_with_required_advantage"
    else:
        recommendation = "keep_python"
        reason = "html_has_no_required_advantage_or_template_evidence"
    return {
        "engine_assessment_version": "1.0",
        "recommendation": recommendation,
        "reason": reason,
        "html_score_advantage": advantage,
        "python": summaries["python"],
        "html": summaries["html"],
        "cases": cases,
    }


def _summary(cases: list[dict[str, Any]], engine: str) -> dict[str, Any]:
    results = [case[engine] for case in cases]
    hard_gate_pass = bool(results) and all(
        all(result.get("hard_gates", {}).get(gate) is True for gate in HARD_GATES)
        for result in results
    )
    scores = [sum(float(result.get("scores", {}).get(field, 0)) for field in SCORE_FIELDS) for result in results]
    return {
        "hard_gate_pass": hard_gate_pass,
        "mean_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "max_score": len(SCORE_FIELDS) * 5,
        "case_count": len(results),
    }
