# Progress

## 2026-09-07 GitHub 私有发布

- 三个交付按现有共享后端结构统一发布至 `g18042663173-a11y/document-toolkit`；生成、模仿、WPF 各有源码入口，`doc-agent-mvp` 仍独立维护。
- 保留现有 Git 历史与全部源码修改；忽略本地真实材料、运行目录、缓存与 ZIP。下载包经清单、SHA-256 和源文件一致性检查，从 GitHub Release 单独提供。
- 仓库检出保持源文件原始字节，避免 Windows 自动换行转换破坏已验收的包内来源哈希。源码与历史凭据模式筛查未发现候选。
- 本次发布沿用9月5日已验证的生成1.1.0、模仿2.0.0、工作台2.2.0便携包；源码包含后续排版检查工具。真实18页材料及修订图留在本地outputs。
- 新克隆回验通过22项回归；三个ZIP与克隆源码完全一致。GitHub附件中文名清理会造成重名，采用英文下载名及中文label，并提供 `tools.zip` 保留原始三个中文ZIP文件名；原本地包哈希保持。

## 2026-09-05 排版纠正：旧视觉结论已撤销

- 用户指出挤压与重叠后，重新检查完整18页PowerPoint实际导出。此前“accepted”的视觉结论不再作为当前交付依据；保留历史文件和运行目录。
- `tmp/imitate-spacing-20260905-140617` 对43个文字/表格对象修订：缩写长句、显式断行与段距、13–14页表格居中并调至12pt正文/13pt表头、拆开图表侧栏、缩短18页总结。未删除任何页或槽，未改图形/图片位置；图片、图表、工作簿和全部非幻灯片部件字节保持。
- 新增 `scripts/rdw_readability_audit.py`；Office导出补充逐行、组合对象和表格文字边界，明确导出成功不代表视觉通过。表格局部坐标已归一；行距筛查注明为启发式，不能冒充字形测量或视觉终审。
- 本轮自动回读18页/284槽通过；逐页看图复核完成。多行紧凑候选24→0，跨对象文字边界重叠0；7个原模板页脚/箭头边界候选保留记录，图上无裁字。修订版与完整前后对照作为新增交付；原三个ZIP的运行时代码未改变，未宣称此次重新发布ZIP或重新做便携验收。
- 新增排版检查5项回归通过；完整 `scripts/verify.py` 通过四格式Word/PPT Stub闭环、Schema快照和覆盖率门禁，overall88.29%。修订PPT已打开至第5页，全页对照已打开。

## 2026-09-05 完整页重构已验收

- 保持全部18页与原页序，完整72页PDF提取、284槽填充并实际PPTX回读通过；6媒体字节与几何保持，3图表缓存/工作簿同步。
- 新契约2.0、证据引用、草稿/正式验收分离；取消按低分删页，保留DeckIR2.2/WordIR1.3交接。
- PowerPoint已全页导出并完成Agent视觉与独立材料复核；最终out-08状态accepted，content-v4。工作目录tmp/imitate-visual-20260905-122511；9/4原目录62文件及2输入复核哈希未变。
- 完整scripts/verify.py通过：parsers91.96%、IR94.06%、lint94.23%、overall88.49%。原生对象7、完整性10、安装12、生成13、模仿20、API62及真实WPF UI验收通过。
- release-final-r2为本轮正式发布：生成1.1.0、模仿2.0.0、工作台2.2.0。三个独立ZIP已回验，两个Skill当前用户安装一致，旧版已备份。
- 最终模仿ZIP另在仓库外中文空格路径、仅包内Python、进程级禁网下完成真实18页闭环。未宣称干净VM/整机物理断网/真实模型API验收。
- 用户交付集中在当前Codex任务outputs：三个短名ZIP、18页仿版.pptx、全页对照、验收报告与哈希清单。实施前源码基线已保存，没有提交或重置Git。


## 2026-09-05 模仿 Skill：骨架草稿、按页打分、删 fit-reject 页

- 9/4 人工对照真实《华为工作汇报模板》后，空白壳已被覆盖门禁/删 omitted 页堵住；人再验收仍会倒在三件事：宿主只绑几个框、整份素材把不该填的页硬填、`verdict=reject` 页留在成品里当空页。
- `extract` 写出可过覆盖门禁的 `extract_pack/skeleton_draft.json`（绑完纳入页全部有字候选；目录/结束/empty 不纳入）。草稿不是 seal；宿主只改角色或省略页。
- `plan` 按该页 `page_pattern` 的角色词打分，`hits=0` 时 role 封顶 8，不再用全文 bullets 给每一页加分。过瘦素材整份仍 `RD-E020`。
- `finalize` 模式 A 从 `deck.pptx` 删除 `omitted`/`empty`/`reject` 页；输出 `skip_report.json` 合并 seal 省略与 fit reject。
- 不把 18 页华为原模板写入 git；不改 DeckIR 2.2；工作台不加模仿按钮；不做复制列/删行。对照脚本仍是 `scripts/rhetoric_deck_visual_qa.py`。
- 相关测试在 `backend/tests/test_rhetoric_deck_skill.py`。

## 2026-09-04 模仿 Skill：母版页脚、槽位覆盖与省略页

- 模式 A 消毒不再清空母版/版式铬；页脚密级改写成用户材料（缺省 `HUAWEI CONFIDENTIAL`）。
- `extract` 写出 `slot_candidates.json`；`seal` 对纳入页强制覆盖，漏绑 `RD-E010`。
- `finalize` 从 `deck.pptx` 删除 `omitted`/`empty` 页，`skip_report.json` 仍保留原因。
- 规格样品改为 4 页 16:9（封面、卡片框、原生表、圆角节点 + 母版页脚），不把 18 页华为原模板提交进 git。
- 相关测试在 `backend/tests/test_rhetoric_deck_skill.py`；对照脚本 `scripts/rhetoric_deck_visual_qa.py` 不进 Skill ZIP。

## 2026-09-04 模仿 Skill 1.0.3：保住 SmartArt 图形和截图像素

- source-shell 保留原页图片与 SmartArt 图形，只清可见文字再填用户材料。空页仍 skip，动画仍剥掉。
- 文本泄漏门 `RD-E040` 不变。源图像素留在产物里是故意的，不是把图画成可编辑原生对象。
- 相关测试在 `backend/tests/test_rhetoric_deck_skill.py`。

## 2026-09-04 双产物离线交付

- **Agent**：`dist/huawei-doc-workflow-1.0.3.zip`、`dist/rhetoric-deck-workflow-1.0.3.zip`
  及 `.sha256`。`python scripts/install_agent_kit.py --from-zip dist` 已在本机装入
  `.codex/skills`，两边 `doctor` 通过。
- **工作台**：`dist/document-workbench-windows-x64-2.2.0.zip`（105,811,123 字节），
  WPF 测试 23/23，Release 便携包已打出。
- **给拿走的短文件名**：`dist/生成.zip`、`dist/模仿.zip`、`dist/工作台.zip`（内容与带版本号 ZIP 相同）。
  说明见 `dist/DELIVER.txt`。

## 2026-09-04 模仿 Skill 1.0.2：恢复 SmartArt / 截图 / 动画页

- SmartArt 抽节点文字并换成可换字文本框；纯截图页改空占位框，不拷原图；动画/切换从页 XML 剥掉，有字的页不再整页跳过。
- 仍无法恢复的空页进 `skip_hints.json`。泄漏门继续扣住成品，`leak_report.json` 增加 `hits.loc`。
- 相关测试在 `backend/tests/test_rhetoric_deck_skill.py`。

## 2026-09-04 离线 Agent Kit（无 Docker）

- **推荐落地**：内网 Windows 不走 Docker、不合成两个 Skill、不打 PyInstaller 单文件。
  Agent 侧一条命令装两个 Skill；人机 Demo 仍用现成工作台便携 ZIP。
- **入口**：`python scripts/install_agent_kit.py` 复制 `huawei-doc-workflow` 与
  `rhetoric-deck-workflow` 到 `%USERPROFILE%\.codex\skills`，写
  `agent_kit_manifest.json`，并分别跑 `doctor`。`--check` 只验收不覆盖。
- **工作台**：继续 `scripts/package_document_workbench.py` 的
  `document-workbench-windows-x64-<VERSION>.zip`，与 Skill 目录解耦。
- **验收**：`backend/tests/test_agent_kit.py` 覆盖双 Skill 复制与 doctor。

## 2026-08-26 实习答辩 PPT（华为浅色模板）

- **最终产物**：已按 `答辩PPT完整设计稿.md` 和用户提供的浅色 16:9 模板完成 19 页可编辑
  PPTX，输出到 `C:\Users\GSQ\Downloads\实习答辩PPT_华为浅色版_20260826.pptx`。
- **叙事与证据**：把仓库程序明确定位为端到端 Demo / 原型验证，不包装成已投产产品；图表与
  关键数字以答辩稿、`docs/taskbook.md` 和仓库可复核统计为准。每页均写入讲稿备注和
  `[Sources]` 来源块。
- **模板与规则**：保留雪山封面、正文母版、Logo、品牌结束页；正文按项目 `hw-report`
  主题使用华为红、黑灰层级、微软雅黑/Arial 和 `HUAWEI CONFIDENTIAL`。源模板 6 个主题
  XML 已逐字节恢复，成品无外部关系、动画、切换和默认占位文字。
- **验收**：19 页均已渲染逐页目检；通用幻灯片测试通过（无文字溢出）；项目 lint 为
  **0 Error / 117 Warning / 1 Info，Pass=True**。Warning 主要来自“保留用户模板几何”与项目
  12 栏网格、字号种类上限之间的预期差异，未放宽任何 lint 规则。
- **审计说明**：模板保真启发式检查仍把 4 个已在 frame map 中声明删除的默认内容占位符
  误判为被新卡片遮盖；最终 PPTX XML 已确认这些占位符实际不存在。Windows PowerPoint
  字体保真与现场投影效果仍需人工终审。

## 2026-08-25 `huawei-doc-workflow` 非多模态可移植交付版 1.0.3

- **定位收敛**：Skill 继续不携带、不调用任何外部模型或图片生成服务；预期宿主 Agent
  不具备多模态图片理解。图片安全解码、规范化、哈希、嵌入和 DPI/裁切审计仍可运行，
  但引擎明确不声明理解图片像素或完成视觉评审。
- **图片语义门禁**：`prepare` 新增私有 `asset_semantics` 记录，模式固定为
  `text_grounded_only`。安全解码、尺寸、哈希、文件名或 `asset_id` 均不构成语义证据；
  未获 brief/源材料明确映射的图片会保留在 AssetManifest 中但从 Skill 输出的 VisualPlan
  图片推荐中过滤，禁止自动编造图片含义、说明、焦点、署名或图文关系。IR、Schema 和
  renderer 公共契约均未修改。
- **人工视觉终审**：`workflow_manifest.json.visual_review` 明确记录确定性引擎没有执行
  像素检查，状态为 `human_required`。有 PowerPoint/LibreOffice 时可导出预览供人查看，
  Agent 不得把“已导出图片”表述为“已视觉检查”；模板分析只承诺 OOXML 结构、槽位、
  几何、颜色和字体适配，不承诺像素级复刻。
- **跨电脑保护**：运行时从当前 `SKILL.md` 所在目录和当前宿主 Python 动态解析路径；
  文档禁止复用其它机器的盘符、用户目录、Python 或输出路径。打包检查扩展到全部文本
  文件，并阻断 `C:\Users\`、`C:/Users/`、`/Users/`、`/home/` 等用户机器绝对路径进入 ZIP。
- **验收结果**：Skill Creator 官方校验通过，Skill 专项 **13 passed**；安装版使用
  “真实 PNG（无文字说明）+ Markdown”前向验证得到 `grounded_assets=0`、
  `ungrounded_assets=1`、`image_recommendations=0`。`python scripts/verify.py` 通过，
  四格式端到端全绿；parsers 91.96%、IR 94.06%、lint 94.23%、整体 88.79%。
- **发布与安装**：`dist/huawei-doc-workflow-1.0.3.zip` 为 239,663 字节，SHA-256
  `87affae88d88de9f32a352732082997d2128770eb19d35fe86c8fd5142fcb875`。离开仓库解压后
  `doctor` 通过，85 个源文件逐一核对包清单；已安装到
  `C:\Users\GSQ\.codex\skills\huawei-doc-workflow`，旧 1.0.2 安装备份位于
  `C:\Users\GSQ\.codex\skill-backups\`。

## 2026-08-25 `huawei-doc-workflow` 商务模板实测与 1.0.2

- **真实套版验收**：用安装后的 Skill 1.0.2 读取
  `基带技术报告_演示生成测试.md`，套用用户提供的 `商务汇报.pptx`，生成 13 页可编辑
  PPTX。本机 PowerPoint 成功打开并导出全部 13 页 PNG；最终 lint 为
  **0 Error / 4 Warning / 1 Info**。四条 Warning 均来自封面沿用模板的非标准网格、页边、
  标题坐标和复杂背景，已做人工可读性复核；仍需目标 Office/字体环境终审。
- **模板安全处理**：原模板包含 18 个外部超链接，严格预检按 E003 阻断。新增公开命令
  `workflow.py sanitize-template`，只在“仅含外部超链接”的可证明场景生成独立安全副本，
  从不修改原文件；对其它外部/嵌入内容继续拒绝。改用 `lxml` 保留 Open XML 的
  `mc:Ignorable` 命名空间，修复标准库重序列化后 PowerPoint 无法打开的问题。
- **模板字段与字体修复**：模板渲染和替换审计支持 `presenter`、`date`、`index`；规划器
  对“演讲人/汇报人/日期/时间/序号/章节”等语义槽位加权，避免日期误写入普通正文。
  不合规或缺失字体会切换到模板提取出的合规回退字体，同时写入 Latin 与 East Asian
  run 属性，并按实际字体重新度量；没有放宽字体 lint。
- **实测边界**：本样例仅封面 1/13 使用 `prototype_replace`，其余 12/13 使用
  `master_redraw`。生成稿继承了模板的蓝色配色、背景语言和封面视觉，但没有智能复刻
  原模板所有卡片、时间线、图片和复杂版式；“安全套版 + 确定性重绘”已可用，复杂模板
  的页面级结构匹配仍是下一阶段主要能力缺口。
- **回归与发布**：模板专项回归 **21 passed**，Skill Creator 官方校验、快照同步检查和
  `python scripts/verify.py` 全部通过（parsers 91.96%、IR 94.06%、lint 94.23%、整体
  88.79%）。发布包 `dist/huawei-doc-workflow-1.0.2.zip` 为 238,304 字节，SHA-256
  `f16979265f9dda83049a14e2758122df0a7ac06f03bb66f0bf3a6b6bfb0cf5d8`；85 个文件按
  manifest 校验后安装到 `C:\Users\GSQ\.codex\skills\huawei-doc-workflow`。
- **最终产物**：`...\huawei-doc-workflow-output\商务汇报模板_基带技术报告_skill_1.0.2_release\`
  内含 `deck.pptx`、安全模板副本、结构分析、模板计划、lint、工作流清单和 PowerPoint
  导出的 `visual-qa`。PPTX SHA-256 为
  `a6e8c0e2e14248a5d4095331cba9689f469863862d3f878440e48e356d98229e`。

## 2026-08-25 `huawei-doc-workflow` 真实前向验收与 1.0.1 修复

- **前向样例**：用安装后的 Skill 处理 `基带技术报告_演示生成测试.md`，生成 13 页
  `hw-report` PPTX，并通过本机 PowerPoint 导出 1600×900 PNG 逐页检查；不再只依赖
  JSON lint。
- **发现的问题**：1.0.0 在无 Graphviz 时虽然能完成渲染，但四节点架构图节点过小、
  整体稀疏，强调节点技术文字出现难看换行；四列 KPI 的 `1.18 Gbps` 也发生单位
  断行。原 lint 为 0 Warning，说明自动检查没有覆盖 Office 实际字体度量和降级布局观感。
- **1.0.1 修复**：无 Graphviz 的未分组架构节点按可用槽位放大，保留显式/分组几何；
  KPI 根据卡片实际宽度预估并降低数值字号，保持“数值 + 单位”单行；Graphviz 降级
  写入 `workflow_manifest.json.runtime_warnings`，`doctor` 与 Skill 指令明确要求视觉复核，
  禁止再表述为“视觉不受影响”。PPT lint 同步接受主题约束内的 KPI 自适应字号，并从
  单页字号层级统计中排除该数值 run；低于主题下限的篡改仍稳定告警。
- **验证证据**：PowerPoint 复渲染确认第 3 页 KPI 与第 5 页架构文字完整、可读；新增
  两条渲染回归。相关 PPT/Skill 套件 **121 passed / 8 skipped**，Skill Creator 官方校验
  通过；最终 `python scripts/verify.py` 通过（全量 backend、四格式端到端；parsers
  91.96%、IR 94.06%、lint 94.23%、整体 88.82%）。最终安装后的样例审计为
  **0 Error / 0 Warning / 1 Info**，并由 PowerPoint 导出 13 页 PNG；唯一架构页已单独复核。
- **发布与安装**：最终包 `dist/huawei-doc-workflow-1.0.1.zip`（237,050 字节），SHA-256
  `b03c87cdfa4768d53e30304736239f7e0e5a02268232c1d94c2ce5aff43c6b91`；已按包清单核对
  85 个文件并更新安装到
  `C:\Users\GSQ\.codex\skills\huawei-doc-workflow`，1.0.0 安装备份保存在
  `C:\Users\GSQ\.codex\skill-backups\`。最终样例位于
  `...\huawei-doc-workflow-output\基带技术报告_演示生成测试_skill_1.0.1_release\`。

## 2026-08-25 `huawei-doc-workflow` 独立 Skill 1.0.0

- **已交付**：新增可直接安装的 `skills/huawei-doc-workflow/`。Skill 仅允许显式
  `$huawei-doc-workflow` 调用，由当前 Agent 根据生成包编写 WordIR 1.3 / DeckIR
  2.2；本地 `workflow.py` 只执行 `doctor → prepare → validate → finalize → audit`
  的确定性解析、校验、渲染和审计，不包含 Stub/NGA/opencode-go、Web、WPF、密钥、
  wheelhouse 或嵌入式 Python。
- **契约与隔离**：冻结产品 2.2.0 的最小运行快照、Schema、few-shot 示例和逐文件
  SHA-256 清单；打包前检查原项目核心与快照漂移，发现差异即阻止发布。非法 IR 最多
  允许初稿加两轮修正，仍失败即 `SKILL-E020` 停止，绝不进入 renderer；已有产物默认
  拒绝覆盖。
- **专项验收**：`backend/tests/test_huawei_doc_skill.py` **12 passed**，覆盖四种输入格式、
  纯主题、Word、完整 Deck、17 种版式契约、四主题、真实图片、模板、独立 audit、
  Graphviz 确定性降级、非法 IR、危险模板、缺失图片、覆盖保护和解压后隔离运行。
  `skill-creator` 官方 `quick_validate.py`、Ruff、源码清单/漂移检查均通过。
- **项目回归**：`python scripts/verify.py` 通过（四格式 Word/Deck 端到端；parsers
  91.96%、IR 94.06%、lint 94.26%、整体 88.68%）。最终 ZIP 离开仓库目录后再次通过
  `doctor + validate + finalize`，生成可编辑 DOCX。
- **发布物**：`dist/huawei-doc-workflow-1.0.0.zip`（235,468 字节，86 个条目），
  SHA-256 `8a1599d299ec03f01e03015fab28ad0a0f5d387feb10fbff44d75890c8923a6e`；
  同目录包含 `.zip.sha256`。仍需人在目标 Windows Word/PowerPoint 与目标字体环境中做
  事实、字体和视觉终审；lint 全绿不替代人工签字。

## 2026-08-14 WPF 下载服务误报修复

- **根因**：`WorkbenchApiClient.DownloadAsync` 对成功的二进制响应也调用了
  `EnsureSuccessAsync`；该方法未先判断 2xx，尝试把 PPTX 解析为 JSON 后统一抛出
  `HttpRequestException`，界面因此错误显示“本地服务暂不可用”。后端实际返回
  `200`，产物 `deck.pptx` 存在且可读。
- **修复**：`EnsureSuccessAsync` 在成功 HTTP 状态时立即返回；非 2xx 响应继续保留
  原有的结构化错误解析与定位。
- **回归**：新增 `WorkbenchApiClientTests.DownloadAsync_WritesSuccessfulBinaryResponse`；
  修复前确定性失败为“本地 API 请求失败（200）”，修复后通过。完整 WPF 测试
  `21/21` 通过，`python scripts/verify.py` 通过（parsers 91.96%、IR 94.06%、
  lint 94.26%、整体 88.78%）。
- **可见复验**：重启更新版工作台，在“任务”页下载已完成 PPTX；界面显示已保存，
  保存副本为有效 ZIP/PPTX（45,212 字节，`PK` 文件头），测试副本已清理。

## 2026-08-14 桌面端异常恢复体验复查

- **复现问题**：隐藏 Python 后端异常退出后，任务页导航会使 `async void` 异常进入全局处理并弹出通用错误框；任务表继续显示旧数据却没有过期提示；侧栏“已连接”与顶部原始 loopback 连接错误相互矛盾；诊断页首次读取失败时字段为空，无法判断当前状态。
- **修复**：任务与诊断的只读请求归并到同一条有界、串行化的后端恢复路径；任务页改为页面内同步/缓存状态，诊断页改为可读的不可用状态，避免暴露本机端口和原始网络错误。恢复达到两次上限时，明确要求重启工作台，不再错误引导用户继续刷新。
- **回归与可见复验**：`dotnet test desktop/DocumentWorkbench.Tests/DocumentWorkbench.Tests.csproj` 通过 **20/20**，覆盖诊断恢复、任务恢复无通用弹窗、恢复上限提示；`python scripts/verify.py` 通过，parsers 91.96%、IR 94.06%、lint 94.26%、整体 88.78%。手动注入后端退出后，任务页与诊断页均在约 3.5 秒内恢复，诊断字段完整显示。
- **Windows 控制台修复**：`verify.py` 入口显式采用 UTF-8 + `backslashreplace` 输出，避免 GBK 终端因 pytest 的 Unicode 输出而中断；新增覆盖该行为的单测。
- **交付状态**：已重建 `dist/document-workbench-windows-x64-2.2.0.zip`，SHA-256 为 `1cb88d66d9a4b49ebcb4ba026dc0c60808ab15c2dd9294bc4104731829dcca4c`（2257 个文件）。

## 2026-08-14 桌面诊断页后端自恢复

- **修复**：诊断页检测到隐藏 Python 后端已退出时，会复用有上限、串行化的
  自动重启流程，待新后端通过 API 就绪检查后重新读取诊断；不再因读取失败走通用
  操作错误提示。诊断页仅使用 `/api/diagnostics` 的既有生成器快照，不再额外依赖
  生成器设置请求。
- **回归**：新增原生 UI 用例，显式终止测试窗口所属后端后点击“诊断”，断言替代
  后端进程成功启动。`dotnet test` 通过 **18/18**；`python scripts/verify.py` 通过，
  parsers 91.96%、IR 94.06%、lint 94.26%、整体 88.78%。
- **交付状态**：已生成独立热修复便携包
  `output/diagnostics-hotfix/document-workbench-windows-x64-2.2.0.zip`
  （SHA-256 `b8a1bd4a6130de6721b4fcad752c2313e8e02c85ed75bd09c3118db02d76135e`）；
  现有运行中的旧便携包未被覆盖。

## 2026-08-14 AI 通道统一管理界面(用户指令:NGA 与 opencode-go 整合)

- **概念统一**:NGA(CLI/HTTP)与 opencode-go 归并为"AI 通道",同一个设置界面
  选择/配置/切换;未来新增 AI(中转站/NGA 变体)只需加 generator + 配置表单。
- **浏览器工作台**:生成设置面板重构为「通道选择(Stub / NGA CLI / NGA HTTP /
  opencode-go)+ 动态表单 + 共用按钮(保存/测试/启用)」;各通道配置独立保存,
  启用后生效;状态卡/引擎栏显示当前通道、模型、Base URL、密钥状态。
- **WPF 桌面端**:设置页"NGA"+"opencode-go"两个子页合并为**「AI 通道」**一个页面:
  通道下拉 + 按通道显隐字段 + 共用保存/测试/启用;密钥仍存 Windows Credential
  Manager,非敏感配置存 settings.json。
- 修复:作者样式覆盖 `hidden` 属性(CSS 加 `[hidden]{display:none!important}`);
  NGA 模型输入按通道拆分为 ngaModelCli/ngaModelHttp 避免 id 冲突。
- 测试:UI 测试更新为统一通道面板断言(desktop+mobile 全绿);pytest **798 passed /
  15 skipped**;ruff 全绿;WPF Release 0 警告 0 错误,xUnit 17/17。
- 发布物重建:ZIP `5410a1bf…` / EXE `5d590405…`;桌面便携版已更新运行中
  (active=codex,设置页可见模型/Base URL/密钥状态)。

## 2026-08-14 设置页 AI 通道可视化 + opencode-go 可配置(用户指令)

- **后端 GeneratorManager 支持 codex 通道配置**:新增 `CodexConfig`(base_url/model/
  api_mode/timeout/reasoning_effort,非敏感);configure/test/activate 三阶段与 NGA
  一致;status 输出 active 的 base_url/model/`credential_configured`(绝不返回密钥);
  initial=CodexGenerator(环境变量)时 draft 自动预填,表单可直接看到/修改当前通道。
- **浏览器工作台**:AI 生成设置面板新增"opencode-go 通道(默认 AI)"配置区
  (Base URL/模型/接口模式/API 密钥/超时/推理强度 + 保存/测试/启用);状态卡与
  引擎栏显示通道名、Base URL、模型、密钥状态。
- **WPF 桌面端**:设置页新增"opencode-go"导航页,展示当前生成器
  (通道/Base URL/模型/密钥状态)并支持编辑保存(密钥存 Windows Credential
  Manager `HuaweiDocumentGenerator/OpenCodeGo`,非敏感配置存 settings.json,
  留空密钥回退环境变量 OPENAI_API_KEY)。
- 测试 +2(codex 配置保存/测试/启用、环境预填与凭据状态);pytest **798 passed /
  15 skipped**;ruff 全绿;WPF Release 0 警告 0 错误,xUnit 17/17。
- 发布物重建:ZIP `fa8f00a5…` / EXE `14ec8db6…`;桌面便携版已更新运行中,
  后端实测 active=codex,设置页展示 Base URL/模型/密钥状态。

## 2026-08-14 AI 优先默认配置(用户指令)+ 三个启动链路修复

- **AI 优先默认**:`default_ir_generator()` 优先级改为 显式 `IR_GENERATOR` > 检测到
  `OPENAI_API_KEY`(用户级环境变量,setx 持久化,不进 git)时默认 **codex/opencode-go**
  (`deepseek-v4-flash`) > 无凭据回退 stub;`desktop_host.main` 与 `web_api.main`
  启动入口应用该默认(create_api_app 默认仍 stub,测试契约不变)。
- **修复 1(环境变量显式传递)**:BackendProcessHost 显式把 `OPENAI_API_KEY` 写入
  后端子进程环境(不依赖隐式继承,不落盘不记录)。
- **修复 2(WPF 启动覆盖默认)**:`MainWindow.InitializeServiceAsync` 原来在 NGA
  未启用时强制 `configure(stub)+activate`,每次都把后端默认覆盖回 stub;改为
  只读后端当前生成器并显示(opencode-go / stub),不再强制切换。
- **修复 3(诊断可见)**:desktop_host 的 state 文件新增 `generator_name` /
  `manager_generator` / `backend_package`,启动后可读证据。
- **真实端到端验证**(带 key 模拟用户双击):WPF 启动 → 后端 API active=**codex** →
  提交 word 任务 → **done,生成器=codex**,lint 0 错误 0 警告。
- 回归:pytest **796 passed / 15 skipped**;ruff 全绿;WPF Release 0 警告 0 错误,
  xUnit 17/17。
- 发布物重建:ZIP `33d3a169…` / EXE `721b7ff8…`(含以上全部修复),桌面便携版已更新
  并运行中。

## 2026-08-14 代码收敛(用户指令)+ 内网 AI 适配清单

- **分支收敛**:主线重命名 `codex/audit-2.1.0` → **`codex/release-2.2.0`**(与
  VERSION 2.2.0 对齐);删除 20 个冗余分支(12 个 `backup-*`、7 个旧 `codex/*`、
  `fix-arch-diagram`)与 2 个旁支 worktree(ai-ppt-2.2.0 / ai-ppt-2.3.0,超长路径
  用 robocopy /MIR 清理),归档至 `dist/git-bundles/branches-archive-20260814.bundle`
  (9MB)+ 2.3.0 未提交 diff 存档 patch;仓库收敛为单分支单 worktree。
- **dist 清理**:删除 2.1.0 与 2026-07 旧发布物(共 10 个文件),仅保留 2.2.0
  ZIP/EXE/SHA-256/交付说明。
- **内网 AI 适配准备**:新增 `docs/内网AI适配信息清单.md` —— 13 项信息收集表
  + 适配步骤 + 验证基线;OpenAI-compatible 仅配置零代码,协议不同则新增 adapter
  (I3:IR/renderer/lint 零改动)。
- 文档同步:GIT_WORKFLOW(唯一主线表述、归档恢复方法)、QUESTIONS、README、
  dist/交付说明;历史审计文档(AUDIT_2.1.0、代码审查报告)保留原样。
- 回归:分支/产物清理不影响代码;`verify.ps1` C0 仍通过。

## 2026-08-14 发布冲刺:真实模型链路 + 2.2.0 重建发布物 + 本机验收演练 + UI 缩放

### 真实模型链路(opencode-go + DeepSeek v4-flash,B9/A4)
- 网关探测:`https://opencode.ai/zen/go/v1` 支持模型 ID **`deepseek-v4-flash`**(显示名
  "DeepSeek V4 Flash" 不被接受,`/models` 实测);responses 与 chat_completions 双模式可用。
- **codex.py 修复**:默认模型改为 `deepseek-v4-flash`;新增浏览器 User-Agent —— 网关
  Cloudflare 风控对 `Python-urllib/3.x` 返回 **HTTP 403 error 1010**,实测必须浏览器 UA。
- 回归测试 +2:网关默认值断言、UA 断言(15 passed)。
- **真实冒烟全链路通过**(key 仅环境变量,不落盘、不提交):
  `quarterly_report.md → parse → prompt → DeepSeek v4-flash → 校验 → 渲染 → lint`
  WordIR 1.3(8 blocks)+ DeckIR 2.2(cover/title_bullets),lint 0 Error 0 Warning。

### 版本对齐 + 发布物重建(B6)
- `VERSION` → **2.2.0**(installer.iss 同步);/api/version 输出 2.2.0 + deck_ir 2.2。
- 重建:`dist/document-workbench-windows-x64-2.2.0.zip`(105.8MB / 2257 文件)与
  `dist/HuaweiDocumentGenerator-Setup-2.2.0.exe`(87.6MB),SHA-256 随包。
- 包内验证:解压清点、`runtime-manifest.json`(Windows 10/11 x64 / python 3.12.10 /
  graphviz 15.1.0 / 29 wheels)、`samples/ir` 58 文件(P0 未复发)、包内 python 起
  web_api → token 流程(401 → session-token → 200,version=2.2.0)。

### 本机验收演练(A1,近似证据;干净真机仍须人工)
- wheelhouse `--no-index --require-hashes --dry-run` 29 wheel 全命中;
- 安装 EXE:静默安装(2259 文件)→ GUI 启动存活 → 静默卸载目录清空;
- Graphviz:系统 PATH 加入 `C:\Program Files\Graphviz\bin` 后 environment_report
  识别 v15.1.0(source=system),架构图不再走 fallback;
- verify.ps1 全绿(C0:parsers 91.96 / ir 94.06 / lint 94.26 / overall 89.13)。

### UI 缩放与阅读体验(B8)
- 工作台新增**界面缩放**(100% / 112% / 125%):`html { zoom: var(--ui-zoom) }`,
  topbar 与设置页双控件同步,localStorage 持久化;Segoe UI Variable 字体栈优先,
  最小可读字号 11px;
- `scripts/test_workbench_ui.py` 修复两处**测试资产滞后**(非产品 bug):
  ① FailOnceGenerator 缺 `cancel_event`(#28 契约透传);② 测试环境未传
  `session_token`(#2 token 流程)导致前端每请求先 GET /api/session-token 404。
  修复后 UI 测试 desktop+mobile 全绿(含新增缩放断言),覆盖真实鉴权路径;
- 排查期间在 web_api.py 的临时调试代码已还原(无净改动)。

### 编译确认(B7)
- 本机 `dotnet build DocumentWorkbench.csproj -c Release`:0 警告 0 错误;
  `dotnet test DocumentWorkbench.Tests`:17/17 通过。

### 回归与遗留
- pytest **796 passed / 15 skipped**;ruff 全绿;UI 测试全绿。
- 遗留:干净断网真机验收、PowerPoint 视觉签字、真实脱敏语料、代码签名仍待人工
  (QUESTIONS.md);NGA 按用户决定不做,默认 stub,真实链路走 codex/opencode-go。

## 2026-08-14 业务形态语料 + 文档契约版本同步 + 进度刷新

- **业务语料(用户委托生成)**:新增 `samples/input/business/` —— docx/xlsx/pptx 各 3 个
  业务形态文件(需求规格说明书、项目周报、技术方案评审稿、销售台账、年度预算编制表、
  项目里程碑计划、产品季度汇报、项目启动会材料、年度总结与规划),由
  `scripts/make_business_samples.py` 确定性生成(虚构、完全脱敏),内容贴近真实业务
  (多级标题/表格/公式/合并单元格/原生图表/演讲备注)。
  - `backend/tests/test_business_corpus.py`:9 文件 × (解析确定性 + Word 全链路 +
    Deck 全链路)= 28 用例,全部通过(8.6s);lint 零 Error。
  - 边界说明:`real/` 目录仍保留给人放真实脱敏文件(gitignore),business 语料
    不冒充真实验收证据,已写入 QUESTIONS.md。
- **文档契约版本同步(代码仓对齐)**:README、docs/taskbook.md、使用说明、HUMAN_REVIEW、
  HTML_EXPERIMENT、DEPLOY_AND_USAGE、FRONTEND_API、华为版式参考映射、codex-goal 的
  DeckIR 2.1→2.2 / WordIR 1.2→1.3 / 迁移路径 1.4-2.1→2.2 引用全部对齐代码现状;
  README 交付资产清单补充 business 语料条目。历史记录类文档(代码审查报告、
  WINDOWS_ACCEPTANCE、AUDIT_2.1.0 等)保持当时时点原样。
- 本次为文档与语料工作,未改动任何业务代码;不触碰旁支 worktree
  (codex/ai-ppt-2.2.0 / codex/ai-ppt-2.3.0),仅维护主线 codex/audit-2.1.0。

## 2026-08-13 深夜补记(commit acce3ba/f6fb13c/492eb9f/9c85e2b,PROGRESS 当时未记录)

- **W-N2 决策落地**:web_api 任务队列改为 2 个并发 worker + 4 等待位(`DEFAULT_NUM_WORKERS=2`),
  reliability 契约同步 worker 字段;队列容量测试逐任务断言失败详情。
- **IR-N4 契约升版仪式完成**:WordIR 1.2→1.3、DeckIR 2.1→2.2 —— 表格 rows 强制
  `min_length=1`(模型侧 validate_rows 与导出 Schema 对齐)、DeckTable body
  `cell_spans` 不得跨越 `row_groups` 标签行;migrate 路径扩展为 1.4-2.1→2.2;
  schema 快照/确定性哈希/测试断言全量更新;`DECK_IR_VERSION` 常量统一 API/诊断版本。
- **C-N9 重试用当前输入**:桌面端重试按钮携带当前输入重放,不再依赖后端保留原始输入。
- 并发/解析/渲染健壮性:md 表格裸分隔行修复、docx/xlsx/pptx 解析边界(共 +38 文件、
  ~1800 行,含 web_api 237 行)、NGA CLI 超时、shell 剥壳、docx_renderer 130 行、
  template planner/text_fit、C# BackendProcessHost 管道排空与 SettingsStore。
- 回归:full pytest **767 passed / 15 skipped**(较上轮 723 新增 44 个回归测试);
  分支 `codex/audit-2.1.0` 工作树干净。

## 2026-08-13 全量排障:两轮审计报告未处理项批量修复(约 45 项)
- 在上一轮(G-N2 主题穿越、P-N2 UTF-16 DTD)基础上,按"先测试后实现"批量清掉两轮
  代码审查报告(`代码审查报告_2026-08-12*.md`)中剩余未修缺陷,覆盖:
  - **解析层**:md 空表头兜底(#7)、表格吸行/第二分隔行/转义管道(#8/P-N7/P-N8)、
    md UTF-16 编码(P-N11)、docx Word 列表识别(#10)、docx UTF-16 unsupported 扫描
    (P-N9)、xlsx 隐藏首行 header_guess(#16)、pptx 非连续页 embedding 警告(P-N10)。
  - **IR/shell**:FENCED_JSON 关闭围栏按行锚定(IR-N5)、正文不平衡花括号不再误判截断
    (#19)、DocumentIR col_widths 校验(#22)、assets 清单原子写(#50)。
  - **渲染/模板**:双向箭头 headEnd/tailEnd 顺序(#12)、列表样式存在性兜底(#14)、
    slide_layouts 空白版式探测(#15)、docx UTF-8 蓝改红容错+临时文件 finally(#17/R-N15)、
    补充平面宽字符计数(R-N10)、缺 accent2-6 派生色板(R-N13)、mermaid 标签含 `;`(#45)、
    规划器容量用匹配形状(#23)、审计占位残留用真实语义(#24)。
  - **lint**:check_pptx 损坏文件 E001 防御(#44)、多序列图表只取首序列(#43)、
    目录章节号单双位对齐(L-N7)、docx word/*.xml UTF-16 容错(#48/L-N11)。
  - **generators/web_api/CLI**:analyze 捕获 ValueError(G-N4)、stub/depth 裸 int()
    防御(G-N9)、M\d+ 里程碑去平台名误判(#49)、markdown 导出转义图片目标(#51)、
    _truncate_text 小 limit 负 tail(#46/G-N12)、超时设 cancel_event(#33)、
    _fail_job 用锁内快照 assets(#35)、取消竞态 409(#39)+写失败封套(W-N8)、
    根路由 `/`(W-N6)、power 脚本 stop_workbench 子进程不再 throw(S-N4)、
    make_wheelhouse 钉 cp ABI(S-N9)、demo_e2e 先校验后写盘(S-N15)。
  - **C#**(未编译验证):FormatBytes(0)、下载临时文件唯一名、bootstrap 保留 10→2 分钟、
    任务列表刷新保留选中。
- 回归:full pytest **723 passed / 15 skipped**(+6 回归测试);ruff 全绿;
  `scripts/verify.py` C0 通过(parsers 93.19 / ir 94.10 / lint 94.26 / overall 88.94)。
- 遗留(见 QUESTIONS.md 新增节):G-N10/W-N2/IR-N4/IR-N8 属产品决策或需契约仪式;
  C-N9 需后端保留原输入;全部 C# 改动待 Windows 真机 dotnet 验证。未提交(待确认)。

## 2026-08-13 Track B 补修:主题路径穿越 + UTF-16 DTD 绕过(2 项 HIGH 安全)
- **G-N2/#5 主题路径穿越(library 层)**:`rendering/theme.py::load_theme` 原按
  `THEMES_DIR / f"{name}.json"` 直接拼路径,未走 `resolve_theme` 白名单;
  CLI/库调用(render/check/prompt builder)可传 `../../...` 读任意本地 .json 并注入
  LLM prompt(外带通道)。修复:load_theme 先 `resolve_theme(name)` 再拼文件名
  (保留 hw_v1→hw_theme.json 特殊映射,呼应 R-N14);`prompting/builder.py::_theme_section`
  捕获 UnknownThemeError 优雅回落空风格段。回归:`test_theme_presets.py` 5 例路径穿越/
  未知主题(load_theme 抛 UnknownThemeError、prompt 不注入)、`test_pptx_renderer.py`
  layout 坐标测试补 registry monkeypatch。
- **P-N2/#6 UTF-16 DTD/ENTITY 字节扫描绕过**:`security/office_package.py::_scan_xml_safety`
  原只做 ASCII 子串匹配,UTF-16 编码的 `<!DOCTYPE`/`<!ENTITY`(带空字节)绕过前置防线后
  直达 stdlib ElementTree 展开内部实体(billion-laughs DoS)。修复:needles 增加
  UTF-16LE/BE 模式,carry 长度按最长 needle 自适应。回归:`test_office_preflight.py`
  参数化 utf-16-le/utf-16-be 两例断言 `unsafe_xml_declaration`。
- 回归:full pytest **717 passed / 15 skipped**;ruff 全绿;`scripts/verify.py` C0 通过
  (parsers 94.50 / ir 94.16 / lint 94.44 / overall 89.18)。
- 未提交(待用户确认);未动 Track C(产品决策,见 QUESTIONS.md)。

## 2026-08-12 发布候选测试(L0-L5 全过 + 2 个发布级修复)
- 重建发布物: 便携 ZIP 105.8MB / 2257 文件、安装程序 EXE 91.9MB,
  哈希见 dist/*.sha256 与 QUESTIONS.md
- 测试矩阵:
  - L0 回归: pytest 708/15、ruff、verify.py C0、dotnet xUnit 16/16
  - L1 完整性: ZIP 解压清点、runtime-manifest(今日生成)
  - L2 打包应用: PortableAcceptanceTests 指向便携包 exe 与已安装 exe 各通过
  - L3 包内后端: 内置 python 起 web_api → token 流程(401/200)+ word 任务
    done + lint pass
  - L4 安装程序: 静默安装→SHA256SUMS 校验→已安装 exe 走查→静默卸载→目录清理
  - L5 离线安装: wheelhouse --require-hashes --dry-run 全命中
- 测试发现并修复:
  ① P0 便携包缺 samples/ir(builder few-shot)导致包内所有生成 E001 失败
  ② packages.lock.json 与 SDK 8.0.423 ILLink.Tasks 版本不同步(NU1004)
- 未完成(人工): 断网机验收/视觉签字/真实语料/真机 NGA/签名 —— QUESTIONS.md

## 2026-08-12 环境验证三件套完成(全部闭环)
- **C# 编译验证**: 安装 .NET SDK 8.0.424 → Release 编译 0 警告 0 错误;
  编译抓到 A8 从静态方法调用实例成员(CS0120)已重构为局部状态;
  xUnit 16/16 通过(含真实启动 Python 后端的 PortableAcceptance)
- **#28 job 级取消**: IRTextGenerator.generate 新增 cancel_event + GeneratorCanceled;
  NGA CLI 轮询取消即杀进程树、HTTP 用守护线程包裹 urlopen 快速返回;
  repair/depth/web_api 全链路透传(条件 kwargs 兼容旧 fake);
  JobRunner 见 canceled 即 set 事件
- **#2 浏览器 token 流程**: main() 默认生成 32 字节随机 token(--no-auth 可关);
  /api/session-token 同源下发;前端 sessionFetch 包装器全 15 处调用带头;
  Origin 校验退居二线
- 回归: pytest 708 passed / 15 skipped;ruff 全绿;verify.py C0 通过;
  dotnet xUnit 16/16
- 至此审计报告全部条目处理完毕: 修复/决策/挂起项均已闭环或记录在案

## 2026-08-12 决策批执行(#2 Origin 校验 + #29 护栏 + R-N3/R-N7/R-N8/L-N3~L-N6/IR-N3/C#/refs)
- 按用户拍板执行:
  - #2: 浏览器模式加 Origin 校验(非回环 Origin 的写请求 403,堵跨源 CSRF)
  - #29/#W-N4: analyze 90s / 连接测试 60s 服务端护栏(守护线程,超时 E012 504,
    超时工作目录留给孤儿清扫)
  - R-N3: combo 阈值渲染到主轴刻度 + IR 约束次轴引用 D004
  - R-N7/R-N8: pptx tcPr / docx pPr、tcPr 子元素顺序合规(ln* 先于 fill、
    pBdr/tcBorders 先于 shd)
  - L-N3: 合并单元格溢出估计按 gridSpan/rowSpan 真实跨度
  - L-N5: docx 超链接 run 与文本框段落纳入字体检查
  - L-N6: 页脚豁免收紧(形状须在页脚带内)
  - L-N4: 无 autofit 元素的外部文件也执行溢出估计
  - IR-N3: DeckMeta.classification 与 WORD_CLASSIFICATIONS 对齐,
    **DeckIR 2.0→2.1 契约仪式**(migrate 1.4-2.0→2.1、TemplatePlan 2.1、
    /api/version 2.1、schema 快照重导出、全测试 payload/断言/确定性哈希更新)
  - C# C-N1~C-N5(轮询代际/终态刷新/try 15s 超时/NGA 保存顺序/StageLabels 补全,
    待真机 dotnet 验证)
  - 清理 .git/refs/codex 损坏 refs(零 sha1+超长路径),gc/commit 不再报错
- 回归: 704 passed / 15 skipped;ruff 全绿;verify.py C0 通过
  (parsers 94.60 / ir 94.20 / lint 94.44 / overall 89.28)
- 剩余待办: C# 编译验证(.NET SDK)、#28 深度取消机制(cancel_event)排期、
  browser 模式 token 流程(可选加固)

## 2026-08-12 系统化排障会话(22 项修复,分支 codex/audit-2.1.0)
- 从审计报告按 P0/P1/P2 逐项"证据链→最小修复→回归测试→commit",每项独立提交:
  解析层 #30(stderr 不计 10MB 上限) #37(codex 畸形 choices) P-N3/#11(pptx 回退
  标题不再重复进正文+空占位符回退) P-N4(空 sheet 无 dimension) P-N5(损坏 inline
  shape) P-N13(负 outlineLvl) P-N6(xlsx 句柄泄漏);web_api #31(413 JSON 封套)
  #34(analysis-* 清扫) #36(word lint 资产) #41(graphviz 缓存);模板 R-N1/R-N2/R-N12;
  IR G-N5(repair 内嵌原始提示) IR-N6/IR-N7;生成器 G-N7(codex max_tokens);
  diagram R-N5(mermaid 标签含箭头);scripts S-N3(断点续传 .part) S-N5(视觉 QA
  旧报告) S-N8(PS null) S-N12(StopIteration)
- 同步样例期望 facts 到 P-N3 修复后行为(项目汇报.pptx body_count 各减 1)+ hash manifest
- 回归: 691 passed / 15 skipped(基线 656 → +35 个回归测试);ruff 全绿;
  verify.py C0 通过(parsers 94.50 / ir 94.23 / lint 94.34 / overall 89.19)
- 未修(记录原因): #2 API 鉴权、#28/#29 线程与超时、R-N3 combo 阈值、IR-N3 deck
  密级枚举 —— 均属产品决策/契约变更,挂 QUESTIONS.md;R-N7/R-N8 OOXML 子元素顺序
  —— 目标环境 PowerPoint 容忍,无可观察故障;C# 项无 .NET SDK 无法验证
- 仓库既有问题(非本次引入): .git/refs/codex 损坏 refs 致 commit 时 geometric-repack 告警


## 2026-08-12 第二轮代码审计 + Track A 修复(8/8 已提交)
- 产出 `代码审查报告_2026-08-12_第二轮.md`:8 个并行 subagent 全仓静态审查 + 主会话
  独立复现关键结论;前轮 63 项复核(47 REAL / 3 PARTIAL / 2 FALSE / 机制修正 4 项)+
  约 55 项新增发现(2 CRITICAL / 9 HIGH / ~30 MEDIUM / ~45 LOW)。
- Track A 八项修复已提交(分支 `codex/audit-2.1.0`),每项"先测试后实现":
  - A1 `web_api._nga_config_from_payload` HTTP 分支白名单构造 → NGA HTTP 配置在
    桌面端可保存(此前恒 E010);回归测试带 transport/cli_path 字段
  - A2 `stub._json_after_marker` 按 marker 位置选 find/rfind + 键校验 → 用户文档
    回显 marker 文本不再劫持解析(静默丢内容/崩溃)
  - A3 `JobRunner._loop` try/except + supervisor 线程 → 失败报告写盘失败不再杀死
    唯一 worker;回归测试模拟 OSError
  - A4 md 表格 12 列 cap + W103(此前 13 列合法表格杀死整个文件 E001)
  - A5 TableBlock/DeckTable col_widths 改 `isfinite` 校验(NaN/Infinity 不再直达
    渲染器)
  - A6 `office_visual_export.ps1` 写无 BOM UTF-8(PS5.1 -Encoding utf8 恒写 BOM,
    目标机视觉 QA 门禁必崩)+ Python 读端 utf-8-sig 双保险
  - A7 打包前置 wheelhouse↔`requirements-win312.lock` 逐 wheel 哈希校验 +
    `MIGRATION_PACKAGE_MANIFEST.json` 补齐 colorama/waitress 两 wheel(27→29)
  - A8 `BackendProcessHost` 子进程 stdout/stderr 持续排空(消除管道死锁);
    **本机无 .NET SDK,C# 编译/测试留 Windows 真机人工验证**
- 回归:`.venv` pytest **663 passed / 15 skipped**(新增 7 个回归测试);ruff 全绿;
  `scripts/verify.py` 通过(C0: parsers 93.53 / ir 94.01 / lint 94.30 / overall 89.00)。
- 未动:Track B(数据正确性/资源/并发)、Track C(产品决策,见 QUESTIONS.md)。
- 已知仓库问题(非本次引入):`.git/refs/codex/...` 损坏 checkpoint refs 导致每次
  commit 时 `geometric-repack` 失败告警(commit 本身成功),后续处理时清理。


## 2026-08-08 2.1.0 审计、原生化与发布候选

- 候选分支：`codex/audit-2.1.0`；保留既有实验工作树和全部 `backup-*` 恢复分支，未修改
  宿主工具留下的 `.git/refs/codex/turn-diffs/checkpoints/...` 损坏 checkpoint refs。
- Windows 11 自动化门禁：`scripts/win/verify_all.ps1 -Ui` 通过。C0 覆盖率为
  parsers 93.51%、IR 93.94%、lint 94.30%、整体 89.20%；可靠性报告 671/671 通过，
  浏览器工作台截图覆盖桌面/移动端、系统/浅色/深色、设置、任务、运行、成功和失败。
- 修复：Graphviz 不再以文本模式读取本地化 `dot` 的 stderr，避免非 UTF-8 字体诊断造成
  后台读取线程 `UnicodeDecodeError`；新增二进制流回归测试。
- 修复测试门禁：FlaUI 原先错误地等待“主窗口出现”；现改为 `Application.Close(false)` 并
  断言 WPF 进程真实退出，失败时清理由测试启动的进程。WPF xUnit/FlaUI 16/16 通过，
  重建便携包验收 1/1 通过且无 `DocumentWorkbench` / `pythonw` 残留。
- 修复截图证据：FlaUI 的屏幕坐标采集在本机 150% DPI/虚拟显示下会抓到后台 Chrome。验收测试和
  `scripts/win/capture_window.ps1` 现以目标 HWND 的 `PrintWindow` 采集，并使用 Per-Monitor V2
  DPI 上下文；最终截图在
  `output/qa/audit-2.1.0/portable-final-printwindow-20260808121728/shots/`。
- 修复深色主题可读性：`PageTitle`、`SectionTitle`、`FieldLabel` 明确继承 token 化的
  `TextBlock` 样式，避免 WPF 默认黑色文字覆盖深色 `TextBrush`；有 XAML 回归测试保护。
- 已重建本轮 ZIP 和安装程序，逐文件清单、外部 SHA-256 和禁止内容检查通过。最终 ZIP
  SHA-256 为 `2ecf5b4dad419cd46ce6a1bb99ca00fe0422e757d593c2d5f7fc925787c3b537`，安装程序为
  `b10330dac2fe8ccac3e8477a7cc1688797563499f3c8a43acb35b16e20ca87b3`。完整结论见
  `docs/AUDIT_2.1.0.md`；最终哈希以 `dist/*.sha256` 为准。
- 当前检查点：自动化 Windows 11 技术候选通过；**不创建正式发布分支**。等待 Windows 10、
  干净断网环境、真实 NGA、Office 视觉签字和代码签名流程（见 `QUESTIONS.md`）。

## 2026-08-07 NGA CLI 超长 prompt 防御性修复（发布阻断 bug）

- 问题：`_send_cli` 把完整 prompt 作为位置参数传给 `nga run`；Windows
  CreateProcess 命令行上限 32767 字符，deck prompt（约 58 KB）必然触发
  WinError 206，且 CPython 将其映射为 FileNotFoundError，被误报为
  E010「CLI not found」（本机已实测复现，临界约 32740 字符）。
- 修复（`backend/app/generators/nga.py`）：
  - win32 下 spawn 前做最坏情况长度预估（list2cmdline 引号转义上界），超限直接
    抛 E010「prompt exceeds the Windows command-line length limit; use the HTTP
    transport or a smaller input」（不可重试），不再误报；
  - `except FileNotFoundError` 区分 winerror 206（超长）与真实「找不到 CLI」。
  - 非 Windows 不受影响（ARG_MAX 约 2 MB）；auto 模式降级 stub 的既有逻辑不变，
    但 fallback_reason / 错误消息现在是真实原因。
- 测试：`test_nga_generator.py` 新增 3 例（winerror 206 不误报、win32 超限不
  spawn、非 win32 长 prompt 放行）；全量 661 passed，ruff 全绿。
- 待确认：永久修复（stdin/文件传 prompt）取决于内网 `nga run` 是否支持，已记入
  `QUESTIONS.md` 第 7 条。

### 同轮中级项处理（代码审查遗留）

- `NgaCliConfig.validate_cli_path` 放行含空格路径（subprocess list 传参无 shell，
  空格无注入风险；`C:\Program Files\...` 可配置），仍拒绝空白与换行。
- `_preflight_generator_environment` 增加确定性拦截：win32 + CLI 传输 + deck 目标
  在提交时直接 400/E010（DeckIR prompt 必然超 Windows 命令行上限），建议改 HTTP
  传输或 Stub；调用点改为先解析 target 再 preflight。
- 测试：`test_web_api.py` 新增 2 例（win32 deck 拦截、非 win32 deck 放行），
  `test_nga_generator.py` 更新路径校验用例；全量 663 passed，ruff 全绿。
- 附带发现：`generators/codex.py::_generate_cli` 已用 stdin 传 prompt
  （`input=prompt`），证明 stdin 路线在本项目有先例，待内网确认 `nga run`
  是否同样支持。

### 重打包（当前最新分发物）

- WPF xUnit/FlaUI 5/5 通过；Release publish 成功。
- 便携 ZIP sha256 `39e2f8ddb9fb260ba86c840bf6c1789e7ba0f2b3694907eb66f5db959ff1fe2b`
  （105.7 MB / 2199 文件，已抽查 ZIP 内含 nga.py 守卫与 web_api.py preflight 拦截）。
- 安装程序 sha256 `170fb933cd118ac9cfaba4034034d4166c4f754be447977c33cff8441f0911de`
  （91.9 MB）。

## 2026-08-06 Windows 一键脚本入口（scripts/win）

### 已完成并通过静态验证

- 把 WINDOWS_ACCEPTANCE_20260806 清单中的手动命令合并为一键 PowerShell 脚本，
  免去手动复制命令：验证、打包、安装程序、启动工作台四个入口。
- 新增 `scripts/win/`：
  - `verify_all.ps1`：verify.ps1 门禁 + 可靠性测试（可选 `-Ui`）+
    本轮专项（主题/auto 降级/NGA CLI）+ ruff，四步中文分步提示；
  - `build_all.ps1`：WPF xUnit/FlaUI 测试 + Release 构建 + 便携 ZIP，
    可选 `-PythonEmbed` / `-GraphvizRoot` 覆盖默认路径；
  - `package_setup.ps1`：从便携 ZIP 编译 Inno Setup 安装程序，
    可选 `-Zip` / `-Iscc` / `-Overwrite`；
  - `start_workbench_ui.ps1`：一键启动浏览器工作台（转发 start_workbench.ps1）；
  - `README.md`：入口引导（首次准备、日常使用表、典型流程、桌面端提示）。
- 脚本规范：`$ErrorActionPreference="Stop"` + `Set-StrictMode` + UTF-8 环境 +
  三级路径回退到项目根；ruff 不涉及（PowerShell）。
- 验证：四脚本关键字段（错误处理、param、路径回退、Python 定位）静态检查通过；
  沙箱无 PowerShell，实际执行留待 Windows 机器。
- README 与验收清单已补一键脚本指引。

## 2026-08-06 安装程序（Inno Setup，用户目录免提权）

### 已完成并通过设计评审

- 目标：给更多人分发，安装到用户目录免管理员权限；双击安装包 → 桌面/开始菜单
  快捷方式 → 点图标即用。
- 设计：`docs/design/INSTALLER_DESIGN.md`；选型 Inno Setup 6（免提权、成熟、
  内网通用）；保留 ZIP 绿色版，Setup 为正式安装版，二者同源（复用
  `package_document_workbench.py` 产物），不重复打包逻辑。
- 新增：
  - `installer.iss`：`PrivilegesRequired=lowest`（免提权）、
    默认装到 `%LOCALAPPDATA%\Programs\HuaweiDocumentGenerator\<VERSION>`、
    桌面+开始菜单快捷方式、卸载注册到"添加或删除程序"、中文向导、
    卸载不删 `%LOCALAPPDATA%\HuaweiDocumentGenerator`（设置/任务/凭据保留）。
  - `scripts/package_installer.py`：从现有便携 ZIP 解压 → 定位 ISCC.exe →
    编译 → 生成 `HuaweiDocumentGenerator-Setup-<VERSION>.exe` + SHA-256；
    不重复打包逻辑。
- 验证：解压逻辑端到端正确（2198 个文件、exe/backend/python 均在）；
  ISCC 缺失时明确报错且 exit code 非零；ruff 全绿；
  全量回归 649 passed, 1 skipped（7 个环境限制 deselected 与本次无关）。
- 签名暂挂：内网代码签名证书到位前不启用（`SigntoolOptions` 预留）；
  SHA-256 清单照常生成保证可追溯。
- 验收步骤已补入 `docs/WINDOWS_ACCEPTANCE_20260806.md` 第五步附加。

### 降级或近似

- 旧 ZIP（2026-07-30）无 `runtime/graphviz` / `file-hashes.json`，沙箱
  解压验证基于旧产物；实际 Windows 打包会重新生成含这些文件的 ZIP 再编译。
- 沙箱无 Inno Setup，`installer.iss` 实际编译留待 Windows 机器。

## 2026-08-06 open-kimi-ppt 借鉴收尾（留档 + IR 可见化 + 前置检查）

### 已完成并通过验收

- `docs/design/REVIEW_OPEN_KIMI_PPT.md` 留档：五项启发点完整结论——
  命名主题已吸收（上轮）、视觉质检明确不采用（内网无多模态，GLM-5.1 纯文本，
  已有 lint+人工签字替代）、前置检查与 IR 可见化本轮落地、双产物机制评估；
  同时记录"我们的优势不可放弃"（python-pptx 自包含离线 vs 浏览器在线依赖）。
- **IR 可见化（deck-ir 受控下载）**：`deck_ir.json` 加入 `ALLOWED_DOWNLOAD_ASSETS`，
  从敏感清理名单排除，作为任务受控资产保留；前端/WPF 下载区显示
  "结构化内容（DeckIR，可改后重渲染）"链接。安全边界保持：prompt.txt /
  raw_ir.txt / document_ir.json 仍清理，deck-ir 与产物同级别（标题属交付内容）。
- **前置环境检查**：`_preflight_generator_environment` 在任务入队前检查
  NGA-CLI 的 cli_path 存在性（绝对路径 is_file / 命令名 shutil.which），
  缺失返回 E010（stage=preflight），不再等任务跑到 generating 阶段才报错。
- 新增测试 3 个：deck-ir 受控下载（内容含 ir_type/theme、可下载）、
  缺失 CLI 提交前拒绝、可用 CLI 正常放行。
- 全量回归：649 passed, 1 skipped（7 个环境限制 deselected 与本次无关）；
  ruff 全绿。

### 明确不采用

- 多模态视觉质检循环（内网无视觉模型）；结构化 AI 二审列为可选后续。
- 浏览器导出/在线编辑器依赖（违反离线要求）。

## 2026-08-06 命名主题预设（hw-report / hw-proposal / hw-academic）

### 已完成并通过验收

- 借鉴 open-kimi-ppt 的"命名设计系统点名即用"机制：用户一句"用 xxx 主题"就
  套用整套风格，解决"用户说不清风格"的痛点。
- 新增三套主题 JSON（`backend/app/rendering/themes/`）：hw-report（汇报版，
  信息密度高）、hw-proposal（方案版，图文并茂）、hw-academic（学术版，
  深蓝主色严谨克制）；每套含 `style_guide` 风格描述；从 hw_theme.json 派生，
  结构完整一致。
- `theme.py` 新增 `THEME_REGISTRY` + `resolve_theme()` 白名单校验（未知主题
  报 `UnknownThemeError`）。
- 生成链路：`GenerationOptions.theme`（默认 hw_v1）；`generate_deck` 校验后
  **统一覆盖 `meta.theme`**（无论 AI/Stub 生成什么，最终由请求主题决定）；
  `_apply_theme_override` 覆盖单页与分段两条路径。
- 入口：CLI `--theme`（demo_e2e/generate）、API `/api/generate` 表单 `theme`
  字段（白名单校验，非法 E001，word 拒绝）、前端"PPT 主题"下拉框（word 时
  禁用）、WPF 常规设置"默认 PPT 主题"下拉框 + `WorkbenchSettings.DefaultTheme`。
- Prompt 注入：`build_prompt(theme=...)` 在末尾注入 `[主题风格 <name>]` 区块
  （参考 open-kimi-ppt 的 design.md 唯一风格源机制）；hw_v1 不注入，
  原 Prompt 字节零变化（既有快照测试兼容）。
- 测试：新增 `test_theme_presets.py` 14 个用例（三套主题加载/渲染/覆盖/
  注入/白名单/默认不变）。API 端到端确认：非法主题 400 E001、合法主题 202、
  word 带 theme 拒绝；`meta.theme` 覆盖端到端通过。
- 全量回归：646 passed, 1 skipped（7 个环境限制 deselected 与本次无关）；
  ruff 全绿。

### 降级或近似

- Word 保持单主题（用户确认不做 Word 主题预设）。
- 三套主题差异在现有字段内（色板/字号/版式密度/style_guide），未新增结构字段。

### 仍待人工/后续

- 三套主题的视觉验收需在 Windows PowerPoint 目标字体环境下人工确认。
- 沙箱无 Windows 工具链，WPF 编译与 verify.ps1 留待 Windows 机器。

## 2026-08-06 前端体验设计优化（引擎可见性）

### 已完成并通过验收

- 核心洞察：功能已齐（Stub / NGA-CLI / NGA-HTTP + auto/strict），但侧栏
  "当前使用：Stub 生成器"是**写死的**，不随实际状态变化，用户无法知道
  当前用哪个引擎在生成。
- **新增生成引擎指示条**（`engine-bar`，位于"开始生成"按钮正上方）：
  - 动态状态点 + 文案（"生成引擎：NGA（model · 本机命令行 · auto 模式）" /
    "生成引擎：确定性 Stub（未接入 AI）"）；
  - 随设置状态实时联动（4 处设置变更点统一更新）；
  - "更改设置"链接点击展开设置面板并平滑滚动定位。
- 侧栏写死文案改为静态说明（"生成引擎可选三种…当前引擎显示在开始生成上方"）。
- 文案用户化：`解析 → IR → 渲染 → 合规检查` 改为
  `解析 → 生成 → 渲染 → 复检`；"IR 校验未通过"改为"内容草稿未通过校验"；
  侧栏技术描述改为用户语言。
- 验证：HTML 标签配对、JS 括号配对、服务实测 7 项检查全 PASS
  （引擎条元素/联动/侧栏文案/工序文案）；全量回归 633 passed, 1 skipped；
  ruff 全绿。
- 沙箱无 root 无法安装 Chromium 系统库，真实浏览器截图验证留待 Windows
  环境（页面静态与动态逻辑均已通过代码级验证）。

## 2026-08-06 设置界面重排与生成器配置文档

### 已完成并通过验收

- 浏览器设置面板重排（`static/index.html`）：
  - 新增**生成器状态卡**：当前使用 Stub / NGA（本机 CLI / HTTP）+ 模式 + 说明，
    一眼看清当前配置；
  - "调用方式"选项带动态提示（CLI：认证由 NGA 自行管理无需凭据；
    HTTP：需服务地址与 Token）；
  - 字段按需显示 + 必填标记 + 示例占位符（如 `w3/GLM-5.1-WX-Auto`）；
  - auto/strict 模式旁附说明文字（auto 降级会标注、strict 严格失败）。
- `docs/使用说明.md` 新增"生成器配置（AI 接入）"章节：
  三种方式决策表（Stub / NGA 本机命令行 / NGA HTTP）+ 配置入口（WPF/浏览器/
  环境变量）+ auto/strict 说明 + 模型调用方式与输出解析。
- README 增加对配置决策表的指引。
- 验证：HTML 标签配对与 JS 括号配对通过；服务启动后页面正常渲染设置面板；
  全量回归 633 passed, 1 skipped（6 个环境限制 deselected 与本次无关）；
  ruff 全绿。

## 2026-08-06 NGA CLI 传输接入（本机命令行调用）

### 已完成并通过验收

- 目标环境的 NGA 不是 HTTP 服务，而是本机命令行工具：
  `nga run "prompt" -m <model> --format json`，输出 NDJSON 事件流；认证由
  CLI 自管（`nga providers login`，OAuth + DPAPI + 自动刷新），项目无需 Token。
- `backend/app/generators/nga.py` 新增 `NgaCliConfig`（transport=cli）与
  `_send_cli`：subprocess 调用 `nga run --model <model> --format json <prompt>`，
  `_extract_ndjson_text` 解析 NDJSON 事件流（step_start/text/tool_use/step_finish
  四类），拼接 `type=="text"` 事件的 `part.text`。
- cli 模式**免 Token**（认证归 CLI）；http 模式保持原 Token 要求。
  错误映射：CLI 未找到→E010、超时→E012（可重试）、非零退出→E013（可重试）、
  空/非法输出→E014。环境变量：`NGA_TRANSPORT=cli`、`NGA_CLI_PATH`、`NGA_MODEL`。
- `web_api._nga_config_from_payload` 按 `transport` 分派配置模型并过滤 CLI 字段；
  `GeneratorManager` cli 配置无需 credential 即可 test/activate。
- WPF：NGA 面板新增"调用方式"下拉（HTTP/CLI），CLI 时隐藏 HTTP 专属字段并显示
  CLI 路径；`NgaStoredConfig` 新增 `Transport`/`CliPath`。浏览器设置面板同样新增
  调用方式切换 + CLI 路径字段。
- 单元测试 10 个（NDJSON 拼接、命令参数、免 Token、重试、错误映射、环境变量）
  + 设置 API CLI 端到端 1 个；fake NGA CLI 走通
  配置→测试→启用→生成 word.docx 全链路，CLI 失败时 auto 降级回退 Stub
  并标记 `fallback: true`。
- 全量回归：633 passed, 1 skipped（6 个环境限制 deselected 与本次无关）；
  ruff 全绿。

### 仍待人工/后续

- 真实 NGA CLI 在目标电脑上的端到端验证（`nga providers login` 后直接可用）；
  沙箱为 Linux，用 fake CLI 验证了协议与全链路，未验证真实二进制。
- Windows 侧需跑一次完整 `verify.ps1` 门禁。

## 2026-08-06 auto 生成器降级与设置补全

### 已完成并通过验收

- 需求：用户希望在另一台电脑上的使用经验基础上，"默认开 AI，用不了自动降级"。
  设计文档 `docs/design/AUTO_GENERATOR_FALLBACK_DESIGN.md`，核心决策（用户确认）：
  默认 `auto` 模式（NGA 失败自动回退 Stub 并显式标注）、保留 `strict` 可选、
  降级不写进产物本体、Stub 不参与回退链。
- `GeneratorManager` 新增 `GeneratorMode = Literal["auto", "strict"]`（默认 auto）：
  `GeneratorSnapshot` 携带 mode，`configure/activate/status` 均支持 mode，
  draft 与 active 状态返回 mode 字段。
- `web_api`：任务快照/`job_state` 新增 `generator_mode` 与 `generator_fallback`
  字段（job_state schema 同步导出）；`_generate_artifact` 外层编排降级——
  NGA 失败且 auto 模式时改用 Stub 重跑生成链，manifest 记录
  `generator: {requested, used, fallback, fallback_reason}`（稳定错误码）；
  strict 模式维持"失败即失败"；设置 API 接受 `mode` 字段。
- 前端 `static/index.html`：新增 AI 生成设置面板（NGA 地址/接口/模型/Token/
  超时/重试 + auto/strict 开关 + 保存/测试/启用/切回 Stub），Token 仅存内存
  draft 不落盘；任务成功结果展示降级提示"AI 生成器不可用，已自动使用
  确定性生成器完成"。
- WPF：`WorkbenchSettings.GeneratorMode`（默认 "auto"）持久化；
  `ApiModels.GeneratorState` 增加 Mode/Fallback；`WorkbenchApiClient` 与
  `MainWindow` 所有配置调用点透传 mode。
- 新增 `backend/tests/test_auto_fallback.py` 12 个用例：auto 默认、strict 可选、
  设置 API mode 读写、NGA 失败自动回退（word + deck manifest）、job_state 落盘、
  strict 不降级、Stub 无回退标记、Stub 失败不回退、schema 兼容。
- WPF 测试新增 `GeneratorModeDefaultsToAutoAndRoundTrips`。
- 验证：相关测试 99 passed；全量 pytest 621 passed、1 skipped
  （6 个 deselected 为沙箱环境限制：Python 3.10 无 `datetime.UTC`、Windows
  wheelhouse、Node 实验，与本次改动无关）；ruff 全绿。

### 降级或近似

- 浏览器设置面板的 Token 只存后端内存 draft，刷新页面需重新输入
  （WPF 走 Credential Manager 不受影响）；非敏感配置如地址/模型/模式可持久化。
- 降级标注只写 API 响应、job_state 与 manifest 审计，不写进 DOCX/PPTX 本体
  （避免污染交付物）。

### 仍待人工/后续

- 真实 NGA 端点端到端验证（配置→测试→启用→生成→下载）仍在 `QUESTIONS.md`。
- 沙箱为 Linux/Python 3.10，未能执行 Windows `.venv` 的 `verify.ps1` 门禁；
  `job_state` schema 快照已重新导出，Windows 侧需跑一次完整 `verify.ps1`。

## 2026-07-29 实际使用可靠性测试与故障治理

- HTML 技术参考已审计：附件描述的是 `HTML -> html2pptx -> PptxGenJS` 浏览器布局转换，只作为经验参考；生产 PPTX 继续保持 DeckIR 1.9 到 python-pptx，不引入 HTML/PptxGenJS/浏览器渲染。
- 新增异步任务失败契约：`code`、`stage`、`retryable`、`message`、`suggestion`、`support_id`；失败任务生成受控 `failure-report`，状态响应和报告均不泄露异常堆栈、原始 Prompt、输入正文或模型原文预览。
- 修复真实开发路径问题：直接使用仓库 `.venv` 执行 pytest 原先缺少 `PYTHONPATH=backend`；已由 `pytest.ini` 固定。超限上传会清理本次新建的空 job 目录；工作台补充空 favicon，浏览器控制台不再出现 404。
- 新增 `scripts/reliability_test.py`，输出 JSON、JUnit、静态 HTML QA 摘要；默认执行离线 `verify.py` 和全量 pytest，可选 `--ui` 开发浏览器验证或 `--real-model` 显式真实模型冒烟。报告只保存测试名、失败类型和错误码。
- 新增开发专用 Playwright 工作台检查、PowerPoint/Word COM 导图脚本和 Pillow PNG 差异工具；它们不进入生产 lock，也不参与 PPT 渲染。HIT Deck 已由 PowerPoint COM 成功导出 PDF/PNG；自比对通过。
- 开发质量依赖固定为 `ruff==0.16.0`，以 `E9/F` 正确性规则作为现阶段仓库门禁；由此发现并修复了 Word 模式携带 `--template` 时引用未定义 `parser` 的 CLI 崩溃，新增无 traceback 的参数错误回归。
- 当前验收：`verify.ps1` 通过（parsers 93.64%、IR 93.99%、lint 93.89%、整体 89.07%）；`scripts/reliability_test.py --skip-verify --ui` 的 QA 报告为 516 tests、501 passed、0 failed、15 skipped；桌面 1280px 与移动 390px 均无横向溢出和控制台错误。`pip check` 与 ruff 正确性检查通过。
- 仍待人工：真实脱敏 docx/xlsx/pptx 各至少 3 个、真实模型稳定端点验收、固定 Office/字体环境下人工批准视觉 baseline 与最终审美签字。

## 2026-07-11 Analyze-then-generate depth task

- Started with an extensive pre-existing dirty worktree; no unrelated changes will be reverted.
- Restored prior context from repository planning files because the planning skill's session-catchup helper is missing.
- Added phases 23-28 for source inspection, analyze CLI, optional generation depth, long-output handling, real-report acceptance, and completion audit.
- Current phase: inspect authoritative parser/generator/prompt/schema/taskbook behavior and capture default/schema baselines before implementation.
- Parser/generator inspection confirms measured counts and outline data already exist in DocumentIR; no parser changes are needed. The Codex transport and downstream shell can be reused, but analyze requires a non-IR response path that does not weaken or widen any schema.
- Prompt/repair inspection confirms legacy Deck generation is capped at 10 pages and already contains the core Huawei rules. The implementation will preserve the existing prompt byte-for-byte for no-option calls and use a separate opt-in depth/segmentation path for 14-18 page output.
- Taskbook and full DeckIR review confirm all depth requirements fit DeckIR v1.4. No parser, schema, renderer, checker, or linter edit is needed; the established demo is the current generation command surface.
- Captured the no-option baseline hashes for the canonical MD sample and all three schema files. Fresh full regression is green: `311 passed in 79.96s`.
- Added test-first coverage for measured analysis, metric-tamper rejection, analyze-only output, optional depth prompt rules, standard/detailed page counts, explicit page override, and the Codex analysis target. Initial run is correctly red: `8 failed`, all from missing new surfaces; no old assertion failed.
- Analyze phase complete. Targeted suite is green (`29 passed`); the CLI prints measured scale and three tiers, writes only `analysis.json`, and rejects AI-altered metrics through the shared repair/validation path.
- Optional depth prompt and stub generation tests are green (`8 passed`): standard defaults to 11 pages, detailed to 16, explicit pages override the range, and the pre-change legacy prompt hash remains exact.
- Added independent default-equivalence and dirty segmented-generation regressions; the focused depth suite is now `9 passed`. Ruff is green for all changed Python modules/tests.
- Long-output phase complete. Documentation and combined analyze/depth/Codex/repair/docs regression pass (`50 passed`). Next gate is full pytest/verify, then the real technical-report analyze + standard/detailed Codex runs and readable PDF exports.
- Full regression and verify are green (`322 passed`; overall coverage 87.34%). Default prompt/raw and all schema hashes are unchanged. The real report and conversion tools are present; starting real Codex analyze/standard/detailed acceptance.
- Real analyze and standard Deck succeeded. First detailed Deck is structurally valid but fails the semantic-depth gate because nested-section evidence was omitted by focused-context selection; adding a red regression before correcting subtree selection and regenerating.

## 2026-07-10 P0 gap closure

- Started from the verified baseline recorded immediately before this task: `220 passed`; `scripts/verify.py` passed with parsers 92.56%, IR 92.68%, lint 91.99%, overall 89.27%.
- The worktree already contains extensive prior user/task changes. They must be preserved; only targeted P0 edits will be added.
- `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` has 34 P0 atomic rows, but several are aggregate acceptance rows. Implementation is organized around five root workstreams: contract gates, CLI failures, prompt/stub flow, parser robustness, and lint scope.
- Captured immutable canonical schema baselines before editing: Word 1.0 `88cf3a...e9a9`, Document 1.0 `915a98...9604`, Deck 1.4 `d8683d...277`.
- Contract batch decision: separate schema verification from explicit export, add version/hash history, and evolve DocumentIR 1.0 to 1.1 for format/content and preview-bound enforcement.
- Contract batch complete: DocumentIR 1.1, positive/negative samples, schema history/version gate, and read-only verify behavior are implemented. Targeted result: `97 passed`; three schema snapshots independently verified.
- CLI failure batch complete. Shared coded JSON boundary covers arguments and I/O; corrupt/missing Office checks write structured reports. Targeted result: `34 passed`; no traceback in negative subprocess cases.
- Prompt/stub content batch complete. Independent parse runs now produce byte-identical prompts; sample-backed few-shot and `est_chars` are present; four-format stub outputs carry a source fact. Targeted result: `17 passed`.
- Parser robustness batch complete. Targeted parser result: `44 passed`; actual >10MB/30,000-row worksheet is parsed under the 5-second test limit with bounded previews/scans.
- PPTX lint scope batch complete. Expanded lint result: `45 passed`; renderer/sample result: `16 passed`; representative rendered layouts have no new warnings.
- P0 closure complete: `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` has 34/34 P0 rows marked ✅ with implementation/test evidence; `docs/history/2026-07/TASKBOOK_COMPLIANCE.md` was independently recounted as 106 satisfied, 22 partial, 13 unmet, with 25 remaining [A] items all belonging to P1/P2.
- Final independent test: `271 passed in 188.84s`. Final verify: parsers 92.90%, IR 93.30%, lint 92.80%, overall 89.50%; four-format semantic E2E and C0 pass.
- Schema verification is green for WordIR 1.0, DocumentIR 1.1, and DeckIR 1.4; ruff is green. No P0 was moved to [B].

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `progress.md` did not exist when restoring planning-with-files context | 1 | Created it for the current P0 task; retained the existing uppercase `PROGRESS.md` as the project-facing historical log. |
| Contract-targeted suite rejected a 30-row DocumentIR table used as a nominal prompt fixture | 1 | The new 20-row Schema limit worked as intended; changed the valid fixture to the 20-row boundary while retaining long-paragraph truncation coverage. |
| Ruff found two unused `sys` imports after CLI error output moved to the shared helper | 1 | Removed the imports; no behavior change. |
| Prompt truncation test parsed through the newly inserted `est_chars` line | 1 | Updated the test to delimit DocumentIR JSON at the explicit `[字符估算]` section; generator extraction already uses `JSONDecoder.raw_decode`. |
| Picture-background contrast test was treated as white because a transparent text box reports `BACKGROUND` fill | 1 | Made `BACKGROUND` defer to picture-overlap detection; transparent text over a picture now yields explicit HW-W09 manual-review warning. |
| Targeted renderer command referenced nonexistent `backend/tests/test_visual_samples.py` | 1 | Located current test files with `rg --files`; reran against `test_pptx_renderer.py` and `test_ir_sample_matrix.py` only. |
| Ruff found missing `pytest` import in the new direct stub edge-case test | 1 | Added the explicit test dependency import before rerunning. |
| First parse double-failure refactor referenced `args.output` inside a helper that only receives `output` | 1 | Caught by immediate source inspection before tests; replaced with the helper parameter. |

## 2026-07-10 P0 independent-review remediation

- Started from `docs/history/2026-07/P0_REVIEW.md`: 23/34 satisfied, 11/34 partial, with seven root defects and four dependent aggregate rows.
- Baseline from the independent review: `271 passed`; verify parsers 92.90%, IR 93.30%, lint 92.80%, overall 89.50%.
- Worktree remains heavily dirty from earlier requested work; all remediation will be narrowly scoped and preserve unrelated changes.
- Phase 12 started: reproduce each review finding with a regression test before changing implementation.
- Persistence audit complete: DocumentIR has no database history, but multiple supported workflows intentionally write `document_ir.json`; compatibility migration is required.
- Verify design decision: delete the externally spoofable recursion flag by removing recursive full-verify invocation from pytest and replacing it with direct positive/negative gate tests.
- Parser design decision: use a killable worker only for large XLSX packages, plus OOXML drawing inspection for per-image geometry.
- Added test-first regressions for coordinated W06 metadata drift, renderer W07 edge placement, full DocumentIR+Prompt reproducibility, marker-only semantic loss, DocumentIR 1.0 migration, verify environment/coverage bypasses, XLSX image geometry, and a killable XLSX hard deadline. Implementation has not yet been changed; the next run is expected red.
- Test-first targeted run produced the expected red state: `13 failed, 84 passed`. Every failure maps to one planned root defect; no unrelated regression appeared.
- Compatibility/time/verify batch is green (`6 passed`): v1.0 reads migrate to v1.1 with a warning, repeated DocumentIR and Prompt bytes match, and an externally preset recursion flag no longer bypasses test failure.
- First multi-fact E2E run caught a real XLSX loss that the old marker missed: the second sheet's `指标/值` header was absent from DeckIR. Stub sheet fact extraction is being expanded before rerunning.
- Multi-fact E2E remediation is green (`5 passed`): marker-only output fails; md/docx/xlsx/pptx each pass through both Word and Deck, and every extracted fact is present in generated IR and the final editable artifact. XLSX with 24 facts stays within the 12-slide cap by omitting the nonessential cards page.
- Actual PPTX geometry remediation is green (`62 passed` across lint, renderer, and IR sample tests). The coordinated metadata spoof and renderer edge-placement regressions now fail correctly; full rendered samples remain free of W06/W07.
- XLSX image geometry and hard-deadline remediation is green. The parser records sheet/anchor/width/height/part/bytes, isolates >=10MB packages, terminates timed-out workers, and preserves structured worker errors.
- A new EOF worker-cleanup issue was found while raising branch coverage and fixed before closure; EOF now yields E001 and unconditional process cleanup.
- DocumentIR 1.0 compatibility is implemented because supported workflows persist `document_ir.json`; migration is in-memory, warning-bearing, and still enforces all 1.1 constraints. Usage documentation and tests describe the no-auto-overwrite boundary.
- `VERIFY_RUNNING` bypass is removed. Direct positive main testing plus external-env failure and low-coverage negatives replace the recursive verify test.
- `docs/history/2026-07/P0_REVIEW.md` and `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` now record 34/34 P0 rows as independently satisfied with current file/test evidence.
- Final full pytest: `288 passed in 31.30s`. Final verify: parsers 93.30%, IR 93.37%, lint 92.88%, overall 89.58%; four-format multi-fact E2E and C0 pass. Schema snapshots/history and ruff are green; no skip/xfail.

## 2026-07-11 analyze first, then depth-controlled generation

- Added an independent, non-IR analysis recommendation structure and `scripts/analyze.py`. The real CAST report result at `output/codex_depth_analysis/analysis.json` reports 62 titles, depth 4, 19 tables, and about 74,123 characters, recommending detailed 14-18 pages.
- Added opt-in `--pages` / `--depth` generation. No options retain the legacy branch byte-for-byte; standard defaults to 11 pages and detailed to 16 only after the new options are explicitly supplied.
- Detailed generation uses an outline plus four-page chunks, shared shell/schema validation, and the existing repair path. The real 16-page run completed in four chunks without truncation; regressions force truncated outline D001 and wrong chunk count D006 through repair.
- Real outputs are `output/codex_depth_standard/` (11 pages) and `output/codex_depth_detailed_v2/` (16 pages). Detailed pages include concrete CNN sample/accuracy evidence, CNN-LSTM architecture and 1000 km/NMSE evidence, WFRFT conditions, and sample-rate/throughput figures.
- Readable Chinese WPS/Noto PDF previews are `output/codex_depth_standard/deck_preview.pdf` and `output/codex_depth_detailed_v2/deck_preview.pdf`.
- Final independent checks: `323 passed in 19.61s`; `scripts/verify.py` passed with parsers 93.75%, IR 93.44%, lint 94.01%, overall 87.46%; focused completion checks `6 passed`; ruff and `git diff --check` green.
- Word/Document/Deck schema SHA-256 hashes are unchanged from the pre-feature baseline. This feature made no task-specific change to IR fields or parse/render/check/lint core behavior.

## 2026-07-11 macOS Chinese-font preview

- Installed user-level Noto Sans CJK SC Regular/Bold solely for local preview. A font-substituted PPTX copy was generated under `output/codex_cli_real_deck_10slides/font_preview_noto/`; no source code, IR, or theme token changed.
- macOS LibreOffice continued to rasterize Chinese as missing glyphs even after the explicit font substitution, so it is not suitable as this host's visual-preview tool.
- WPS Office opened the existing 10-slide deck with correct Chinese fallback and exported a verified 10-page PDF. The copied preview is `output/codex_cli_real_deck_10slides/font_preview_noto/wps/deck_wps_preview.pdf`; sampled pages 1, 5, 6, 8, and 10 contain readable Chinese with no black-background or box-glyph issue.

## 2026-07-10 Temporary CodexGenerator upper-bound validation

- Added the isolated `backend/app/generators/codex.py` adapter. It calls OpenAI-compatible Responses API only through `OPENAI_API_KEY`, defaults to `gpt-5.6-terra` unless `OPENAI_MODEL` overrides it, supports custom `OPENAI_BASE_URL`, and never writes credentials or API response diagnostics containing secrets.
- The existing `shell.py` extraction, target-schema validation, error-code mapping, and `repair_ir_text()` two-retry loop remain the only validation path. `scripts/demo_e2e.py --generator codex` now uses that same path; parse/render/check/lint and both target schemas were not changed.
- Added eight non-network tests for request construction, deck prompting rules, key/API failure redaction, repair-loop reuse, explicit `codex` selection, environment selection, default stub behavior, and structured no-key CLI failure.
- Current verification: `308 passed in 15.88s`; schema snapshots are unchanged and `git diff --check` is green. `python scripts/verify.py` passed: parsers 93.75%, IR 93.37%, lint 94.01%, overall 89.52%.
- The user authorized a temporary OpenAI-compatible upper-bound run through a custom Responses endpoint. The key remains process-only and must be rotated afterward because it was supplied in chat.
- Initial runtime network audit: the Python installation had no default CA file, so HTTPS first failed before reaching the API. A process-only `SSL_CERT_FILE` pointing at the already-installed certifi bundle reached the official endpoint but returned HTTP 401 before model dispatch; the later custom-provider run below is the authoritative live validation.
- Live custom-provider validation: the configured OpenAI-compatible `/models` endpoint returned HTTP 200 when reached with a process-only certificate bundle. A minimal WordIR request returned valid JSON and passed the existing schema shell without repair.
- Public DOCX Word run: the source parsed to 859 blocks (62 headings, 778 paragraphs, 19 tables) with 102 parser warnings. The real model's initial WordIR directly passed validation (no repair), produced 24 blocks (13 headings, 9 paragraphs, 1 bullet list, 1 table), rendered to `output/codex_real_word/word.docx`, and its DOCX lint report was `pass=true` with no items.
- Honest visual boundary: the macOS LibreOffice preview has missing Chinese glyphs and a black second-page rendering anomaly, so the generated DOCX is structurally verified but not visually accepted on this host. Windows with the required font stack remains the required visual gate.
- Public DOCX Deck run: no real-model PPTX was produced. Under the requested `gpt-5.6-terra + xhigh + responses` configuration, the full DeckIR request exceeded the 300-second timeout, while reduced and minimal DeckIR requests each returned upstream HTTP 502. This was mapped to `D001`; no stub fallback was presented as a real-model result. Provider recovery or an approved model/API-mode change is required before retrying.
- DeckIR retry: a separate rerun against the same public DOCX and requested configuration again failed immediately with upstream HTTP 502 (`output/codex_real_deck_retry/run.log`). The local parser completed and the prompt was produced; no incomplete IR or PPTX artifact was kept.
- `gpt-5.5` retry: changing only `OPENAI_MODEL` to `gpt-5.5` also returned upstream HTTP 502 for the public DOCX DeckIR request. A minimal WordIR probe failed with the same result, so this is currently a provider routing/model-availability failure rather than a DeckIR-specific issue.
- CCSwitch validation: the imported 百事可乐 provider was initially not active; it was activated in CCSwitch, which wrote `model=gpt-5.5`, `model_provider=custom`, and the configured Responses endpoint to the Codex config. CCSwitch correctly required a new client session.
- A new `codex exec` session through that CCSwitch configuration returned a minimal expected response, then generated both target IRs from the public DOCX. DeckIR was 1,555 characters, directly schema-valid, and rendered to a 6-slide PPTX (cover, agenda, title_bullets, architecture_diagram, cards, conclusion); its lint report had 0 Error, HW-W09 Warning, and HW-I01 Info. WordIR was 2,241 characters, directly schema-valid, and rendered to a 27-block DOCX (12 headings, 11 paragraphs, 1 list, 1 table, 2 image placeholders); its lint report had no items.
- This is a real successful model-to-IR-to-render validation through CCSwitch, but it uses the Codex CLI's authenticated custom-provider route rather than the project's API-key-based `CodexGenerator` HTTP adapter. No source implementation or IR contract was changed for this fallback test. macOS LibreOffice previews still lack the required Chinese font and show black/box-glyph rendering, so they are not visual acceptance evidence.
- Final generator integration: `CodexGenerator` now has an explicit `CODEX_GENERATOR_TRANSPORT=cli` option for already-authenticated CCSwitch/Codex CLI routes. It keeps `http` as the default, runs `codex exec --ephemeral --ignore-rules -s read-only`, uses UTF-8 subprocess I/O, writes the final message only inside a temporary directory, avoids logs/credentials in errors, and preserves the active CCSwitch model unless `OPENAI_MODEL` is explicit. Tests cover invocation, explicit-model handling, failure redaction, and the existing repair loop.
- Final real E2E through `scripts/demo_e2e.py --generator codex`: Word output at `output/codex_cli_real_word/word.docx` came from a directly valid 33-block WordIR (14 headings, 15 paragraphs, 1 list, 2 tables, 1 image placeholder) and its DOCX lint report is clean. Deck output at `output/codex_cli_real_deck_10slides/deck.pptx` came from a directly valid 10-slide DeckIR (cover, agenda, section, 2 title-bullets pages, table, architecture diagram, cards, two-column, conclusion); its lint report has 0 Error, HW-W09 Warning, and HW-I01 Info. Both have PDF previews.
- Final regression: `311 passed in 16.56s`; `python scripts/verify.py` passed (parsers 93.75%, IR 93.37%, lint 94.01%, overall 89.40%). All three schema snapshots match their exported schemas (Word SHA-256 `fa45ae66...`, Document `7bb8fe73...`, Deck `469643c3...`); ruff and `git diff --check` are green.

## 2026-07-10 P1 delivery asset closure

- Started after confirming all 18 P1 rows remain open and `samples/expected/` has no files.
- No pytest/verify/demo/Office conversion process survived the interrupted turn.
- Scope is asset-only: fixed fixtures, manifests, expected JSON, review records, docs, demo evidence, and tests. Core app behavior and IR contracts will not be changed.
- Planned batches: fixed samples/expected/invalid assets; Windows dependency hashes and review records; docs/demo screenshots; full verification and 18-row evidence update.
- Added deterministic asset builders for Appendix B Office files, parser category matrix, structural expected JSON, sample outputs, Deck D001-D006 fixtures, lint violation injection, Windows wheel hashes, and cross-platform demo evidence.
- Generated 24 core delivery assets plus three official DOCX outputs, full Deck output, lint violation PPTX/report, 20 parser-category fixtures, and 8-page Appendix B PPTX expected.
- Downloaded 26 real CPython 3.12/win_amd64 wheels (17 MB local ignored wheelhouse), wrote `requirements-win312.lock` and SHA-256 manifest, and verified the complete lock with pip `--dry-run --require-hashes`.
- Generated real command logs and 1600x900 success/failure screenshots; visual inspection confirmed readable Chinese and visible return codes/D003.
- Added delivery/review/task-card docs and synchronized README, usage, intranet, acceptance, style, and Appendix A.2.
- Asset/docs targeted verification: `16 passed`.
- P1 independent verification complete: `300 passed in 95.29s`; `python scripts/verify.py` passed with four-format semantic E2E and C0. Coverage: parsers 93.75%, IR 93.37%, lint 92.88%, overall 89.66%. Schema snapshot verification, ruff, and `git diff --check` are green.

## 2026-07-11 analyze/depth generation completion

- Real analyze result is persisted at `output/codex_depth_analysis/analysis.json`: 62 titles, 4-level structure, 19 tables, about 74,123 characters; detailed 14-18 pages is recommended.
- Real standard output is 11 pages in `output/codex_depth_standard/`; real detailed output is 16 pages in `output/codex_depth_detailed_v2/` and was assembled from four validated chunks with no real truncation or repair event.
- The corrected detailed Deck contains concrete method/data evidence rather than additional headings: 40 to 72+ samples and 90.84% to 95.59%; 4-layer CNN plus two 256-unit LSTM layers, 20,000 data groups, 1000 km and NMSE -10 dB; WFRFT order/step/SIR conditions; 245.76/61.44 MHz processing parameters and 1.047 Gbps throughput.
- WPS/Noto Chinese PDF previews are final at `output/codex_depth_standard/deck_preview.pdf` (11 pages) and `output/codex_depth_detailed_v2/deck_preview.pdf` (16 pages). Visual samples contain readable Chinese and no converter black background.
- Final verification: `323 passed in 19.61s`; `scripts/verify.py` passed with parsers 93.75%, IR 93.44%, lint 94.01%, overall 87.46%; focused default/schema/truncation checks `6 passed`; ruff and `git diff --check` green.
- Three schema hashes exactly match the feature baseline. No task-specific edit touched an IR field or parse/render/check/lint core behavior; the legacy no-option prompt/raw/DeckIR remain byte-identical.
- XLSX image geometry and hard-deadline remediation is green. The parser records sheet/anchor/width/height/part/bytes, isolates >=10MB packages, terminates timed-out workers, and preserves structured worker errors.
- A new EOF worker-cleanup issue was found while raising branch coverage and fixed before closure; EOF now yields E001 and unconditional process cleanup.
- DocumentIR 1.0 compatibility is implemented because supported workflows persist `document_ir.json`; migration is in-memory, warning-bearing, and still enforces all 1.1 constraints. Usage documentation and tests describe the no-auto-overwrite boundary.
- `VERIFY_RUNNING` bypass is removed. Direct positive main testing plus external-env failure and low-coverage negatives replace the recursive verify test.
- `docs/history/2026-07/P0_REVIEW.md` and `docs/history/2026-07/TASKBOOK_GAP_PLAN.md` now record 34/34 P0 rows as independently satisfied with current file/test evidence.
- Final full pytest: `288 passed in 31.30s`. Final verify: parsers 93.30%, IR 93.37%, lint 92.88%, overall 89.58%; four-format multi-fact E2E and C0 pass. Schema snapshots/history and ruff are green; no skip/xfail.

## 2026-07-20 Composite 组合页版式

- 从提交 `fb0cd24` 的干净基线开始；设计报告为 `docs/design/COMPOSITE_LAYOUT_DESIGN.md`。
- 用户确认首版仅嵌入 table / architecture_diagram / title_bullets / cards；process_flow 暂缓但保留后续扩展。
- 先补回归测试，初始红灯为 `8 failed, 2 passed`，失败均来自尚未实现的 DeckIR 1.7 / composite。
- DeckIR 已升到 1.7，1.4 / 1.5 / 1.6 可在内存迁移；CompositeRegion 复用四种既有 slide model，非法 table / architecture / bullets / cards 会递归返回原 D003-D006。
- 左右区域由主题 12 栏网格定义为 5 栏 + 1 栏间距 + 6 栏；表格、Graphviz 架构、要点、卡片复用原绘制函数，旧整页调用默认参数不变。
- 嵌入架构图超过 12 条边的真实 PPTX 仍由现有 lint 报 `HW-W03`，未新增 composite lint 豁免。
- 过程错误：planning-with-files 要求的 `progress.md` 在 macOS 大小写不敏感文件系统上指向了本文件，曾短暂覆盖历史内容；已从 HEAD 完整恢复后追加本节。
- 最终全量测试 `411 passed in 30.14s`；`verify.py` 通过，覆盖率 parsers 93.75%、IR 93.83%、lint 94.44%、overall 88.72%；ruff 与 schema 快照均通过。
- 试点产物为 `output/composite_layout_review/deck_composite_table_architecture.pptx`，中文 WPS PDF 为 `output/deck_composite_table_architecture_wps_preview.pdf`；视觉检查无重叠、裁切或标签压节点。

## 2026-07-20 Composite v1.8 栏内堆叠

- DeckIR 从 1.7 升至 1.8：`CompositeRegion.component` 演进为 `components[1..3]`；1.4/1.5/1.6/1.7 在内存深拷贝迁移到 1.8，1.7 的单 component 自动包为单元素列表，原输入对象不会被修改。
- 单元素 components 继续走 v1.7 整栏渲染路径；回读测试比较 v1.7 与等价 v1.8 的原生 PPTX shape 名称、文本和几何，结果一致。
- 多块区域按主题 token 从上到下堆叠：表格使用主题行高、要点使用最大正文候选字号测量、卡片使用原有卡片高度、架构图以 Graphviz 实际包围盒测量；累计超出栏高时，lint 从透明块边界的真实几何输出 `HW-W03`，不缩到不可读、不截断、不自动拆页。
- 递归 lint 已覆盖：堆叠内 13 条边 architecture_diagram 仍报既有密度 `HW-W03`；三块累计超高时新增 `组合页该栏内容过多` `HW-W03`。table、要点和 KPI 的原有产物规则继续通过原 lint 路径执行。
- 视觉样例为 `samples/ir/deck_valid_11_composite_stacked.json`，产物 `output/composite_stacked_venus_review/deck_composite_stacked_venus.pptx`，中文 PDF `output/composite_stacked_venus_review/deck_composite_stacked_venus.pdf`。左栏表格、架构图、要点顺序清楚且无重叠/裁切；该混合密度页仍有 1 条真实 `HW-W01`（全页 7 种字号超过主题上限 3 种），未做豁免。
- 相关回归 `268 passed`，全量 pytest 在新增 v1.8 兼容几何测试前为 `417 passed`；最终门禁待本轮结束时再次运行。

## 2026-07-20 Architecture diagram v1.9 语义配色

- DeckIR 升至 1.9：ArchitectureNode.type 改为非空、可扩展字符串；主题注册 primary/secondary/emphasis/data/job/module，未知 type 不猜测业务含义，回退到 theme default 色。
- 既有色值保持不变：primary 青、secondary 黄、emphasis 红、data 绿；新增 job 黄、module 绿。renderer 与 lint 都从 `layouts.architecture_diagram.node_type_colors` 读取同一映射，不保留硬编码配色表。
- 试点样例 `samples/ir/deck_valid_12_architecture_semantic_colors.json` 已生成原生可编辑 PPTX 和中文 PDF：`output/architecture_semantic_colors_review/deck_architecture_semantic_colors.pdf`。视觉检查确认 Job/未知 type 为黄，module/data 为绿，Graphviz 关系和标签清楚；CLI lint 为 0 Error / 0 Warning。
- 回归覆盖注册 type 与未知 default 填色、主题色 lint、已有架构与 composite/堆叠样例。最终全量 pytest、verify、ruff、Schema 快照待本轮结束时再次运行。

## 2026-07-29 Windows、模板驱动 PPT 与图表质量升级

### 已完成并通过阶段验收

- Windows 基线固定为仓库 `.venv` / Python 3.12.10；依赖闭包加入 `colorama==0.4.6`，28 个 Windows wheel 的 lock、manifest 与 SHA-256 已更新，离线 `pip --dry-run --require-hashes` 成功。
- 新增 `bootstrap_windows.ps1`、强化 `verify.ps1`，并生成 `output/environment_report.json`；Graphviz 优先本地 `tools\graphviz\bin\dot.exe`，其次系统 `dot.exe`，当前系统 Graphviz 15.1.0 的版本和 SHA-256 已记录。
- DeckIR 保持 1.9；新增严格的 `TemplateProfile 1.0`、`TemplatePlan 1.0`、独立 JSON Schema、原型评分、Pillow 字体测量、运行时容量回退、W201/W202 与模板感知 lint。
- 模板包限制覆盖 50 MB 压缩、500 MB 解包、200 页、5000 形状、路径穿越、宏、ActiveX、OLE、外部关系、XML/Content Types/关系目标和 XML 关系反向引用。
- 模板 renderer 复用 master/layout/theme，安全复制内部图片；不复制 transition、timing、notes、comments、外部超链接、chart/OLE/embedding；表格、图表和图形重绘保持原生可编辑。
- CLI、`scripts/generate.py`、`demo_e2e.py`、异步 Flask API 和工作台均支持可选 `.pptx`；Word 明确拒绝模板；下载资产固定为 output/lint/profile/plan/package-report。
- 图表实现了零轴、正/负/混合/全负范围、折线窄区间、1/2/2.5/5 漂亮刻度、字面量单位格式、长类目旋转/skip、折线 marker、饼图类别百分比及 HW-W10/W11/W12；Prompt 已加入图表选择规则。
- HIT 32 页真实模板生成 14 页验收 Deck。修复了模板 tags 关系被剥离后遗留空 `<p:tags/>` 导致 PowerPoint 拒绝打开的问题；PowerPoint 16 已成功打开并导出 14 页 PDF/PNG。自动结果为 0 Error、0 HW-W03、无 `XXXX`、每页密级完整、包关系通过。

### 降级或近似

- 14 页官方样例中 5 页使用安全原型替换，9 页因版式不支持或运行时容量不足使用同 master/layout/theme 下的 `master_redraw`，均记录 W201；缺失字体按字体聚合为 3 条 W202。
- HIT 联系表证明 PowerPoint 可打开、页面非空且无明显裁切，但该官方 IR 是版式边界样例，部分页面信息量较低，不代表真实业务内容质量。

### 阻塞待人输入

- 真实脱敏 docx/xlsx/pptx 各至少 3 个仍需业务侧提供；详见 `QUESTIONS.md`。
- PowerPoint 自动导出不替代最终审美签字；HIT 联系表位于 `output/hit_template_acceptance/powerpoint_visual_20260729/contact_sheet.png`。

### 仍不确定

- 当前系统已完成联网 Windows 环境的 wheelhouse dry-run，但“全新干净 Windows + 物理断网”的安装记录仍属于交付流程证据，不冒充为已完成。
- 最终 `verify.ps1` 已通过:四格式 word/deck stub E2E 全绿,覆盖率 parsers 93.64%、IR 93.99%、lint 93.89%、整体 89.04%,输出 `C0 verify passed`。联合模板/API/图表/renderer/lint/文档回归为 `179 passed`。
- 工作台已启动于 5056 并完成浏览器验收:1280px 桌面和 390px 窄屏均无横向溢出、文本裁切或控件重叠,控制台无 error/warning。

## 2026-07-29 PPT 双引擎融合与自主决策

### 已完成并通过验收

- 生产默认仍是 `DeckIR 1.9 -> python-pptx`；DeckIR、生产 API、工作台和 Windows 离线依赖闭包均未引入 Node、浏览器或 PptxGenJS。
- 模板输出新增 `template_structure.json`、`template_structure.md` 与 `template_replacement_audit.json`；受控下载和工作台均展示 structure/replacement-audit。审计只记录形状 ID、替换动作、哈希和检查状态，不记录正文或 Prompt。
- 模板感知 lint 以 Profile 的字体、色板和正文安全区为准；它只排除已归档的装饰形状，继续检查密级、动画、字号、溢出、业务对象重叠和页码。边界序列化的 4 EMU 容差防止精确安全线被误报。
- `scripts/template_inspect.py` 可独立运行并自行设置 `backend` 导入路径；新增 PNG 联系表、Office PDF/PNG 导出、视觉差异和 `manual_pending` 状态。
- 新建隔离的 `experiments/html2pptx/`。它只接收 Schema 已验证的 DeckIR，固定映射 HTML 后用 Playwright 测量，再由 PptxGenJS 生成可编辑对象；Node 25.2.1、PptxGenJS 4.0.1、Playwright 1.62.0、Sharp 0.35.3 均不属于生产依赖。
- 最终 HIT 源模板对照集位于 `output/html2pptx-final-office/`。Python 对三个固定样例均通过 Schema、包关系、lint、无 HW-W03/HW-W07、Office 打开和原生文本/表格/图表门禁；HTML 无模板样例可继续实验，但模板样例明确 `native_editability=false`，因此 `engine_assessment.json` 的推荐为 `keep_python`，没有自动切换生产。
- Office 已成功导出两套引擎共六份 PPTX 的 PDF/PNG 联系表；所有视觉状态为 `manual_pending`，没有人工基线时没有伪装成通过。
- 最终回归：`510 passed, 15 skipped`；可靠性门禁含工作台 UI 为 `525` 测试、`510` 通过、`15` 跳过；ruff 和 `git diff --check` 通过；`verify.ps1` C0 通过，parsers 93.75%、IR 93.99%、lint 94.24%、整体 89.25%。

### 阻塞待人输入

- 真实脱敏业务语料和最终 PowerPoint 审美签字仍按 `QUESTIONS.md` 执行。HTML 对照结论不会替代此人工门禁，也不会更改生产架构。

## 2026-07-29 PPT 图生成与视觉制作能力升级

### 已完成并通过验收

- DeckIR 已按契约先行升级并冻结为 2.0；1.4-1.9 仅在校验入口深拷贝迁移，不覆盖用户原文件。Schema、正反样例、迁移器、快照和 v2 样例矩阵均已通过。
- 新增独立 `AssetManifest 1.0` / `AssetUsageAudit 1.0`：PNG/JPEG/WebP 完整解码、EXIF 方向修正、元数据移除、SHA-256、去重、白名单/Office media 提取、20 MB/40MP/20 张/100 MB 限制及 A001-A006 已落地。合法 `image_ref` 嵌入真图，缺失引用以 A005 阻断，不再静默占位。
- 图片渲染支持 contain/cover、焦点、caption/credit/alt、`image_text` 和 2-4 图 `image_grid`；模板替换审计记录资产哈希、图片槽、fit/crop/focal 与回退原因。
- 新增 funnel/quadrant/cycle/matrix 原生可编辑信息图和 24 个企业语义 AutoShape 图标；architecture/process/timeline 保持原生 shape、文本框与 connector。
- 图表增加 scatter、combo、主次轴元数据、轴标题、显式数字格式、数据来源/口径/备注；新增 HW-W13-W16，且不合并、删除、排序或改写业务数据。
- 新增 `VisualPlan 1.0` / `VisualSelectionAudit 1.0` 和默认禁用的 `ImageProvider`。生成链路、CLI、API、工作台均输出并提供受控下载；模型仍只能产出通过 DeckIR Schema 的 JSON。
- API/工作台支持重复 `asset_files`、多图移除、Word 隔离、normalizing_assets/planning_visuals 阶段和资产/视觉审计下载。浏览器实测发现并修复同步 API 错误 payload 被前端降级为 E001 的问题；损坏模板现在正确显示 E003。
- 全量 pytest 为 `539 passed, 15 skipped`；可靠性报告 `output/qa/report.json` 为 554 项、539 通过、15 跳过、0 失败。`scripts/verify.py` 通过，覆盖率 parsers 93.75%、IR 93.82%、lint 94.26%、整体 88.72%；`verify.ps1` 通过，覆盖率 parsers 93.75%、IR 93.82%、lint 94.34%、整体 89.30%。ruff 与 `git diff --check` 全绿。
- 当前工作台已由仓库 `.venv` 启动于 `http://127.0.0.1:5056/static/index.html`。真实浏览器完成带图片 Deck 成功流和损坏模板失败流；图片资产清单、使用审计、VisualPlan、选择审计均可下载。默认 1265px 与 390px 视口无横向溢出、控件越界或文本裁切，控制台无 error/warning。

### 降级或近似

- combo 以两张对齐的 PowerPoint 原生图表实现：主轴 bar 与次轴 line 分别可编辑，不是单一 OOXML combo chart 对象，也没有把页面栅格化。
- 24 个语义图标是主题一致的基础 AutoShape 组合，不是复杂插画库。默认 `DisabledImageProvider` 保持离线生产边界，AI 生图未作为可用生产能力。
- Graphviz 在正式 `verify.ps1` 中检测到系统 `dot.exe`；未注入 PATH 的独立 pytest 子进程会发出确定性 fallback warning，但测试和输出不会失败。

### 阻塞待人输入

- 真实脱敏 docx/xlsx/pptx 和有明确版权/署名/替代文本的真实图片语料仍需业务侧提供，详见 `QUESTIONS.md`。
- PowerPoint 自动打开、lint、联系表和像素检查不替代目标字体环境下的最终内容与视觉签字。

### 仍不确定

- combo 的主次轴在当前自动结构回读中通过，但仍需用真实双量纲业务数据在目标 PowerPoint 版本中确认往返保存后的右轴语义和人工可读性。
- 当前 wheelhouse dry-run 与 Windows 本机门禁通过；全新干净 Windows 物理断网安装记录仍需按交付流程补证据，不能由本机结果替代。

### 2026-07-29 OLE 模板错误治理

- 实际模板触发 `E003: ppt/embeddings/oleobject1.bin`。确认这是既定安全门禁，而非 renderer 崩溃；OLE、宏、ActiveX 和外部关系继续禁止执行或复制。
- 包校验现在反查 `.rels`，把嵌入部件定位到具体幻灯片；同步 API 错误返回 `loc=template_file`、`retryable=false` 和“删除嵌入对象或转 PNG”的处理建议，工作台显示定位信息，不再提示稍后重试。
- 新增关系定位、API 结构化建议和前端定位文本回归，专项 `3 passed`；最终全量 pytest 为 `540 passed, 15 skipped`，ruff 与 `git diff --check` 通过。
- `verify.ps1` 完整通过：四格式 word/deck stub 链路全绿，覆盖率 parsers 93.75%、IR 93.82%、lint 94.34%、整体 89.32%，输出 `C0 verify passed`。
- 开发专用浏览器回归新增真实 OLE 上传拒绝场景；1280px 桌面与 390px 窄屏均确认显示 E003、`template_file`、引用页码和删除/转 PNG 建议，且不显示不存在的失败报告。报告位于 `output/qa/workbench-ui-ole/workbench_ui_report.json`。
- 清理了 5056 端口残留的旧工作台父子进程并以仓库 `.venv` 重启；实时 multipart 请求已确认当前服务返回第 1 页定位、`retryable=false` 和可执行建议，而非旧版笼统错误。

## 2026-07-29 上线前发布加固终验

### 已完成并通过验收

- Office 包预检修复了 ZIP 纯目录项 `ppt/embeddings/` 被误判为危险嵌入的问题。扫描器只忽略以 `/` 结尾的目录记录；未归属 `ppt/embeddings/*.xlsx`、任何 `.bin`、OLE、宏、ActiveX 和外部关系仍保持阻断，只有图表内部 `/package` 关系明确拥有的 `.xlsx` 可通过并接受嵌套 OOXML 安全检查。
- 界面文档回归已对齐当前 `start_workbench.ps1`、5056 端口和稳定失败字段，不再断言废弃的 5055 同步启动命令。包安全、文档和 HTML 对照专项 `18 passed`；HTML 无模板样例恢复为 `expand_html_experiment`，生产默认仍为 `python-pptx`。
- 最终全量 pytest 为 `573 passed, 15 skipped`，0 失败；Ruff 全绿，`git diff --check` 无空白错误。29 个 Windows CPython 3.12 依赖 wheel 通过 `--no-index --find-links wheelhouse --require-hashes --dry-run`。
- `verify.ps1` 完整通过：四格式 Word/Deck stub 链路全绿，Graphviz 使用 `C:\Program Files\Graphviz\bin\dot.exe`；覆盖率 parsers 93.51%、IR 93.82%、lint 94.34%、整体 89.10%，输出 `C0 verify passed`。
- 统一可靠性门禁位于 `output/qa/release-final/`：共 588 项，573 通过、15 跳过、0 失败；offline_verify、pytest、workbench_ui 三个 gate 均通过。浏览器在 1280x900 与 390x844 两个视口通过，无失败用例。

### 降级或近似

- 无本轮新增功能降级。普通 pytest 未注入 Graphviz PATH 时仍会记录确定性 fallback warning；正式 Windows 验收已识别并使用系统 Graphviz，不影响产物与门禁。

### 阻塞待人输入

- 真实脱敏业务语料、授权真实图片、PowerPoint 最终审美签字和全新 Windows 物理断网安装证据仍按 `QUESTIONS.md` 执行；自动绿色结果不替代这四项人工交付证据。

### 仍不确定

- 自动化范围内未发现未解决的软件失败。真实业务内容语义、目标字体环境审美及干净内网机器安装结果只能由后续人工验收确认。

## 2026-07-30 Windows 原生 EXE 与 NGA 配置

### 已完成并通过验收

- 从交付基线 `a99f4bf` 创建 `codex/windows-native-app`。新增 .NET 8 WPF 原生客户端，未使用 WebView2、Electron、PySide6 或第三方 UI 框架；生成、任务、设置、诊断、关于及 NGA 二级设置页已落地。
- 新增 `NgaHttpConfig 1.0`、OpenAI-compatible Chat Completions adapter、`GeneratorManager`、配置测试/激活 API、E010-E014、任务 generator 名称/修订快照和桌面会话鉴权。启用 NGA 后配置失败阻断，不回退 Stub。
- NGA Token 只由 WPF 写入 Windows Credential Manager `HuaweiDocumentGenerator/NGA`；非敏感配置位于 `%LOCALAPPDATA%\HuaweiDocumentGenerator\settings.json`。任务状态、失败报告、API 响应和便携包不包含凭据。
- 桌面宿主使用 Waitress 绑定 `127.0.0.1` 随机端口；一次性 bootstrap 由当前 Windows 用户 ACL 保护，后端读取即删。后端状态文件不含会话密钥，父进程退出后看门狗停止服务。
- 便携构建脚本锁定 .NET SDK 8.0.423、CPython embeddable 3.12.10 和 Graphviz 15.1.0，输出运行时清单、第三方许可、逐文件 SHA-256 与 ZIP SHA-256；生产包排除 xUnit/FlaUI/Playwright、缓存、设置、凭据和任务。
- 修复 Windows 异常退出生命周期：`OpenProcess` 能打开“已退出但句柄仍被测试框架持有”的进程，旧探测会误判为存活并留下 pythonw。当前同时使用 `GetExitCodeProcess == STILL_ACTIVE` 判定，并增加真实 Windows 进程句柄回归；WPF 测试后确认无遗留 `app.desktop_host`。
- 最新验证：`verify.ps1` 通过，Graphviz 使用 `C:\Program Files\Graphviz\bin\dot.exe`；覆盖率 parsers 93.51%、IR 93.82%、lint 94.34%、整体 88.82%。可靠性报告 `output/qa/windows-native-final/report.json` 为 613 项、598 通过、15 跳过、0 失败；1280x900 与 390x844 浏览器工作台均通过。WPF build 为 0 warning/0 error，xUnit/FlaUI 3/3 通过。

### 降级或近似

- NGA 首版仅支持 OpenAI-compatible、非流式 Chat Completions；自定义协议需新增 adapter。真实 NGA 未配置时默认 Stub，明确启用后不允许降级。
- WPF 自动化覆盖原生启动、导航、键盘可达和设置持久化；完整模板/图片/取消/恢复/审计下载已由后端与浏览器回归覆盖，并在本机 WPF Stub PPT 实跑通过。干净机器上的完整原生交互仍属于人工便携验收。

### 阻塞待人输入

- 真实 NGA 地址、模型、Token、证书链和实际响应兼容性冒烟；内网代码签名证书；干净物理断网 Windows 10/11 x64 便携包验收；真实脱敏业务语料、授权图片和 PowerPoint 最终审美签字，均见 `QUESTIONS.md`。

### 仍不确定

- 自动测试无法证明目标内网网关完全兼容 OpenAI Chat Completions，也不能替代企业签名策略、目标机安全软件兼容性和 Office 最终审美结论。

## 2026-08-01 仓库治理与分阶段架构重构

### 已完成并通过验收

- 在 `codex/repository-cleanup-20260731` 分支实施；基线提交为 `c9e000e99c30d1f680a0f5574296be0a51e02c1a`。迁移备份为 `dist/huawei_document_generator_windows_dev_20260731.zip`，SHA-256 为 `9aece8fcd42bfb555a21e26130238cdffb45080a280c08c292dacb09c9389245`。
- 新增 `REPO_AUDIT.md`、`ARCHITECTURE.md`、`REFACTOR_PLAN.md`、`docs/GIT_WORKFLOW.md` 和 `docs/GENERATION.md`；当前运行文档统一归入 `docs/`，设计记录归入 `docs/design/`，历史审计归入 `docs/history/2026-07/`。
- 删除无正式引用且已有替代实现的旧同步 Web、placeholder renderer、synthetic passing lint、空 storage 包和对应旧测试；删除由 Git 历史可恢复、已被当前文档替代的状态快照与周报。
- `scripts/demo_e2e.py` 现在始终执行真实 PPT lint；`--lint` 仅作为隐藏兼容参数保留。CLI Word/PPT 分支已拆分，API 的路由装配、请求处理、任务失败映射和产物上下文已按职责分解，未修改公共路由、IR、错误码或输出格式。
- 仓库治理特征测试锁定正式 `web_api` 入口、IR 唯一契约、HTML 实验隔离、文档归档位置和旧 Web 不得恢复。
- 全量 Python 回归为 `595 passed, 15 skipped`。`scripts/verify.py` 通过，覆盖率 parsers 93.51%、IR 93.82%、lint 94.30%、整体 88.95%；`verify.ps1` 通过，Graphviz 使用系统 `dot.exe`，整体覆盖率 89.17%。
- 可靠性报告 `output/qa/report.json` 共 610 项：595 通过、15 跳过、0 失败；JSON、JUnit 与静态 HTML 报告均已生成。
- WPF 使用锁定 .NET SDK 8.0.423 完成 Release 构建，0 warning/0 error；xUnit/FlaUI 3/3 通过。Ruff、`git diff --check`、删除入口残留扫描和敏感配置扫描均通过。

### 降级或近似

- `pptx_renderer.py`、`pptx_lint.py` 和 WPF `MainWindow.xaml.cs` 仍偏大。本轮没有为减少行数而切割高风险 Office/视觉逻辑；继续拆分须先补稳定的 Office 视觉 golden 与往返保存基线，已列为 R7 独立后续任务。
- Composio 未配置且本次未获得外部 issue/PR 权限，因此按 `codebase-migrate` 的本地小批次、逐批测试与回滚原则执行，没有创建远程事项。

### 阻塞待人输入

- 真实脱敏业务语料、授权图片、PowerPoint 最终视觉签字、全新 Windows 物理断网验收、真实 NGA 配置及正式代码签名仍按 `QUESTIONS.md` 执行，自动测试不能替代。
- 本地存在多个 `backup-*` 分支且没有 release tag；需人工确认保留策略后再归档或删除。Codex checkpoint refs 有宿主工具级损坏警告，本轮没有直接编辑 `.git`。

### 仍不确定

- 自动化范围内未发现重构引入的行为回归。目标内网 NGA 协议差异、终端安全软件对便携 EXE 的影响及 Office 最终审美，只能在交付环境继续确认。

## 2026-08-01 唯一正式版本整合

### 已完成并通过验收

- 从干净提交 `fd0317f` 创建 `codex/consolidate-latest-20260801`，并建立保护标签
  `pre-version-consolidation-20260801`。没有 reset、force push、远程分支删除或用户修改丢失。
- 逐分支验证 17 个旧分支全部是当前正式候选的祖先，独有提交均为 0；当前提交
  `30426e53907bee115fc2773206c4609252784384` 比它们多 1-16 个提交，因此没有遗漏的
  `FEATURE_DONOR` 需要 cherry-pick。
- `VERSION_CONSOLIDATION_AUDIT.md` 已记录候选矩阵、证据评分、调用关系和处理状态；
  `VERSION_CONSOLIDATION_REPORT.md` 已记录合并、替换、恢复方式、唯一正式入口和未决事项。
- 产品版本从 Python API、打包器、WPF csproj、XAML 和 User-Agent 多处硬编码收敛到根
  `VERSION`。便携 backend 会携带该文件；WPF Assembly 为 2.1.0.0，Python/API 为 2.1.0。
- README 明确 WPF 主入口、唯一 Flask API、分阶段 CLI、统一 verify、WPF 打包入口以及
  HTML/PptxGenJS 实验边界。本仓库没有训练或推理入口。
- 早期 `docs/HUMAN_REVIEW.md` 已替换为当前 DeckIR 2.0、AssetManifest、NGA、WPF、模板
  安全和 `manual_pending` 人工门禁；旧内容只通过 Git 历史恢复。
- 全量 Python 为 `601 passed, 15 skipped`。`scripts/verify.py` 通过，整体覆盖率 88.95%；
  `verify.ps1` 通过，Graphviz 使用系统运行时，整体覆盖率 89.17%。
- 可靠性报告共 616 项：601 通过、15 跳过、0 失败。WPF Debug xUnit/FlaUI 3/3；Release
  build 0 warning、0 error。Ruff、diff、含糊路径、旧入口和生产实验引用扫描均通过。

### 降级或近似

- HTML/PptxGenJS 保留为 `experiments/html2pptx/` 对照实验，不是待合并的第二生产版本。
- 浏览器工作台保留为同一 Flask API 的兼容客户端，WPF 是主用户入口；二者不是两套业务后端。

### 阻塞待人输入

- 12 个 `backup-*` 本地分支均已合并且无独有提交，但是否删除仍需确认人工备份用途。
- 正式 release tag 仍需等待代码签名、干净 Windows 断网验收和 PowerPoint 人工视觉签字。
- 真实业务语料、授权图片和真实 NGA 继续按 `QUESTIONS.md` 与 `docs/HUMAN_REVIEW.md` 执行。

### 仍不确定

- 损坏的 Codex checkpoint ref 会让 Git geometric repack 和部分全局枚举报错；当前提交有效、
  工作树与分支正常，但该宿主工具引用需要由其所有者处理，本轮未直接编辑 `.git`。

## 2026-08-06 Windows 真机执行 + 前端审美改版

### 已完成并通过验收

- **Windows 真机任务 1（代码级验证）全绿**：`verify_all.ps1` —— C0 门禁通过、
  覆盖率 app/parsers=93.51%、ir=93.94%、lint=94.30%、overall=89.29%，专项 49 passed，
  ruff 全绿。QA 报告 `output/qa/report.json`。
- **Windows 真机任务 2（WPF 编译 + 便携 ZIP）通过**：xUnit 4/4；Release 构建成功；
  `dist/document-workbench-windows-x64-2.1.0.zip`（105.7 MB）+ sha256。
- **前端审美改版**：`backend/app/static/index.html` 全量重设计，色板对齐
  `docs/风格规范.md` 与 `rendering/themes/*.json`；胶囊分段控件、自定义下拉箭头、
  红色聚焦环、`:focus-visible`、`prefers-reduced-motion`、PPT 主题色板联动（学术版切蓝色系）。
  所有 `data-testid` 与 JS 契约保留，`test_web_api_static` 通过；截图留档 `output/ui-redesign/`。
- **修复接力书未记录的坑**：全部 `.ps1` 原为 UTF-8 无 BOM，Windows PowerShell 5.1 按 GBK
  解析直接 ParserError；已补 BOM 并记入 `TASK_HANDOFF.md` 快速定位章节。

### 阻塞待人输入

- 任务 3（安装程序编译）：Inno Setup 6 未安装，需人工安装后跑 `scripts/win/package_setup.ps1 -Overwrite`。
- 任务 4-8（工作台功能验收、NGA 接入、视觉签字、QUESTIONS 待办）仍为人工项，见 `TASK_HANDOFF.md`。

## 2026-08-06 双端设计 Token 统一

### 已完成并通过验收

- 新建 `docs/design/FRONTEND_TOKENS.md`：Web/WPF 界面 token 单一事实源（颜色/形状/动效/字体 +
  有意的平台差异说明），规则为"改实现前先改表"。
- 修正 WPF 色板 7 项（`MainWindow.xaml` 资源块）：主红 `#C7002B→#C7000B`、深红、墨色、次要文字、
  边框、画布、焦点色蓝→红；`scripts/build_desktop_icon.py` 同步修正并重建 `app-icon.ico`。
- 回归：`scripts/test_workbench_ui.py` 全 pass（desktop/mobile 双视口）、`test_web_api_static` 通过、
  WPF xUnit 4/4、Release 0 警告 0 错误；WPF 实机启动截屏确认新色板生效。
  截图留档 `output/frontend-unification/`。

### 仍不确定

- WPF 视觉细节（圆角、胶囊徽章、悬停态）尚未向 Web 对齐——计划方案 B，留待任务 7 人工验收时定夺。

## 2026-08-06 专业办公效率风格增强

- Web：圆角档位收紧（卡片 6px / 控件 4px）、主标题改半粗、分析指标数字 tabular-nums、按钮 36px 密度。
- WPF：清除 3 个离调色板硬编码色（导航选中标记 `#F23D61`、导航焦点 `#8FB4FF`、子导航选中底 `#FDECEF`），
  新增 `AccentPressedBrush #8C0008`（主按钮按压态）与 `AccentOnDarkBrush #F85948`（深导航上的红色强调）。
- `docs/design/FRONTEND_TOKENS.md` 同步新增 token；全仓 grep 无离板色残留。
- 验证：WPF Release 0 警告 + xUnit 4/4；Web 静态测试 + UI 回归双视口全 pass；双端实机截图复核
  （`output/frontend-unification/web-desktop-v2.png`、`wpf-screen-v2.png`）。

## 2026-08-06 稳定性收尾 + 交付重打包

### 已完成并通过验收

- **修复 2 个 Web 设置面板真 bug**（`backend/app/static/index.html`）：
  ① CLI 模式下"保存配置/测试连接"被错误要求 `base_url`，永远无法通过——接力书任务 5（NGA 接入）
  会被此卡死；已改为按传输方式校验（CLI 仅需模型名）。② Stub 激活时加载页面不应用字段显隐，
  HTTP 专用字段在 CLI 模式下全部误显示。两项均经真实服务器 + Playwright E2E 验证（5 断言）。
- **回归覆盖**：`scripts/test_workbench_ui.py` 新增 CLI 设置流程检查（显隐 + 双模式校验提示）。
- **全量自测全绿**：verify_all 四步——C0 门禁（E2E 8 链路、覆盖率 89.29%）、可靠性 657 passed / 0 failed、
  专项 49 passed、ruff 全绿；UI 回归 desktop/mobile 全 pass；WPF xUnit 4/4、Release 0 警告 0 错误。
- **交付重打包**：`dist/document-workbench-windows-x64-2.1.0.zip`（105.7 MB，2199 文件），
  新 sha256 `64a4c353d4fd44663f8b12489c52cb6392f8b816e2cc591401cca511f0230cfb`；
  已抽查 ZIP 内 `index.html` 含本次 bug 修复与主题色板联动。

### 降级或近似

- 全量 pytest 在 Graphviz 不在 PATH 的裸 shell 下有 15 个无害线程告警（确定性回退按设计生效）；
  verify 环境（Graphviz 在 PATH）无此告警。

### 阻塞待人输入

- 5056 端口有两个 8/6 23:09 残留的 `app.web_api` 进程（PID 9388/11232），执行任务 4 前需结束。
- 安装程序编译仍需 Inno Setup 6（人工安装）。

## 2026-08-06 任务 3 解除阻塞：安装程序已编译

- 清理 5056 端口残留 `app.web_api` 进程（PID 9388/11232，8/6 23:09 遗留），端口已释放。
- 静默安装 Inno Setup 6.7.3（GitHub 官方发布包，Authenticode 验签 Valid / Pyrsys B.V.）；
  补装简体中文语言包 `ChineseSimplified.isl`（jrsoftware 官方翻译库，issrc main 分支）。
- `package_setup.ps1 -Overwrite` 通过：`dist/HuaweiDocumentGenerator-Setup-2.1.0.exe`（91.8 MB）
  + sha256 `6671199c3828716ba6bbecc1d958806f300d6de4bd0abce0c1e353518a1b197f`，源为最新便携 ZIP。
- 至此任务 0-3 全部完成；剩余任务 4-8 为人工验收项（工作台功能、NGA 接入、视觉签字、WPF/安装程序验收、QUESTIONS 待办）。

## 2026-08-07 Web UI 视觉验收（AI 代行，用户委托）

- Playwright + Chrome 实机渲染 12 张全状态截图逐张审阅（`output/visual-review/`，
  工具 `scripts/visual_review_shots.py`，开发专用、不进交付物）。
- **修复 2 项真实视觉缺陷**（均在 `backend/app/static/index.html`）：
  ① 文件已选行被 `.dropzone` 的 `place-items:center` 穿透（Chromium block 布局
  justify-items 新特性）导致内容居中、删除按钮不靠右——`.dropzone.is-file` 补
  `place-items: normal`；② 移动端（≤620px）AI 生成设置双列网格截字——该断点下
  `.generator-settings__grid` 收为单列。
- 回归：`test_web_api_static` 通过；`test_workbench_ui` 双视口 pass；ruff 全绿。
- 签字结论：`output/ui-visual-signoff.txt`（通过）。
- 边界：TASK_HANDOFF 任务 6（三套 PPT 主题视觉签字）需 PowerPoint + 华为字体环境，
  本机无渲染条件，仍为人工待办；任务 7（WPF/安装程序双击验收）同为人工。
- 因 index.html 有修复，已重跑 build_all + package_setup 刷新 dist 交付物：
  ZIP sha256 `643a3a80a2a840d1e530f86c0b6e8cfb6d6f61d984dbe6cc953bd807798de7be`
  （105.7 MB / 2199 文件，已抽查含两处修复）；
  安装程序 sha256 `22a837050707f6cdfd04a919362884d432a827057bed1d54eb5bd966d5874fa2`（91.8 MB）。
  WPF xUnit 4/4、Release 构建随 build_all 复验通过。

## 2026-08-07 任务 6/7 代行验收（用户委托 AI 按人工标准执行）

### 任务 6：三套 PPT 主题视觉签字 —— 通过

- 本机有 PowerPoint 16.0 + 微软雅黑/Arial（主题白名单字体），满足"PowerPoint + 目标字体环境"。
- 同一源文档（samples/input/项目汇报.pptx）Stub 生成三主题各 11 页，COM 实机导出 33 张 PNG 逐页审阅。
- **修复 3 项缺陷**：
  ① hw-academic 学术蓝不生效（渲染器锚点统一取 `colors.hw_red`，主题仅覆盖 accent1/hlink，
  学术版与汇报版曾逐像素一致）→ `hw-academic.json` 的 hw_red 改为 #1F4E79；
  ② `check_pptx(theme_name=)` 四处调用点（web_api×2、cli/render、demo_e2e）未透传主题，
  非默认主题误报 HW-W02 → 全部透传 `deck.meta.theme`，`cli/check.py` 新增 `--theme`，
  `test_theme_presets.py` 新增回归 `test_named_theme_lint_uses_own_palette`；
  ③ hw-proposal 行距 10.08pt 破坏 8pt 基线（HW-W06×5）→ 0.111111in；
  卡片 tag 灰底灰字对比度 4.23:1（HW-W09，三主题共性）→ tag 色 token secondary→body。
- 修复后三主题 lint 全 0 误 0 警；全量后端 643 passed / 0 failed。
- 签字：`output/theme-visual-signoff.txt`；证据：`output/theme-visual-signoff/*/png + contact.png`。
- 工具留档：`scripts/win/export_deck_png.ps1`（PowerPoint COM 导 PNG，纯 ASCII 无 BOM 陷阱）。

### 任务 7：WPF + 安装程序验收 —— 通过

- 新增 `desktop/DocumentWorkbench.Tests/PortableAcceptanceTests.cs`（FlaUI 走查，
  `DOCUMENT_WORKBENCH_EXE` 缺省时跳过；新增 System.Drawing.Common 8.0.10 引用用于截图）。
- 便携包 exe 与"已安装实例"各跑一遍走查：断言全过，截图 `output/desktop-qa/*-shots/`。
- 安装程序：中文向导真实走完 → `%LOCALAPPDATA%\Programs\HuaweiDocumentGenerator\2.1.0\`
  → 桌面/开始菜单图标 → 完成页自动启动 → `unins000.exe /VERYSILENT` exit 0
  → 目录/图标清除、`settings.json` 卸载前后 md5 一致。
- 记录：`output/desktop-qa/installer-acceptance.txt`（含证据瑕疵如实说明）。
- 工具留档：`scripts/win/capture_window.ps1`、`scripts/win/capture_installer_wizard.ps1`。
- 注意：Git Bash 直调 unins000.exe 静默卸载会挂起（子进程分离），须用 PowerShell
  `Start-Process -Wait` 调用。

### 任务 6 修复后重打包（最终分发物）

- 便携 ZIP sha256 `59412d85e0ee722e2773765fa672622a98ce371ac85d691deafd66084143593e`
  （105.7 MB / 2199 文件，已抽查含学术蓝锚点与 lint 主题透传修复）。
- 安装程序 sha256 `387899fc42f39031a7b35cfd50bbdcc0877ab46ae8d844ffa072fc0121c67273`（91.8 MB）。
- build_all 随包复验：xUnit 全过、Release 0 警告 0 错误。

### 边界（仍需人工）

- 任务 4（工作台 Web UI 功能走查）可由 `.\scripts\win\start_workbench_ui.ps1` 人工或后续会话执行；
- 任务 5（NGA 真机接入）需内网凭据；任务 8（QUESTIONS.md 长期待办）需人工收集真实语料。

## 2026-08-07 AI Arena 交互模式吸收 + 双主题（用户委托实施）

- **双主题**：WPF 调色板抽为 `Themes/Palette.Dark.xaml` / `Palette.Light.xaml`（合并字典 +
  样式全部 DynamicResource），"设置 > 常规 > 外观"即时切换并持久化 `settings.json: appearance`；
  浅色模式侧导航保持深色签名。Web 端 `:root[data-theme="light"]` 变量覆盖 + 顶栏切换按钮
  （localStorage 持久化），截图验证两色均正常。
- **简洁/高级渐进披露**：生成页默认只留输入资料/输出类型/深度/分析/生成；
  模板、图片资产、输出主题（新增任务级 `GenerateThemeComboBox`，仍走 hw_v1 等既有值）
  收进"高级选项"折叠面板（DisclosureToggle，键盘可操作）。不改任务请求格式。
- **任务面板**：阶段链可视化为 10 段 Run（排队→…→校验包结构，对应 StageLabels），
  当前阶段红色加粗、已完成灰色、未开始淡色；进度区加生成器快照；结果页分块为
  主产物 / 合规与审计 / 下一步（含重新提交）。
- **修复的真实缺陷**：设置页"默认输出类型/默认 PPT 深度"启动不回显（ApplySettingsToControls
  补两项预选）；UIA 程序化 Toggle 不触发 Click → 高级面板改挂 Checked/Unchecked 事件。
- **测试**：`PortableAcceptanceTests` 扩展（高级面板显隐断言、浅色切换截图、1024×700 与
  宽屏截图）；xUnit 5/5；后端 658 passed 无回归；ruff 全绿；UI 回归 pass。
- **留档**：`output/desktop-qa/arena-shots/`（8 张实机截图）、`output/visual-review-dual/`。
- 注：本机 150% DPI 实测覆盖；100%/200% DPI 与 1366×768 物理分辨率留人工复核项。
- **已重打包（当前最新分发物）**：ZIP sha256 `0a6d0411d41c48a48147a60df60a048ed042c147b27a45e341978064fc2b36a2`；
  安装程序 sha256 `55070608157d1a9c79181b98a9c9124990b250bfc44cc11234d244acfa9da38f`。
  含架构图渲染改造 + 深色/浅色双主题 + AI Arena 交互吸收全部改动。

## 2026-08-14 模板上传预检与晚期生成失败修复

### 已完成并通过验收

- 根因确认：用户模板 `商务汇报.pptx` 的
  `ppt/slideLayouts/_rels/slideLayout12.xml.rels:rId2` 含外部超链接关系；该关系继续按
  `E003` 安全规则拒绝，未放宽 Office 包安全校验。
- 新增 `POST /api/templates/validate`：复用生成链路的模板上传和包校验逻辑，在临时
  `analysis-*` 工作区完成检查并始终清理，不创建任务、不保留用户模板。
- 浏览器工作台和 WPF 在选择模板后立即显示校验状态；无效或尚未完成校验的模板只禁用 PPT
  生成，不影响“分析资料”。生成前还会按文件大小和修改时间重新检查，后端保留最终权威校验。
- 外部关系提示按关系类型显示为 `(hyperlink)`，不暴露外链目标；界面给出 PowerPoint
  “视图 → 幻灯片母版 → 移除超链接 → 另存为”的可执行处理路径。
- 回归通过：`dotnet test desktop/DocumentWorkbench.Tests/DocumentWorkbench.Tests.csproj -c Release --no-restore`
  为 22/22；`python scripts/verify.py` 通过（parsers 91.96%、ir 94.06%、lint 94.26%、
  overall 88.78%）；`scripts/test_workbench_ui.py` 在 desktop/mobile 视口均通过。

### 使用边界

- 含外部关系的原模板不能直接用于生成；用户可移除母版中的外部超链接后重新选择，或移除模板
  使用默认主题。该限制是安全策略，不能通过 UI 或渲染器绕过。

## 2026-08-14 外部超链接模板安全副本

### 已完成并通过验收

- 新增 `sanitize_template_hyperlinks()`：先以 source 级 Office 安全检查扫描模板，只移除
  `TargetMode=External` 且关系类型为 `hyperlink` 的关系及其 XML 引用；原模板不会被修改，
  输出副本会再次经过 `validate_template_package()` 权威校验。
- 新增 `POST /api/templates/sanitize`：只在内存中返回已校验的 `.pptx` 副本，临时
  `analysis-*` 工作区始终清理；浏览器下载后要求重新选择副本，WPF 通过保存对话框写入副本后
  自动切换并复检。
- 浏览器与 WPF 仅在预检确认 `E003 (hyperlink)` 时显示“生成安全副本”；布局在移动端会换行，
  保持按钮可达和文本不溢出。
- 对用户真实模板 `商务汇报.pptx` 已生成不覆盖原件的
  `C:\\Users\\GSQ\\Desktop\\商务汇报_安全副本.pptx`：移除 18 个外部超链接，模板校验通过；
  python-pptx 与模板画像链路均成功读取 22 页。
- 回归通过：`pytest backend/tests/test_template_rendering.py backend/tests/test_web_api.py -q`
  为 80 passed；WPF xUnit 23/23；`scripts/test_workbench_ui.py` desktop/mobile 均通过；
  `python scripts/verify.py` 通过（parsers 91.96%、ir 94.06%、lint 94.26%、overall 88.68%）；
  ruff 与 `git diff --check` 通过。

### 使用边界

- 自动安全副本只适用于外部超链接。任何宏、OLE/ActiveX、嵌入图表数据中的外部关系或非 hyperlink
  外部关系仍会被 `E003` 拒绝，必须由模板提供方人工处理，不能通过转换器绕过。

## 2026-08-26 实习答辩 PPT 交付

### 已完成并通过验收

- 基于 `PPT模板-浅色版16-9.pptx` 生成 19 页答辩 PPTX，并导出 19 页 PDF 备份；
  所有页面均保留华为 logo、`HUAWEI CONFIDENTIAL`、版权与页码。
- 使用原生 PowerPoint 形状、连接线和表格重建架构图、流程图、卡片与对比表；19 页均写入纯讲稿备注。
- `check.py`：0 Error / 0 Warning / 0 Info；`slides_test.py`：无溢出；模板忠实度检查：0 issue。
- PowerPoint COM 实机渲染 19/19 页，PDF 经 Poppler 栅格化逐页检查，无裁切、重叠、黑块或缺页。
- 模板 6 个 theme part 与源模板逐字节一致；包内 0 外部关系、0 视频媒体、0 页面切换、0 元素动画；
  四种禁用说法与备注噪声词均为 0 命中。
- 交付物：`output/实习答辩PPT_华为浅色版_19页.pptx`、
  `output/pdf/实习答辩PPT_华为浅色版_19页.pdf`、
  `output/实习答辩PPT_交付报告与人工替换清单.md`。

### 降级、待人输入与边界

- 未发现已注册的 `template_v2` / `huawei-project-report`，按指令将页 4、页 9 的“10 套”降级为可核实的“8 套”。
- 页 1 个人信息、页 9 模板墙截图、页 12 `demo.mp4`、页 13 两项端到端实测值仍需答辩人替换；未伪造数据或媒体。
- 当前机器已用 PowerPoint 2024 做视觉终检；答辩电脑仍需人工确认现场字体、视频编码、投影比例和最终华为风格观感。

### 2026-08-26 通用业务版（未使用 academic-pptx）

- 仅使用通用 `presentations` 工作流，在同一华为模板和已核验内容上另做
  `output/实习答辩PPT_通用业务版_19页.pptx`；未调用 `academic-pptx` 或学术答辩优化技能。
- 视觉改为扁平业务汇报：去除大部分卡片底色/边框，保留必要原生流程图，强化红色证据条，
  第 19 页重构为三列编号式总结；19 页备注、占位和“8 套”诚实降级保持不变。
- 验证：`check.py` 0 Error / 0 Warning / 0 Info；无溢出；模板忠实度 0 issue；
  逐页全尺寸渲染检查通过；6 个 theme part 与源模板一致；19 页/19 备注；
  0 外部关系、0 页面切换、0 元素动画、四种禁用说法 0 命中。

## 2026-08-26 实习答辩 PPT（项目工程汇报版，不使用 academic-pptx）

### 已完成并通过验收

- 按用户要求未使用 `academic-pptx`，仅沿用通用演示文稿工作流；依据答辩稿重组为 19 页项目工程复盘，直接复用所给浅色模板的封面、母版、Logo、密级、版权与页码体系。
- 叙事围绕“输入解析 → DeckIR 契约 → 确定性渲染 → 合规校验 → Demo 验证”展开；明确程序仅为 Demo/原型，不包装为产品发布，不填写未实测的耗时、成功率或采用率。
- 图表与图示按答辩稿和仓库可核验证据制作：原生可编辑柱图展示 17 种布局、4 套主题、20 条规则、77 个冻结引擎文件，并标注 16,323 LOC、后端占比 69.5%；架构图、流程图、表格、卡片均保持可编辑。
- 19 页逐页渲染检查通过；`slides_test.py` 无溢出；模板忠实度检查 0 issue；项目合规检查为 Pass（0 Error、6 Warning、1 Info）。
- 包结构审计：19 slides、19 notes、19 个 `[Sources]` 来源块；0 外部关系、0 页面切换、0 元素动画、0 默认占位提示；6/6 theme part 与源模板同名文件哈希一致。
- 交付物：`C:\\Users\\GSQ\\Downloads\\实习答辩PPT_项目工程汇报版_非academic-pptx_20260826.pptx`。

### 降级、待人输入与边界

- 合规 Warning 集中在第 9/12/13 页的字号层级、网格最小间距与原生柱图坐标轴声明；均未造成溢出或结构错误，终稿判定通过。
- 封面个人信息仍需答辩人填写；“华为模板源码存在”不等于已注册进 Demo 运行库，现场展示前仍需完成注册与实测。
- 当前完成程序化渲染与逐页视觉检查；正式答辩电脑仍需人工确认 Office 字体、投影比例及现场播放效果。

## 2026-08-26 实习答辩 PPT（项目 DeckIR 2.2 引擎版）

### 已完成并通过验收

- 按 `docs/taskbook.md` 的唯一主链路，用项目自身
  `DeckIR 2.2 → Schema 校验 → python-pptx 渲染 → PPTX lint` 生成 19 页答辩稿；
  IR、PPTX、19 页演讲备注和双格式 lint 报告统一放在
  `output/defense-deck-20260826/`。
- 叙事采用 19 个结论式动作标题，完成“痛点 → 任务判断 → 分层架构 → IR 契约 →
  人机协同 → 内网 Skill → 合规与交接 → 边界与总结”的幽灵稿检查。
- 对设计稿中的旧数字重新按仓库实测口径校正：Skill 引擎冻结 77 个文件，当前 ZIP
  239,663 bytes（约 234 KiB），Skill Python 13,657 行 / 主项目后端 20,760 行，
  占 65.8%；未继续使用旧稿中的 16,323 行 / 69.5%。
- 最终 PPTX 含 19 slides、19 notes；项目 lint 为 0 Error / 0 Warning / 0 Info；
  PowerPoint 实机成功导出 19 张 1600×900 PNG，并对总览及架构、流程、表格、占位和总结页
  做全尺寸视觉检查，未发现裁切、遮挡或不可读连线。
- `python scripts/verify.py` 全量通过：四格式 word/deck stub E2E 全绿；覆盖率
  parsers 91.96%、ir 94.06%、lint 94.23%、overall 88.99%。

### 降级或近似

- 页 9 模板墙和页 12 演示视频缺少真实媒体，按契约使用 `image.placeholder`；可见文字已改为
  面向评委的“8 套已注册内置模板 / 支持导入自有 PPTX”和“实机演示视频 / 100 秒 / 本地文件”，
  替换操作仅保留在演讲备注中。
- 架构图使用仓库便携包自带 Graphviz 自动布局；流程、表格、卡片、连接线和文本均为原生
  PowerPoint 对象，可继续编辑。

### 阻塞待人输入

- 封面姓名、部门、导师和结论页联系方式仍为明确占位，需要答辩人填写。
- 页 9 需替换真实模板墙截图；页 12 需插入脱敏的本地 100 秒演示视频并准备静态截图备份。

### 仍不确定

- 设计稿涉及的 Web 工作台功能口径来自用户材料，本次只做本地仓库事实复核，未启动另一套
  Web 平台逐项做在线功能验收。
- 当前 Windows + PowerPoint 环境视觉检查已通过；正式答辩电脑的投影比例、视频编码、字体
  和最终华为 CI 观感仍需现场人工确认。

## 2026-08-26 实习答辩 PPT（通用项目汇报版，未使用 academic-pptx）

### 已完成并通过验收

- 按用户要求未使用 `academic-pptx`；仅使用通用 `presentations` 工作流，并严格走项目自身
  `DeckIR 2.2 → Schema 校验 → python-pptx 渲染 → PPTX lint` 主链路生成独立版本。
- 采用 `hw-report` 主题，将 19 页标题统一为“模块 + 结论”的业务项目汇报表达；重点强化
  场景痛点、系统架构、分层 IR、Demo 证据、阶段结果、内网落地和项目结论。
- 最终文件为
  `output/defense-deck-20260826-general/实习答辩PPT_通用项目汇报版_19页.pptx`；同目录保留
  DeckIR 2.2、演讲备注和 lint 报告，未覆盖上一版交付物。
- 结构审计为 19 slides、19 notes、19 个 `[Sources]` 来源块；项目 lint 为
  0 Error / 0 Warning / 0 Info，PowerPoint 实机成功导出 19 张 1600×900 PNG。
- 已检查总览及封面、架构、分层 IR、阶段结果、Skill 工作流和结论等重点页面，未发现裁切、
  重叠、文本溢出或不可读连线；最终文件 SHA-256 为
  `A472AF20EC7AD72571CAD055FAF3B6724AC06F63E20372FFD93A4B65A399FFBA`。

### 待答辩人替换

- 封面姓名、部门、导师和结论页联系方式仍为明确占位。
- 第 9 页需替换真实模板墙截图；第 12 页需插入脱敏的本地演示视频，并保留静态截图备份。

## 2026-08-27 rhetoric-deck-workflow Skill 1.0.0

### 已完成并通过验收

- 新增独立、显式调用的 `skills/rhetoric-deck-workflow/`；宿主 Agent 负责两次语义推理，Skill
  自身不调用模型 API。命令覆盖 `doctor / extract / seal / plan / finalize / library`，均以稳定
  JSON 诊断和退出码交互。
- 按用户边界冻结直接复制：Office 包安全预检、CJK 字号拟合、CLI 错误 JSON 约定和 DeckIR
  2.2 Schema；`engine/runtime_manifest.json` 记录产品版本 2.2.0、源路径与 SHA-256，包脚本发现
  源漂移即阻止发布。
- `seal` 已验证：Schema 与零原文门禁通过后才生成 shell；源副本与 `extract_pack/pages/`
  物理删除；仅保留 SHA-256 n-gram/数字/术语指纹。非法 skeleton 不销毁源上下文，便于修正。
- `finalize` 已验证：非法 FillContent 返回 `RD-E030` 且不建产物目录；注入源句返回
  `RD-E040`，只保留泄漏报告，不生成 PPTX；模式 A 仅在现有 shape/cell 中替换文字与缩字，
  不实现布局；模式 B 只输出通过冻结 Schema 的 DeckIR 2.2。
- 四类主输入链路已覆盖：UTF-8 Markdown、DOCX、XLSX、PPTX；专项测试 6 passed。Skill 官方
  `quick_validate.py` 返回 `Skill is valid!`。
- 项目 Python 3.12 下 `python scripts/verify.py` 全绿：原项目四格式 word/deck stub E2E 通过，
  parsers 91.96%、ir 94.06%、lint 94.23%、overall 88.79%。
- 生成 `dist/rhetoric-deck-workflow-1.0.0.zip`（119,791 bytes，解压 255,795 bytes，51 entries）
  与 SHA-256 `cfbc924156d164c332ec097b872e3ef1de64d2ee400c8b2e2b61606a0fc4966d`；包内 0 渲染器、
  0 lint、0 template assets、0 generators/Web/WPF。解压到临时目录后已自动跑通 doctor、
  source-shell 全链路和 deck-ir 全链路。

### 降级 / 近似

- 非多模态环境无法判断图片是装饰还是源内容。为保证“源数据不进入产物”，seal 会删除所有
  可识别图片/媒体；若母版或特殊部件仍残留媒体则阻断，而不是冒险保留。矢量形状、位置、样式、
  表格与文本 run 结构仍保留。
- `--allow-page-adjust` 只记录允许的适配建议并启用容量宽容，不复制列、不删行、不重排几何；
  这是为了遵守“本 Skill 不实现版式渲染”的直接约束。
- 五因子打分是确定性信号评分，能稳定分流 fill/adapt/reject，但不能替代宿主 Agent 的语义判断。

### 阻塞待人输入

- 无阻塞。正式推广前仍需业务方在代表性真实脱敏源件上确认：图片一律移除是否符合模式 A 的
  使用预期，以及目标 PowerPoint/字体环境的视觉签字。

### 仍不确定

- 规格中的 deck_pattern 页序含 `cover/conclusion/risk_plan/next_plan/benefit_plan`，但页级契约只
  允许 9 个 page_pattern。当前不扩张契约：内置骨架只使用九类业务页，DeckIR 模式从用户材料
  确定性补 cover，并仅在存在用户结论内容时补 conclusion；模式 A 不合成这些页。
- `python-pptx` 的正常安装会带来其传递依赖 Pillow；Skill 自身只声明并检查用户指定的三个直接
  依赖 `python-pptx/jsonschema/lxml`，没有额外安装逻辑或依赖包。
