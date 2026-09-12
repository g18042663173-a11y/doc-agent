"""Assemble an offline, all-page comparison from actual Office exports."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source_dir: Path, result_dir: Path, content_path: Path, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValueError("Comparison output must be empty")
    source = json.loads((source_dir / "office_export.json").read_text(encoding="utf-8"))
    result = json.loads((result_dir / "office_export.json").read_text(encoding="utf-8"))
    content = json.loads(content_path.read_text(encoding="utf-8"))
    ids = [page["page_id"] for page in content["pages"]]
    if ids != [page["page_id"] for page in source["pages"]] or ids != [page["page_id"] for page in result["pages"]]:
        raise ValueError("Source, content and final render pages must match in order")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for side, export, folder in (("source", source, source_dir), ("result", result, result_dir)):
        (output / side).mkdir()
        for page in export["pages"]:
            png = folder / f"{page['page_id']}.png"
            if digest(png) != page["png_sha256"]:
                raise ValueError(f"Render changed: {png}")
            shutil.copy2(png, output / side / png.name)
    for page in content["pages"]:
        texts = [slot["value"] for slot in page["slots"] if isinstance(slot.get("value"), str)]
        title = texts[2] if len(texts) > 2 else page["page_id"]
        rows.append({"page_id": page["page_id"], "title": title, "slots": len(page["slots"]),
                     "evidence_refs": sorted({ref for slot in page["slots"] for ref in slot.get("evidence_refs", [])})})
    options = "".join(f'<option value="{i}">{row["page_id"]} · {html.escape(row["title"])}</option>' for i, row in enumerate(rows))
    all_pages = "".join(
        f'<article><h3>{row["page_id"]} · {html.escape(row["title"])}</h3><div class="pair">'
        f'<a href="source/{row["page_id"]}.png"><img loading="lazy" src="source/{row["page_id"]}.png" alt="{row["page_id"]} 原模板"></a>'
        f'<a href="result/{row["page_id"]}.png"><img loading="lazy" src="result/{row["page_id"]}.png" alt="{row["page_id"]} 仿版结果"></a></div></article>' for row in rows)
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>18 页原模板与仿版对照</title><style>
:root{font-family:"Microsoft YaHei",system-ui,sans-serif;color:#202020;background:#f4f4f4}*{box-sizing:border-box}body{margin:0}header{background:#202020;color:white;padding:24px 3vw}h1{font-size:26px;margin:0 0 10px}header p{color:#ddd;margin:0;font-size:14px;line-height:1.8}main{padding:20px 3vw}nav{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:16px}button,select{font:inherit;padding:9px 14px;border:1px solid #ccc;border-radius:5px;background:white}button{cursor:pointer}button:hover{border-color:#c7000a;color:#c7000a}select{max-width:100%;min-width:280px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair img{width:100%;display:block;background:white;border:1px solid #ddd}.caption{color:#666;font-size:13px;margin:8px 0 18px}.side{font-weight:bold;padding:8px 0;color:#555}#facts{font-size:14px;line-height:1.8;overflow-wrap:anywhere}details{margin-top:24px}summary{cursor:pointer;font-size:18px;padding:12px 0}article{margin:24px 0}h3{font-size:16px}.badge{display:inline-block;background:#c7000a;padding:3px 8px;border-radius:4px;margin-right:8px;font-size:13px}a{color:inherit}@media(max-width:900px){.pair{grid-template-columns:1fr}}@media print{nav,details{display:none}.pair{grid-template-columns:1fr 1fr}}
</style><header><h1><span class="badge">全部 __COUNT__ 页</span>原模板与仿版对照</h1><p>来自本机 PowerPoint 的完整逐页导出。左侧原模板，右侧真实材料仿版；点击图片查看 1920 × 1080 原图。<br>图片和截图像素沿用源件，截图内原字属于保留资产；正文、表格和图表的证据见逐页验收报告。</p></header><main>
<nav><button id="prev" aria-label="上一页">← 上一页</button><select id="page" aria-label="选择页面">__OPTIONS__</select><button id="next" aria-label="下一页">下一页 →</button><span id="position"></span></nav>
<div class="pair"><div><div class="side">原模板</div><a id="source-link"><img id="source" alt="原模板页面"></a></div><div><div class="side">仿版结果</div><a id="result-link"><img id="result" alt="仿版结果页面"></a></div></div>
<p class="caption">支持键盘左右方向键。对照图是渲染证据；PPTX 内仍保留原生图形、表格、图表和可编辑文字。</p><p id="facts"></p>
<details><summary>展开全部页面对照</summary>__ALL__</details></main>
<script>const rows=__ROWS__;const select=document.getElementById('page');function show(i){i=(i+rows.length)%rows.length;select.value=i;const r=rows[i];for(const side of ['source','result']){const url=side+'/'+r.page_id+'.png';document.getElementById(side).src=url;document.getElementById(side+'-link').href=url;}document.getElementById('position').textContent=(i+1)+' / '+rows.length;document.getElementById('facts').textContent='本页填充 '+r.slots+' 个槽；PDF 物理页证据：'+r.evidence_refs.join('、');}select.onchange=()=>show(+select.value);document.getElementById('prev').onclick=()=>show(+select.value-1);document.getElementById('next').onclick=()=>show(+select.value+1);document.addEventListener('keydown',e=>{if(e.target.tagName==='SELECT')return;if(e.key==='ArrowLeft')show(+select.value-1);if(e.key==='ArrowRight')show(+select.value+1)});show(0);</script></html>'''
    document = document.replace("__COUNT__", str(len(rows))).replace("__OPTIONS__", options).replace("__ALL__", all_pages).replace("__ROWS__", json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c"))
    (output / "index.html").write_text(document, encoding="utf-8")
    record = {"source_artifact_sha256": source["artifact_sha256"], "result_artifact_sha256": result["artifact_sha256"],
              "content_sha256": digest(content_path), "pages": rows,
              "files": [{"path": path.relative_to(output).as_posix(), "sha256": digest(path)} for path in sorted(output.rglob("*")) if path.is_file()]}
    (output / "comparison_manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-render", type=Path, required=True)
    parser.add_argument("--result-render", type=Path, required=True)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = build(args.source_render, args.result_render, args.content, args.output)
    print(json.dumps({"pages": len(record["pages"]), "comparison": str(args.output / "index.html")}, ensure_ascii=False))
