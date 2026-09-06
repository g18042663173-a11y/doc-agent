from __future__ import annotations

from pathlib import Path
import shutil

from engine.extract.source import extract_source, skip_report
from engine.fit.scoring import score_pages
from engine.fit.evidence import audit_evidence
from engine.native.package import audit_output, readback_audit, visible_texts
from engine.leak.check import check_output
from engine.library.store import get_pattern
from engine.material import parse_material
from engine.render.deck_ir import build_deck_ir
from engine.render.source_shell import fill_source_shell
from engine.seal.service import seal_workdir
from engine.shared.chrome import DEFAULT_CLASSIFICATION
from engine.shared.common import RdwError, SKILL_ROOT, flatten_strings, read_json, sha256, write_json, write_text
from engine.skeleton.contracts import compile_fill_schema, validate_fill_content, validate_skeleton


def run_extract(source: Path, out: Path) -> dict:
    return extract_source(source, out)


def run_seal(workdir: Path, skeleton: Path) -> dict:
    return seal_workdir(workdir, skeleton)


def run_plan(
    workdir: Path,
    *,
    skeleton_path: Path | None,
    pattern: str | None,
    materials: list[Path],
    render_mode: str,
    allow_page_adjust: bool,
) -> dict:
    workdir = workdir.resolve()
    if bool(skeleton_path) == bool(pattern):
        raise RdwError("RD-E020", "skeleton/pattern", "必须且只能指定 --skeleton 或 --pattern 之一。", "仿写用 sealed skeleton；套用用 library pattern id。")
    if pattern:
        if render_mode != "deck-ir":
            raise RdwError("RD-E020", "render_mode", "library pattern 没有 source shell，只支持 deck-ir。", "改用 --render-mode deck-ir。")
        skeleton = get_pattern(pattern)
    else:
        skeleton = validate_skeleton(read_json(skeleton_path.resolve(), code="RD-E010", loc="skeleton"))
    if render_mode == "source-shell":
        shell = workdir / "sealed/shell.pptx"
        if skeleton["source_kind"] != "extracted" or not shell.is_file():
            raise RdwError("RD-E020", "render_mode", "source-shell 需要当前 workdir 内已 seal 的 extracted 骨架。", "先执行 extract 与 seal，或改用 deck-ir。")
        sealed = workdir / "sealed/skeleton.sealed.json"
        if not sealed.is_file() or read_json(sealed, code="RD-E010", loc="sealed_skeleton") != skeleton:
            raise RdwError("RD-E020", "skeleton", "传入骨架与当前 workdir 的 sealed 骨架不一致。", "使用 sealed/skeleton.sealed.json。")
    material = parse_material(materials)
    fit_report = score_pages(skeleton, material, allow_page_adjust=allow_page_adjust)
    accepted = {page["page_id"] for page in skeleton["pages"]}
    if not accepted:
        raise RdwError("RD-E020", "fit_report", "全部页面适配度低于 50，无可用页。", "换用更匹配的骨架，或补充能支撑目标修辞角色的用户素材。")
    fill_pack = workdir / "fill_pack"
    if fill_pack.exists():
        raise RdwError("RD-E020", "fill_pack", "fill_pack 已存在，拒绝覆盖。", "使用新的工作目录或保留旧包后显式清理。")
    fill_pack.mkdir(parents=True)
    shutil.copy2(SKILL_ROOT / "prompts/fill.md", fill_pack / "INSTRUCTIONS.md")
    write_json(fill_pack / "skeleton.json", skeleton)
    write_json(fill_pack / "material.json", material)
    write_json(fill_pack / "fit_report.json", fit_report)
    compiled_schema = compile_fill_schema(skeleton, accepted)
    schema_dir = fill_pack / "schema"
    schema_dir.mkdir()
    write_json(schema_dir / "fill_content.schema.json", compiled_schema)
    write_text(fill_pack / "TASK.md", "阅读 INSTRUCTIONS.md、skeleton.json、material.json、fit_report.json 与 schema，写出 content.json。\n")
    write_json(
        workdir / "workflow_state.json",
        {
            "format": "rdw_workflow_state", "version": "1.0", "render_mode": render_mode,
            "allow_page_adjust": allow_page_adjust, "accepted_page_ids": sorted(accepted),
            "source_kind": skeleton["source_kind"], "pattern": skeleton["deck_pattern"],
        },
    )
    return {"fill_pack": str(fill_pack), "accepted_pages": [p["page_id"] for p in skeleton["pages"]], "rejected_pages": [], "warnings": material.get("warnings", [])}


def run_finalize(workdir: Path, content_path: Path, outdir: Path, *, preview: bool = False) -> dict:
    workdir = workdir.resolve()
    state = read_json(workdir / "workflow_state.json", code="RD-E030", loc="workflow_state")
    fill_pack = workdir / "fill_pack"
    skeleton = validate_skeleton(read_json(fill_pack / "skeleton.json", code="RD-E010", loc="skeleton"))
    material = read_json(fill_pack / "material.json", code="RD-E030", loc="material")
    fit_report = read_json(fill_pack / "fit_report.json", code="RD-E030", loc="fit_report")
    schema = read_json(fill_pack / "schema/fill_content.schema.json", code="RD-E030", loc="fill_schema")
    accepted = set(state["accepted_page_ids"])
    content = validate_fill_content(read_json(content_path.resolve(), code="RD-E030", loc="content"), schema, skeleton, accepted)
    evidence_report = audit_evidence(content, material)
    if not evidence_report["pass"] and not preview:
        first = evidence_report["issues"][0]
        raise RdwError("RD-E030", first["loc"], first["message"], "补齐所有槽位及有效 evidence_refs；只看草稿可用 --preview。")
    labels = {label for page in skeleton["pages"] for label in page["structural_labels"].get("_display", [])}
    classification = str(material.get("classification") or DEFAULT_CLASSIFICATION)
    labels.update({classification, DEFAULT_CLASSIFICATION})
    fingerprints_path = workdir / "sealed/source_ngrams.json"
    fingerprints = read_json(fingerprints_path, code="RD-E040", loc="source_ngrams") if fingerprints_path.is_file() else {"cjk_ngrams": [], "numbers": [], "terms": []}
    located = [(f"{page['page_id']}.{item['slot_id']}." + ".".join(map(str, path)), text)
               for page in content["pages"] for item in page["slots"]
               for path, text in flatten_strings(item.get("value", ""))]
    leak_report = check_output(located, material["raw_text"], fingerprints, labels)
    outdir = outdir.resolve()
    if outdir.exists() and any(outdir.iterdir()):
        raise RdwError("RD-E050", "out", "输出目录必须为空。", "使用新的空目录，避免覆盖既有产物。")
    outdir.mkdir(parents=True, exist_ok=True)
    write_json(outdir / "leak_report.json", leak_report)
    write_json(outdir / "evidence_report.json", evidence_report)
    if not leak_report["pass"]:
        loc = leak_report["hits"][0]["loc"] if leak_report.get("hits") else "content"
        raise RdwError(
            "RD-E040",
            loc,
            "出口泄漏检查未通过，演示产物已扣住。",
            "按 leak_report.json 的 hits.loc 删除不在用户素材中的源件重合内容后重试。",
        )
    skip_path = workdir / "sealed/skip_report.json"
    skipped_pages = read_json(skip_path, code="RD-E030", loc="skip_report")["pages"] if skip_path.is_file() else []
    if skipped_pages:
        raise RdwError("RD-E030", "skip_report", "旧工作目录含省略页，不能用于完整仿版。", "使用新目录重新 extract/seal，保留全部页。")
    artifact_result: dict
    if state["render_mode"] == "source-shell":
        artifact_result = fill_source_shell(
            workdir / "sealed/shell.pptx",
            skeleton,
            content,
            outdir / ("draft.pptx" if preview else "deck.pptx"),
            classification=classification,
            skip_pages=skipped_pages,
        )
    elif state["render_mode"] == "deck-ir":
        deck_ir = build_deck_ir(skeleton, content, material)
        artifact = outdir / "deck_ir.json"
        write_json(artifact, deck_ir, overwrite=False)
        artifact_result = {"artifact": str(artifact), "sha256": sha256(artifact), "warnings": []}
    else:
        raise RdwError("RD-E050", "render_mode", "workflow_state 含未知输出模式。", "重新执行 plan。")
    if state["render_mode"] == "source-shell":
        artifact = Path(artifact_result["artifact"])
        reference = workdir / "source_reference.pptx"
        if not reference.is_file():
            reference = workdir / "source.pptx"
        native_report = audit_output(reference, artifact)
        readback_report = readback_audit(artifact, skeleton, content)
        output_leaks = check_output(visible_texts(artifact), material["raw_text"], fingerprints, labels)
        write_json(outdir / "native_audit.json", native_report)
        write_json(outdir / "readback_audit.json", readback_report)
        write_json(outdir / "output_leak_report.json", output_leaks)
        if not preview and (not native_report["pass"] or not readback_report["pass"] or not output_leaks["pass"]):
            artifact.rename(outdir / "draft.pptx")
            raise RdwError("RD-E050", "output_readback", "最终原生对象、填充回读或残留检查未通过。", "查看逐槽审计并修复，仅保留内部草稿。")
    missing = [
        {"page_id": page["page_id"], "slot_id": item["slot_id"], "reason": item["reason"]}
        for page in content["pages"] for item in page["slots"] if item.get("status") == "missing"
    ]
    rejected = []
    report_lines = ["# 修辞适配报告", "", f"- 输出模式：`{state['render_mode']}`", f"- 可填页：{len(accepted)}", f"- 跳过页：{len(rejected)}", f"- 缺失必填槽位：{len(missing)}", "", "## 逐页结果", ""]
    report_lines.extend(f"- `{page['page_id']}` / `{page['page_pattern']}`：{page['score']}，`{page['verdict']}` — {page['reason']}" for page in fit_report["pages"])
    if missing:
        report_lines.extend(["", "## 明确缺失", ""] + [f"- `{item['page_id']}.{item['slot_id']}`：{item['reason']}" for item in missing])
    report_lines.extend(["", "## 人工终审", "", "Schema 与泄漏检查通过不等于视觉和语义终审。请在目标 PowerPoint/渲染器中逐页检查字体、溢出、图形残留、论证准确性与密级。", ""])
    write_text(outdir / "fit_report.md", "\n".join(report_lines))
    warnings = list(artifact_result.get("warnings", []))
    if any(warning.get("code") in {"RD-W003", "RD-W004"} for warning in warnings) and not preview:
        artifact = Path(artifact_result["artifact"])
        artifact.rename(outdir / "draft.pptx")
        write_json(outdir / "blocked_report.json", {"status": "blocked", "warnings": warnings})
        raise RdwError("RD-E050", "text_fit", "原生文字存在溢出或未替换对象；仅保留内部草稿。", "缩短文字并在新输出目录重试。")
    if rejected:
        warnings.append({"code": "RD-W001", "pages": [page["page_id"] for page in rejected], "message": "pages skipped due to low fit"})
    if leak_report["warnings"]["terms"]:
        warnings.append({"code": "RD-W002", "terms": leak_report["warnings"]["terms"], "message": "possible source acronym/proper-name overlap; confirm manually"})
    if skip_path.is_file() or skipped_pages:
        write_json(outdir / "skip_report.json", skip_report(pages=skipped_pages))
    recoveries_path = workdir / "sealed/recoveries.json"
    recovered_pages = []
    if recoveries_path.is_file():
        recovered_pages = read_json(recoveries_path, code="RD-E030", loc="recoveries").get("pages", [])
        write_json(outdir / "recoveries.json", {"format": "rdw_recoveries", "version": "1.0", "pages": recovered_pages})
    manifest_path = outdir / "manifest.json"
    records = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path != manifest_path:
            records.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(
        manifest_path,
        {
            "format": "rdw_output_manifest", "version": "2.0", "render_mode": state["render_mode"],
            "status": "draft" if preview else "needs_visual_review", "page_ids": [p["page_id"] for p in skeleton["pages"]],
            "evidence_pass": evidence_report["pass"], "content_sha256": sha256(content_path),
            "artifact": Path(artifact_result["artifact"]).name, "warnings": warnings,
            "missing_required_slots": missing, "skipped_pages": skipped_pages,
            "recovered_pages": recovered_pages, "files": records,
        },
    )
    return {"artifact": artifact_result["artifact"], "outdir": str(outdir), "warnings": warnings, "manual_visual_review_required": True}


def run_accept(outdir: Path, review_path: Path) -> dict:
    """Bind a complete, independently authored visual review to immutable outputs."""
    outdir = outdir.resolve()
    manifest = read_json(outdir / "manifest.json", code="RD-E050", loc="manifest")
    review = read_json(review_path, code="RD-E050", loc="visual_review")
    artifact = outdir / manifest["artifact"]
    if manifest.get("status") != "needs_visual_review" or not manifest.get("evidence_pass"):
        raise RdwError("RD-E050", "manifest.status", "此结果尚不满足结构与证据验收。", "修复问题后重新 finalize。")
    for record in manifest["files"]:
        path = outdir / record["path"]
        if not path.is_file() or sha256(path) != record["sha256"]:
            raise RdwError("RD-E050", "manifest.files", "产物或报告在 finalize 后发生变化。", "重新 finalize，禁止裸覆写产物。")
    pages = review.get("pages", [])
    if review.get("artifact_sha256") != sha256(artifact) or [p.get("page_id") for p in pages] != manifest["page_ids"]:
        raise RdwError("RD-E050", "visual_review", "视觉复核与当前产物或完整页清单不匹配。", "逐页检查最终产物后提交复核记录。")
    if review.get("pass") is not True or not review.get("reviewer") or any(p.get("pass") is not True for p in pages):
        raise RdwError("RD-E050", "visual_review.pages", "仍有未通过或未完成的逐页复核。", "修复并重新导出全部页。")
    semantic = review.get("semantic_review", {})
    if (semantic.get("pass") is not True or not semantic.get("reviewer")
            or not manifest.get("content_sha256")
            or semantic.get("content_sha256") != manifest["content_sha256"]):
        raise RdwError("RD-E050", "visual_review.semantic_review", "缺少与当前填充内容一致的独立材料复核。", "提交 semantic_review 的 pass、reviewer、content_sha256，明确核对论证和图表口径。")
    for page in pages:
        png = Path(page.get("png", ""))
        if not png.is_file() or not page.get("png_sha256") or sha256(png) != page["png_sha256"]:
            raise RdwError("RD-E050", "visual_review.png", "逐页渲染图片缺失或哈希不符。", "用目标 Office 导出并核对全部图片。")
    write_json(outdir / "acceptance_report.json", review)
    manifest["status"] = "accepted"
    report_path = outdir / "acceptance_report.json"
    manifest["files"].append({"path": report_path.name, "bytes": report_path.stat().st_size, "sha256": sha256(report_path)})
    write_json(outdir / "manifest.json", manifest)
    return {"artifact": str(artifact), "status": "accepted", "pages": len(pages)}
