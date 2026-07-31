# Version Consolidation Audit

审计日期: 2026-08-01
保护标签: `pre-version-consolidation-20260801`
工作分支: `codex/consolidate-latest-20260801`
权威规格: `docs/taskbook.md`

## 1. 判定方法

本审计不以文件时间、分支时间或名称中的版本号作为结论。证据来自当前调用关系、
Git 祖先关系、分支独有提交、测试、构建、发布脚本、文档和任务书不变量。

评分仅作证据摘要：当前主流程 +25、最近明确能力 +20、核心测试 +20、构建 +15、
文档 +5、静态检查 +5、异常处理 +5；无调用 -15、废弃 -25、占位 -25、重复 -20、
实验专用 -10、接口落后 -15。最终结论仍以文字证据为准。

## 2. Git 开发进度候选

`git merge-base --is-ancestor <branch> HEAD` 和
`git rev-list --left-right --count HEAD...<branch>` 的结果如下。右侧独有提交全部为 0，
因此旧分支没有尚未吸收的功能捐赠提交。

`FEATURE_DONOR` 检查结果为无：没有任何旧分支或旧工作树实现同时满足“当前未覆盖的有效
功能”和“可验证”的条件，不需要 cherry-pick 或复制历史代码。

| 候选 | 相对 HEAD | 独有提交 | 证据分 | 状态 | 结论 |
| --- | ---: | ---: | ---: | --- | --- |
| `codex/consolidate-latest-20260801` / `fd0317f` | 0 | 0 | 95 | `CANONICAL_CANDIDATE` | 当前完整工作树，已通过 Python、可靠性和 WPF 门禁 |
| `codex/repository-cleanup-20260731` | 0 | 0 | 80 | `DUPLICATE` | 与保护点相同，仅作为上一阶段分支引用 |
| `codex/windows-native-app` | 落后 1 | 0 | 55 | `OBSOLETE` | WPF/NGA 已全部进入当前分支，缺少仓库治理提交 |
| `codex/release-hardening` | 落后 3 | 0 | 45 | `OBSOLETE` | 发布加固已被 WPF/NGA 和治理提交覆盖 |
| `fix-arch-diagram` | 落后 4 | 0 | 35 | `OBSOLETE` | 架构图功能已在当前 renderer、Schema 和测试中 |
| `codex-c0-contract` | 落后 13 | 0 | 20 | `OBSOLETE` | 早期契约基线，后续迁移器和 Schema 已覆盖 |
| 12 个 `backup-*` 分支 | 落后 5-15 | 0 | 0 | `OBSOLETE` | 全部是 HEAD 祖先，无独有提交；仅保留为待人工清理的 Git 引用 |

当前没有远程配置和远程分支。损坏的 `refs/codex/turn-diffs/checkpoints/...` 会让部分
全局 Git 枚举/维护命令报错；它属于 Codex 宿主引用，不直接编辑 `.git`。

## 3. 工作树候选矩阵

| 功能组 | 候选版本 | 路径/历史 | 是否被调用 | 完整度与测试 | 独有功能 | 已知问题 | 建议处理 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Web API | 异步正式 API | `backend/app/web_api.py` | 是，CLI/WPF/浏览器和测试 | 完整，API/NGA/资产/模板/可靠性覆盖 | 任务队列、恢复、审计、会话保护 | 模块仍较大 | `CANONICAL_CANDIDATE` |
| Web API | 旧同步原型 | 历史 `backend/app/web.py` | 否，已删除 | 缺异步任务和当前安全契约 | 无 | 5055 旧入口、功能回退 | `OBSOLETE` |
| PPT 生产 | Python 原生 renderer | `backend/app/rendering` | 是 | DeckIR 2.0、模板、图片、图表、lint 全覆盖 | 原生可编辑、离线、模板安全 | 高风险大模块 | `CANONICAL_CANDIDATE` |
| PPT 对照 | HTML/PptxGenJS | `experiments/html2pptx` | 生产不调用 | 独立 benchmark | 从零布局的对照证据 | 不处理模板，不满足生产依赖边界 | `EXPERIMENTAL` |
| 用户界面 | WPF 原生客户端 | `desktop/DocumentWorkbench` | 是，主用户入口 | Release/xUnit/FlaUI 通过 | Credential Manager、进程宿主 | Windows 专用 | `CANONICAL_CANDIDATE` |
| 用户界面 | 浏览器工作台 | `backend/app/static` | 是，兼容/诊断入口 | API 与可选浏览器回归覆盖 | 无安装诊断入口 | 不是独立后端 | `KEEP`，共享同一 API |
| Office 安全 | 通用包扫描 | `backend/app/security/office_package.py` | 是 | OLE/宏/ActiveX/关系安全测试 | 通用包错误上下文 | 无 | `CANONICAL_CANDIDATE` |
| Office 安全 | parser 预检 | `backend/app/parsers/office_preflight.py` | 是 | parser 错误契约覆盖 | 将通用异常转为 `ParseFailure` | 名称看似重复但职责不同 | `KEEP`，适配器 |
| Deck 生成脚本 | 完整 E2E | `scripts/demo_e2e.py` | 是 | Word/PPT、修复、审计 | 支持多目标 | 参数较多 | `CANONICAL_CANDIDATE` |
| Deck 生成脚本 | Deck 便捷入口 | `scripts/generate.py` | 是 | 对完整 E2E 的薄包装 | 简化工作台/人工命令 | 不是第二套生成逻辑 | `KEEP`，兼容包装 |
| 产品版本 | 多处硬编码 `2.1.0` | Python/WPF/XAML/packager | 是 | 当前值一致，无单源约束 | 无 | 发布时可能漂移 | `MERGE` 到根 `VERSION` |
| 人工验收文档 | 早期能力清单 | `docs/HUMAN_REVIEW.md` | README 引用 | 内容未随 DeckIR 2.0 更新 | 早期历史证据 | 错称图片/图表/NGA 仍为占位或未实现 | `OBSOLETE`，以当前清单替换 |

## 4. 路径与内容扫描

- 受 Git 管理的工作树路径未命中 `old/new/latest/final/copy/backup/bak/tmp/temp/legacy`
  等含糊源码副本名称。
- `backend/`、`scripts/`、`desktop/` 中大于 100 字节的源码没有完全相同 SHA-256。
- `experiments/html2pptx/` 是任务书允许的隔离实验，不被生产 Python 或 WPF 引用。
- `requirements.txt`、Windows hash lock、质量/UI 开发依赖和 HTML 实验 `package-lock.json`
  分属不同依赖边界，不是互相竞争的正式依赖清单。
- `.venv`、`wheelhouse`、`output`、`dist` 和迁移 manifest 是忽略或交付资产，不参与源码候选判断。

## 5. 正式版本决定

唯一正式开发基础为保护标签所指向的 `fd0317f`，并在
`codex/consolidate-latest-20260801` 上继续收敛。旧分支不存在独有提交，因此没有代码需要
反向合并。生产 PPT 唯一引擎仍为 DeckIR 2.0 到 `python-pptx`；WPF 是主用户入口，浏览器
只作为共享 API 的兼容客户端；HTML 引擎继续作为显式实验。

本轮需要合并的有效内容不是旧分支代码，而是跨栈版本声明：将 Python、WPF 和打包器
统一到根目录 `VERSION`，并用回归测试阻止再次漂移。过期人工验收文档将替换为当前能力
边界，历史内容通过 Git 提交恢复，不在当前树继续保存副本。
