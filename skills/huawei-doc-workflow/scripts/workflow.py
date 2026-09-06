"""Deterministic workflow CLI for the standalone huawei-doc-workflow skill."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Callable
import warnings


SKILL_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = Path(__file__).resolve().parent / "engine"
ENGINE_APP_ROOT = ENGINE_ROOT / "app"
SKILL_NAME = "huawei-doc-workflow"
SKILL_VERSION = "1.1.0"
MAX_DRAFT_BYTES = 10 * 1024 * 1024
MAX_VALIDATION_ATTEMPTS = 3  # Initial draft plus two agent-authored repairs.
THEMES = ("hw_v1", "hw-report", "hw-proposal", "hw-academic")

if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


class WorkflowError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        loc: str = "workflow",
        suggestion: str | None = None,
        exit_code: int = 3,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.loc = loc
        self.suggestion = suggestion
        self.exit_code = exit_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "level": "Error",
            "loc": self.loc,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare, validate, render, and audit agent-authored Huawei document IR."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check the host Python and document dependencies.")
    doctor.add_argument("--json", action="store_true", help="Print the complete machine-readable report.")
    doctor.set_defaults(handler=_cmd_doctor)

    sanitize_template = subparsers.add_parser(
        "sanitize-template",
        help="Create a revalidated PPTX copy with external hyperlinks removed.",
    )
    sanitize_template.add_argument("file", type=Path)
    sanitize_template.add_argument("--output", type=Path, required=True)
    sanitize_template.add_argument("--overwrite", action="store_true")
    sanitize_template.set_defaults(handler=_cmd_sanitize_template)

    prepare = subparsers.add_parser("prepare", help="Parse inputs and build a compact agent generation packet.")
    prepare.add_argument("--target", choices=["word", "deck"], required=True)
    prepare.add_argument("--brief-file", type=Path, required=True)
    prepare.add_argument("--input", type=Path)
    prepare.add_argument("--theme", choices=THEMES, default="hw_v1")
    prepare.add_argument("--pages", type=int)
    prepare.add_argument("--depth", choices=["概览", "标准", "详细"])
    prepare.add_argument("--template", type=Path)
    prepare.add_argument("--asset", type=Path, action="append", default=[])
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--overwrite", action="store_true")
    prepare.set_defaults(handler=_cmd_prepare)

    validate = subparsers.add_parser("validate", help="Shell, migrate, and validate an agent-authored IR draft.")
    validate.add_argument("--target", choices=["word", "deck"], required=True)
    validate.add_argument("--draft", type=Path, required=True)
    validate.add_argument("--output-dir", type=Path, required=True)
    validate.add_argument("--overwrite", action="store_true")
    validate.set_defaults(handler=_cmd_validate)

    finalize = subparsers.add_parser("finalize", help="Revalidate, render, lint, and write the workflow manifest.")
    finalize.add_argument("--target", choices=["word", "deck"], required=True)
    finalize.add_argument("--ir", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--template", type=Path)
    finalize.add_argument("--asset-manifest", type=Path)
    finalize.add_argument("--overwrite", action="store_true")
    finalize.set_defaults(handler=_cmd_finalize)

    audit = subparsers.add_parser("audit", help="Run the deterministic checks on an existing DOCX or PPTX.")
    audit.add_argument("file", type=Path)
    audit.add_argument("--output-dir", type=Path, required=True)
    audit.add_argument("--theme", choices=THEMES, default="hw_v1")
    audit.add_argument("--classification")
    audit.add_argument("--overwrite", action="store_true")
    audit.set_defaults(handler=_cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except WorkflowError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # Stable public failure boundary; never expose a traceback.
        failure = WorkflowError(
            "SKILL-E999",
            f"工作流执行失败: {exc}",
            suggestion="检查输入、输出目录和 doctor 结果；仍失败时保留错误码并停止交付。",
        )
        print(json.dumps(failure.to_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        return failure.exit_code


def _cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    python_ok = sys.version_info[:2] == (3, 12)
    checks.append(
        {
            "name": "python",
            "required": True,
            "ok": python_ok,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "message": "需要 CPython 3.12。" if not python_ok else "CPython 3.12 可用。",
        }
    )
    dependencies = (
        ("pydantic", "pydantic", "__version__"),
        ("python-docx", "docx", "__version__"),
        ("openpyxl", "openpyxl", "__version__"),
        ("python-pptx", "pptx", "__version__"),
        ("Pillow", "PIL", "__version__"),
    )
    for label, module_name, version_attr in dependencies:
        try:
            module = importlib.import_module(module_name)
            version = str(getattr(module, version_attr, "unknown"))
            ok = not (module_name == "pydantic" and not version.startswith("2."))
            message = f"{label} {version} 可用。" if ok else f"{label} 必须使用 v2。"
        except Exception as exc:
            version = None
            ok = False
            message = f"无法导入 {label}: {exc}"
        checks.append(
            {"name": label, "required": True, "ok": ok, "version": version, "message": message}
        )

    graphviz_python = _optional_import_version("graphviz")
    dot_path = shutil.which("dot")
    graphviz_ok = graphviz_python is not None and dot_path is not None
    checks.append(
        {
            "name": "graphviz",
            "required": False,
            "ok": graphviz_ok,
            "version": graphviz_python,
            "path": dot_path,
            "message": (
                "Graphviz 可用。"
                if graphviz_ok
                else "Graphviz 不完整；architecture_diagram 将使用确定性降级布局，必须进行视觉复核。"
            ),
        }
    )
    engine_ok = (ENGINE_ROOT / "runtime_manifest.json").is_file() and ENGINE_APP_ROOT.is_dir()
    checks.append(
        {
            "name": "engine_snapshot",
            "required": True,
            "ok": engine_ok,
            "version": _engine_version() if engine_ok else None,
            "message": "独立引擎快照可用。" if engine_ok else "Skill 引擎快照不完整。",
        }
    )
    passed = all(item["ok"] for item in checks if item["required"])
    report = {
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "pass": passed,
        "checks": checks,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{SKILL_NAME} doctor: {'PASS' if passed else 'FAIL'}")
        for item in checks:
            label = "OK" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
            print(f"[{label}] {item['name']}: {item['message']}")
    return 0 if passed else 3


def _cmd_sanitize_template(args: argparse.Namespace) -> int:
    _require_engine()
    source = args.file.resolve()
    output = args.output.resolve()
    if not source.is_file() or source.suffix.casefold() != ".pptx":
        raise WorkflowError("SKILL-E002", "待清理模板必须是存在的 PPTX 文件。", loc="file")
    if source == output:
        raise WorkflowError("SKILL-E003", "安全副本不能覆盖原模板。", loc="output")
    if output.suffix.casefold() != ".pptx":
        raise WorkflowError("SKILL-E002", "安全副本必须使用 .pptx 扩展名。", loc="output")
    _prepare_owned_outputs([output], overwrite=args.overwrite)
    from app.template.package import TemplateInputError, sanitize_template_hyperlinks

    try:
        removed = sanitize_template_hyperlinks(source, output)
    except TemplateInputError as exc:
        raise WorkflowError(exc.code, exc.message, loc=exc.loc) from exc
    print(
        json.dumps(
            {
                "source": {"filename": source.name, "sha256": _sha256(source)},
                "output": {"path": str(output), "sha256": _sha256(output)},
                "removed_external_hyperlinks": removed,
                "original_modified": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cmd_prepare(args: argparse.Namespace) -> int:
    _require_engine()
    _validate_prepare_options(args)
    brief_path = args.brief_file.resolve()
    if not brief_path.is_file():
        raise WorkflowError("SKILL-E002", "brief 文件不存在。", loc="brief_file")
    try:
        brief = brief_path.read_text(encoding="utf-8").strip()
    except UnicodeError as exc:
        raise WorkflowError("SKILL-E002", "brief 必须是 UTF-8 文本。", loc="brief_file") from exc
    if not brief:
        raise WorkflowError("SKILL-E002", "brief 不能为空。", loc="brief_file")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    owned_files = [
        output_dir / "generation_packet.json",
        output_dir / "document_ir.json",
        output_dir / "visual_plan.json",
        output_dir / "template_preflight.json",
        output_dir / "template_profile.json",
    ]
    _prepare_owned_outputs(owned_files, overwrite=args.overwrite)
    assets_dir = output_dir / "assets"
    if args.asset:
        _prepare_owned_directory(assets_dir, output_dir, overwrite=args.overwrite)

    document = None
    source_record = None
    if args.input is not None:
        source = args.input.resolve()
        document = _parse_source(source)
        document_path = output_dir / "document_ir.json"
        document_path.write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")
        source_record = {
            "filename": source.name,
            "sha256": _sha256(source),
            "document_ir": document_path.name,
            "summary": _document_summary(document),
        }

    asset_manifest = None
    if args.asset:
        from app.assets.errors import AssetError
        from app.assets.pipeline import normalize_assets

        try:
            asset_manifest = normalize_assets(
                [path.resolve() for path in args.asset],
                assets_dir,
                source_type="upload",
            )
        except AssetError as exc:
            raise WorkflowError(exc.code, exc.message, loc=exc.loc) from exc
    asset_semantics = _asset_semantics_record(asset_manifest)

    template_record = None
    if args.template is not None:
        from app.template.package import TemplateInputError, validate_template_package
        from app.template.profile import extract_template_profile, write_template_profile

        template = args.template.resolve()
        try:
            preflight = validate_template_package(template)
            profile = extract_template_profile(template)
        except TemplateInputError as exc:
            raise WorkflowError(exc.code, exc.message, loc=exc.loc) from exc
        (output_dir / "template_preflight.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        profile_path = write_template_profile(profile, output_dir / "template_profile.json")
        template_record = {
            "filename": template.name,
            "sha256": _sha256(template),
            "preflight": "template_preflight.json",
            "profile": profile_path.name,
        }

    visual_plan_record = None
    if document is not None and args.target == "deck":
        from app.visual.planner import build_visual_plan

        visual_plan = build_visual_plan(document, asset_manifest)
        grounded_asset_ids = {
            item["asset_id"] for item in (asset_semantics or {}).get("grounded_assets", [])
        }
        visual_plan = _text_ground_visual_plan(visual_plan, grounded_asset_ids)
        visual_path = output_dir / "visual_plan.json"
        visual_path.write_text(visual_plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
        visual_plan_record = visual_path.name

    packet = {
        "workflow_version": "1.0",
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "engine_version": _engine_version(),
        "target": args.target,
        "brief": brief,
        "source": source_record,
        "options": {
            "theme": args.theme,
            "pages": args.pages,
            "depth": args.depth,
        },
        "template": template_record,
        "asset_manifest": "assets/asset_manifest.json" if asset_manifest is not None else None,
        "asset_semantics": asset_semantics,
        "visual_plan": visual_plan_record,
        "contract": _contract_record(args.target),
        "agent_instructions": [
            "阅读 target 对应 reference、generation_packet 和可选 DocumentIR/VisualPlan。",
            "由当前 Agent 自己生成一个完整裸 JSON；不得调用外部模型或生成器适配器。",
            "本工作流不执行图片像素语义理解；未获 brief 或源材料明确映射的图片不得自动配图。",
            "把草稿保存为 UTF-8 JSON，再运行 validate；初稿失败后最多修正两轮。",
            "只有 validated_ir.json 可以交给 finalize，finalize 仍会重新校验。",
            "不得把 lint 全绿解释为人工视觉或语义终审完成。",
        ],
        "recommended_draft": "draft_ir.json",
        "manual_review_required": True,
    }
    packet_path = output_dir / "generation_packet.json"
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(packet_path)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    _require_engine()
    draft = args.draft.resolve()
    raw = _read_draft(draft)
    output_dir = args.output_dir.resolve()
    validation_dir = output_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    existing_attempts = sorted(validation_dir.glob("attempt-*.json"))
    attempt = len(existing_attempts) + 1
    if attempt > MAX_VALIDATION_ATTEMPTS:
        raise WorkflowError(
            "SKILL-E020",
            "IR 已达到初稿加两轮修正的上限，必须停止自动修复。",
            loc="validation.attempts",
            suggestion="向用户汇报最后的错误码与定位，不要继续猜测或放宽 Schema。",
            exit_code=2,
        )
    result = _validate_text(args.target, raw)
    report = _validation_report(result, attempt=attempt, draft=draft)
    attempt_path = validation_dir / f"attempt-{attempt:02d}.json"
    latest_path = output_dir / "validation_report.json"
    attempt_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not result.ok or result.value is None:
        print(latest_path, file=sys.stderr)
        return 2

    validated_path = output_dir / "validated_ir.json"
    if validated_path.exists() and not args.overwrite:
        raise WorkflowError(
            "SKILL-E003",
            "validated_ir.json 已存在，拒绝覆盖。",
            loc="output_dir",
            suggestion="使用新的输出目录；确需覆盖时显式传入 --overwrite。",
        )
    _write_validated_ir(args.target, result.value, validated_path)
    print(validated_path)
    return 0


def _cmd_finalize(args: argparse.Namespace) -> int:
    _require_engine()
    _validate_finalize_options(args)
    ir_path = args.ir.resolve()
    raw = _read_draft(ir_path)
    result = _validate_text(args.target, raw)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / ("document.docx" if args.target == "word" else "deck.pptx")
    temporary = output_dir / (".document.tmp.docx" if args.target == "word" else ".deck.tmp.pptx")
    final_report_path = output_dir / "final_validation_report.json"
    conflicts = [
        artifact,
        output_dir / "report.json",
        output_dir / "report.md",
        output_dir / "workflow_manifest.json",
        final_report_path,
    ]
    if args.target == "deck":
        conflicts.append(output_dir / "visual_selection_audit.json")
    if args.asset_manifest is not None:
        conflicts.append(output_dir / "asset_usage_audit.json")
    if args.template is not None:
        conflicts.extend(
            output_dir / name
            for name in (
                "pptx_package_report.json",
                "template_plan.json",
                "template_replacement_audit.json",
                "template_structure.json",
                "template_structure.md",
            )
        )
    _prepare_owned_outputs(conflicts, overwrite=args.overwrite)
    final_report_path.write_text(
        json.dumps(_validation_report(result, attempt=None, draft=ir_path), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not result.ok or result.value is None:
        print(final_report_path, file=sys.stderr)
        return 2

    temporary.unlink(missing_ok=True)

    template_result = None
    asset_registry = None
    report = None
    runtime_warnings: list[dict[str, str]] = []
    try:
        if args.target == "word":
            from app.lint.docx_lint import check_docx, write_docx_reports
            from app.rendering.docx_renderer import render_word_ir

            render_word_ir(result.value, temporary)
            report = check_docx(temporary, classification=result.value.meta.classification)
            write_docx_reports(report, output_dir)
        else:
            from app.assets.pipeline import load_asset_manifest
            from app.lint.pptx_lint import check_pptx, write_reports
            from app.rendering.pptx_renderer import render_deck_ir
            from app.template.renderer import render_deck_ir_with_template

            if args.asset_manifest is not None:
                asset_registry = load_asset_manifest(args.asset_manifest.resolve())
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", RuntimeWarning)
                if args.template is not None:
                    template_result = render_deck_ir_with_template(
                        result.value,
                        args.template.resolve(),
                        temporary,
                        audit_dir=output_dir,
                        asset_registry=asset_registry,
                    )
                else:
                    render_deck_ir(result.value, temporary, asset_registry=asset_registry)
            runtime_warnings = [
                {"category": item.category.__name__, "message": str(item.message)}
                for item in caught
                if issubclass(item.category, RuntimeWarning)
            ]
            for item in runtime_warnings:
                print(f"[WARN] {item['category']}: {item['message']}", file=sys.stderr)
            report = check_pptx(
                temporary,
                classification=result.value.meta.classification,
                theme_name=result.value.meta.theme,
                template_profile=template_result.profile if template_result is not None else None,
            )
            write_reports(report, output_dir)
            _write_visual_selection_audit(output_dir, result.value)

        status = "complete" if report.summary["pass"] else "blocked"
        if report.summary["pass"]:
            os.replace(temporary, artifact)
        else:
            temporary.unlink(missing_ok=True)
        manifest_path = _write_workflow_manifest(
            output_dir=output_dir,
            target=args.target,
            ir_path=ir_path,
            ir_value=result.value,
            artifact=artifact if report.summary["pass"] else None,
            report=report,
            status=status,
            runtime_warnings=runtime_warnings,
        )
        if not report.summary["pass"]:
            print(manifest_path, file=sys.stderr)
            return 4
        print(artifact)
        print(output_dir / "report.json")
        print(manifest_path)
        return 0
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        try:
            from app.assets.errors import AssetError
            from app.template.package import TemplateInputError
        except Exception:
            raise
        if isinstance(exc, AssetError):
            raise WorkflowError(exc.code, exc.message, loc=exc.loc) from exc
        if isinstance(exc, TemplateInputError):
            raise WorkflowError(exc.code, exc.message, loc=exc.loc) from exc
        raise


def _cmd_audit(args: argparse.Namespace) -> int:
    _require_engine()
    source = args.file.resolve()
    if not source.is_file():
        raise WorkflowError("SKILL-E002", "待复检文件不存在。", loc="file")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _prepare_owned_outputs(
        [output_dir / "report.json", output_dir / "report.md"],
        overwrite=args.overwrite,
    )
    suffix = source.suffix.lower()
    if suffix == ".docx":
        from app.lint.docx_lint import check_docx, write_docx_reports

        report = check_docx(source, classification=args.classification, theme_name=args.theme)
        paths = write_docx_reports(report, output_dir)
    elif suffix == ".pptx":
        from app.lint.pptx_lint import check_pptx, write_reports

        report = check_pptx(source, classification=args.classification, theme_name=args.theme)
        paths = write_reports(report, output_dir)
    else:
        raise WorkflowError(
            "SKILL-E002",
            f"不支持复检格式: {suffix or '<none>'}",
            loc="file",
            suggestion="audit 仅支持 .docx 和 .pptx。",
        )
    for path in paths:
        print(path)
    return 0 if report.summary["pass"] else 4


def _validate_prepare_options(args: argparse.Namespace) -> None:
    if args.pages is not None and not 1 <= args.pages <= 30:
        raise WorkflowError("SKILL-E002", "pages 必须在 1-30 之间。", loc="pages")
    if args.target == "word":
        if args.pages is not None or args.depth is not None:
            raise WorkflowError("SKILL-E002", "pages/depth 仅适用于 deck。", loc="target")
        if args.template is not None or args.asset:
            raise WorkflowError("SKILL-E002", "template/asset 仅适用于 deck。", loc="target")
        if args.theme != "hw_v1":
            raise WorkflowError("SKILL-E002", "Word 输出当前只使用 hw_v1 主题。", loc="theme")
    if args.template is not None and args.template.suffix.lower() != ".pptx":
        raise WorkflowError("SKILL-E002", "template 必须是 .pptx。", loc="template")


def _validate_finalize_options(args: argparse.Namespace) -> None:
    if args.target == "word" and (args.template is not None or args.asset_manifest is not None):
        raise WorkflowError("SKILL-E002", "template/asset-manifest 仅适用于 deck。", loc="target")
    if args.template is not None and args.template.suffix.lower() != ".pptx":
        raise WorkflowError("SKILL-E002", "template 必须是 .pptx。", loc="template")


def _parse_source(path: Path):
    if not path.is_file():
        raise WorkflowError("SKILL-E002", "输入文件不存在。", loc="input")
    from app.parsers.docx_parser import parse_docx
    from app.parsers.errors import ParseFailure
    from app.parsers.md_parser import parse_markdown
    from app.parsers.pptx_parser import parse_pptx
    from app.parsers.xlsx_parser import parse_xlsx

    parser_by_suffix: dict[str, Callable[[Path], Any]] = {
        ".md": parse_markdown,
        ".docx": parse_docx,
        ".xlsx": parse_xlsx,
        ".pptx": parse_pptx,
    }
    parser = parser_by_suffix.get(path.suffix.lower())
    if parser is None:
        raise WorkflowError(
            "SKILL-E002",
            f"不支持输入格式: {path.suffix or '<none>'}",
            loc="input",
            suggestion="仅支持 md、docx、xlsx 和 pptx。",
        )
    try:
        return parser(path)
    except ParseFailure as exc:
        raise WorkflowError(
            exc.code,
            exc.message,
            loc=exc.loc,
            suggestion=exc.suggestion,
        ) from exc


def _validate_text(target: str, raw: str):
    from app.ir.shell import validate_deck_ir_text, validate_word_ir_text

    return validate_word_ir_text(raw) if target == "word" else validate_deck_ir_text(raw)


def _read_draft(path: Path) -> str:
    if not path.is_file():
        raise WorkflowError("SKILL-E002", "IR 文件不存在。", loc="draft")
    if path.stat().st_size > MAX_DRAFT_BYTES:
        raise WorkflowError("SKILL-E002", "IR 文件超过 10 MB 安全上限。", loc="draft")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise WorkflowError("SKILL-E002", "IR 必须使用 UTF-8 编码。", loc="draft") from exc


def _validation_report(result: Any, *, attempt: int | None, draft: Path) -> dict[str, Any]:
    items = [*result.errors, *result.warnings, *result.infos]
    return {
        "summary": {
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "infos": len(result.infos),
            "pass": bool(result.ok),
        },
        "attempt": attempt,
        "remaining_repairs": (
            None if attempt is None else max(0, MAX_VALIDATION_ATTEMPTS - attempt)
        ),
        "draft": {"filename": draft.name, "sha256": _sha256(draft)},
        "items": [asdict(item) for item in items],
    }


def _write_validated_ir(target: str, value: Any, path: Path) -> None:
    if target == "word":
        text = value.model_dump_json(indent=2)
    else:
        text = value.model_dump_json(indent=2, by_alias=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def _write_visual_selection_audit(output_dir: Path, deck: Any) -> None:
    plan_path = output_dir / "visual_plan.json"
    if not plan_path.is_file():
        return
    from app.visual.contracts import VisualPlan
    from app.visual.planner import audit_visual_selection

    plan = VisualPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    audit = audit_visual_selection(plan, deck)
    (output_dir / "visual_selection_audit.json").write_text(
        audit.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def _write_workflow_manifest(
    *,
    output_dir: Path,
    target: str,
    ir_path: Path,
    ir_value: Any,
    artifact: Path | None,
    report: Any,
    status: str,
    runtime_warnings: list[dict[str, str]],
) -> Path:
    packet_path = output_dir / "generation_packet.json"
    packet = None
    if packet_path.is_file():
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            packet = None
    audits = sorted(
        path.name
        for path in output_dir.glob("*.json")
        if path.name
        not in {
            "generation_packet.json",
            "workflow_manifest.json",
            "final_validation_report.json",
        }
    )
    manifest = {
        "workflow_version": "1.0",
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "engine_version": _engine_version(),
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "source": packet.get("source") if isinstance(packet, dict) else None,
        "ir": {
            "filename": ir_path.name,
            "sha256": _sha256(ir_path),
            "ir_type": ir_value.ir_type,
            "ir_version": ir_value.ir_version,
        },
        "artifact": (
            {"filename": artifact.name, "bytes": artifact.stat().st_size, "sha256": _sha256(artifact)}
            if artifact is not None and artifact.is_file()
            else None
        ),
        "lint": report.summary,
        "lint_item_codes": [item.code for item in report.items],
        "runtime_warnings": runtime_warnings,
        "audits": audits,
        "manual_review_required": True,
        "manual_review_note": "自动 lint 不能替代内容语义抽查和目标 Office/字体环境中的视觉终审。",
        "visual_review": {
            "engine_pixel_inspection_performed": False,
            "status": "human_required",
            "note": "确定性引擎不理解或评审渲染像素；预览图仅供人工终审。",
        },
    }
    path = output_dir / "workflow_manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _document_summary(document: Any) -> dict[str, Any]:
    content = document.content
    return {
        "source": document.source.model_dump(mode="json"),
        "stats": document.stats.model_dump(mode="json"),
        "warnings": list(document.warnings),
        "counts": {
            "blocks": len(content.blocks),
            "outline": len(content.outline),
            "sheets": len(content.sheets),
            "slides": len(content.slides),
        },
    }


def _contract_record(target: str) -> dict[str, Any]:
    if target == "word":
        return {
            "ir_type": "word",
            "ir_version": "1.3",
            "reference": "references/word.md",
            "schema": "scripts/engine/schemas/word_ir.schema.json",
            "examples": [
                "scripts/engine/examples/word_valid_01_plain.json",
                "scripts/engine/examples/word_valid_03_table.json",
                "scripts/engine/examples/word_valid_05_document_control.json",
            ],
        }
    return {
        "ir_type": "deck",
        "ir_version": "2.2",
        "reference": "references/deck.md",
        "schema": "scripts/engine/schemas/deck_ir.schema.json",
        "examples": [
            "scripts/engine/examples/deck_few_shot_table_v19.json",
            "scripts/engine/examples/deck_few_shot_architecture_v19.json",
            "scripts/engine/examples/deck_few_shot_composite_v19.json",
            "scripts/engine/examples/deck_valid_full.json",
        ],
    }


def _asset_semantics_record(asset_manifest: Any | None) -> dict[str, Any] | None:
    if asset_manifest is None:
        return None
    grounded_assets = []
    ungrounded_assets = []
    for asset in asset_manifest.assets:
        record = {
            "asset_id": asset.asset_id,
            "source_filename": asset.source_filename,
        }
        if asset.label or asset.alt:
            grounded_assets.append(
                {
                    **record,
                    "label": asset.label,
                    "alt": asset.alt,
                }
            )
        else:
            ungrounded_assets.append(record)
    return {
        "mode": "text_grounded_only",
        "engine_image_understanding": False,
        "grounded_assets": grounded_assets,
        "ungrounded_assets": ungrounded_assets,
        "policy": (
            "安全解码、尺寸、哈希或文件名不构成图片语义证据；"
            "仅当 brief 或源材料明确说明图片内容与用途时，Agent 才可引用对应 asset_id。"
        ),
    }


def _text_ground_visual_plan(visual_plan: Any, grounded_asset_ids: set[str]) -> Any:
    opportunities = [
        opportunity
        for opportunity in visual_plan.opportunities
        if not opportunity.asset_ids
        or all(asset_id in grounded_asset_ids for asset_id in opportunity.asset_ids)
    ]
    return visual_plan.model_copy(update={"opportunities": opportunities})


def _prepare_owned_outputs(paths: list[Path], *, overwrite: bool) -> None:
    conflicts = [path for path in paths if path.exists()]
    if conflicts and not overwrite:
        names = ", ".join(path.name for path in conflicts)
        raise WorkflowError(
            "SKILL-E003",
            f"拒绝覆盖已有工作流产物: {names}",
            loc="output_dir",
            suggestion="使用新的输出目录；确需覆盖时显式传入 --overwrite。",
        )
    if overwrite:
        for path in conflicts:
            if path.is_file():
                path.unlink()


def _prepare_owned_directory(path: Path, output_dir: Path, *, overwrite: bool) -> None:
    if not path.exists():
        return
    if not overwrite:
        raise WorkflowError(
            "SKILL-E003",
            f"拒绝覆盖已有工作流目录: {path.name}",
            loc="output_dir",
            suggestion="使用新的输出目录；确需覆盖时显式传入 --overwrite。",
        )
    resolved = path.resolve()
    try:
        resolved.relative_to(output_dir.resolve())
    except ValueError as exc:
        raise WorkflowError("SKILL-E003", "拒绝清理输出目录之外的路径。", loc="output_dir") from exc
    if path.name != "assets":
        raise WorkflowError("SKILL-E003", "只允许重建 Skill 自有的 assets 目录。", loc="output_dir")
    shutil.rmtree(resolved)


def _require_engine() -> None:
    if not ENGINE_APP_ROOT.is_dir() or not (ENGINE_ROOT / "runtime_manifest.json").is_file():
        raise WorkflowError(
            "SKILL-E001",
            "独立引擎快照缺失或不完整。",
            suggestion="重新安装完整的 huawei-doc-workflow Skill 压缩包。",
        )


def _engine_version() -> str:
    version_path = ENGINE_ROOT / "VERSION"
    return version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else "unknown"


def _optional_import_version(module_name: str) -> str | None:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    return str(getattr(module, "__version__", "unknown"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
