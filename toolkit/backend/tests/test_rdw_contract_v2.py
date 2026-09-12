"""Acceptance invariants: preserving pages and grounded slots, not keyword scores."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

SKILL = Path(__file__).resolve().parents[2] / "skills/rhetoric-deck-workflow"
sys.path.insert(0, str(SKILL))
from engine.skeleton.contracts import compile_fill_schema, validate_fill_content, validate_skeleton
from engine.shared.common import RdwError
from engine.fit.scoring import score_pages


def fixture_pair():
    skeleton = validate_skeleton(json.loads((SKILL / "samples/expected/skeleton.json").read_text(encoding="utf-8")))
    content = {"format": "fill_content", "version": "2.0", "pages": [
        {"page_id": page["page_id"], "slots": [
            {"slot_id": slot["slot_id"], "value": ["材料支持的结论"] * slot["cardinality"]["min"], "evidence_refs": ["d01:b0001"]}
            for slot in page["slots"]]}
        for page in skeleton["pages"]]}
    expected = {p["page_id"] for p in skeleton["pages"]}
    validate_fill_content(content, compile_fill_schema(skeleton, expected), skeleton, expected)
    return skeleton, content


def test_missing_whole_page_is_rejected():
    skeleton, content = fixture_pair()
    expected = {p["page_id"] for p in skeleton["pages"]}
    schema = compile_fill_schema(skeleton, expected)
    content["pages"].pop()
    with pytest.raises(RdwError, match="页面|page"):
        validate_fill_content(content, schema, skeleton, expected)


def test_reordered_pages_are_rejected():
    skeleton, content = fixture_pair()
    expected = {p["page_id"] for p in skeleton["pages"]}
    schema = compile_fill_schema(skeleton, expected)
    content["pages"].reverse()
    with pytest.raises(RdwError, match="顺序|页面|page"):
        validate_fill_content(content, schema, skeleton, expected)


def test_blank_text_is_rejected():
    skeleton, content = fixture_pair()
    expected = {p["page_id"] for p in skeleton["pages"]}
    schema = compile_fill_schema(skeleton, expected)
    content["pages"][0]["slots"][0]["value"] = "   "
    with pytest.raises(RdwError):
        validate_fill_content(content, schema, skeleton, expected)


def test_low_fit_does_not_exclude_any_source_page():
    skeleton, _ = fixture_pair()
    report = score_pages(skeleton, {"raw_text": "短材料", "title": "短材料"}, allow_page_adjust=False)
    assert [p["page_id"] for p in report["pages"]] == [p["page_id"] for p in skeleton["pages"]]
    assert all(p["verdict"] != "reject" for p in report["pages"])
    assert report["ready_for_final"] is False


def test_keywords_do_not_prove_evidence_or_readiness():
    skeleton, _ = fixture_pair()
    report = score_pages(skeleton, {"raw_text": "能力价值收益提升指标基线目标方案对比问题测试完成" * 10, "title": "关键词"}, allow_page_adjust=False)
    assert report["ready_for_final"] is False
    assert all(p["evidence_status"] == "unassigned" for p in report["pages"])


def test_missing_slot_is_rejected():
    skeleton, content = fixture_pair()
    expected = {p["page_id"] for p in skeleton["pages"]}
    schema = compile_fill_schema(skeleton, expected)
    content["pages"][0]["slots"].pop()
    with pytest.raises(RdwError):
        validate_fill_content(content, schema, skeleton, expected)


def test_missing_blank_and_unknown_evidence_are_reported():
    from engine.fit.evidence import audit_evidence
    _, content = fixture_pair()
    material = {"evidence": [{"id": "d01:b0001", "text": "真实材料"}, {"id": "blank", "text": " "}]}
    assert audit_evidence(content, material)["pass"]
    for bad_refs in ([], ["does-not-exist"], ["blank"]):
        bad = deepcopy(content)
        bad["pages"][0]["slots"][0]["evidence_refs"] = bad_refs
        assert not audit_evidence(bad, material)["pass"]
    bad = deepcopy(content)
    for page in bad["pages"]:
        for slot in page["slots"]:
            slot.clear()
            slot.update(slot_id="missing", status="missing", reason="材料不足")
    assert not audit_evidence(bad, material)["pass"]


def test_pdf_keeps_physical_pages_and_reports_scanned_page(tmp_path):
    from engine.material import parse_material
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    output = tmp_path / "material.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 40 700 Td (Evidence on physical page two) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(output)
    material = parse_material([output])
    assert [item["page"] for item in material["evidence"]] == [1, 2]
    assert material["evidence"][0]["text"] == ""
    assert material["evidence"][1]["id"] == "d01:p0002"
    assert "Evidence" in material["evidence"][1]["text"]
    assert material["warnings"][0]["page"] == 1
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(tmp_path / "scan.pdf")
    with pytest.raises(RdwError, match="文本"):
        parse_material([tmp_path / "scan.pdf"])


def test_number_leak_check_normalizes_padding_but_preserves_units():
    from engine.leak.check import build_source_fingerprints, check_output
    source = build_source_fingerprints(["01 50% 8192"])
    assert check_output(["01"], "1", source, set())["pass"]
    assert not check_output(["50%"], "50", source, set())["pass"]
    assert not check_output(["8192"], "4096", source, set())["pass"]


def test_accept_requires_full_final_pages_and_unchanged_files(tmp_path):
    from engine.shared.common import sha256, write_json
    from engine.workflow import run_accept
    out = tmp_path / "out"
    out.mkdir()
    artifact = out / "deck.pptx"
    artifact.write_bytes(b"fixture artifact whose hash must remain exact")
    png = tmp_path / "page.png"
    png.write_bytes(b"render fixture")
    manifest = {"status": "needs_visual_review", "artifact": artifact.name,
        "evidence_pass": True, "content_sha256": "authored-content-hash", "page_ids": ["p01", "p02"],
        "files": [{"path": artifact.name, "sha256": sha256(artifact)}]}
    review = {"pass": True, "reviewer": "independent reviewer", "artifact_sha256": sha256(artifact),
        "pages": [{"page_id": pid, "pass": True, "png": str(png), "png_sha256": sha256(png)} for pid in manifest["page_ids"]],
        "semantic_review": {"pass": True, "reviewer": "material auditor", "content_sha256": "authored-content-hash"}}
    write_json(out / "manifest.json", manifest)
    review_path = tmp_path / "review.json"
    incomplete = deepcopy(review)
    incomplete["pages"].pop()
    write_json(review_path, incomplete)
    with pytest.raises(RdwError, match="完整"):
        run_accept(out, review_path)
    write_json(review_path, review)
    artifact.write_bytes(b"changed after finalize")
    with pytest.raises(RdwError, match="变化"):
        run_accept(out, review_path)
    artifact.write_bytes(b"fixture artifact whose hash must remain exact")
    stale = deepcopy(review)
    stale["semantic_review"]["content_sha256"] = "earlier-content-hash"
    write_json(review_path, stale)
    with pytest.raises(RdwError, match="材料复核"):
        run_accept(out, review_path)
    write_json(review_path, review)
    assert run_accept(out, review_path)["status"] == "accepted"
