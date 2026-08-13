from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def load_schema(name: str) -> dict:
    return json.loads((ROOT / "backend" / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_word_ir_validates_minimal_report() -> None:
    from app.ir.word_ir import WordIR

    ir = WordIR.model_validate(
        {
            "ir_type": "word",
            "ir_version": "1.0",
            "meta": {"title": "周报", "classification": "内部公开"},
            "blocks": [
                {"type": "heading", "level": 1, "text": "本周进展"},
                {"type": "paragraph", "text": "完成 C0 契约冻结。"},
            ],
        }
    )

    assert ir.meta.title == "周报"
    assert ir.ir_version == "1.3"
    assert ir.blocks[0].type == "heading"


@pytest.mark.parametrize("source_version", ["1.0", "1.1", "1.2"])
def test_word_ir_legacy_versions_migrate_to_v13_without_mutating_input(source_version: str) -> None:
    import copy

    from app.ir.word_ir import WordIR

    payload = {
        "ir_type": "word",
        "ir_version": source_version,
        "meta": {"title": "旧版报告"},
        "blocks": [{"type": "paragraph", "text": "正文"}],
    }
    original = copy.deepcopy(payload)

    migrated = WordIR.model_validate(payload)

    assert migrated.ir_version == "1.3"
    assert payload == original


def test_word_ir_document_control_requires_matching_classification() -> None:
    from pydantic import ValidationError

    from app.ir.word_ir import WordIR

    with pytest.raises(ValidationError, match="must match meta.classification"):
        WordIR.model_validate(
            {
                "ir_type": "word",
                "ir_version": "1.2",
                "meta": {
                    "title": "详设",
                    "classification": "内部公开",
                    "document_control": {
                        "product_name": "产品",
                        "document_name": "模块详设",
                        "classification": "公开",
                        "version": "V1.0",
                    },
                },
                "blocks": [{"type": "paragraph", "text": "正文"}],
            }
        )


def test_word_ir_rejects_empty_blocks() -> None:
    from pydantic import ValidationError

    from app.ir.word_ir import WordIR

    with pytest.raises(ValidationError):
        WordIR.model_validate(
            {
                "ir_type": "word",
                "ir_version": "1.0",
                "meta": {"title": "空文档", "classification": "内部公开"},
                "blocks": [],
            }
        )


def test_document_ir_validates_empty_input_summary() -> None:
    from app.ir.document_ir import DocumentIR

    ir = DocumentIR.model_validate(
        {
            "ir_type": "document",
            "ir_version": "1.1",
            "source": {
                "filename": "empty.md",
                "format": "md",
                "size_kb": 0,
                "parsed_at": "2026-07-08T00:00:00Z",
            },
            "stats": {"headings": 0, "paragraphs": 0, "tables": 0, "images": 0},
            "warnings": [],
            "content": {"blocks": [], "outline": []},
        }
    )

    assert ir.source.format == "md"
    assert ir.content.blocks == []


def test_deck_ir_validates_minimal_deck() -> None:
    from app.ir.deck_ir import DeckIR

    ir = DeckIR.model_validate(
        {
            "ir_type": "deck",
            "ir_version": "1.7",
            "meta": {"title": "C0 契约冻结", "classification": "HUAWEI CONFIDENTIAL", "theme": "hw_v1"},
            "slides": [
                {"layout": "cover", "title": "C0 契约冻结", "subtitle": "IR / Schema / Stub"},
                {"layout": "agenda", "items": ["IR", "Schema", "Stub"]},
            ],
        }
    )

    assert ir.meta.title == "C0 契约冻结"
    assert [slide.layout for slide in ir.slides] == ["cover", "agenda"]


def test_schema_files_match_current_models() -> None:
    from app.ir.deck_ir import DeckIR
    from app.ir.document_ir import DocumentIR
    from app.ir.word_ir import WordIR
    from app.ir.schema_export import normalized_schema

    assert load_schema("word_ir") == normalized_schema(WordIR)
    assert load_schema("document_ir") == normalized_schema(DocumentIR)
    assert load_schema("deck_ir") == normalized_schema(DeckIR)


def test_schema_history_and_snapshots_match_current_models() -> None:
    from app.ir.schema_export import verify_schema_snapshots

    verified = verify_schema_snapshots(ROOT / "backend" / "schemas")

    assert {path.name for path in verified} == {
        "word_ir.schema.json",
        "document_ir.schema.json",
        "deck_ir.schema.json",
    }


def test_schema_snapshot_tamper_is_rejected(tmp_path: Path) -> None:
    import shutil

    from app.ir.schema_export import SchemaSnapshotError, verify_schema_snapshots

    schema_dir = tmp_path / "schemas"
    shutil.copytree(ROOT / "backend" / "schemas", schema_dir)
    schema = json.loads((schema_dir / "word_ir.schema.json").read_text(encoding="utf-8"))
    schema["properties"]["blocks"]["minItems"] = 0
    (schema_dir / "word_ir.schema.json").write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(SchemaSnapshotError, match="snapshot drifted"):
        verify_schema_snapshots(schema_dir)


def test_schema_change_without_version_bump_cannot_be_exported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from app.ir import schema_export
    from app.ir.schema_export import SchemaVersionError, export_schemas
    from app.ir.word_ir import WordIR

    class ChangedWordIR(WordIR):
        accidental_field: str | None = None

    schema_dir = tmp_path / "schemas"
    shutil.copytree(ROOT / "backend" / "schemas", schema_dir)
    monkeypatch.setitem(schema_export.SCHEMA_MODELS, "word_ir", ChangedWordIR)

    with pytest.raises(SchemaVersionError, match="ir_version stayed"):
        export_schemas(schema_dir, update_history=True)


def test_explicit_schema_export_rewrites_registered_snapshots(tmp_path: Path) -> None:
    import shutil

    from app.ir.schema_export import export_schemas, verify_schema_snapshots

    schema_dir = tmp_path / "schemas"
    shutil.copytree(ROOT / "backend" / "schemas", schema_dir)

    written = export_schemas(schema_dir, update_history=True)

    assert {path.name for path in written} == {
        "word_ir.schema.json",
        "document_ir.schema.json",
        "deck_ir.schema.json",
        "schema_history.json",
    }
    assert len(verify_schema_snapshots(schema_dir)) == 3


def test_description_only_schema_update_can_refresh_same_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import copy
    import shutil

    from app.ir import schema_export
    from app.ir.schema_export import export_schemas, verify_schema_snapshots

    schema_dir = tmp_path / "schemas"
    shutil.copytree(ROOT / "backend" / "schemas", schema_dir)
    original_normalized_schema = schema_export.normalized_schema

    def with_description(model):
        schema = copy.deepcopy(original_normalized_schema(model))
        if model is schema_export.SCHEMA_MODELS["word_ir"]:
            schema["properties"]["blocks"]["description"] = "仅补充字段语义说明"
        return schema

    monkeypatch.setattr(schema_export, "normalized_schema", with_description)

    export_schemas(schema_dir, update_history=True)

    assert len(verify_schema_snapshots(schema_dir)) == 3
    updated = json.loads((schema_dir / "word_ir.schema.json").read_text(encoding="utf-8"))
    assert updated["properties"]["blocks"]["description"] == "仅补充字段语义说明"


def test_verify_stops_on_schema_failure_without_rewriting(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import scripts.verify as verify
    from app.ir.schema_export import SchemaSnapshotError

    def fail_verification(_path: Path) -> None:
        raise SchemaSnapshotError("injected drift")

    monkeypatch.setattr(verify, "verify_schema_snapshots", fail_verification)

    assert verify.main() == 1
    assert "schema verification failed: injected drift" in capsys.readouterr().err


def test_word_schema_requires_non_empty_blocks() -> None:
    schema = load_schema("word_ir")

    assert "blocks" in schema["required"]
    assert schema["properties"]["blocks"]["minItems"] == 1


def test_document_schema_exposes_format_and_preview_limits() -> None:
    schema = load_schema("document_ir")
    sheet_props = schema["$defs"]["SheetSummary"]["properties"]
    table_props = schema["$defs"]["DocumentTableBlock"]["properties"]

    assert schema["properties"]["ir_version"]["const"] == "1.2"
    assert len(schema["allOf"]) == 3
    assert sheet_props["preview_rows"]["maxItems"] == 20
    assert sheet_props["preview_rows"]["items"]["maxItems"] == 15
    assert table_props["rows"]["maxItems"] == 20


@pytest.mark.parametrize(
    ("source_format", "content_key"),
    [
        ("md", "sheets"),
        ("docx", "slides"),
        ("xlsx", "blocks"),
        ("xlsx", "outline"),
        ("pptx", "sheets"),
    ],
)
def test_document_ir_rejects_content_for_another_format(source_format: str, content_key: str) -> None:
    from pydantic import ValidationError

    from app.ir.document_ir import DocumentIR

    foreign_content = {
        "blocks": [{"type": "paragraph", "text": "不应出现"}],
        "outline": [{"level": 1, "text": "不应出现"}],
        "sheets": [{"name": "不应出现", "nrows": 0, "ncols": 0}],
        "slides": [{"index": 1, "title": "不应出现"}],
    }[content_key]
    payload = {
        "ir_type": "document",
        "ir_version": "1.1",
        "source": {
            "filename": f"input.{source_format}",
            "format": source_format,
            "size_kb": 1,
            "parsed_at": "2026-07-10T00:00:00Z",
        },
        "stats": {},
        "content": {content_key: foreign_content},
    }

    with pytest.raises(ValidationError, match=f"content.{content_key}"):
        DocumentIR.model_validate(payload)


def test_document_ir_accepts_preview_limits_and_rejects_overflow() -> None:
    from pydantic import ValidationError

    from app.ir.document_ir import DocumentIR

    payload = {
        "ir_type": "document",
        "ir_version": "1.1",
        "source": {
            "filename": "台账.xlsx",
            "format": "xlsx",
            "size_kb": 1,
            "parsed_at": "2026-07-10T00:00:00Z",
        },
        "stats": {},
        "content": {
            "sheets": [
                {
                    "name": "台账",
                    "nrows": 21,
                    "ncols": 15,
                    "preview_rows": [[str(column) for column in range(15)] for _ in range(20)],
                }
            ]
        },
    }

    assert len(DocumentIR.model_validate(payload).content.sheets[0].preview_rows) == 20
    payload["content"]["sheets"][0]["preview_rows"].append(["overflow"])
    with pytest.raises(ValidationError, match="at most 20 items"):
        DocumentIR.model_validate(payload)

    payload["content"]["sheets"][0]["preview_rows"] = [[str(column) for column in range(16)]]
    with pytest.raises(ValidationError, match="at most 15 items"):
        DocumentIR.model_validate(payload)


def test_document_ir_reads_v10_as_v12_with_explicit_migration_warning() -> None:
    from app.ir.document_ir import DocumentIR

    payload = {
        "ir_type": "document",
        "ir_version": "1.0",
        "source": {
            "filename": "legacy.md",
            "format": "md",
            "size_kb": 1,
            "parsed_at": "2026-07-01T00:00:00Z",
        },
        "stats": {},
        "warnings": [],
        "content": {"blocks": [{"type": "paragraph", "text": "存量摘要"}]},
    }

    migrated = DocumentIR.model_validate(payload)

    assert migrated.ir_version == "1.2"
    assert migrated.content.blocks[0].text == "存量摘要"
    assert any("DocumentIR 1.0" in warning and "1.2" in warning for warning in migrated.warnings)


def test_document_ir_v10_migration_still_enforces_v11_constraints() -> None:
    from pydantic import ValidationError

    from app.ir.document_ir import DocumentIR

    payload = {
        "ir_type": "document",
        "ir_version": "1.0",
        "source": {"filename": "legacy.md", "format": "md", "size_kb": 1, "parsed_at": "now"},
        "stats": {},
        "content": {"sheets": [{"name": "非法跨格式", "nrows": 0, "ncols": 0}]},
    }

    with pytest.raises(ValidationError, match="content.sheets"):
        DocumentIR.model_validate(payload)


def test_deck_schema_exposes_decision_matrix_table_contract() -> None:
    schema = load_schema("deck_ir")
    table_props = schema["$defs"]["DeckTable"]["properties"]

    assert schema["properties"]["ir_version"]["const"] == "2.2"
    assert {"column_groups", "row_groups", "cell_spans", "conclusion_col", "col_widths"} <= set(table_props)
    assert table_props["rows"]["maxItems"] == 12
    assert table_props["header"]["maxItems"] == 8


def test_deck_schema_exposes_performance_chart_contract() -> None:
    schema = load_schema("deck_ir")
    chart_props = schema["$defs"]["ChartSpec"]["properties"]
    series_props = schema["$defs"]["ChartSeries"]["properties"]

    assert {"orientation", "unit", "thresholds", "show_data_labels", "legend_position", "side_conclusion", "side_table"} <= set(chart_props)
    assert chart_props["orientation"]["default"] == "vertical"
    assert "emphasis" in series_props


def test_deck_schema_v20_exposes_kpi_card_variant() -> None:
    schema = load_schema("deck_ir")
    cards_props = schema["$defs"]["CardsSlide"]["properties"]

    assert schema["properties"]["ir_version"]["const"] == "2.2"
    assert cards_props["variant"]["default"] == "default"
    assert set(cards_props["variant"]["enum"]) == {"default", "kpi"}


def test_deck_schema_exposes_architecture_diagram_contract() -> None:
    schema = load_schema("deck_ir")
    slide_props = schema["$defs"]["ArchitectureDiagramSlide"]["properties"]
    node_props = schema["$defs"]["ArchitectureNode"]["properties"]
    edge_props = schema["$defs"]["ArchitectureEdge"]["properties"]
    group_props = schema["$defs"]["ArchitectureGroup"]["properties"]

    assert schema["properties"]["ir_version"]["const"] == "2.2"
    assert {"nodes", "edges", "groups", "manual_hints"} <= set(slide_props)
    assert {"layout", "title", "nodes", "edges", "groups"} <= set(schema["$defs"]["ArchitectureDiagramSlide"]["required"])
    assert {"id", "text", "type", "group", "position", "size"} <= set(node_props)
    assert node_props["type"]["type"] == "string"
    assert "job" in node_props["type"]["description"] and "module" in node_props["type"]["description"]
    assert {"from", "to", "label", "style", "direction"} <= set(edge_props)
    assert {"id", "label", "node_ids"} <= set(group_props)


def test_deck_schema_v20_exposes_process_flow_and_timeline_contracts() -> None:
    schema = load_schema("deck_ir")
    process_props = schema["$defs"]["ProcessFlowSlide"]["properties"]
    step_props = schema["$defs"]["ProcessStep"]["properties"]
    timeline_props = schema["$defs"]["TimelineSlide"]["properties"]
    milestone_props = schema["$defs"]["TimelineMilestone"]["properties"]

    assert schema["properties"]["ir_version"]["const"] == "2.2"
    assert {"layout", "title", "steps", "orientation"} <= set(process_props)
    assert process_props["steps"]["minItems"] == 2
    assert process_props["steps"]["maxItems"] == 7
    assert {"id", "title", "description"} <= set(step_props)
    assert {"layout", "title", "milestones", "orientation"} <= set(timeline_props)
    assert timeline_props["milestones"]["minItems"] == 2
    assert timeline_props["milestones"]["maxItems"] == 8
    assert {"label", "title", "description", "status"} <= set(milestone_props)
    assert set(milestone_props["status"]["enum"]) == {"completed", "current", "planned"}


def test_deck_schema_v20_exposes_stacked_composite_as_existing_component_union() -> None:
    schema = load_schema("deck_ir")
    composite_props = schema["$defs"]["CompositeSlide"]["properties"]
    region_props = schema["$defs"]["CompositeRegion"]["properties"]

    assert schema["properties"]["ir_version"]["const"] == "2.2"
    assert composite_props["regions"]["minItems"] == 2
    assert composite_props["regions"]["maxItems"] == 2
    assert set(region_props["slot"]["enum"]) == {"left", "right"}
    component_refs = {
        item["$ref"]
        for item in region_props["components"]["items"]["oneOf"]
    }
    assert component_refs == {
        "#/$defs/TableSlide",
        "#/$defs/ArchitectureDiagramSlide",
        "#/$defs/TitleBulletsSlide",
        "#/$defs/CardsSlide",
    }
    assert region_props["components"]["minItems"] == 1
    assert region_props["components"]["maxItems"] == 3


def test_schema_describes_model_facing_table_chart_and_architecture_semantics() -> None:
    word_schema = load_schema("word_ir")
    deck_schema = load_schema("deck_ir")

    word_col_widths = word_schema["$defs"]["TableBlock"]["properties"]["col_widths"]["description"]
    table_props = deck_schema["$defs"]["DeckTable"]["properties"]
    column_group_props = deck_schema["$defs"]["TableColumnGroup"]["properties"]
    span_props = deck_schema["$defs"]["TableCellSpan"]["properties"]
    chart_props = deck_schema["$defs"]["ChartSpec"]["properties"]
    threshold_props = deck_schema["$defs"]["ChartThreshold"]["properties"]
    position_props = deck_schema["$defs"]["DiagramPosition"]["properties"]
    size_props = deck_schema["$defs"]["DiagramSize"]["properties"]
    hint_props = deck_schema["$defs"]["ArchitectureManualHints"]["properties"]

    assert "相对宽度权重" in word_col_widths and "不是英寸" in word_col_widths
    assert "相对宽度权重" in table_props["col_widths"]["description"]
    assert "0 起始" in table_props["conclusion_col"]["description"]
    assert "0 起始" in column_group_props["start_col"]["description"]
    assert "数量" in column_group_props["span"]["description"]
    assert "0 起始" in span_props["row"]["description"]
    assert "数量" in span_props["rowspan"]["description"]
    assert "显示后缀" in chart_props["unit"]["description"]
    assert "相同数值单位" in threshold_props["value"]["description"]
    assert "中心" in position_props["x"]["description"]
    assert "比例" in size_props["width"]["description"]
    assert "覆盖" in hint_props["node_positions"]["description"]


def test_stub_generator_outputs_valid_target_ir() -> None:
    from app.generators.stub import StubGenerator
    from app.ir.deck_ir import DeckIR
    from app.ir.word_ir import WordIR

    generator = StubGenerator()

    word = WordIR.model_validate_json(generator.generate("empty", target="word_ir"))
    deck = DeckIR.model_validate_json(generator.generate("empty", target="deck_ir"))

    assert word.ir_type == "word"
    assert deck.ir_type == "deck"


def test_nga_generator_requires_intranet_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.generators.nga import NgaGenerator, NgaGeneratorError

    monkeypatch.delenv("NGA_BASE_URL", raising=False)
    monkeypatch.delenv("NGA_MODEL", raising=False)
    monkeypatch.delenv("NGA_TOKEN", raising=False)
    generator = NgaGenerator(base_url=None, token=None)

    with pytest.raises(NgaGeneratorError) as captured:
        generator.generate("prompt", target="deck_ir")

    assert captured.value.code == "E010"
    assert captured.value.retryable is False


def test_verify_main_runs_stub_chain_when_all_gates_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.verify as verify

    monkeypatch.setattr(verify, "_run_four_format_e2e", lambda _output_dir: True)
    monkeypatch.setattr(verify, "_run_pytest_with_coverage", lambda _output_dir: True)

    # Write into an isolated directory: the shared ROOT/output is a race with
    # any concurrently running pytest instance (or verify.py) over the same
    # c0_word.docx/c0_deck.pptx/report.json files.
    assert verify.main(tmp_path) == 0
    assert (tmp_path / "c0_word.docx").exists()
    assert (tmp_path / "c0_deck.pptx").exists()
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["pass"] is True


def test_verify_coverage_gate_cannot_be_bypassed_by_external_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.verify as verify

    monkeypatch.setenv("VERIFY_RUNNING", "1")
    monkeypatch.setattr(
        verify.subprocess,
        "run",
        lambda *_args, **_kwargs: type("Result", (), {"returncode": 1, "stdout": "failed", "stderr": ""})(),
    )

    assert verify._run_pytest_with_coverage(tmp_path) is False


def test_verify_coverage_gate_rejects_low_package_and_overall_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.verify as verify

    def write_low_coverage(command, **_kwargs):
        report_arg = next(value for value in command if value.startswith("--cov-report=json:"))
        report_path = Path(report_arg.split(":", 1)[1])
        report_path.write_text(
            json.dumps(
                {
                    "files": {
                        "backend/app/parsers/a.py": {"summary": {"num_statements": 100, "covered_lines": 79}},
                        "backend/app/ir/a.py": {"summary": {"num_statements": 100, "covered_lines": 79}},
                        "backend/app/lint/a.py": {"summary": {"num_statements": 100, "covered_lines": 79}},
                    },
                    "totals": {"percent_covered": 69.0},
                }
            ),
            encoding="utf-8",
        )
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.delenv("VERIFY_RUNNING", raising=False)
    monkeypatch.setattr(verify.subprocess, "run", write_low_coverage)

    assert verify._run_pytest_with_coverage(tmp_path) is False


def test_table_row_schemas_require_min_one_row_but_document_ir_stays_lenient() -> None:
    word = load_schema("word_ir")
    deck = load_schema("deck_ir")
    document = load_schema("document_ir")

    # IR-N4: the output contracts' exported schema must match the model's
    # runtime "at least one data row" validator so the model never emits a
    # table that the validator then rejects.
    assert word["$defs"]["TableBlock"]["properties"]["rows"]["minItems"] == 1
    assert deck["$defs"]["DeckTable"]["properties"]["rows"]["minItems"] == 1
    # IR-N8: DocumentIR is source data; empty tables are legal there.
    assert "minItems" not in document["$defs"]["DocumentTableBlock"]["properties"]["rows"]
