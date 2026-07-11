# 项目现状盘点

生成时间：2026-07-09
范围：只读检查 + 跑测试取证；除本报告外，不修改源码、配置或 IR 契约。

## 一、主题校准现状

### 1.1 当前颜色 token

证据：`backend/app/rendering/themes/hw_theme.json:3`

| token | 当前值 | 证据 |
|---|---:|---|
| `hw_red` | `#C7000B` | `backend/app/rendering/themes/hw_theme.json:4` |
| `accent1` | `#C7000B` | `backend/app/rendering/themes/hw_theme.json:5` |
| `accent2` 浅红 | `#F85948` | `backend/app/rendering/themes/hw_theme.json:6` |
| `accent3` 橙 | `#ED6D00` | `backend/app/rendering/themes/hw_theme.json:7` |
| `accent4` 黄 | `#FCC800` | `backend/app/rendering/themes/hw_theme.json:8` |
| `accent5` 绿 | `#61B230` | `backend/app/rendering/themes/hw_theme.json:9` |
| `accent6` 青 | `#30B5C5` | `backend/app/rendering/themes/hw_theme.json:10` |
| 主文字 `title/body` | `#1D1D1A` | `backend/app/rendering/themes/hw_theme.json:11`、`backend/app/rendering/themes/hw_theme.json:12` |
| 次要文字 `secondary/muted` | `#666666` | `backend/app/rendering/themes/hw_theme.json:13`、`backend/app/rendering/themes/hw_theme.json:14` |
| 灰底/边框 | `#DDDDDD` | `backend/app/rendering/themes/hw_theme.json:15`、`backend/app/rendering/themes/hw_theme.json:16` |
| 白底 | `#FFFFFF` | `backend/app/rendering/themes/hw_theme.json:17` |

结论：当前主红是 `#C7000B`，不是 `#C00000`。

### 1.2 当前字体、字号、页面尺寸、页脚/密级配置

| 项 | 当前值 | 证据 |
|---|---|---|
| 中文字体 | `微软雅黑` | `backend/app/rendering/themes/hw_theme.json:23` |
| 英文字体 | `Arial` | `backend/app/rendering/themes/hw_theme.json:24` |
| 大数字字体 | `Arial` | `backend/app/rendering/themes/hw_theme.json:25` |
| 字体白名单 | `微软雅黑`、`Arial` | `backend/app/rendering/themes/hw_theme.json:27`-`backend/app/rendering/themes/hw_theme.json:34` |
| 字号层级 | 14 / 12 / 11 / 10 / 9 / 8pt；最小 8pt | `backend/app/rendering/themes/hw_theme.json:37`-`backend/app/rendering/themes/hw_theme.json:50` |
| 行距 | `1.3` | `backend/app/rendering/themes/hw_theme.json:53` |
| 卡片边框线宽 | `0.5pt` | `backend/app/rendering/themes/hw_theme.json:54` |
| 幻灯片尺寸 | `13.34in × 7.5in` | `backend/app/rendering/themes/hw_theme.json:59`-`backend/app/rendering/themes/hw_theme.json:60` |
| 页边距 | 左右 `0.57in`、上 `0.29in`、下 `0.5in` | `backend/app/rendering/themes/hw_theme.json:63`-`backend/app/rendering/themes/hw_theme.json:66` |
| 页脚槽位 | 左密级、中版权、右页码 | `backend/app/rendering/themes/hw_theme.json:79`-`backend/app/rendering/themes/hw_theme.json:81` |
| 密级前缀 | `Security Level: ` | `backend/app/rendering/themes/hw_theme.json:82` |
| 页码格式 | `{current}/{total}` | `backend/app/rendering/themes/hw_theme.json:83` |
| 版权文本 | `Copyright (C) Huawei Technologies Co., Ltd.` | `backend/app/rendering/themes/hw_theme.json:84` |
| 默认密级 | `HUAWEI CONFIDENTIAL` | `backend/app/rendering/themes/hw_theme.json:85` |
| Logo 位置 | 右上角，`left=12.89/top=0.06/width=0.35/height=0.2` | `backend/app/rendering/themes/hw_theme.json:87`-`backend/app/rendering/themes/hw_theme.json:92` |

一句话结论：theme 当前按“源文件实测 SOURCE_FILE_SPEC，主红 `#C7000B`”校准；不是按“规范文档 PPTskill，主红 `#C00000`”校准。

## 二、代码健康度

### 2.1 pytest

命令：

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
```

结果：

```text
........................................................................ [ 59%]
..................................................                       [100%]
122 passed in 18.44s
```

结论：`122 passed`，失败数 0。

### 2.2 verify.py

命令：

```bash
python scripts/verify.py
```

结果：

```text
e2e: four input formats passed word/deck stub chains
coverage: app/parsers=93.80%, app/ir=92.88%, app/lint=89.97%, overall=86.71%
C0 verify passed
schemas: /Users/guoshuaiqi/Documents/开发/backend/schemas
artifacts: c0_word.docx, c0_deck.pptx
report: report.json
```

结论：`verify.py` 通过；覆盖率为 `app/parsers=93.80%`、`app/ir=92.88%`、`app/lint=89.97%`、整体 `86.71%`。

### 2.3 IR schema 与快照

命令：

```bash
git diff -- backend/schemas
```

结果：无输出。

结论：当前 `backend/schemas` 与工作区快照无 diff。

当前 `ir_version`：

| schema | `ir_version` | 证据 |
|---|---:|---|
| `word_ir.schema.json` | `1.0` | `backend/schemas/word_ir.schema.json:359`-`backend/schemas/word_ir.schema.json:360` |
| `document_ir.schema.json` | `1.0` | `backend/schemas/document_ir.schema.json:594`-`backend/schemas/document_ir.schema.json:595` |
| `deck_ir.schema.json` | `1.1` | `backend/schemas/deck_ir.schema.json:599`-`backend/schemas/deck_ir.schema.json:600` |

## 三、版式与能力现状

### 3.1 DeckIR 当前支持的 layout

以代码与 schema 对应模型为准，当前 DeckIR 支持 10 种 layout：

| layout | 证据 |
|---|---|
| `cover` | `backend/app/ir/deck_ir.py:21`-`backend/app/ir/deck_ir.py:27` |
| `agenda` | `backend/app/ir/deck_ir.py:31`-`backend/app/ir/deck_ir.py:34` |
| `section` | `backend/app/ir/deck_ir.py:36`-`backend/app/ir/deck_ir.py:42` |
| `title_bullets` | `backend/app/ir/deck_ir.py:45`-`backend/app/ir/deck_ir.py:49` |
| `two_column` | `backend/app/ir/deck_ir.py:59`-`backend/app/ir/deck_ir.py:65` |
| `table` | `backend/app/ir/deck_ir.py:80`-`backend/app/ir/deck_ir.py:85` |
| `cards` | `backend/app/ir/deck_ir.py:94`-`backend/app/ir/deck_ir.py:99` |
| `chart` | `backend/app/ir/deck_ir.py:113`-`backend/app/ir/deck_ir.py:118` |
| `image` | `backend/app/ir/deck_ir.py:121`-`backend/app/ir/deck_ir.py:128` |
| `conclusion` | `backend/app/ir/deck_ir.py:131`-`backend/app/ir/deck_ir.py:137` |

DeckIR union 证据：`backend/app/ir/deck_ir.py:140`-`backend/app/ir/deck_ir.py:154`。

### 3.2 WordIR 当前支持的 block 类型

当前 WordIR block union 支持：

`heading`、`paragraph`、`bullet_list`、`numbered_list`、`table`、`image_placeholder`、`page_break`。

证据：`backend/app/ir/word_ir.py:31`-`backend/app/ir/word_ir.py:42`；具体 block 定义在 `backend/app/ir/common.py:26`-`backend/app/ir/common.py:84`。

### 3.3 chart、image、架构类版式状态

| 能力 | 当前状态 | 证据 |
|---|---|---|
| `chart` | 有 DeckIR 字段和 renderer 分支，但渲染为占位/降级，不是真实 PPT 图表 | `backend/app/ir/deck_ir.py:102`-`backend/app/ir/deck_ir.py:118`；`backend/app/rendering/pptx_renderer.py:236`-`backend/app/rendering/pptx_renderer.py:262` |
| `image` | 有 DeckIR 字段和 renderer 分支，但渲染为占位框，不插入真实图片 | `backend/app/ir/deck_ir.py:121`-`backend/app/ir/deck_ir.py:128`；`backend/app/rendering/pptx_renderer.py:265`-`backend/app/rendering/pptx_renderer.py:285` |
| 架构/节点连线类版式 | DeckIR 没有独立 layout；当前只能用 `cards`、`two_column`、`image` 等近似表达，不能表达节点、边、方向、分组的真实图结构 | DeckIR layout union 中无 architecture 类：`backend/app/ir/deck_ir.py:140`-`backend/app/ir/deck_ir.py:154` |

### 3.4 lint 规则实现状态

当前有定义并有触发测试覆盖的合规码：

| code | 当前实现 | 代码证据 | 测试证据 |
|---|---|---|---|
| `HW-E01` | 页脚/密级存在性 | `backend/app/lint/pptx_lint.py:71`-`backend/app/lint/pptx_lint.py:74` | `backend/tests/test_pptx_lint.py:149`、`backend/tests/test_pptx_lint.py:164` |
| `HW-E02` | 字体白名单 | `backend/app/lint/pptx_lint.py:119`-`backend/app/lint/pptx_lint.py:139` | `backend/tests/test_pptx_lint.py:150` |
| `HW-E03` | 禁动画/切换 | `backend/app/lint/pptx_lint.py:76`-`backend/app/lint/pptx_lint.py:78` | `backend/tests/test_pptx_lint.py:313` |
| `HW-W01` | 字号过小/字号种类过多 | `backend/app/lint/pptx_lint.py:119`-`backend/app/lint/pptx_lint.py:139`、`backend/app/lint/pptx_lint.py:155`-`backend/app/lint/pptx_lint.py:176` | `backend/tests/test_pptx_lint.py:179`、`backend/tests/test_pptx_lint.py:212`、`backend/tests/test_pptx_lint.py:230` |
| `HW-W02` | 标题红色/强调检查 | `backend/app/lint/pptx_lint.py:119`-`backend/app/lint/pptx_lint.py:139` | `backend/tests/test_pptx_lint.py:194`-`backend/tests/test_pptx_lint.py:195` |
| `HW-W03` | 列表深度 | `backend/app/lint/pptx_lint.py:179`-`backend/app/lint/pptx_lint.py:190` | `backend/tests/test_pptx_lint.py:246`、`backend/tests/test_pptx_lint.py:262` |
| `HW-W04` | 表格规整 | `backend/app/lint/pptx_lint.py:142`-`backend/app/lint/pptx_lint.py:152` | `backend/tests/test_pptx_lint.py:314` |
| `HW-W05` | 页数范围 | `backend/app/lint/pptx_lint.py:60`-`backend/app/lint/pptx_lint.py:68` | `backend/tests/test_pptx_lint.py:315` |
| `HW-W06` | 网格吸附 | `backend/app/lint/pptx_lint.py:193`-`backend/app/lint/pptx_lint.py:220` | `backend/tests/test_pptx_lint.py:51`、`backend/tests/test_pptx_lint.py:66` |
| `HW-W07` | Logo/页眉页脚区域近似布局检查 | `backend/app/lint/pptx_lint.py:223`-`backend/app/lint/pptx_lint.py:250` | `backend/tests/test_pptx_lint.py:278`、`backend/tests/test_pptx_lint.py:294` |
| `HW-W08` | 关键框坐标偏离 | `backend/app/lint/pptx_lint.py:253`-`backend/app/lint/pptx_lint.py:279` | `backend/tests/test_pptx_lint.py:86`、`backend/tests/test_pptx_lint.py:101` |
| `HW-W09` | 对比度检查 | `backend/app/lint/pptx_lint.py:282`-`backend/app/lint/pptx_lint.py:305` | `backend/tests/test_pptx_lint.py:116`、`backend/tests/test_pptx_lint.py:131` |
| `HW-I01` | 结构提示 | `backend/app/lint/pptx_lint.py:384`-`backend/app/lint/pptx_lint.py:413` | `backend/tests/test_pptx_lint.py:340`、`backend/tests/test_pptx_lint.py:364` |

近似或未实现说明：

- `HW-W07` 当前是几何区域/间距近似检测，不是官方 Logo 图像识别。证据：`backend/app/lint/pptx_lint.py:223`-`backend/app/lint/pptx_lint.py:250`。
- `HW-W06` 依赖 theme 网格 token 与容差做几何吸附判断，不能替代人工视觉终审。证据：`backend/app/lint/pptx_lint.py:193`-`backend/app/lint/pptx_lint.py:220`。
- `HW-W09` 基于 shape fill 和 run color 推算对比度，照片/复杂背景/真实模板视觉仍需人工复核。证据：`backend/app/lint/pptx_lint.py:282`-`backend/app/lint/pptx_lint.py:305`。
- 架构图语义 lint、真实 Logo 识别、真实 chart 生成、真实图片插入不在当前实现内。

### 3.5 E/W/I/D 错误码状态

错误码建议表覆盖 `E001-E006`、`W101-W104`、`I201`、`D001-D006`。证据：`backend/app/ir/report.py:7`-`backend/app/ir/report.py:23`。

触发映射主要在 `backend/app/ir/validation.py`：

- `W104`：`backend/app/ir/validation.py:94`
- `I201`：`backend/app/ir/validation.py:198`
- `W102`：`backend/app/ir/validation.py:221`
- `W101`：`backend/app/ir/validation.py:237`
- `W103`：`backend/app/ir/validation.py:263`、`backend/app/ir/validation.py:277`
- `E001-E006`：`backend/app/ir/validation.py:291`-`backend/app/ir/validation.py:301`
- `D002-D006`：`backend/app/ir/validation.py:317`-`backend/app/ir/validation.py:327`
- `D001`：`backend/app/ir/validation.py:361`

测试覆盖证据：`backend/tests/test_ir_validation.py:18`、`backend/tests/test_ir_validation.py:34`、`backend/tests/test_ir_validation.py:57`、`backend/tests/test_ir_validation.py:76`、`backend/tests/test_ir_validation.py:97`、`backend/tests/test_ir_validation.py:117`、`backend/tests/test_ir_validation.py:136`-`backend/tests/test_ir_validation.py:137`、`backend/tests/test_ir_validation.py:159`、`backend/tests/test_ir_validation.py:177`、`backend/tests/test_ir_validation.py:210`、`backend/tests/test_ir_validation.py:219`、`backend/tests/test_ir_validation.py:228`、`backend/tests/test_ir_validation.py:244`、`backend/tests/test_ir_validation.py:266`、`backend/tests/test_ir_shell_and_repair.py:50`、`backend/tests/test_ir_shell_and_repair.py:59`。

## 四、内网底层进展（A 线）

### 4.1 NgaGenerator 状态

当前 `NgaGenerator` 不是已接 `codeagent.exe` 的实现。代码只读取 `NGA_BASE_URL` / `NGA_TOKEN`，缺失时抛 `RuntimeError`，有配置后仍抛 `NotImplementedError`。

证据：

- `backend/app/generators/nga.py:7`-`backend/app/generators/nga.py:18`
- `backend/app/generators/nga.py:15`-`backend/app/generators/nga.py:18`

仓库内未发现 `NGA_INTEGRATION.md`。命令：

```bash
find . -maxdepth 3 \( -iname '*nga*' -o -iname '*integration*' -o -iname '*windows*' -o -iname '*内网*' -o -iname '*验收*' \) -print
```

输出仅包含：

```text
./docs/验收手册.md
./docs/内网接入.md
```

已有内网说明是 `docs/内网接入.md`：当前外网阶段只交付确定性本地链路，黄区替换 generator 和官方渲染 Skill。证据：`docs/内网接入.md:1`-`docs/内网接入.md:4`；替换点见 `docs/内网接入.md:7`-`docs/内网接入.md:20`。

### 4.2 Windows / wheelhouse / subprocess 编码

| 项 | 当前状态 | 证据 |
|---|---|---|
| Windows 离线 wheelhouse | 有构建脚本，无已构建 `wheelhouse/` 目录，无断网 Windows 真机验证证据 | `scripts/make_wheelhouse.py:12`-`scripts/make_wheelhouse.py:39`；`docs/验收手册.md:19`-`docs/验收手册.md:32`；`find . -maxdepth 2 -type d -name 'wheelhouse' -print` 无输出 |
| `WINDOWS_SETUP.md` | 仓库内未发现 | 同上 `find` 命令输出仅有 `docs/验收手册.md`、`docs/内网接入.md` |
| subprocess 编码 | 当前扫描测试要求 `subprocess.run/check_call/check_output/Popen` 显式 `encoding="utf-8"`；本轮 pytest 通过，说明测试覆盖的路径满足该约束 | `backend/tests/test_subprocess_encoding.py:12`-`backend/tests/test_subprocess_encoding.py:24`；pytest 输出 `122 passed` |
| wheelhouse 脚本编码 | `subprocess.run(..., encoding="utf-8", errors="replace")` | `scripts/make_wheelhouse.py:24`-`scripts/make_wheelhouse.py:39` |

结论：subprocess 编码问题在当前代码扫描范围内已有测试兜底；但 Windows GBK 环境未实机复现验证。wheelhouse 只有脚本和说明，没有本机生成物，也没有 Windows 断网安装验收记录。

### 4.3 真实文件解析

命令：

```bash
find samples/input/real -maxdepth 2 -type f -print
```

结果：

```text
find: samples/input/real: No such file or directory
```

结论：`samples/input/real/` 当前不存在，未跑过真实文件语料。

当前存在的是人工构造样例和 synthetic 脏样例，例如 `samples/input/parser_samples/` 与 `samples/input/synthetic/`。证据：`find samples/input -maxdepth 2 -type f | sort` 显示 `parser_samples` 与 `synthetic` 文件，但没有 `real` 文件。

## 五、待办与遗留

### 5.1 HUMAN_REVIEW.md / AUDIT.md / PROGRESS.md 当前未决项

| 类别 | 当前状态 | 证据 |
|---|---|---|
| 自动侧 FALSE-GREEN | 当前文档记录为 0 | `HUMAN_REVIEW.md:16`-`HUMAN_REVIEW.md:18`；`AUDIT.md:163`；`PROGRESS.md:18`-`PROGRESS.md:19` |
| 真实文件语料 | 仍需人工提供真实脱敏 docx/xlsx/pptx，每类不少于 3 个；synthetic 不替代 real | `QUESTIONS.md:5`-`QUESTIONS.md:7`；`AUDIT.md:18`；`AUDIT.md:132`；`PROGRESS.md:159`-`PROGRESS.md:164` |
| Windows 离线真机验收 | 仍需 Windows + Python 3.12 + 离线 wheelhouse 断网安装/运行验证 | `QUESTIONS.md:8`-`QUESTIONS.md:10`；`HUMAN_REVIEW.md:198`-`HUMAN_REVIEW.md:208`；`AUDIT.md:169`-`AUDIT.md:172` |
| PPTX 视觉/内容终审 | 自动 lint 不能证明像不像、能不能交付；需人工在 PowerPoint 中终审 | `QUESTIONS.md:11`-`QUESTIONS.md:13`；`HUMAN_REVIEW.md:211`-`HUMAN_REVIEW.md:223`；`AUDIT.md:167`-`AUDIT.md:168` |
| DOCX 视觉/编辑体验终审 | 需人工用 Word/WPS/目标环境检查分页、表格、样式、可编辑性 | `HUMAN_REVIEW.md:226`-`HUMAN_REVIEW.md:235`；`AUDIT.md:167`-`AUDIT.md:168` |
| 内网 NGA 协议/CI/字体素材 | 需内网协议、真实 endpoint/token 或 `codeagent.exe` 接入信息；需官方 CI 资源继续校准 | `HUMAN_REVIEW.md:255`-`HUMAN_REVIEW.md:277`；`docs/内网接入.md:7`-`docs/内网接入.md:20` |

### 5.2 当前不能自证的边界

这些不应标为“已通过”：

- Windows 离线 wheelhouse 真机验收：没有 Windows 实机证据。
- 真实文件解析鲁棒性：`samples/input/real/` 不存在。
- PPTX/DOCX 视觉观感与交付质量：自动 lint 和测试不能替代人工终审。
- NGA 内网接入：当前没有 `codeagent.exe` 实接实现，也没有 `NGA_INTEGRATION.md`。

## 总结

1. theme 主红当前是 `#C7000B`，accent 六色也按 SOURCE_FILE_SPEC 实测值落入；不是 `#C00000` 口径。
2. 本轮 `pytest` 为 `122 passed`；`scripts/verify.py` 通过，整体覆盖率 `86.71%`。
3. DeckIR 仍是 10 个基础 layout；`chart` 与 `image` 是占位/降级；架构类节点连线版式未实现。
4. `NgaGenerator` 仍是内网替换点/占位，不是 `codeagent.exe` 实接。
5. Windows 离线 wheelhouse、真实文件解析、PPTX/DOCX 视觉终审仍是人工或外部输入待办。
