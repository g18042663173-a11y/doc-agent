from pathlib import Path

from docx import Document

from doc_agent.ir.schemas import WordBlockIR, WordIR
from doc_agent.renderers.docx_python_renderer import PythonDocxRenderer


def test_python_docx_renderer_writes_editable_document(tmp_path: Path) -> None:
    word = WordIR(
        title="企业文档生成 Agent",
        subtitle="MVP 方案",
        blocks=[
            WordBlockIR(type="heading", text="摘要", level=1),
            WordBlockIR(type="paragraph", text="系统通过结构化 IR 生成可编辑企业文档。"),
            WordBlockIR(type="bullet_list", items=["默认 mock", "本地渲染"]),
            WordBlockIR(
                type="table",
                table_headers=["模块", "状态"],
                table_rows=[["Renderer", "ready"]],
            ),
        ],
    )
    output = tmp_path / "demo.docx"

    result = PythonDocxRenderer().render(word.model_dump(), output)

    doc = Document(str(result))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    assert "企业文档生成 Agent" in text
    assert result.stat().st_size > 0
