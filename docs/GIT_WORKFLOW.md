# Git Workflow

## 分支

- 正式稳定分支由项目负责人指定；当前交付基线是 `codex/windows-native-app`。
- Codex 开发分支统一使用 `codex/<short-purpose>`。
- 功能、修复、重构使用短生命周期分支，不复制整个目录创建 `final2` 或 `new_new`。
- `experiments/` 内的试验可使用独立实验分支，但不得反向成为生产入口。

## 提交

提交格式采用:

```text
<type>: <imperative summary>
```

常用 type: `feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`release`。

每个提交只包含一个主要变换，例如“删除旧 Web”与“拆分 API handler”应分开。不要把批量格式化、依赖升级和行为修改混在同一提交。

## 合并与回滚

1. 分支创建前确认工作区和基线 commit。
2. 每批先跑相关专项测试，再进行下一批。
3. 最后运行全量 pytest、coverage、verify 和平台构建。
4. 使用普通 merge 或团队约定的 squash；禁止改写共享历史和 force push。
5. 回滚以单批提交为单位，禁止用 `reset --hard` 清理不明来源修改。

## 标签与版本

- 正式内部发布使用 `vMAJOR.MINOR.PATCH` annotated tag。
- tag 只能指向已经通过发布门禁并有产物 SHA-256 的 commit。
- 版本号需要同步 API/WPF/便携包清单；不能只修改文件名。
- 当前仓库尚无正式 tag，首次 tag 由项目负责人在签名和真机验收后创建。

## 历史与实验

- 历史代码优先依赖 Git，而不是在工作树保留 `old`、`copy`、日期副本。
- 必须留在仓库的非生产实现放 `experiments/<name>/`，包含 README、独立依赖锁和退出标准。
- 历史审计材料放 `docs/history/`；当前事实只写入 `README.md`、`PROGRESS.md` 和权威专题文档。
- 删除 `backup-*` 分支前必须确认它不承担远程或人工备份职责。

## 发布检查

```powershell
git status --short
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\verify.ps1
```

发布产物必须附文件清单、第三方许可和 SHA-256；不得包含 `.venv`、缓存、用户配置、Credential、Prompt、输入正文或任务目录。
