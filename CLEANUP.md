# 清理记录

日期: 2026-07-09

## 工具执行

| 工具 / 命令 | 结果 | 处理 |
| --- | --- | --- |
| `python3 -m ruff check backend scripts` | 初次命中 2 个未使用 import + 18 个 E402;复跑 `All checks passed!` | 删除未使用 import;脚本 E402 为本地 `backend/` 注入后导入 app 包,加文件级说明保留。 |
| `python3 -m pyflakes backend scripts` | 初次命中 2 个未使用 import;复跑无输出 | 删除。 |
| `python3 -m vulture backend scripts --min-confidence 80` | 初次命中 3 个 pydantic validator 的 `cls`;复跑无输出 | 改名为 `_cls`,保留 validator 签名。 |
| `rg -n "print\\(|pdb|breakpoint\\(|TODO|FIXME|pass\\s*(#|$)|placeholder|待实现|debug" backend scripts docs README.md *.md` | 命中 CLI 正常输出、任务书要求 TODO、占位降级和文档示例 | 未发现可删的调试代码;保留项见下。 |
| 2026-07-09 终轮复跑 `ruff` / `pyflakes` / `vulture` | `ruff`: All checks passed;`pyflakes`、`vulture` 均无输出 | 未新增清理项。 |

## 已清理

| 文件 | 位置 | 动作 | 为什么可删 / 可改 | 验证 |
| --- | --- | --- | --- | --- |
| `backend/app/rendering/docx_renderer.py` | import 区 | 删除未使用 `WD_BREAK` | ruff/pyflakes 均报告未引用;代码实际用 `document.add_page_break()` | `PYTHONPATH=backend python3 -m pytest backend/tests/test_docx_renderer.py backend/tests/test_placeholder_lint.py -q` |
| `backend/app/rendering/placeholder.py` | import 区 | 删除未使用 `json` | 该模块直接写 `model_dump_json`,不调用 `json` | `PYTHONPATH=backend python3 -m pytest backend/tests/test_docx_renderer.py backend/tests/test_placeholder_lint.py -q` |
| `backend/app/ir/common.py` | `TableBlock` validators | `cls` 改为 `_cls` | pydantic validator 必须保留类方法签名,但参数未使用;改名消除 vulture 噪音 | `PYTHONPATH=backend python3 -m pytest backend/tests/test_ir_validation.py backend/tests/test_repro_cli.py -q` |
| `scripts/demo_e2e.py` | 文件顶部 | 增加 `# ruff: noqa: E402` | 脚本需先把 `backend/` 放入 `sys.path`,再导入 `app.*`;这是当前 CLI 脚本运行方式,不是垃圾代码 | `python3 -m ruff check backend scripts` |
| `scripts/export_schemas.py` | 文件顶部 | 增加 `# ruff: noqa: E402` | 同上 | `python3 -m ruff check backend scripts` |
| `scripts/verify.py` | 文件顶部 | 增加 `# ruff: noqa: E402` | 同上 | `python3 -m ruff check backend scripts` |

## 确认保留

| 项目 | 位置 | 保留原因 |
| --- | --- | --- |
| CLI `print(...)` | `backend/app/cli/*.py`, `scripts/demo_e2e.py`, `scripts/verify.py`, `scripts/export_schemas.py`, `scripts/make_dirty_samples.py` | 命令行契约需要打印输出路径、报告和验收结论,不是调试输出。 |
| `QUESTIONS.md` TODO | `QUESTIONS.md:7`, `QUESTIONS.md:10`, `QUESTIONS.md:13` | AGENTS.md 要求把外部输入阻塞记录为 TODO;真实语料、Windows 真机、内网字体/CI 必须人工处理。 |
| NgaGenerator / TODO 说明 | `docs/taskbook.md:46`, `docs/taskbook.md:102`, `docs/taskbook.md:143`, `backend/app/generators/nga.py` | 任务书要求外网只预留接口,真实协议待内网确认;不能当死代码删。 |
| placeholder report / renderer | `backend/app/lint/placeholder.py`, `backend/app/rendering/placeholder.py`, `scripts/demo_e2e.py` | stub/C0 和无 lint 分支需要轻量报告占位;任务书允许 chart/image 占位降级。 |
| image/chart 占位降级 | `backend/app/rendering/docx_renderer.py`, `backend/app/rendering/pptx_renderer.py` | 任务书把 DOCX 图片透传、原生 chart 列为 P2/降级,外网阶段不能伪造真图或真图表。 |

## 存疑项

当前没有需要用户拍板才能删除的代码项。外部输入类待办仍在 `HUMAN_REVIEW.md` 与 `QUESTIONS.md` 中保留。
