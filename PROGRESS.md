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
