"""Build, verify and atomically publish the three short-name deliverables."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import package_document_workbench as workbench
from scripts import package_huawei_doc_skill as generation
from scripts import package_rhetoric_deck_skill as imitation
from scripts.portable_skill_runtime import sha256, verify_archive


def verify_release(directory: Path) -> dict:
    manifest = json.loads((directory / "release-manifest.json").read_text(encoding="utf-8"))
    required = {"生成.zip", "模仿.zip", "工作台.zip"}
    if {item["name"] for item in manifest["artifacts"]} != required:
        raise ValueError("Release must contain exactly the three short-name artifacts")
    for item in manifest["artifacts"]:
        archive = directory / item["name"]
        digest = sha256(archive)
        companion = archive.with_suffix(".zip.sha256")
        if digest != item["sha256"] or companion.read_text(encoding="utf-8").split()[0] != digest:
            raise ValueError(f"Release checksum mismatch: {archive.name}")
        package = workbench.verify_archive(archive) if archive.name == "工作台.zip" else verify_archive(archive)
        version = package.get("product_version") or package["skill_version"]
        if version != item["version"]:
            raise ValueError(f"Release version mismatch: {archive.name}")
    return manifest


def verify_release_sources(directory: Path) -> None:
    """Reject a release built while source files were still changing."""
    for short, packager in (("生成.zip", generation), ("模仿.zip", imitation)):
        manifest = verify_archive(directory / short)
        for item in manifest["source_files"]:
            source = packager.SKILL_DIR / item["path"]
            if not source.is_file() or sha256(source) != item["sha256"]:
                raise ValueError(f"Source changed since packaging: {packager.SKILL_NAME}/{item['path']}")
    package = workbench.verify_archive(directory / "工作台.zip")
    if package["source"].get("tree_sha256") != workbench.source_tree_sha256():
        raise ValueError("Workbench source changed since packaging")


def publish_release(output: Path, *, workbench_archive: Path | None = None) -> Path:
    output = output.resolve()
    if output.exists():
        raise ValueError("Release output must not exist; choose a new directory to preserve previous releases")
    output.parent.mkdir(parents=True, exist_ok=True)
    generation.synchronize_engine_snapshot()
    imitation.synchronize_direct_copies()
    with tempfile.TemporaryDirectory(prefix=".release-", dir=output.parent) as temporary:
        build = Path(temporary)
        published = build / "release"
        published.mkdir()
        g, _ = generation.build_archive(build, overwrite=False)
        r, _ = imitation.build_archive(build, imitation.verify_skill_source(), overwrite=False)
        imitation_qa = imitation.verify_isolated_archive(r)
        generation_qa = generation.verify_isolated_archive(g, additional_deck_ir=imitation_qa.pop("deck_ir"))
        if workbench_archive is None:
            workbench.main(["--output-dir", str(build)])
            w = build / f"{workbench.PACKAGE_NAME}.zip"
        else:
            w = workbench_archive.resolve()
            checked = workbench.verify_archive(w)
            if checked["source"].get("tree_sha256") != workbench.source_tree_sha256():
                raise ValueError("Reused workbench archive does not match the current source tree")
        workbench_qa = workbench.verify_isolated_archive(w)
        artifacts = []
        for source, name, version in ((g, "生成.zip", generation.SKILL_VERSION),
                                      (r, "模仿.zip", imitation.SKILL_VERSION),
                                      (w, "工作台.zip", workbench.VERSION)):
            target = published / name
            shutil.copy2(source, target)
            digest = sha256(target)
            target.with_suffix(".zip.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8")
            artifacts.append({"name": name, "version": version, "bytes": target.stat().st_size, "sha256": digest})
        # Both independently packaged DeckIR schemas must be byte-identical.
        import zipfile
        with zipfile.ZipFile(g) as archive:
            schema = archive.read("huawei-doc-workflow/scripts/engine/schemas/deck_ir.schema.json")
        with zipfile.ZipFile(r) as archive:
            if schema != archive.read("rhetoric-deck-workflow/schemas/deck_ir.schema.json"):
                raise ValueError("Cross-skill DeckIR schema mismatch")
        manifest = {"schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "docker_required": False, "artifacts": artifacts,
                    "deck_ir_schema_sha256": hashlib.sha256(schema).hexdigest(),
                    "workbench_imitation_supported": False}
        (published / "generation-portable-acceptance.json").write_text(
            json.dumps(generation_qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (published / "imitation-portable-acceptance.json").write_text(
            json.dumps(imitation_qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (published / "workbench-portable-acceptance.json").write_text(
            json.dumps(workbench_qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (published / "release-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (published / "交付说明.txt").write_text(
            "生成.zip：给 Agent 生成 Word/PPT，自带 Python、依赖和 Graphviz。\n"
            "模仿.zip：给 Agent 按原件图形换字，自带 Python 与依赖。\n"
            "解压任一 Skill 后运行 install.cmd；或将整个 Skill 目录放入自己的 skills 目录。\n"
            "运行 run.cmd doctor --json 可检查；不需要系统 Python，不需要联网安装。\n"
            "工作台.zip：给人使用，解压后双击 DocumentWorkbench.exe，仅支持生成。\n"
            "三个包均无需 Docker。保留整个解压目录；不要仅复制启动器或 EXE。\n"
            "本目录摘要来自当前 ZIP；release-manifest.json 记录各包版本与校验值。\n",
            encoding="utf-8")
        verify_release(published)
        verify_release_sources(published)
        published.rename(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--workbench-archive", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_release(args.verify), ensure_ascii=False, indent=2))
    elif args.output_dir:
        print(publish_release(args.output_dir, workbench_archive=args.workbench_archive))
    else:
        parser.error("Provide --output-dir or --verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
