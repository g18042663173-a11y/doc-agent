# Codex Goal —— 一次输入,驱动整个确定性构建

## 前置(一次性)

1. 更新 Codex CLI 到 0.128.0+;在 `config.toml` 里开启:`[features]` 下 `goals = true`。
2. Codex 用 **ChatGPT 账号登录**(Goal 模式不走 API key / 代理)。
3. 仓库放好:`docs/taskbook.md`(规格)、根目录 `AGENTS.md`(运行手册)。
4. `git init` 并**新建一个分支**再跑(它改动快,便于随时 `git diff` / 回退)。
5. 到账号里设好 **token 花费上限**(无人值守长跑很费 token)。

## 启动(把下面整段作为 `/goal` 的目标)

```
/goal 先通读 docs/taskbook.md 与 AGENTS.md,然后实现其中定义的“命令行文档生成工具链”,全程严格遵守 AGENTS.md 的原则、护栏与阻塞处理规则。

要达成(达成即停):
- 三份 IR(WordIR / DocumentIR / DeckIR)以 pydantic 建模,导出 JSON Schema 到文件并加快照测试,作为第一个 commit 冻结;
- 实现四个输入解析器(md / docx / xlsx / pptx)、DOCX 渲染器、DeckIR 2.1 的 17 版式华为风格 PPTX 渲染器(真实图片、原生图表与信息图)、合规检查器(含 HW-W06~W16)、Prompt/VisualPlan 组装器与 stub generator;
- 任务卡 S1-1~S3-6 的验收标准全部满足。

停止条件(全部满足才算 done):python scripts/verify.py 在 stub 通道全绿、pytest 全绿、parsers+ir+lint 三包覆盖率 ≥ 80%。

不要改动:IR 契约字段(除非按 AGENTS.md 流程先改 Schema + 升 ir_version + 更新样例);不要引入 FastAPI / Web;不要用手工 HTML 生成 PPTX。

验证方式:每个里程碑后运行 python scripts/verify.py 与 pytest,修复失败再继续。

遇到需要外部事实 / 人工的事(附录 A.2、真实文件语料、Windows 真机验收、字体视觉终审):记入 QUESTIONS.md 并继续其它未阻塞工作,不要卡住整个 run;这些不算未完成,如实在报告里标注。

进度写入 PROGRESS.md。结束时按 AGENTS.md 的四块格式出报告。
```

## 运行中控制

- `/goal` 看当前状态;`/goal pause` 暂停;`/goal resume` 继续;`/goal clear` 清除。
- 想问问题又不想打断主 run:用 Codex 的 **side chat**(并行会话,同一项目上下文)。

## 可选:想要一道安全闸(推荐但不强制)

IR 契约是最高杠杆——错了下游全错。若你愿意花两分钟看一眼,可**先跑一个只到 C0 的小目标**,确认后再跑上面的大目标:

```
/goal 通读 docs/taskbook.md 与 AGENTS.md,只做契约冻结:三份 IR 的 pydantic 模型 + 导出 JSON Schema 到文件 + 快照测试 + 最小 stub generator,让 python scripts/verify.py 能跑通一条空链路(stub → 校验 → 渲染占位 → 检查)。达成即停,不要开始 S1-1。
```

看完这次的 schema 和空链路没问题,再启动主目标即可。
