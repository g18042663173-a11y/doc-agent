"""Generate business-shaped corpus files for parser and pipeline regression.

These files are deterministic synthetic business documents (fictional, fully
de-identified) used for parsing and end-to-end regression. They are NOT real
business files: samples/input/real/ remains the reserved location for genuine
de-identified corpus provided by the business side.

Usage:
    python scripts/make_business_samples.py [--output-dir samples/input/business]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt as DocxPt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "samples" / "input" / "business"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic business-shaped corpus files for parser regression."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def _docx_page_footer(document: Document, text: str) -> None:
    section = document.sections[0]
    paragraph = section.footer.paragraphs[0]
    paragraph.text = text
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in paragraph.runs:
        run.font.size = DocxPt(9)


def _docx_table(document: Document, header: list[str], rows: list[list[str]]) -> None:
    table = document.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Table Grid"
    for col, text in enumerate(header):
        table.cell(0, col).text = text
    for row_index, row in enumerate(rows, start=1):
        for col, text in enumerate(row):
            table.cell(row_index, col).text = text


def _make_docx_requirements(output_dir: Path) -> Path:
    document = Document()
    _docx_page_footer(document, "内部公开")
    document.add_heading("智能仓储管理系统需求规格说明书", level=0)
    document.add_paragraph("文档编号:WH-REQ-2026-031  版本:v1.2  拟制:产品部  日期:2026-06-18")
    document.add_heading("1  引言", level=1)
    document.add_paragraph(
        "本文档定义智能仓储管理系统(WMS)的功能需求与非功能需求,作为设计、开发和验收的依据。"
        "系统面向三个仓区(华东、华南、华北),支持入库、出库、盘点与预警四大核心流程。"
    )
    document.add_heading("1.1  范围", level=2)
    document.add_paragraph("本期范围仅覆盖标准品整箱作业,不包含冷链与危险品场景;该两类场景在下一期规划中评估。")
    document.add_heading("1.2  术语", level=2)
    document.add_paragraph("SKU:库存管理单元;波次:按订单批量拣货的作业单元;越库:货物不经入库直接分拣出库。", style="List Bullet")
    document.add_paragraph("WMS:仓库管理系统;ERP:企业资源计划系统。", style="List Bullet")
    document.add_heading("2  功能需求", level=1)
    document.add_paragraph("下表按优先级排列本期功能需求,优先级 P0 为上线必需,P1 为三个月内补齐。")
    _docx_table(
        document,
        ["需求编号", "功能名称", "需求描述", "优先级"],
        [
            ["FR-001", "入库预约", "承运商提前预约到货时间与月台,系统自动排期并生成收货单", "P0"],
            ["FR-002", "收货上架", "扫码核对 SKU 与数量,异常件转入待处理区并记录差异", "P0"],
            ["FR-003", "波次拣货", "按订单时效与库位就近原则生成拣货波次,支持任务拆分", "P0"],
            ["FR-004", "库存盘点", "支持循环盘点与全盘,差异单需主管审批后生效", "P0"],
            ["FR-005", "库存预警", "低于安全库存或临期时生成预警消息,推送至仓管员", "P1"],
            ["FR-006", "报表统计", "按日/周/月输出吞吐、库存周转与作业效率报表", "P1"],
        ],
    )
    document.add_heading("2.1  业务规则", level=2)
    document.add_paragraph("拣货遵循先进先出原则;同 SKU 不同批次不得混放;危化品仓区门禁独立。", style="List Number")
    document.add_paragraph("盘点期间冻结该库位出入库操作;差异率超过 2% 需二次复盘。", style="List Number")
    document.add_heading("3  非功能需求", level=1)
    document.add_paragraph("可用性:核心流程全年可用率不低于 99.5%,计划内维护每月不超过 2 小时。")
    document.add_paragraph("性能:入库单据处理平均响应时间不超过 2 秒,峰值并发 200 用户。")
    document.add_heading("4  验收标准", level=1)
    document.add_paragraph("以本文档需求编号为验收单元,逐条对照;P0 需求全部通过后方可进入试运行。")
    _docx_table(
        document,
        ["验收项", "操作步骤", "通过判据"],
        [
            ["FR-001", "创建一条到货预约", "生成收货单且月台排期无冲突"],
            ["FR-003", "创建 50 个订单并触发波次", "波次任务数与订单覆盖一致,无遗漏"],
            ["FR-005", "将某 SKU 库存调至安全值以下", "2 分钟内生成预警消息"],
        ],
    )
    document.add_heading("5  附录", level=1)
    document.add_paragraph("A. 需求变更记录表(见版本历史);B. 与 ERP 的接口清单详见《系统接口设计》。")
    path = output_dir / "docx_01_需求规格说明书.docx"
    document.save(path)
    return path


def _make_docx_weekly_report(output_dir: Path) -> Path:
    document = Document()
    _docx_page_footer(document, "内部公开")
    document.add_heading("XX 渠道运营项目周报", level=0)
    document.add_paragraph("项目名称:渠道数字化改造  汇报周期:2026 年第 32 周  汇报人:运营组")
    document.add_heading("1  本周进展", level=1)
    document.add_paragraph("本周完成渠道数据看板 V2 的核心指标上线,并启动两场城市站运营活动。", style="List Bullet")
    document.add_paragraph("完成 12 家重点渠道商的季度对账,差异 3 家已进入人工复核。", style="List Bullet")
    document.add_paragraph("数据中台口径对齐会议达成一致,下周三前输出口径文档。", style="List Bullet")
    document.add_heading("2  风险与问题", level=1)
    _docx_table(
        document,
        ["编号", "风险描述", "等级", "应对措施"],
        [
            ["R-01", "渠道商对账接口改造依赖对方排期,存在延期风险", "高", "已升级至项目例会,准备手工对账兜底"],
            ["R-02", "看板数据源切换后历史口径需重算", "中", "安排周五夜间批量重算"],
            ["R-03", "活动物资物流周期较长", "低", "提前一周下单,每日跟踪物流节点"],
        ],
    )
    document.add_heading("3  下周计划", level=1)
    document.add_paragraph("发布口径文档并完成评审。", style="List Number")
    document.add_paragraph("完成 3 家差异渠道的对账复核与结案。", style="List Number")
    document.add_paragraph("启动城市站活动复盘模板设计。", style="List Number")
    document.add_heading("4  需协调事项", level=1)
    document.add_paragraph("请财务本周五前确认对账差异处理规则,避免影响结案进度。")
    path = output_dir / "docx_02_项目周报.docx"
    document.save(path)
    return path


def _make_docx_tech_proposal(output_dir: Path) -> Path:
    document = Document()
    _docx_page_footer(document, "内部公开")
    document.add_heading("数据中台建设技术方案(评审稿)", level=0)
    document.add_paragraph("密级:内部公开  版本:v0.9  编制:架构组  日期:2026-07-30")
    document.add_heading("1  建设背景", level=1)
    document.add_paragraph(
        "当前各业务系统数据分散、口径不一,报表开发周期长。本方案拟通过数据中台统一采集、加工与"
        "服务,一期覆盖营销、供应链、财务三个域,支撑经营分析看板与自助取数。"
    )
    document.add_heading("2  总体架构", level=1)
    document.add_paragraph("总体分为四层:数据采集层、数据加工层、数据服务层与数据治理层。")
    document.add_paragraph("采集层通过 CDC 与定时批量两种方式接入源系统;加工层采用批流一体框架;"
                           "服务层提供指标 API 与即席查询;治理层负责元数据、质量与安全。")
    document.add_heading("3  技术选型", level=1)
    _docx_table(
        document,
        ["环节", "选型", "理由"],
        [
            ["采集", "CDC + 批量调度", "实时性与成本平衡,兼容既有 Oracle 与 MySQL"],
            ["加工", "批流一体计算引擎", "一套 SQL 同时支撑批与流,降低维护成本"],
            ["存储", "湖仓一体", "明细入湖、指标入仓,兼顾成本与查询性能"],
            ["服务", "指标平台 + API 网关", "口径统一收敛在指标层,消费方不直连表"],
        ],
    )
    document.add_heading("4  实施计划", level=1)
    document.add_paragraph("实施分三个阶段,每阶段末安排一次业务验证。")
    _docx_table(
        document,
        ["阶段", "周期", "范围", "里程碑"],
        [
            ["一期", "2026 Q3", "营销域 + 经营看板", "看板 30 个核心指标上线"],
            ["二期", "2026 Q4", "供应链域 + 自助取数", "自助取数覆盖 80% 报表场景"],
            ["三期", "2027 Q1", "财务域 + 数据治理", "治理成熟度达到 L3"],
        ],
    )
    document.add_heading("5  风险与对策", level=1)
    document.add_paragraph("源系统改造配合度风险:由项目组与各系统负责人签订接口 SLA。")
    document.add_paragraph("口径冲突风险:建立指标口径评审委员会,所有指标上线前评审。")
    document.add_heading("6  附录", level=1)
    document.add_paragraph("附录 A 指标清单(草案);附录 B 数据模型命名规范。")
    path = output_dir / "docx_03_技术方案评审稿.docx"
    document.save(path)
    return path


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------

def _make_xlsx_sales_ledger(output_dir: Path) -> Path:
    workbook = Workbook()
    details = workbook.active
    details.title = "销售明细"
    header = ["订单号", "客户", "区域", "产品", "数量", "单价(元)", "金额(元)", "日期", "销售代表"]
    details.append(header)
    rows = [
        ["SO202607001", "华信科技", "华东", "智能网关 GW-200", 120, 860, 103200, "2026-07-01", "张伟"],
        ["SO202607002", "远景制造", "华南", "工业路由器 IR-500", 60, 1520, 91200, "2026-07-02", "李娜"],
        ["SO202607003", "云帆物流", "华北", "定位终端 LT-100", 300, 320, 96000, "2026-07-03", "王强"],
        ["SO202607004", "华信科技", "华东", "工业路由器 IR-500", 80, 1520, 121600, "2026-07-05", "张伟"],
        ["SO202607005", "恒达电子", "西南", "智能网关 GW-200", 200, 860, 172000, "2026-07-08", "赵敏"],
        ["SO202607006", "云帆物流", "华北", "智能网关 GW-200", 150, 860, 129000, "2026-07-10", "王强"],
        ["SO202607007", "远景制造", "华南", "定位终端 LT-100", 500, 320, 160000, "2026-07-12", "李娜"],
        ["SO202607008", "恒达电子", "西南", "工业路由器 IR-500", 40, 1520, 60800, "2026-07-15", "赵敏"],
    ]
    for row in rows:
        details.append(row)
    details.append(["合计", "", "", "", "", "", "=SUM(G2:G9)", "", ""])
    for col in "ABCDEFGHI":
        details[f"{col}1"].font = Font(bold=True)
    details.column_dimensions["A"].width = 14
    details.column_dimensions["H"].width = 12

    summary = workbook.create_sheet("区域汇总")
    summary.append(["区域", "订单数", "销售额(元)"])
    summary.append(["华东", "=COUNTIF(销售明细!C:C,\"华东\")", "=SUMIF(销售明细!C:C,\"华东\",销售明细!G:G)"])
    summary.append(["华南", "=COUNTIF(销售明细!C:C,\"华南\")", "=SUMIF(销售明细!C:C,\"华南\",销售明细!G:G)"])
    summary.append(["华北", "=COUNTIF(销售明细!C:C,\"华北\")", "=SUMIF(销售明细!C:C,\"华北\",销售明细!G:G)"])
    summary.append(["西南", "=COUNTIF(销售明细!C:C,\"西南\")", "=SUMIF(销售明细!C:C,\"西南\",销售明细!G:G)"])
    summary.append(["总计", "=SUM(B2:B5)", "=SUM(C2:C5)"])
    for col in "ABC":
        summary[f"{col}1"].font = Font(bold=True)
    summary.column_dimensions["A"].width = 10
    summary.column_dimensions["C"].width = 16

    trend = workbook.create_sheet("月度趋势")
    trend.append(["月份", "销售额(元)"])
    trend.append(["2026-04", 680000])
    trend.append(["2026-05", 742000])
    trend.append(["2026-06", 815000])
    trend.append(["2026-07", "=SUM(销售明细!G2:G9)"])
    for col in "AB":
        trend[f"{col}1"].font = Font(bold=True)

    path = output_dir / "xlsx_01_销售台账.xlsx"
    workbook.save(path)
    return path


def _make_xlsx_budget(output_dir: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "2026 年度预算"
    sheet.merge_cells("A1:A2")
    sheet["A1"] = "费用科目"
    sheet.merge_cells("B1:E1")
    sheet["B1"] = "一季度"
    sheet.merge_cells("F1:I1")
    sheet["F1"] = "二季度"
    sheet.merge_cells("J1:J2")
    sheet["J1"] = "全年合计"
    sheet.merge_cells("K1:K2")
    sheet["K1"] = "占比"
    for col, label in zip("BCDE", ["1月", "2月", "3月", "小计"]):
        sheet[f"{col}2"] = label
    for col, label in zip("FGHI", ["4月", "5月", "6月", "小计"]):
        sheet[f"{col}2"] = label
    items = [
        ["人力成本", 320, 320, 340, "=SUM(B3:D3)", 340, 340, 360, "=SUM(F3:H3)", "=SUM(E3,I3)", "=J3/$J$9"],
        ["采购成本", 180, 150, 200, "=SUM(B4:D4)", 210, 190, 220, "=SUM(F4:H4)", "=SUM(E4,I4)", "=J4/$J$9"],
        ["差旅费用", 25, 30, 28, "=SUM(B5:D5)", 32, 35, 40, "=SUM(F5:H5)", "=SUM(E5,I5)", "=J5/$J$9"],
        ["市场活动", 60, 45, 80, "=SUM(B6:D6)", 90, 70, 110, "=SUM(F6:H6)", "=SUM(E6,I6)", "=J6/$J$9"],
        ["IT 支撑", 40, 40, 40, "=SUM(B7:D7)", 45, 45, 45, "=SUM(F7:H7)", "=SUM(E7,I7)", "=J7/$J$9"],
        ["其他", 15, 15, 12, "=SUM(B8:D8)", 15, 18, 15, "=SUM(F8:H8)", "=SUM(E8,I8)", "=J8/$J$9"],
    ]
    for row in items:
        sheet.append(row)
    sheet.append(["合计", "=SUM(B3:B8)", "=SUM(C3:C8)", "=SUM(D3:D8)", "=SUM(E3:E8)",
                  "=SUM(F3:F8)", "=SUM(G3:G8)", "=SUM(H3:H8)", "=SUM(I3:I8)",
                  "=SUM(J3:J8)", "=SUM(J3:J8)/SUM(J3:J8)"])
    sheet["A1"].font = Font(bold=True)
    sheet["B1"].font = Font(bold=True)
    sheet["F1"].font = Font(bold=True)
    sheet["J1"].font = Font(bold=True)
    sheet["A9"].font = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="DDEBF7")
    for cell in ("A1", "B1", "F1", "J1"):
        sheet[cell].fill = header_fill
    for col in "ABCDEFGHIJK":
        sheet.column_dimensions[col].width = 10
    sheet.column_dimensions["A"].width = 12
    sheet.freeze_panes = "A3"

    path = output_dir / "xlsx_02_年度预算编制表.xlsx"
    workbook.save(path)
    return path


def _make_xlsx_milestones(output_dir: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "里程碑计划"
    header = ["阶段", "里程碑", "负责人", "开始日期", "结束日期", "状态", "交付物", "风险"]
    sheet.append(header)
    rows = [
        ["启动", "项目立项评审通过", "王经理", "2026-08-03", "2026-08-07", "已完成", "立项报告", "无"],
        ["设计", "总体方案设计完成", "刘架构师", "2026-08-10", "2026-08-28", "进行中", "总体设计文档", "接口依赖未冻结"],
        ["开发", "核心模块开发完成", "陈开发", "2026-08-31", "2026-10-16", "未开始", "可运行版本", "人力紧张"],
        ["测试", "系统测试通过", "周测试", "2026-10-19", "2026-11-06", "未开始", "测试报告", "数据质量"],
        ["上线", "试运行与验收", "王经理", "2026-11-09", "2026-11-27", "未开始", "验收报告", "变更范围"],
    ]
    for row in rows:
        sheet.append(row)
    sheet.append(["", "总体进度", "", "", "", "=COUNTA(F2:F6)/COUNTA(F2:F6)", "", ""])
    for col in "ABCDEFGH":
        sheet[f"{col}1"].font = Font(bold=True)
    sheet.column_dimensions["A"].width = 8
    sheet.column_dimensions["B"].width = 20
    sheet.column_dimensions["C"].width = 12
    sheet.column_dimensions["G"].width = 16

    risks = workbook.create_sheet("风险登记册")
    risks.append(["编号", "风险描述", "等级", "概率", "影响", "应对措施", "责任人"])
    risk_rows = [
        ["R-01", "外部接口交付延期", "高", "高", "高", "每周对齐 + 接口先行联调", "刘架构师"],
        ["R-02", "测试数据不足", "中", "中", "中", "提前准备脱敏生产数据", "周测试"],
        ["R-03", "需求变更频繁", "中", "高", "低", "变更走评审委员会", "王经理"],
    ]
    for row in risk_rows:
        risks.append(row)
    for col in "ABCDEFG":
        risks[f"{col}1"].font = Font(bold=True)

    path = output_dir / "xlsx_03_项目里程碑计划.xlsx"
    workbook.save(path)
    return path


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------

def _pptx_set_footer(slide, text: str) -> None:
    box = slide.shapes.add_textbox(Inches(0.3), Inches(7.0), Inches(9.4), Inches(0.4))
    paragraph = box.text_frame.paragraphs[0]
    paragraph.text = text
    for run in paragraph.runs:
        run.font.size = Pt(9)


def _pptx_bullets(frame, items: list[str]) -> None:
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = item
        paragraph.font.size = Pt(18)


def _make_pptx_quarterly_report(output_dir: Path) -> Path:
    presentation = Presentation()
    presentation.slide_width = Inches(10)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(1), Inches(2.2), Inches(8), Inches(1.2))
    box.text_frame.paragraphs[0].text = "智能连接产品线 Q3 业务汇报"
    box.text_frame.paragraphs[0].font.size = Pt(36)
    box = slide.shapes.add_textbox(Inches(1), Inches(3.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "汇报人:产品管理部 | 2026-09-30"
    box.text_frame.paragraphs[0].font.size = Pt(16)
    _pptx_set_footer(slide, "HUAWEI CONFIDENTIAL")

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "目录"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["季度经营概况", "重点产品进展", "市场与渠道", "风险与对策", "下季度计划"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "季度经营概况"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["销售额完成 1.28 亿,达成率 106%", "毛利率 38.2%,同比提升 2.4 个百分点", "新增渠道商 26 家,回款周期缩短 5 天"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "分产品销售额(万元)"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    chart_data = CategoryChartData()
    chart_data.categories = ["智能网关", "工业路由器", "定位终端", "配套服务"]
    chart_data.add_series("Q3", (5200, 4100, 2300, 1200))
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.8), Inches(8), Inches(4.6), chart_data)
    chart.has_legend = False
    table = slide.shapes.add_table(4, 3, Inches(1), Inches(1.8), Inches(8), Inches(2.2)).table
    for col, header in enumerate(["指标", "Q2", "Q3"]):
        table.cell(0, col).text = header
    for row, values in enumerate([["销售额(万元)", 9800, 12800], ["毛利率", "35.8%", "38.2%"], ["渠道商数", 118, 144]], start=1):
        for col, value in enumerate(values):
            table.cell(row, col).text = str(value)

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "风险与对策"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["核心器件供应紧张:已锁定三家备选供应商", "渠道库存偏高:启动促销消化,目标降低 15%", "汇率波动:合同增加汇率保护条款"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "下季度计划"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["发布新一代智能网关,目标首月订单 3 万台", "完成华南仓备货与两场渠道峰会", "启动海外试点两个国家"])

    for slide_index, note in enumerate(
        [
            "开场 1 分钟讲经营概况,重点突出达成率与毛利改善。",
            "目录页控制在 30 秒,引导听众进入重点产品章节。",
            "经营数据口径以财务确认版为准。",
            "图表为演示数据,汇报前替换为最新月度数据。",
            "风险页只讲对策,不展开细节。",
            "结尾落到下季度三个可量化目标。",
        ]
    ):
        presentation.slides[slide_index].notes_slide.notes_text_frame.text = note

    path = output_dir / "pptx_01_产品季度汇报.pptx"
    presentation.save(path)
    return path


def _make_pptx_kickoff(output_dir: Path) -> Path:
    presentation = Presentation()
    presentation.slide_width = Inches(10)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(1), Inches(2.4), Inches(8), Inches(1.2))
    box.text_frame.paragraphs[0].text = "数据中台项目启动会"
    box.text_frame.paragraphs[0].font.size = Pt(36)
    box = slide.shapes.add_textbox(Inches(1), Inches(3.8), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "2026-08-03 | 项目组全体"
    box.text_frame.paragraphs[0].font.size = Pt(16)
    _pptx_set_footer(slide, "HUAWEI CONFIDENTIAL")

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "项目背景与目标"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["现状:报表开发周期平均 15 天,口径不一致", "目标:一期 30 个核心指标口径统一、看板自助化", "范围:营销域先行,供应链、财务域二期"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "组织分工"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    table = slide.shapes.add_table(6, 3, Inches(0.8), Inches(1.8), Inches(8.4), Inches(4)).table
    for col, header in enumerate(["角色", "人员", "职责"]):
        table.cell(0, col).text = header
    roles = [
        ["项目经理", "王经理", "整体计划、风险与干系人管理"],
        ["架构师", "刘架构师", "技术方案、接口标准"],
        ["开发组", "陈开发等 5 人", "采集、加工、服务层开发"],
        ["测试组", "周测试等 2 人", "测试计划与质量门禁"],
        ["业务接口人", "各域负责人", "口径确认与验收"],
    ]
    for row, values in enumerate(roles, start=1):
        for col, value in enumerate(values):
            table.cell(row, col).text = value

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "里程碑计划"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["8 月:立项与总体设计", "9-10 月:开发与联调", "11 月:测试与试运行", "11 月底:验收与转产"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "关键风险"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    table = slide.shapes.add_table(4, 3, Inches(0.8), Inches(1.8), Inches(8.4), Inches(2.6)).table
    for col, header in enumerate(["风险", "等级", "应对"]):
        table.cell(0, col).text = header
    for row, values in enumerate(
        [
            ["源系统接口延期", "高", "SLA 约束 + 双周对齐"],
            ["口径冲突", "中", "口径评审委员会"],
            ["测试数据不足", "中", "脱敏生产数据提前准备"],
        ],
        start=1,
    ):
        for col, value in enumerate(values):
            table.cell(row, col).text = value

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "下一步行动"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["本周五前各域提交指标清单", "下周三输出接口清单初稿", "8 月 17 日总体方案评审"])

    for slide_index, note in enumerate(
        [
            "强调项目对经营分析效率的提升价值。",
            "背景页讲清楚为什么现在做。",
            "分工页确认各角色第一责任人。",
            "里程碑以立项评审通过为起点。",
            "风险页请业务接口人当场确认应对措施。",
            "结尾明确三项行动的截止时间。",
        ]
    ):
        presentation.slides[slide_index].notes_slide.notes_text_frame.text = note

    path = output_dir / "pptx_02_项目启动会材料.pptx"
    presentation.save(path)
    return path


def _make_pptx_annual_summary(output_dir: Path) -> Path:
    presentation = Presentation()
    presentation.slide_width = Inches(10)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(1), Inches(2.2), Inches(8), Inches(1.2))
    box.text_frame.paragraphs[0].text = "2026 年度总结与 2027 规划"
    box.text_frame.paragraphs[0].font.size = Pt(34)
    box = slide.shapes.add_textbox(Inches(1), Inches(3.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "供应链管理部"
    box.text_frame.paragraphs[0].font.size = Pt(16)
    _pptx_set_footer(slide, "HUAWEI CONFIDENTIAL")

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "年度总结"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["交付及时率 96.8%,同比提升 3.1 个百分点", "库存周转天数下降至 32 天", "完成华南新仓开仓与自动化分拣上线", "供应商协同平台覆盖 85% 核心供应商"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "关键指标对比"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    chart_data = CategoryChartData()
    chart_data.categories = ["交付及时率", "库存周转天数", "预测准确率"]
    chart_data.add_series("2025", (93.7, 38, 82))
    chart_data.add_series("2026", (96.8, 32, 88))
    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.8), Inches(8), Inches(4.6), chart_data)

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "问题与改进"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["旺季运力不足:已与 3 家承运商签订旺季保障协议", "部分区域预测偏差大:引入机器学习补货试点", "退货处理周期偏长:流程再造预计缩短 40%"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "2027 规划"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(1.6), Inches(8), Inches(4))
    _pptx_bullets(box.text_frame, ["交付及时率目标 98%,库存周转目标 28 天", "智能补货覆盖全部 A 类 SKU", "启动绿色供应链与碳足迹核算"])

    slide = presentation.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(8), Inches(0.8))
    box.text_frame.paragraphs[0].text = "结束"
    box.text_frame.paragraphs[0].font.size = Pt(28)
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.4), Inches(8), Inches(1))
    box.text_frame.paragraphs[0].text = "谢谢!欢迎指导。"
    box.text_frame.paragraphs[0].font.size = Pt(20)

    for slide_index, note in enumerate(
        [
            "总结会面向管理层,重点讲结果与改善。",
            "年度总结页数据为全年累计口径。",
            "指标对比图为演示数据,汇报前更新。",
            "问题页只讲已启动的改进动作。",
            "规划页强调三个可量化目标。",
            "结束页留出提问时间。",
        ]
    ):
        presentation.slides[slide_index].notes_slide.notes_text_frame.text = note

    path = output_dir / "pptx_03_年度总结与规划.pptx"
    presentation.save(path)
    return path


# ---------------------------------------------------------------------------

def generate_business_samples(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = [
        _make_docx_requirements(output_dir),
        _make_docx_weekly_report(output_dir),
        _make_docx_tech_proposal(output_dir),
        _make_xlsx_sales_ledger(output_dir),
        _make_xlsx_budget(output_dir),
        _make_xlsx_milestones(output_dir),
        _make_pptx_quarterly_report(output_dir),
        _make_pptx_kickoff(output_dir),
        _make_pptx_annual_summary(output_dir),
    ]
    return generated


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    generated = generate_business_samples(args.output_dir)
    for path in generated:
        print(path)
    print(f"generated {len(generated)} business samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
