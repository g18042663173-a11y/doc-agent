from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree
from pptx import Presentation

from engine.extract.source import skip_report
from engine.fit.text_fit import replace_text_preserving_style
from engine.leak.check import build_source_fingerprints
from engine.security.office_package import OfficePackageError, preflight_office_package
from engine.shared.chrome import DEFAULT_CLASSIFICATION, rewrite_classification_chrome
from engine.shared.common import RdwError, read_json, sha256, within, write_json
from engine.skeleton.contracts import validate_skeleton
from engine.native.package import inspect_package, sanitize_package as sanitize_native_package

CHROME_PART_PREFIXES = (
    "docprops/",
    "ppt/slidemasters/",
    "ppt/slidelayouts/",
    "ppt/notesmasters/",
    "ppt/handoutmasters/",
    "ppt/theme/",
)
VISIBLE_BODY_PREFIXES = (
    "ppt/slides/slide",
    "ppt/notesslides/",
    "ppt/diagrams/",
    "ppt/charts/",
)


XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)


def seal_workdir(workdir: Path, skeleton_path: Path) -> dict:
    workdir = workdir.resolve()
    source = within(workdir / "source.pptx", workdir)
    pages = within(workdir / "extract_pack/pages", workdir)
    if not source.is_file() or not pages.is_dir():
        raise RdwError("RD-E002", "workdir", "工作目录缺少 extract 产生的源副本或 pages。", "重新执行 extract，或不要对已 seal 的目录重复 seal。")
    skeleton = read_json(skeleton_path.resolve(), code="RD-E010", loc="skeleton")
    fragments = _package_fragments(source)
    source_text = "\n".join(fragments)
    skeleton = validate_skeleton(skeleton, source_text=source_text)
    _assert_included_page_coverage(workdir, skeleton)
    skip_pages = _sealed_skip_pages(workdir, skeleton)
    try:
        preflight = preflight_office_package(source, purpose="source")
    except OfficePackageError as exc:
        raise RdwError("RD-E002", exc.loc, exc.message, "重新提供安全源件。") from exc
    if preflight.active_parts:
        raise RdwError("RD-E002", "source", "含宏、ActiveX 或非图表嵌入对象的源件不能生成安全 shell。", "另存为无活动内容的 PPTX 后重试。")
    label_refs = _approved_label_refs(source, skeleton)
    sealed_dir = workdir / "sealed"
    sealed_dir.mkdir(exist_ok=True)
    shell = sealed_dir / "shell.pptx"
    if shell.exists():
        raise RdwError("RD-E050", "sealed/shell.pptx", "sealed 产物已存在。", "使用新的工作目录，避免覆盖审计链。")
    temporary = sealed_dir / ".shell-building.pptx"
    try:
        shutil.copy2(source, temporary)
        _sanitize_package(temporary, shell)
        temporary.unlink(missing_ok=True)
        _restore_labels(shell, label_refs)
        _rewrite_shell_chrome(shell)
        report = preflight_office_package(shell, purpose="output")
        native = inspect_package(shell)
        # Charts intentionally retain internal source caches until mandatory replacement.
        residual = {item.get("text", "") for page in native["pages"] for item in page["objects"] if item["kind"] != "chart"} - {item[2] for item in label_refs} - {DEFAULT_CLASSIFICATION}
        if any(value.strip() for value in residual):
            raise RdwError("RD-E011", "sealed/shell.pptx", "shell 仍包含非白名单可见文字。", "检查特殊图形或图表文本后再 seal。")
        fingerprints = build_source_fingerprints(fragments)
        write_json(sealed_dir / "source_ngrams.json", fingerprints)
        write_json(sealed_dir / "skeleton.sealed.json", skeleton)
        write_json(sealed_dir / "skip_report.json", skip_report(pages=skip_pages))
        write_json(sealed_dir / "native_inventory.json", inspect_package(source))
        recoveries_path = workdir / "extract_pack/recoveries.json"
        if recoveries_path.is_file():
            write_json(sealed_dir / "recoveries.json", read_json(recoveries_path, code="RD-E010", loc="recoveries"))
        candidates_path = workdir / "extract_pack/slot_candidates.json"
        if candidates_path.is_file():
            write_json(sealed_dir / "slot_candidates.json", read_json(candidates_path, code="RD-E010", loc="slot_candidates"))
        write_json(
            sealed_dir / "seal_manifest.json",
            {
                "format": "rdw_seal_manifest", "version": "1.0",
                "shell_sha256": sha256(shell), "page_count": skeleton["page_count"],
                "structural_label_instances": len(label_refs), "media_removed": False,
                "preflight": report.model_dump(),
            },
        )
    except Exception:
        temporary.unlink(missing_ok=True)
        shell.unlink(missing_ok=True)
        raise
    return {
        "sealed": str(sealed_dir), "shell": str(shell), "skeleton": str(sealed_dir / "skeleton.sealed.json"),
        "deleted": [],
        "internal_only": ["source.pptx", "extract_pack/pages", "sealed/shell.pptx"],
        "warnings": ["source pictures and SmartArt graphics were kept; visible text was sanitized"],
        "skipped_pages": skip_pages,
    }


def _sealed_skip_pages(workdir: Path, skeleton: dict) -> list[dict]:
    extract_state = read_json(workdir / "extract_state.json", code="RD-E002", loc="extract_state")
    expected = [f"p{i:02d}" for i in range(1, int(extract_state["page_count"]) + 1)]
    actual = [page["page_id"] for page in skeleton["pages"]]
    if actual != expected:
        raise RdwError("RD-E010", "skeleton.pages", "模仿必须保留全部源页及原页序。", "补齐全部页面；不得省略或重排。")
    return []

def _package_fragments(path: Path) -> list[str]:
    fragments: list[str] = []
    with ZipFile(path) as package:
        for name in package.namelist():
            if not (name.casefold().endswith(".xml") or name.casefold().endswith(".rels")):
                continue
            try:
                root = etree.fromstring(package.read(name), parser=XML_PARSER)
            except etree.XMLSyntaxError:
                continue
            fragments.extend(element.text for element in root.iter() if element.text and element.text.strip())
    return fragments


def _visible_fragments(path: Path) -> list[str]:
    with ZipFile(path) as package:
        fragments = []
        for name in package.namelist():
            if not _is_visible_body_part(name):
                continue
            root = etree.fromstring(package.read(name), parser=XML_PARSER)
            fragments.extend(element.text for element in root.iter() if etree.QName(element).localname in {"t", "v", "f"} and element.text and element.text.strip())
        return fragments


def _approved_label_refs(path: Path, skeleton: dict) -> list[tuple[int, str, str]]:
    presentation = Presentation(path)
    slot_refs = {page["page_id"]: {slot["shape_ref"] for slot in page["slots"] if slot["shape_ref"]} for page in skeleton["pages"]}
    approved: list[tuple[int, str, str]] = []
    for page in skeleton["pages"]:
        slide_index = int(page["page_id"][1:])
        if slide_index > len(presentation.slides):
            raise RdwError("RD-E010", f"skeleton.{page['page_id']}", "page_id 超出源件页数。", "修正 page_id。")
        labels = set(page["structural_labels"].get("_display", []))
        for ref, text in _slide_text_refs(presentation.slides[slide_index - 1]):
            if text.strip() in labels and ref not in slot_refs[page["page_id"]]:
                approved.append((slide_index, ref, text.strip()))
    return approved


def _slide_text_refs(slide) -> list[tuple[str, str]]:
    result = []
    for shape in _walk_shapes(slide.shapes):
        if getattr(shape, "has_text_frame", False):
            result.append((f"sp_{shape.shape_id}", shape.text))
        if getattr(shape, "has_table", False):
            for r, row in enumerate(shape.table.rows):
                for c, cell in enumerate(row.cells):
                    result.append((f"sp_{shape.shape_id}.cell_{r}_{c}", cell.text))
    return result


def _sanitize_package(source: Path, destination: Path) -> None:
    sanitize_native_package(source, destination)
    return

def _drop_relationship(element) -> bool:
    return element.get("TargetMode") == "External"


def _should_sanitize_text(name: str) -> bool:
    part = name.replace("\\", "/").casefold()
    return (
        part.startswith("ppt/slides/slide")
        or part.startswith("ppt/notesslides/")
        or part.startswith("ppt/diagrams/")
        or part.startswith("ppt/charts/")
        or "/customxml/" in part
        or part.startswith("ppt/embeddings/")
    )


def _rewrite_xml(data: bytes, *, clear_text: bool, drop_external: bool) -> bytes:
    root = etree.fromstring(data, parser=XML_PARSER)
    for element in list(root.iter()):
        local = etree.QName(element).localname
        if clear_text and local in {"t", "v", "f"} and element.text:
            element.text = ""
        if drop_external and local == "Relationship" and _drop_relationship(element):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _is_chrome_part(name: str) -> bool:
    part = name.replace("\\", "/").casefold()
    return any(part.startswith(prefix) for prefix in CHROME_PART_PREFIXES)


def _is_visible_body_part(name: str) -> bool:
    part = name.replace("\\", "/").casefold()
    return part.endswith(".xml") and any(part.startswith(prefix) for prefix in VISIBLE_BODY_PREFIXES)


def _rewrite_shell_chrome(shell: Path) -> None:
    presentation = Presentation(shell)
    rewrite_classification_chrome(presentation, DEFAULT_CLASSIFICATION)
    presentation.save(shell)


def _assert_included_page_coverage(workdir: Path, skeleton: dict) -> None:
    candidates_path = workdir / "extract_pack/slot_candidates.json"
    if not candidates_path.is_file():
        raise RdwError("RD-E010", "extract_pack.slot_candidates", "缺少 slot_candidates.json。", "重新执行 extract。")
    payload = read_json(candidates_path, code="RD-E010", loc="slot_candidates")
    included = {page["page_id"]: page for page in skeleton["pages"]}
    missing: list[tuple[str, str]] = []
    for page in payload.get("pages", []):
        page_id = page["page_id"]
        spec = included.get(page_id)
        if spec is None:
            continue
        bound_refs = {slot.get("shape_ref") for slot in spec["slots"] if slot.get("shape_ref")}
        labels = {item.strip() for item in spec.get("structural_labels", {}).get("_display", [])}
        texts = _page_element_texts(workdir, page_id)
        for candidate in page.get("candidates", []):
            ref = candidate.get("shape_ref")
            if not ref or ref in bound_refs:
                continue
            text = (texts.get(ref) or "").strip()
            if text and text in labels:
                continue
            missing.append((page_id, ref))
    if not missing:
        return
    listed = ", ".join(f"{page_id}.{ref}" for page_id, ref in missing[:20])
    loc = f"skeleton.{missing[0][0]}.{missing[0][1]}"
    raise RdwError(
        "RD-E010",
        loc,
        f"纳入页存在未绑定的可见文字对象: {listed}",
        "为每个候选写入 slots[].shape_ref 或 _display，或把该页从 skeleton.pages 省略。",
    )


def _page_element_texts(workdir: Path, page_id: str) -> dict[str, str]:
    path = workdir / f"extract_pack/pages/{page_id}.json"
    if not path.is_file():
        return {}
    page = read_json(path, code="RD-E010", loc=f"pages.{page_id}")
    return {item["shape_ref"]: item.get("text") or "" for item in page.get("elements", []) if item.get("shape_ref")}


def _sanitize_nested_xlsx(data: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="rdw-nested-") as name:
        root_dir = Path(name)
        source = root_dir / "source.xlsx"
        target = root_dir / "target.xlsx"
        source.write_bytes(data)
        with ZipFile(source) as incoming, ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as outgoing:
            for info in incoming.infolist():
                part = incoming.read(info.filename)
                if info.filename.casefold().endswith(".rels"):
                    part = _rewrite_xml(part, clear_text=False, drop_external=True)
                elif info.filename.casefold().endswith(".xml"):
                    part = _rewrite_xml(part, clear_text=True, drop_external=False)
                outgoing.writestr(info, part)
        return target.read_bytes()


def _restore_labels(shell: Path, refs: list[tuple[int, str, str]]) -> None:
    if not refs:
        return
    presentation = Presentation(shell)
    for slide_index, ref, label in refs:
        target = _resolve_ref(presentation.slides[slide_index - 1], ref)
        if target is None:
            raise RdwError("RD-E011", ref, "无法在 shell 中恢复结构标签位置。", "删除该结构标签或修正 shape_ref。")
        replace_text_preserving_style(target, label, role="body")
    presentation.save(shell)


def _resolve_ref(slide, ref: str):
    shape_part, _, cell_part = ref.partition(".cell_")
    shape_id = int(shape_part.removeprefix("sp_"))
    shape = next((item for item in _walk_shapes(slide.shapes) if item.shape_id == shape_id), None)
    if shape is None:
        return None
    if not cell_part:
        return shape
    row, column = map(int, cell_part.split("_"))
    return shape.table.cell(row, column)


def _walk_shapes(shapes):
    for shape in shapes:
        yield shape
        if getattr(shape, "shape_type", None) == 6:
            yield from _walk_shapes(shape.shapes)
