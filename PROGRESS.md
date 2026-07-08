# PROGRESS

## 2026-07-08

- 初始化 git 仓库并创建分支 `codex-c0-contract`。
- 放置 `AGENTS.md`、`docs/taskbook.md`、`docs/codex-goal.md`。
- 开始 C0: 三份 IR 契约、Schema 快照、stub generator、占位 verify 链路。
- C0 验证:
  - `python3 -m pytest backend/tests -q`: 6 passed.
  - `python3 scripts/verify.py`: C0 verify passed.
- 根据契约评审意见收紧 WordIR:
  - `blocks` 改为必填且至少 1 条。
  - 增加用户面向校验结果,将 pydantic 校验失败映射为 E/W/D 错误码。
  - 表格行列规整、未知字段 warning、Schema 快照测试已覆盖。
- 主目标 S1-2:
  - 增加模型输出剥壳器,覆盖裸 JSON、json 代码块、混杂解释三种形态。
  - 增加 WordIR / DeckIR 文本校验入口,剥壳失败映射 E001 / D001。
  - 增加可注入 generator 的 IR 修复回路,最多重试 2 次。
  - `python3 -m pytest backend/tests -q`: 20 passed.
  - `python3 scripts/verify.py`: C0 verify passed.
- 主目标 S1-3:
  - 增加 `python-docx` DOCX renderer,输出可编辑 DOCX。
  - 覆盖标题 1-4 级、普通段落、quote / note、两级项目符号与编号列表、分页。
  - 页眉默认写入文档标题,页脚写入密级与 PAGE 页码域。
  - `python3 -m pytest backend/tests -q`: 23 passed.
  - `python3 scripts/verify.py`: 生成 `output/c0_word.docx` 并通过。
- 主目标 S1-4:
  - 表格渲染增加表头加粗、灰底、重复表头标记与比例列宽。
  - 增加 100 行 x 12 列极限表 golden 回读测试。
  - `python3 -m pytest backend/tests -q`: 25 passed.
  - `python3 scripts/verify.py`: 通过。
- 主目标 S1-5:
  - 增加 3 个 WordIR 正样例:纯文本报告、带列表方案、带表格业务说明。
  - 增加 5 个 WordIR 失败样例并回归错误码 E002-E006。
  - 增加校验报告格式化器,输出错误码、定位与中文建议。
  - `python3 -m pytest backend/tests -q`: 27 passed.
  - `python3 scripts/verify.py`: 通过。
