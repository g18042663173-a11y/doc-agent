from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from flask import Flask, abort, render_template_string, request, send_file, url_for

from app.cli.parse import parse_file
from app.generators.interface import GeneratorTarget, IRTextGenerator, default_ir_generator
from app.ir.deck_ir import DeckIR
from app.ir.errors import ValidationResult
from app.ir.repair import repair_ir_text
from app.ir.shell import validate_deck_ir_text, validate_word_ir_text
from app.ir.word_ir import WordIR
from app.lint.docx_lint import check_docx
from app.lint.pptx_lint import check_pptx
from app.prompting.builder import build_prompt
from app.rendering.docx_renderer import render_word_ir
from app.rendering.pptx_renderer import render_deck_ir


ALLOWED_INPUT_SUFFIXES = {".md", ".docx", ".xlsx", ".pptx"}
TargetKind = Literal["word", "deck"]


def create_app(*, work_dir: Path | None = None, generator: IRTextGenerator | None = None) -> Flask:
    app = Flask(__name__)
    root = (work_dir or Path("output") / "web").resolve()
    root.mkdir(parents=True, exist_ok=True)
    app.config["WEB_WORK_DIR"] = root
    app.config["IR_GENERATOR"] = generator or default_ir_generator()

    @app.get("/")
    def index():
        return _render_page()

    @app.post("/")
    def generate():
        target = _target_from_form()
        job_dir = _new_job_dir(root)
        manual_ir = request.form.get("manual_ir", "").strip()
        try:
            if manual_ir:
                result = _render_manual_ir(manual_ir, target=target, job_dir=job_dir)
            else:
                result = _run_generation(
                    target=target,
                    job_dir=job_dir,
                    generator=app.config["IR_GENERATOR"],
                )
        except ValueError as exc:
            return _render_page(error=str(exc), target=target)
        except Exception as exc:
            return _render_page(error=f"生成失败: {exc}", target=target)

        if result.get("needs_manual_fix"):
            return _render_page(
                error="IR 校验失败",
                target=target,
                raw_ir=result["raw_ir"],
                validation_items=result["validation_items"],
            )
        return _render_page(result=result, target=target)

    @app.get("/download/<job_id>/<filename>")
    def download(job_id: str, filename: str):
        path = (root / job_id / filename).resolve()
        if root not in path.parents or not path.is_file():
            abort(404)
        return send_file(path, as_attachment=True, download_name=filename)

    return app


def _target_from_form() -> TargetKind:
    target = request.form.get("target", "word")
    if target not in {"word", "deck"}:
        raise ValueError("target 只支持 word 或 deck。")
    return target  # type: ignore[return-value]


def _new_job_dir(root: Path) -> Path:
    job_dir = root / uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=False)
    return job_dir


def _run_generation(*, target: TargetKind, job_dir: Path, generator: IRTextGenerator) -> dict[str, Any]:
    input_path = _materialize_input(job_dir)
    document_ir = parse_file(input_path)
    (job_dir / "document_ir.json").write_text(document_ir.model_dump_json(indent=2) + "\n", encoding="utf-8")

    prompt = build_prompt(kind=target, context=document_ir)
    (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    generator_target = _generator_target(target)
    raw_ir = generator.generate(prompt, target=generator_target)
    (job_dir / "generated_ir.json").write_text(raw_ir.strip() + "\n", encoding="utf-8")

    validation = repair_ir_text(raw_ir, target=generator_target, generator=generator)
    if not validation.ok or validation.value is None:
        return {
            "needs_manual_fix": True,
            "raw_ir": raw_ir,
            "validation_items": _validation_items(validation),
        }
    return _render_valid_ir(validation.value, target=target, job_dir=job_dir)


def _render_manual_ir(raw_ir: str, *, target: TargetKind, job_dir: Path) -> dict[str, Any]:
    validation = _validate_ir_text(raw_ir, target)
    if not validation.ok or validation.value is None:
        return {
            "needs_manual_fix": True,
            "raw_ir": raw_ir,
            "validation_items": _validation_items(validation),
        }
    (job_dir / "manual_ir.json").write_text(raw_ir.strip() + "\n", encoding="utf-8")
    return _render_valid_ir(validation.value, target=target, job_dir=job_dir)


def _materialize_input(job_dir: Path) -> Path:
    upload = request.files.get("input_file")
    if upload is not None and upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in ALLOWED_INPUT_SUFFIXES:
            raise ValueError("输入文件只支持 md/docx/xlsx/pptx。")
        path = job_dir / f"input{suffix}"
        upload.save(path)
        return path

    topic = request.form.get("topic_text", "").strip()
    if not topic:
        raise ValueError("请上传输入文件或填写主题文本。")
    path = job_dir / "topic.md"
    path.write_text(f"# 主题\n\n{topic}\n", encoding="utf-8")
    return path


def _render_valid_ir(ir: WordIR | DeckIR, *, target: TargetKind, job_dir: Path) -> dict[str, Any]:
    if target == "word":
        if not isinstance(ir, WordIR):
            raise ValueError("生成结果不是 WordIR。")
        artifact = render_word_ir(ir, job_dir / "word.docx")
        report = check_docx(artifact, classification=ir.meta.classification)
    else:
        if not isinstance(ir, DeckIR):
            raise ValueError("生成结果不是 DeckIR。")
        artifact = render_deck_ir(ir, job_dir / "deck.pptx")
        report = check_pptx(artifact, classification=ir.meta.classification)

    report_payload = report.to_dict()
    return {
        "artifact_name": artifact.name,
        "download_href": url_for("download", job_id=job_dir.name, filename=artifact.name),
        "report": report_payload,
        "report_groups": _report_groups(report_payload),
    }


def _validate_ir_text(raw_ir: str, target: TargetKind) -> ValidationResult:
    if target == "word":
        return validate_word_ir_text(raw_ir)
    return validate_deck_ir_text(raw_ir)


def _generator_target(target: TargetKind) -> GeneratorTarget:
    return "word_ir" if target == "word" else "deck_ir"


def _validation_items(result: ValidationResult) -> list[dict[str, str]]:
    return [
        {
            "level": item.level,
            "code": item.code,
            "loc": item.loc or "<root>",
            "message": item.message,
            "suggestion": item.suggestion or "",
        }
        for item in result.errors + result.warnings + result.infos
    ]


def _report_groups(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    items = report.get("items", [])
    return {level: [item for item in items if item.get("level") == level] for level in ("Error", "Warning", "Info")}


def _render_page(
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    target: TargetKind = "word",
    raw_ir: str = "",
    validation_items: list[dict[str, str]] | None = None,
) -> str:
    return render_template_string(
        PAGE_TEMPLATE,
        result=result,
        error=error,
        target=target,
        raw_ir=raw_ir,
        validation_items=validation_items or [],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the minimal local document-generation web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--work-dir", type=Path, default=Path("output") / "web")
    args = parser.parse_args(argv)
    app = create_app(work_dir=args.work_dir)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


PAGE_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>文档生成</title>
</head>
<body>
  <h1>文档生成</h1>
  <form method="post" enctype="multipart/form-data">
    <section>
      <h2>输入</h2>
      <p><input type="file" name="input_file" accept=".md,.docx,.xlsx,.pptx"></p>
      <p><textarea name="topic_text" rows="5" cols="72" placeholder="或输入主题文本"></textarea></p>
    </section>
    <section>
      <h2>生成</h2>
      <p>
        <label><input type="radio" name="target" value="word" {% if target == "word" %}checked{% endif %}> Word</label>
        <label><input type="radio" name="target" value="deck" {% if target == "deck" %}checked{% endif %}> PPTX</label>
      </p>
      <p><button type="submit">生成</button></p>
    </section>
  </form>

  {% if error %}
    <section>
      <h2>{{ error }}</h2>
      {% if validation_items %}
        <ul>
          {% for item in validation_items %}
            <li>[{{ item.level }}] {{ item.code }} {{ item.loc }}: {{ item.message }}</li>
          {% endfor %}
        </ul>
        <form method="post">
          <input type="hidden" name="target" value="{{ target }}">
          <p><textarea name="manual_ir" rows="16" cols="96">{{ raw_ir }}</textarea></p>
          <p><button type="submit">使用修正后的 IR 渲染</button></p>
        </form>
      {% endif %}
    </section>
  {% endif %}

  {% if result %}
    <section>
      <h2>合规检查报告</h2>
      <p><a href="{{ result.download_href }}">下载产物 {{ result.artifact_name }}</a></p>
      <p>
        Error: {{ result.report.summary.errors }}
        Warning: {{ result.report.summary.warnings }}
        Info: {{ result.report.summary.infos }}
        Pass: {{ result.report.summary.pass }}
      </p>
      {% for level in ["Error", "Warning", "Info"] %}
        <h3>{{ level }}</h3>
        {% if result.report_groups[level] %}
          <ul>
            {% for item in result.report_groups[level] %}
              <li>{{ item.code }}{% if item.slide is defined %} slide {{ item.slide }}{% endif %}: {{ item.message }}</li>
            {% endfor %}
          </ul>
        {% else %}
          <p>无</p>
        {% endif %}
      {% endfor %}
    </section>
  {% endif %}
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
