from __future__ import annotations

import copy

import math
import re
from typing import Annotated, Any, Literal, Union

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.ir.common import ContractModel, ListItem, non_empty


class DeckMeta(ContractModel):
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str | None = None
    date: str | None = None
    classification: str = "HUAWEI CONFIDENTIAL"
    theme: str = "hw_v1"

    _title_not_blank = field_validator("title")(non_empty)


class CoverSlide(ContractModel):
    layout: Literal["cover"]
    title: str = Field(min_length=1)
    subtitle: str | None = None
    presenter: str | None = None
    date: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


class AgendaSlide(ContractModel):
    layout: Literal["agenda"]
    items: list[str] = Field(min_length=2, max_length=8)

    @field_validator("items")
    @classmethod
    def items_not_blank(_cls, value: list[str]) -> list[str]:
        return [non_empty(item) for item in value]


class SectionSlide(ContractModel):
    layout: Literal["section"]
    index: int = Field(ge=1)
    title: str = Field(min_length=1)
    subtitle: str | None = None

    _title_not_blank = field_validator("title")(non_empty)


class TitleBulletsSlide(ContractModel):
    layout: Literal["title_bullets"]
    title: str = Field(min_length=1)
    bullets: list[ListItem] = Field(min_length=1, max_length=7)

    _title_not_blank = field_validator("title")(non_empty)


class ColumnContent(ContractModel):
    heading: str | None = None
    bullets: list[ListItem] = Field(default_factory=list, max_length=7)
    text: str | None = None

    @field_validator("heading", "text")
    @classmethod
    def optional_text_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None

    @model_validator(mode="after")
    def require_body_content(self) -> "ColumnContent":
        if not self.text and not self.bullets:
            raise ValueError("two_column column requires text or bullets")
        return self


class TwoColumnSlide(ContractModel):
    layout: Literal["two_column"]
    title: str = Field(min_length=1)
    left: ColumnContent
    right: ColumnContent

    _title_not_blank = field_validator("title")(non_empty)


class DeckTableCell(ContractModel):
    text: str = ""
    items: list[str] = Field(default_factory=list, max_length=4)
    emphasis: Literal["yellow", "cyan"] | None = None

    @field_validator("items")
    @classmethod
    def items_not_blank(_cls, value: list[str]) -> list[str]:
        if any(not str(item).strip() for item in value):
            raise ValueError("table cell items must not be blank")
        return value


class TableColumnGroup(ContractModel):
    label: str = Field(min_length=1)
    start_col: int = Field(ge=0, description="分组起始列的 0 起始索引。")
    span: int = Field(ge=1, description="分组覆盖的列数量，不是结束列索引。")

    _label_not_blank = field_validator("label")(non_empty)


class TableRowGroup(ContractModel):
    label: str = Field(min_length=1)
    start_row: int = Field(ge=0, description="分组起始数据行的 0 起始索引。")
    span: int = Field(ge=1, description="分组覆盖的数据行数量，不是结束行索引。")

    _label_not_blank = field_validator("label")(non_empty)


class TableCellSpan(ContractModel):
    area: Literal["header", "body"] = "body"
    row: int = Field(ge=0, description="合并区域起始行的 0 起始索引；header 区固定从 0 行开始。")
    col: int = Field(ge=0, description="合并区域起始列的 0 起始索引。")
    rowspan: int = Field(default=1, ge=1, description="合并区域覆盖的行数量，不是结束行索引。")
    colspan: int = Field(default=1, ge=1, description="合并区域覆盖的列数量，不是结束列索引。")


DeckTableCellValue = DeckTableCell | str


def _table_cell_has_content(value: DeckTableCellValue) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value.text.strip() or value.items)


class DeckTable(ContractModel):
    header: list[str] = Field(min_length=1, max_length=8)
    rows: list[list[DeckTableCellValue]] = Field(default_factory=list, max_length=12)
    col_widths: list[float] | None = Field(
        default=None,
        description="各列的正数相对宽度权重；渲染时归一化到版心可用宽度，不是英寸或其它绝对单位。",
    )
    column_groups: list[TableColumnGroup] = Field(default_factory=list, max_length=4)
    row_groups: list[TableRowGroup] = Field(default_factory=list, max_length=8)
    cell_spans: list[TableCellSpan] = Field(default_factory=list, max_length=16)
    conclusion_col: int | None = Field(default=None, ge=0, description="结论列的 0 起始列索引。")

    @field_validator("header")
    @classmethod
    def header_cells_not_blank(_cls, value: list[str]) -> list[str]:
        if any(not str(cell).strip() for cell in value):
            raise ValueError("table header cells must not be blank")
        return value

    @field_validator("col_widths")
    @classmethod
    def col_widths_positive(_cls, value: list[float] | None) -> list[float] | None:
        if value is not None and any(not math.isfinite(width) or width <= 0 for width in value):
            raise ValueError("col_widths must be finite and positive")
        return value

    @model_validator(mode="after")
    def validate_rows(self) -> "DeckTable":
        expected_cols = len(self.header)
        if not self.rows:
            raise ValueError("table rows must contain at least one data row")
        if any(len(row) != expected_cols for row in self.rows):
            raise ValueError("rows must match header column count")
        if self.col_widths is not None and len(self.col_widths) != expected_cols:
            raise ValueError("col_widths must match header column count")
        if self.conclusion_col is not None and self.conclusion_col >= expected_cols:
            raise ValueError("conclusion_col must be within table columns")
        self._validate_column_groups(expected_cols)
        self._validate_row_groups(len(self.rows))
        self._validate_cell_spans(expected_cols, len(self.rows))
        self._validate_covered_cell_content()
        return self

    def _validate_column_groups(self, expected_cols: int) -> None:
        used: set[int] = set()
        for group in self.column_groups:
            group_cols = set(range(group.start_col, group.start_col + group.span))
            if not group_cols or max(group_cols) >= expected_cols:
                raise ValueError("column_groups must be within table columns")
            if used & group_cols:
                raise ValueError("column_groups must not overlap")
            used.update(group_cols)

    def _validate_row_groups(self, row_count: int) -> None:
        used: set[int] = set()
        for group in self.row_groups:
            group_rows = set(range(group.start_row, group.start_row + group.span))
            if not group_rows or max(group_rows) >= row_count:
                raise ValueError("row_groups must be within table rows")
            if used & group_rows:
                raise ValueError("row_groups must not overlap")
            used.update(group_rows)

    def _validate_cell_spans(self, expected_cols: int, row_count: int) -> None:
        used: set[tuple[str, int, int]] = set()
        for span in self.cell_spans:
            max_rows = 1 if span.area == "header" else row_count
            if span.area == "header" and span.rowspan != 1:
                raise ValueError("header cell_spans cannot span multiple rows")
            if span.row + span.rowspan > max_rows or span.col + span.colspan > expected_cols:
                raise ValueError("cell_spans must be within table bounds")
            span_cells = {
                (span.area, row, col)
                for row in range(span.row, span.row + span.rowspan)
                for col in range(span.col, span.col + span.colspan)
            }
            if used & span_cells:
                raise ValueError("cell_spans must not overlap")
            used.update(span_cells)

    def _validate_covered_cell_content(self) -> None:
        for span in self.cell_spans:
            if span.area != "body":
                continue
            for row in range(span.row, span.row + span.rowspan):
                for col in range(span.col, span.col + span.colspan):
                    if (row, col) == (span.row, span.col):
                        continue
                    if _table_cell_has_content(self.rows[row][col]):
                        raise ValueError("covered table cells must be empty")


class TableSlide(ContractModel):
    layout: Literal["table"]
    title: str = Field(min_length=1)
    table: DeckTable

    _title_not_blank = field_validator("title")(non_empty)


class Card(ContractModel):
    title: str = Field(min_length=1)
    desc: str = Field(min_length=1)
    tag: str | None = None

    _title_not_blank = field_validator("title")(non_empty)
    _desc_not_blank = field_validator("desc")(non_empty)

    @field_validator("tag")
    @classmethod
    def tag_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class CardsSlide(ContractModel):
    layout: Literal["cards"]
    title: str = Field(min_length=1)
    cards: list[Card] = Field(min_length=2, max_length=4)
    variant: Literal["default", "kpi"] = Field(
        default="default",
        description=(
            "卡片视觉语义。default 为普通并列卡片；kpi 时 card.title 是指标名、"
            "card.desc 是核心数值、card.tag 是可选趋势或统计口径。"
        ),
    )

    _title_not_blank = field_validator("title")(non_empty)


class ChartSeries(ContractModel):
    name: str = Field(min_length=1)
    values: list[float] = Field(min_length=1, description="系列数值；与 thresholds[].value 使用相同数值单位。")
    x_values: list[float] | None = Field(default=None, description="scatter 系列的横坐标；其它图表必须省略。")
    chart_type: Literal["bar", "line"] | None = Field(default=None, description="combo 系列的原生图表类型。")
    axis: Literal["primary", "secondary"] = "primary"
    unit: str | None = Field(default=None, description="系列量纲；用于组合图双轴适用性审计，不执行单位换算。")
    emphasis: bool = False

    _name_not_blank = field_validator("name")(non_empty)

    @field_validator("values", "x_values")
    @classmethod
    def values_must_be_finite(_cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        if any(not math.isfinite(item) for item in value):
            raise ValueError("chart series values must be finite")
        return value

    @field_validator("unit")
    @classmethod
    def unit_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class ChartThreshold(ContractModel):
    value: float = Field(description="阈值数值；必须与 chart.series[].values 使用相同数值单位。")
    label: str = Field(min_length=1)

    _label_not_blank = field_validator("label")(non_empty)

    @field_validator("value")
    @classmethod
    def value_must_be_finite(_cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("chart threshold value must be finite")
        return value


class ChartSideTable(ContractModel):
    header: list[str] = Field(min_length=1, max_length=4)
    rows: list[list[str]] = Field(default_factory=list, max_length=6)

    @field_validator("header")
    @classmethod
    def header_cells_not_blank(_cls, value: list[str]) -> list[str]:
        if any(not str(cell).strip() for cell in value):
            raise ValueError("chart side_table header cells must not be blank")
        return value

    @model_validator(mode="after")
    def validate_rows(self) -> "ChartSideTable":
        expected_cols = len(self.header)
        if any(len(row) != expected_cols for row in self.rows):
            raise ValueError("chart side_table rows must match header column count")
        return self


class ChartSpec(ContractModel):
    kind: Literal["bar", "line", "pie", "scatter", "combo"]
    orientation: Literal["vertical", "horizontal"] = Field(
        default="vertical",
        description="bar 的数据方向；horizontal 生成横向数据条，line/pie 只能使用默认 vertical。",
    )
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(min_length=1)
    unit: str | None = Field(default=None, description="仅用于坐标轴和数据/阈值标签的显示后缀，不执行单位换算。")
    category_axis_title: str | None = None
    value_axis_title: str | None = None
    secondary_value_axis_title: str | None = None
    number_format: str | None = None
    secondary_number_format: str | None = None
    source: str | None = None
    methodology: str | None = None
    note: str | None = None
    thresholds: list[ChartThreshold] = Field(default_factory=list, max_length=4)
    show_data_labels: bool = True
    legend_position: Literal["top", "right", "none"] = "top"
    side_conclusion: str | None = None
    side_table: ChartSideTable | None = None

    @field_validator("categories")
    @classmethod
    def categories_not_blank(_cls, value: list[str]) -> list[str]:
        return [non_empty(category) for category in value]

    @field_validator(
        "unit",
        "category_axis_title",
        "value_axis_title",
        "secondary_value_axis_title",
        "number_format",
        "secondary_number_format",
        "source",
        "methodology",
        "note",
    )
    @classmethod
    def optional_chart_text_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None

    @model_validator(mode="after")
    def validate_chart_shape(self) -> "ChartSpec":
        expected_points = len(self.categories)
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("chart categories must be unique")
        series_names = [series.name for series in self.series]
        if len(set(series_names)) != len(series_names):
            raise ValueError("chart series names must be unique")
        if sum(1 for series in self.series if series.emphasis) > 1:
            raise ValueError("chart allows at most one emphasized series")
        if self.kind == "scatter":
            if self.categories:
                raise ValueError("scatter chart categories must be empty; use series x_values")
            for series in self.series:
                if series.x_values is None or len(series.x_values) != len(series.values):
                    raise ValueError("scatter series x_values must match values length")
                if series.chart_type is not None or series.axis != "primary":
                    raise ValueError("scatter series does not support chart_type or secondary axis")
        else:
            if not self.categories:
                raise ValueError("chart categories must contain at least one item")
            for series in self.series:
                if len(series.values) != expected_points:
                    raise ValueError("chart series values must match categories length")
                if series.x_values is not None:
                    raise ValueError("x_values is only supported for scatter charts")
        if self.kind == "pie" and len(self.series) != 1:
            raise ValueError("pie chart requires exactly one series")
        if self.kind == "pie" and self.thresholds:
            raise ValueError("pie chart does not support thresholds")
        if self.orientation == "horizontal" and self.kind != "bar":
            raise ValueError("horizontal chart orientation is only supported for bar charts")
        if self.kind == "combo":
            types = {series.chart_type for series in self.series}
            axes = {series.axis for series in self.series}
            if None in types or not {"bar", "line"}.issubset(types):
                raise ValueError("combo chart requires explicit bar and line series")
            if axes != {"primary", "secondary"}:
                raise ValueError("combo chart requires primary and secondary axes")
            primary_units = {series.unit or self.unit for series in self.series if series.axis == "primary"}
            secondary_units = {series.unit or self.unit for series in self.series if series.axis == "secondary"}
            if primary_units == secondary_units:
                raise ValueError("combo secondary axis requires a different business unit")
        elif any(series.chart_type is not None or series.axis != "primary" for series in self.series):
            raise ValueError("chart_type and secondary axis are only supported for combo charts")
        if self.kind != "combo" and (self.secondary_value_axis_title or self.secondary_number_format):
            raise ValueError("secondary axis metadata is only supported for combo charts")
        self._validate_side_conclusion()
        return self

    def _validate_side_conclusion(self) -> None:
        if not self.side_conclusion or not self.thresholds:
            return
        predicate = _threshold_predicate(self.side_conclusion)
        if predicate is None:
            return
        target = _chart_threshold_target_series(self.series)
        if target is None:
            raise ValueError("threshold side_conclusion requires exactly one emphasized series")
        if self.kind == "combo" and target.axis != "primary":
            raise ValueError("combo chart side_conclusion thresholds must reference the primary axis series")
        threshold = _chart_threshold_value(self.side_conclusion, self.thresholds)
        if threshold is None:
            return
        count = _continuous_month_count(self.side_conclusion)
        if count is not None and not _has_consecutive_run(target.values, count, lambda value: predicate(value, threshold.value)):
            raise ValueError("side_conclusion contradicts chart threshold values")
        start_index = _category_start_index(self.side_conclusion, self.categories)
        if start_index is not None and not all(predicate(value, threshold.value) for value in target.values[start_index:]):
            raise ValueError("side_conclusion contradicts chart threshold values")


def _chart_threshold_value(text: str, thresholds: list["ChartThreshold"]) -> "ChartThreshold | None":
    """Select the threshold referenced by the side_conclusion text.

    The text usually echoes the threshold number (e.g. "连续三个月高于80").
    With several thresholds the first one is no longer the right reference;
    when the text carries no unambiguous numeric reference the check is skipped.
    """
    if len(thresholds) == 1:
        return thresholds[0]
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    for number in reversed(numbers):
        target = float(number)
        for threshold in thresholds:
            if threshold.value == target:
                return threshold
    return None


class ChartSlide(ContractModel):
    layout: Literal["chart"]
    title: str = Field(min_length=1)
    chart: ChartSpec

    _title_not_blank = field_validator("title")(non_empty)


class DiagramPosition(ContractModel):
    x: float = Field(ge=0, le=1, description="节点中心相对架构图内容区宽度的归一化横坐标。")
    y: float = Field(ge=0, le=1, description="节点中心相对架构图内容区高度的归一化纵坐标。")


class DiagramSize(ContractModel):
    width: float = Field(gt=0, le=1, description="节点宽度占架构图内容区宽度的比例。")
    height: float = Field(gt=0, le=1, description="节点高度占架构图内容区高度的比例。")


class ArchitectureNode(ContractModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    type: str = Field(
        default="secondary",
        min_length=1,
        description=(
            "节点业务语义类型。主题已注册 primary、secondary、emphasis、data、job、module；"
            "其它非空值回退到 theme 的 default 配色，renderer 不根据节点文本猜测业务语义。"
        ),
    )
    group: str | None = None
    position: DiagramPosition | None = Field(default=None, description="可选节点中心位置；坐标相对架构图内容区归一化。")
    size: DiagramSize | None = Field(default=None, description="可选节点尺寸；宽高分别是架构图内容区宽高的比例。")

    _id_not_blank = field_validator("id")(non_empty)
    _text_not_blank = field_validator("text")(non_empty)
    _type_not_blank = field_validator("type")(non_empty)

    @field_validator("group")
    @classmethod
    def group_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class ArchitectureEdge(ContractModel):
    model_config = ConfigDict(extra="ignore", serialize_by_alias=True)

    from_node: str = Field(alias="from", min_length=1)
    to: str = Field(min_length=1)
    label: str | None = None
    style: Literal["solid", "dashed"] = "solid"
    direction: Literal["forward", "backward", "both", "none"] = "forward"

    _from_not_blank = field_validator("from_node")(non_empty)
    _to_not_blank = field_validator("to")(non_empty)

    @field_validator("label")
    @classmethod
    def label_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class ArchitectureGroup(ContractModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    node_ids: list[str] = Field(min_length=1, max_length=8)

    _id_not_blank = field_validator("id")(non_empty)
    _label_not_blank = field_validator("label")(non_empty)

    @field_validator("node_ids")
    @classmethod
    def node_ids_valid(_cls, value: list[str]) -> list[str]:
        normalized = [non_empty(node_id) for node_id in value]
        if len(set(normalized)) != len(normalized):
            raise ValueError("group node_ids must be unique")
        return normalized


class ArchitectureManualHints(ContractModel):
    node_positions: dict[str, DiagramPosition] = Field(
        default_factory=dict,
        max_length=12,
        description="按节点 id 覆盖 nodes[].position；不是在原坐标上追加偏移。",
    )
    node_sizes: dict[str, DiagramSize] = Field(
        default_factory=dict,
        max_length=12,
        description="按节点 id 覆盖 nodes[].size；不是在原尺寸上追加缩放。",
    )


class ArchitectureDiagramSlide(ContractModel):
    layout: Literal["architecture_diagram"]
    title: str = Field(min_length=1)
    nodes: list[ArchitectureNode] = Field(min_length=1, max_length=12)
    edges: list[ArchitectureEdge] = Field(max_length=24)
    groups: list[ArchitectureGroup] = Field(max_length=6)
    manual_hints: ArchitectureManualHints | None = None

    _title_not_blank = field_validator("title")(non_empty)

    @model_validator(mode="after")
    def validate_structure(self) -> "ArchitectureDiagramSlide":
        node_ids = [node.id for node in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("architecture node ids must be unique")
        group_ids = [group.id for group in self.groups]
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("architecture group ids must be unique")

        known_nodes = set(node_ids)
        known_groups = set(group_ids)
        for edge in self.edges:
            missing = [node_id for node_id in (edge.from_node, edge.to) if node_id not in known_nodes]
            if missing:
                raise ValueError(f"architecture edge references unknown node id: {', '.join(missing)}")
            if edge.from_node == edge.to:
                raise ValueError(f"architecture edge self-loop is not supported: {edge.from_node}")

        grouped_nodes: dict[str, str] = {}
        for group in self.groups:
            for node_id in group.node_ids:
                if node_id not in known_nodes:
                    raise ValueError(f"architecture group references unknown node id: {node_id}")
                if node_id in grouped_nodes:
                    raise ValueError(f"architecture node belongs to multiple groups: {node_id}")
                grouped_nodes[node_id] = group.id

        for node in self.nodes:
            if node.group is None:
                continue
            if node.group not in known_groups:
                raise ValueError(f"architecture node references unknown group id: {node.group}")
            if grouped_nodes.get(node.id) != node.group:
                raise ValueError(f"architecture node/group membership is inconsistent: {node.id}")

        if self.manual_hints is not None:
            hinted_nodes = set(self.manual_hints.node_positions) | set(self.manual_hints.node_sizes)
            unknown_hints = sorted(hinted_nodes - known_nodes)
            if unknown_hints:
                raise ValueError(f"architecture manual_hints reference unknown node id: {', '.join(unknown_hints)}")
        return self


class ProcessStep(ContractModel):
    id: str = Field(min_length=1, description="流程步骤的唯一稳定标识，供渲染对象命名和顺序复核使用。")
    title: str = Field(min_length=1, description="步骤名称，应直接来自输入材料中的顺序步骤。")
    description: str | None = Field(default=None, description="可选的步骤说明；不得补写输入中不存在的事实。")

    _id_not_blank = field_validator("id")(non_empty)
    _title_not_blank = field_validator("title")(non_empty)

    @field_validator("description")
    @classmethod
    def description_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class ProcessFlowSlide(ContractModel):
    layout: Literal["process_flow"] = Field(description="固定为 process_flow，仅表达无分支的线性步骤。")
    title: str = Field(min_length=1, description="结论式页面标题，说明该流程达成的结果。")
    steps: list[ProcessStep] = Field(
        min_length=2,
        max_length=7,
        description="按执行顺序排列的 2-7 个步骤；存在分支时应改用 architecture_diagram。",
    )
    orientation: Literal["horizontal", "vertical"] = Field(
        default="horizontal",
        description="步骤排列方向；密集纵向流程可能触发 HW-W03 人工拆分提示。",
    )

    _title_not_blank = field_validator("title")(non_empty)

    @model_validator(mode="after")
    def validate_step_ids(self) -> "ProcessFlowSlide":
        step_ids = [step.id for step in self.steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("process_flow step ids must be unique")
        return self


class TimelineMilestone(ContractModel):
    label: str = Field(min_length=1, description="时间或里程碑标签，例如 2026 Q3、7月或 M1。")
    title: str = Field(min_length=1, description="该时间节点对应的事件或阶段名称。")
    description: str | None = Field(default=None, description="可选的里程碑说明；不得编造日期、状态或结果。")
    status: Literal["completed", "current", "planned"] = Field(
        default="planned",
        description="里程碑状态；数组内按 completed、current、planned 的时间顺序排列。",
    )

    _label_not_blank = field_validator("label")(non_empty)
    _title_not_blank = field_validator("title")(non_empty)

    @field_validator("description")
    @classmethod
    def description_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class TimelineSlide(ContractModel):
    layout: Literal["timeline"] = Field(description="固定为 timeline，仅表达带明确时间标签的阶段演进。")
    title: str = Field(min_length=1, description="结论式页面标题，说明阶段演进带来的判断。")
    milestones: list[TimelineMilestone] = Field(
        min_length=2,
        max_length=8,
        description="按时间顺序排列的 2-8 个里程碑；不用于表达精确 Gantt 的持续时间或依赖关系。",
    )
    orientation: Literal["horizontal", "vertical"] = Field(
        default="horizontal",
        description="里程碑排列方向；密集纵向时间线可能触发 HW-W03 人工拆分提示。",
    )

    _title_not_blank = field_validator("title")(non_empty)

    @model_validator(mode="after")
    def validate_status_sequence(self) -> "TimelineSlide":
        statuses = [milestone.status for milestone in self.milestones]
        if statuses.count("current") > 1:
            raise ValueError("timeline allows at most one current milestone")
        rank = {"completed": 0, "current": 1, "planned": 2}
        if any(rank[current] < rank[previous] for previous, current in zip(statuses, statuses[1:])):
            raise ValueError("timeline statuses must follow completed, current, planned order")
        return self


def _chart_threshold_target_series(series: list[ChartSeries]) -> ChartSeries | None:
    emphasized = [item for item in series if item.emphasis]
    if len(emphasized) == 1:
        return emphasized[0]
    if len(series) == 1:
        return series[0]
    return None


def _threshold_predicate(text: str):
    if "低于" in text:
        return lambda value, threshold: value < threshold
    if any(word in text for word in ("高于", "超过", "超出")):
        return lambda value, threshold: value > threshold
    return None


def _category_start_index(text: str, categories: list[str]) -> int | None:
    matches = [(len(category), index) for index, category in enumerate(categories) if f"{category}起" in text]
    if not matches:
        return None
    return max(matches)[1]


def _continuous_month_count(text: str) -> int | None:
    match = re.search(r"连续\s*(?P<count>\d+|[一二两三四五六七八九十]+)\s*个?月", text)
    if not match:
        return None
    value = match.group("count")
    if value.isdigit():
        return int(value)
    return _chinese_count(value)


def _chinese_count(value: str) -> int | None:
    digits = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value == "十":
        return 10
    if value in digits:
        return digits[value]
    if value.startswith("十") and len(value) == 2 and value[1] in digits:
        return 10 + digits[value[1]]
    if value.endswith("十") and len(value) == 2 and value[0] in digits:
        return digits[value[0]] * 10
    if "十" in value and len(value) == 3 and value[0] in digits and value[2] in digits:
        return digits[value[0]] * 10 + digits[value[2]]
    return None


def _has_consecutive_run(values: list[float], count: int | None, predicate) -> bool:
    if count is None or count <= 0:
        return True
    current = 0
    for value in values:
        current = current + 1 if predicate(value) else 0
        if current >= count:
            return True
    return False


SemanticIcon = Literal[
    "person",
    "team",
    "organization",
    "target",
    "risk",
    "cost",
    "quality",
    "data",
    "cloud",
    "device",
    "security",
    "process",
    "time",
    "growth",
    "decline",
    "check",
    "warning",
    "idea",
    "service",
    "network",
    "database",
    "document",
    "settings",
    "delivery",
]


class ImageAssetSpec(ContractModel):
    image_ref: str = Field(min_length=1)
    fit: Literal["contain", "cover"] = "contain"
    focal_x: float = Field(default=0.5, ge=0, le=1)
    focal_y: float = Field(default=0.5, ge=0, le=1)
    alt: str | None = None
    caption: str | None = None
    credit: str | None = None

    _image_ref_not_blank = field_validator("image_ref")(non_empty)

    @field_validator("alt", "caption", "credit")
    @classmethod
    def optional_image_text_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class ImageSlide(ContractModel):
    layout: Literal["image"]
    title: str = Field(min_length=1)
    image_ref: str | None = None
    placeholder: str | None = None
    caption: str | None = None
    fit: Literal["contain", "cover"] = "contain"
    focal_x: float = Field(default=0.5, ge=0, le=1)
    focal_y: float = Field(default=0.5, ge=0, le=1)
    alt: str | None = None
    credit: str | None = None

    _title_not_blank = field_validator("title")(non_empty)

    @field_validator("image_ref", "placeholder", "caption", "alt", "credit")
    @classmethod
    def optional_value_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None

    @model_validator(mode="after")
    def require_image_source_or_placeholder(self) -> "ImageSlide":
        if not self.image_ref and not self.placeholder:
            raise ValueError("image layout requires image_ref or placeholder")
        return self


class ImageTextSlide(ContractModel):
    layout: Literal["image_text"]
    title: str = Field(min_length=1)
    image: ImageAssetSpec
    image_position: Literal["left", "right"] = "left"
    heading: str | None = None
    text: str | None = None
    bullets: list[str] = Field(default_factory=list, max_length=5)

    _title_not_blank = field_validator("title")(non_empty)

    @field_validator("heading", "text")
    @classmethod
    def optional_text_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None

    @field_validator("bullets")
    @classmethod
    def bullets_not_blank(_cls, value: list[str]) -> list[str]:
        return [non_empty(item) for item in value]

    @model_validator(mode="after")
    def body_is_present(self) -> "ImageTextSlide":
        if not self.text and not self.bullets:
            raise ValueError("image_text requires text or bullets")
        return self


class ImageGridSlide(ContractModel):
    layout: Literal["image_grid"]
    title: str = Field(min_length=1)
    images: list[ImageAssetSpec] = Field(min_length=2, max_length=4)

    _title_not_blank = field_validator("title")(non_empty)

    @model_validator(mode="after")
    def image_refs_are_unique(self) -> "ImageGridSlide":
        refs = [image.image_ref for image in self.images]
        if len(refs) != len(set(refs)):
            raise ValueError("image_grid image_ref values must be unique")
        return self


class InfographicStage(ContractModel):
    label: str = Field(min_length=1)
    description: str | None = None
    value: str | None = None
    icon: SemanticIcon | None = None

    _label_not_blank = field_validator("label")(non_empty)

    @field_validator("description", "value")
    @classmethod
    def optional_stage_text_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


class FunnelInfographic(ContractModel):
    kind: Literal["funnel"]
    direction: Literal["forward", "reverse"] = "forward"
    stages: list[InfographicStage] = Field(min_length=3, max_length=6)


class QuadrantItem(ContractModel):
    label: str = Field(min_length=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    category: str | None = None
    icon: SemanticIcon | None = None

    _label_not_blank = field_validator("label")(non_empty)


class QuadrantInfographic(ContractModel):
    kind: Literal["quadrant"]
    x_axis: str = Field(min_length=1)
    y_axis: str = Field(min_length=1)
    items: list[QuadrantItem] = Field(min_length=1, max_length=12)

    _x_axis_not_blank = field_validator("x_axis")(non_empty)
    _y_axis_not_blank = field_validator("y_axis")(non_empty)


class CycleInfographic(ContractModel):
    kind: Literal["cycle"]
    stages: list[InfographicStage] = Field(min_length=3, max_length=6)


class MatrixInfographic(ContractModel):
    kind: Literal["matrix"]
    row_labels: list[str] = Field(min_length=2, max_length=4)
    column_labels: list[str] = Field(min_length=2, max_length=4)
    cells: list[list[str]] = Field(min_length=2, max_length=4)

    @field_validator("row_labels", "column_labels")
    @classmethod
    def labels_not_blank(_cls, value: list[str]) -> list[str]:
        return [non_empty(item) for item in value]

    @model_validator(mode="after")
    def cells_match_labels(self) -> "MatrixInfographic":
        if len(self.cells) != len(self.row_labels) or any(len(row) != len(self.column_labels) for row in self.cells):
            raise ValueError("matrix cells must match row and column labels")
        self.cells = [[non_empty(cell) for cell in row] for row in self.cells]
        return self


InfographicSpec = Annotated[
    Union[FunnelInfographic, QuadrantInfographic, CycleInfographic, MatrixInfographic],
    Field(discriminator="kind"),
]


class InfographicSlide(ContractModel):
    layout: Literal["infographic"]
    title: str = Field(min_length=1)
    infographic: InfographicSpec

    _title_not_blank = field_validator("title")(non_empty)


class ConclusionSlide(ContractModel):
    layout: Literal["conclusion"]
    title: str = Field(min_length=1)
    bullets: list[str] = Field(default_factory=list, max_length=5)
    cta: str | None = None

    _title_not_blank = field_validator("title")(non_empty)

    @field_validator("bullets")
    @classmethod
    def bullets_not_blank(_cls, value: list[str]) -> list[str]:
        return [non_empty(item) for item in value]

    @field_validator("cta")
    @classmethod
    def cta_not_blank(_cls, value: str | None) -> str | None:
        return non_empty(value) if value is not None else None


CompositeComponent = Annotated[
    Union[TableSlide, ArchitectureDiagramSlide, TitleBulletsSlide, CardsSlide],
    Field(
        discriminator="layout",
        description=(
            "嵌入区域复用的既有组件；首版仅允许 table、architecture_diagram、"
            "title_bullets、cards，并继续执行对应组件的全部字段校验。"
        ),
    ),
]


class CompositeRegion(ContractModel):
    slot: Literal["left", "right"] = Field(description="区域位置；固定为 left 或 right。")
    components: list[CompositeComponent] = Field(
        min_length=1,
        max_length=3,
        description=(
            "栏内从上到下堆叠的既有组件，首版最多 3 块。单块列表与 v1.7 的单 component"
            " 语义一致；超过栏高时渲染后由 HW-W03 提示人工拆分。"
        ),
    )


class CompositeSlide(ContractModel):
    layout: Literal["composite"] = Field(description="固定为 composite，表达左右栏内多个既有组件的联读关系。")
    title: str = Field(min_length=1, description="整页结论式标题；每个嵌入组件仍保留自己的区域小标题。")
    regions: list[CompositeRegion] = Field(
        min_length=2,
        max_length=2,
        description="恰好两个区域，必须各包含一个 left 和 right；区域坐标和栏内堆叠坐标由主题确定，模型不提供任意坐标。",
    )

    _title_not_blank = field_validator("title")(non_empty)

    @model_validator(mode="after")
    def validate_region_slots(self) -> "CompositeSlide":
        slots = [region.slot for region in self.regions]
        if slots.count("left") != 1 or slots.count("right") != 1:
            raise ValueError("composite regions must contain exactly one left and one right slot")
        return self


DeckSlide = Annotated[
    Union[
        CoverSlide,
        AgendaSlide,
        SectionSlide,
        TitleBulletsSlide,
        TwoColumnSlide,
        TableSlide,
        CardsSlide,
        ChartSlide,
        ArchitectureDiagramSlide,
        ProcessFlowSlide,
        TimelineSlide,
        ImageSlide,
        ImageTextSlide,
        ImageGridSlide,
        InfographicSlide,
        ConclusionSlide,
        CompositeSlide,
    ],
    Field(discriminator="layout"),
]


def migrate_deck_payload(value: Any, *, target_version: str = "2.0") -> tuple[Any, str | None]:
    if (
        not isinstance(value, dict)
        or value.get("ir_version") not in {"1.4", "1.5", "1.6", "1.7", "1.8", "1.9"}
        or target_version != "2.0"
    ):
        return value, None
    source_version = value["ir_version"]
    migrated = copy.deepcopy(value)
    if source_version == "1.7":
        slides = migrated.get("slides")
        if isinstance(slides, list):
            for slide in slides:
                if not isinstance(slide, dict) or slide.get("layout") != "composite":
                    continue
                regions = slide.get("regions")
                if not isinstance(regions, list):
                    continue
                for region in regions:
                    if not isinstance(region, dict) or "components" in region or "component" not in region:
                        continue
                    region["components"] = [region.pop("component")]
    migrated["ir_version"] = "2.0"
    return migrated, source_version


class DeckIR(ContractModel):
    ir_type: Literal["deck"]
    ir_version: Literal["2.0"]
    meta: DeckMeta
    slides: list[DeckSlide] = Field(min_length=1, max_length=30)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_payload(cls, value: Any) -> Any:
        migrated, _source_version = migrate_deck_payload(value)
        return migrated
