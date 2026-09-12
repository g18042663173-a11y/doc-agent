from __future__ import annotations


ROLE_TERMS = {
    "capability_evidence": ("能力", "价值", "收益", "提升", "指标", "基线", "目标"),
    "solution_selection": ("方案", "选型", "对比", "优点", "缺点", "选择", "推荐"),
    "method_walkthrough": ("步骤", "流程", "方法", "先", "然后", "最后", "前后"),
    "implementation_detail": ("实现", "组件", "模块", "接口", "约束", "架构", "部署"),
    "test_matrix": ("测试", "验证", "用例", "场景", "通过", "预期", "结果"),
    "issue_retro": ("问题", "现象", "原因", "分析", "措施", "复盘", "改进"),
    "phase_summary": ("阶段", "投入", "产出", "里程碑", "时间", "完成"),
    "context_pain": ("背景", "现状", "痛点", "挑战", "目标", "需求"),
    "status_progress": ("目标", "进展", "状态", "风险", "下一步", "计划"),
    "struct_cover": ("标题", "封面", "汇报", "课题"),
}
EMPHASIS_TERMS = ("关键", "重点", "结论", "推荐", "风险")


def score_pages(skeleton: dict, material: dict, *, allow_page_adjust: bool) -> dict:
    """Offer role hints without mistaking whole-document keywords for page evidence."""
    folded = material["raw_text"].casefold()
    pages = []
    for page in skeleton["pages"]:
        terms = ROLE_TERMS.get(page["page_pattern"], ())
        hits = sum(term.casefold() in folded for term in terms)
        pages.append({
            "page_id": page["page_id"], "page_pattern": page["page_pattern"],
            "score": None, "verdict": "needs_content", "role_hint_hits": hits,
            "evidence_status": "unassigned", "capacity_status": "unmeasured",
            "required_slots": len(page["slots"]), "adjustments": [],
            "reason": "Assign material evidence to every slot; role keywords do not prove readiness.",
        })
    return {"format": "rdw_fit_report", "version": "2.0", "page_policy": "preserve",
            "ready_for_final": False, "pages": pages}
