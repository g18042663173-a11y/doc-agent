from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile

from engine.library.store import add_pattern, get_pattern, list_patterns, remove_pattern
from engine.shared.cli_errors import CliFailure, emit_cli_failure
from engine.shared.common import RdwError, SKILL_ROOT, emit_error, success, write_json
from engine.workflow import run_extract, run_finalize, run_plan, run_seal, run_accept


EXIT_CODES = {
    "RD-E001": 10, "RD-E002": 20, "RD-E010": 30, "RD-E011": 31,
    "RD-E020": 40, "RD-E030": 50, "RD-E040": 60, "RD-E050": 70, "RD-E999": 99,
}


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit_cli_failure(CliFailure("RD-E001", "arguments", f"命令行参数无效: {message}", "运行 rdw.py --help 查看签名。"))
        raise SystemExit(2)


def build_parser() -> Parser:
    parser = Parser(prog="rdw", description="Rhetorical deck workflow")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    extract = commands.add_parser("extract")
    extract.add_argument("--source", type=Path, required=True)
    extract.add_argument("--out", type=Path, required=True)
    seal = commands.add_parser("seal")
    seal.add_argument("--workdir", type=Path, required=True)
    seal.add_argument("--skeleton", type=Path, required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--workdir", type=Path, required=True)
    choice = plan.add_mutually_exclusive_group(required=True)
    choice.add_argument("--skeleton", type=Path)
    choice.add_argument("--pattern")
    plan.add_argument("--material", type=Path, action="append", required=True)
    plan.add_argument("--render-mode", choices=("source-shell", "deck-ir"), required=True)
    plan.add_argument("--allow-page-adjust", action="store_true")
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--workdir", type=Path, required=True)
    finalize.add_argument("--content", type=Path, required=True)
    finalize.add_argument("--out", type=Path, required=True)
    finalize.add_argument("--preview", action="store_true")
    accept = commands.add_parser("accept")
    accept.add_argument("--out", type=Path, required=True)
    accept.add_argument("--review", type=Path, required=True)
    library = commands.add_parser("library")
    library_commands = library.add_subparsers(dest="library_command", required=True, parser_class=Parser)
    list_command = library_commands.add_parser("list")
    list_command.add_argument("--tag")
    get_command = library_commands.add_parser("get")
    get_command.add_argument("--id", required=True)
    get_command.add_argument("--out", type=Path, required=True)
    add_command = library_commands.add_parser("add")
    add_command.add_argument("--skeleton", type=Path, required=True)
    add_command.add_argument("--id", required=True)
    add_command.add_argument("--name", required=True)
    add_command.add_argument("--tags", default="")
    rm_command = library_commands.add_parser("rm")
    rm_command.add_argument("--id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        args = build_parser().parse_args(argv)
        if args.command == "doctor":
            result = doctor_result()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("PASS" if result["ok"] else "FAIL")
                for check in result["checks"]:
                    print(f"- {check['name']}: {check['status']} {check.get('detail', '')}".rstrip())
            return 0 if result["ok"] else EXIT_CODES["RD-E001"]
        if args.command == "extract":
            payload = run_extract(args.source, args.out)
        elif args.command == "seal":
            payload = run_seal(args.workdir, args.skeleton)
        elif args.command == "plan":
            payload = run_plan(args.workdir, skeleton_path=args.skeleton, pattern=args.pattern, materials=args.material, render_mode=args.render_mode, allow_page_adjust=args.allow_page_adjust)
        elif args.command == "finalize":
            payload = run_finalize(args.workdir, args.content, args.out, preview=args.preview)
        elif args.command == "accept":
            payload = run_accept(args.out, args.review)
        elif args.command == "library":
            payload = _library(args)
        else:
            raise RdwError("RD-E999", "command", "未知命令。", "运行 --help。")
        print(json.dumps(success(args.command, **payload), ensure_ascii=False, indent=2))
        return 0
    except RdwError as exc:
        emit_error(exc)
        return EXIT_CODES.get(exc.code, 99)
    except Exception as exc:
        error = RdwError("RD-E999", "runtime", f"未处理错误: {type(exc).__name__}: {exc}", "保留 stderr 与工作目录，检查输入后重试。")
        emit_error(error)
        return EXIT_CODES["RD-E999"]


def doctor_result() -> dict:
    checks = []
    python_ok = sys.version_info >= (3, 12)
    checks.append({"name": "python", "status": "pass" if python_ok else "error", "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"})
    dependencies = (("python-pptx", "pptx"), ("jsonschema", "jsonschema"), ("lxml", "lxml"), ("pydantic", "pydantic"), ("pypdf", "pypdf"), ("fonttools", "fontTools"))
    for distribution, import_name in dependencies:
        try:
            version = importlib.metadata.version(distribution)
            __import__(import_name)
            checks.append({"name": distribution, "status": "pass", "detail": version})
        except (importlib.metadata.PackageNotFoundError, ImportError) as exc:
            checks.append({"name": distribution, "status": "error", "detail": str(exc)})
    try:
        with tempfile.NamedTemporaryFile(prefix="rdw-doctor-", dir=SKILL_ROOT / "library", delete=True):
            pass
        checks.append({"name": "skill_write", "status": "pass", "detail": "library is writable"})
    except OSError as exc:
        checks.append({"name": "skill_write", "status": "error", "detail": str(exc)})
    manifest = SKILL_ROOT / "engine/runtime_manifest.json"
    checks.append({"name": "frozen_manifest", "status": "pass" if manifest.is_file() else "error", "detail": str(manifest.name)})
    return {
        "ok": all(item["status"] == "pass" for item in checks),
        "command": "doctor", "skill_version": (SKILL_ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "checks": checks, "external_dependencies": [name for name, _ in dependencies],
        "model_api": False, "layout_renderer": False,
    }


def _library(args) -> dict:
    if args.library_command == "list":
        return {"patterns": list_patterns(args.tag)}
    if args.library_command == "get":
        skeleton = get_pattern(args.id)
        write_json(args.out.resolve(), skeleton, overwrite=False)
        return {"id": args.id, "output": str(args.out.resolve())}
    if args.library_command == "add":
        target = add_pattern(args.skeleton.resolve(), args.id, args.name, [tag for tag in args.tags.split(",") if tag])
        return {"id": args.id, "output": str(target)}
    if args.library_command == "rm":
        target = remove_pattern(args.id)
        return {"id": args.id, "removed": str(target)}
    raise RdwError("RD-E999", "library", "未知 library 命令。", "运行 library --help。")
