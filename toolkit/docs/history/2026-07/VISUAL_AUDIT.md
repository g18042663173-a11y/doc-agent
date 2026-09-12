# DeckIR 版式视觉自查

本轮只诊断,未改业务代码、IR 契约、schema 或配置。审计样例与截图均生成在 `output/visual_audit/`。

## 取证范围

- 样例 IR: `output/visual_audit/visual_audit_samples.json`
- PPTX: `output/visual_audit/visual_audit_samples.pptx`
- PDF: `output/visual_audit/pdf/visual_audit_samples.pdf`
- JPEG: `output/visual_audit/jpg/slide-01.jpg` 至 `slide-20.jpg`
- 总览图: `output/visual_audit/contact_sheet.jpg`
- 转换命令:
  - `PYTHONPATH=backend python -m app.cli.render --type deck output/visual_audit/visual_audit_samples.json --output output/visual_audit/visual_audit_samples.pptx`
  - `soffice --headless --convert-to pdf --outdir output/visual_audit/pdf output/visual_audit/visual_audit_samples.pptx`
  - `pdftoppm -jpeg -r 160 output/visual_audit/pdf/visual_audit_samples.pdf output/visual_audit/jpg/slide`
- lint 结果: `0 Errors / 36 Warnings / 1 Info`;主要为 `HW-W06/HW-W07`,图片页另有 `HW-W09`。

## 样例页覆盖

| 页码 | layout | 样例 |
| --- | --- | --- |
| 1-2 | cover | 少内容封面 / 长标题封面 |
| 3-4 | agenda | 2 项目录 / 8 项目录 |
| 5-6 | section | 简短章节页 / 长标题章节页 |
| 7-8 | title_bullets | 少量要点 / 7 条长要点 |
| 9-10 | two_column | 少内容双栏 / 双栏多内容 |
| 11-12 | table | 普通状态表 / 方案对比决策矩阵 |
| 13-14 | cards | 2 卡片 / 4 卡片 |
| 15-16 | chart | 简单折线图 / 性能柱状图 + 阈值 + 侧栏 |
| 17-18 | image | 短占位 / 长占位 |
| 19-20 | conclusion | 少内容结论 / 多要点结论 |

## 问题清单

| 严重程度 | 版式 | 样例 | 问题 | 修改方向 |
| --- | --- | --- | --- | --- |
| 必须修 | 全局多版式 | slide 1-14, 17-20 | lint 大面积报 `HW-W06/HW-W07`:文本框未吸附网格/基线或间距小于主题下限。人工看图没有每页都明显重叠,但这说明多数版式坐标与合规规则不一致,后续会反复误报或漏报真实贴边问题。 | 逐版式把 title、正文、卡片、占位框、页脚以 12 栏网格和 8pt baseline 重新落 token;先修共享 title/footer,再修每个 layout 的主体坐标。 |
| 必须修 | chart | slide 15 简单趋势图 | 阈值虚线和标签出现在图表内部大标题/图例附近,不在真实 plot 坐标位置;视觉上像一条横穿标题区的辅助线,读者会误解阈值对应的 Y 值。 | 阈值线坐标不能按 chart 外框线性估算,需要按实际 plot area 计算或改成原生图表辅助系列;同时关闭/控制 chart 内部自动标题。 |
| 必须修 | chart | slide 16 性能趋势与阈值 | 侧边结论写“方案A连续三个月低于目标阈值”,但数据为 62/58/55,阈值 60,首月并未低于阈值;视觉语义与数据含义不一致。 | generator/stub 或渲染前校验应按阈值方向生成结论,例如“2 月起低于 60ms,1 月仍超阈值”。必要时 IR 增加阈值方向另走契约演进。 |
| 必须修 | image | slide 17-18 图片占位 | 占位框灰底 + 灰字对比度低,lint 报 `HW-W09`;肉眼看占位说明也偏弱,正式评审时容易被当成空白图或缺图。 | 占位框内文案改为高对比正文色,增加清晰的“占位 / 待替换”标签;必要时用浅红提示条而不是低对比灰字。 |
| 必须修 | table | slide 12 方案对比决策矩阵 | 分组表头产生空白红色表头块,左上和右上红块像缺列名;对“评估维度”到底覆盖哪些列不够清楚。 | column_groups 渲染时未覆盖列应显式保留原 header 或使用浅底空白,避免大块无文字红底;也可把分组行只画在被分组列上。 |
| 建议修 | 全局 | all slides | 所有页面没有显示右上角 Logo,而 theme 已有 logo token;如果按真实华为模板验收,品牌锚点缺失。 | 明确是否有 logo asset;有则渲染,无则在报告中标注“资产缺失导致不渲染”。 |
| 建议修 | cover | slide 1-2 | 封面主体集中在左侧,右侧大面积空白;长标题仍可读,但整体不像正式封面,更像普通正文页。 | cover 需要更明确的主视觉结构:标题区扩大、meta 下移或右侧加入品牌/项目辅助信息;红条不要孤立落在左下。 |
| 建议修 | agenda | slide 3 | 2 项目录使用和 8 项目录同一排版,内容过少时显得稀疏。 | 根据 items 数量切换 compact agenda:少于 4 项时居中或加大行距/字号。 |
| 建议修 | agenda | slide 4 | 8 项目录两栏可读,但左右栏间距很大,缺少视觉连接;项目编号和标题的距离略松。 | 收紧列距,让编号和文本作为一组对齐;可增加细分栏线或统一起始网格。 |
| 建议修 | section | slide 5-6 | 章节页极简可接受,但长标题页的副标题层级偏弱,页面整体仍显空。 | section 可保留极简,但长标题场景可增加副标题容器或章节摘要,避免只有一行信息漂浮。 |
| 可接受 | title_bullets | slide 7 | 少量要点无重叠、无裁切,可读性正常。 | 暂无必须修改。 |
| 建议修 | title_bullets | slide 8 | 7 条长要点虽然没压字,但全部同一层级、行宽较长,扫读成本高。 | 对长要点增加二级缩进、强调词或分组;超长句可自动断行为两行并加大行高。 |
| 可接受 | two_column | slide 9 | 少内容双栏无裁切,左右语义清楚。 | 暂无必须修改。 |
| 建议修 | two_column | slide 10 | 多内容双栏可读,但两栏只是并列文本,缺少分组底板或垂直参考线;信息密度高时层级不够。 | 增加轻量列标题底线/分隔线;长文本和 bullet 的垂直间距按内容量自适应。 |
| 建议修 | table | slide 11 普通状态表 | 2 行表格占据过宽,表格显得厚重;少内容表可读但比例不克制。 | 表格宽度随列数和内容量收缩,或对少行表增加说明/结论区。 |
| 建议修 | cards | slide 13 | 2 张卡片过大,灰色块占比太高,内容很少时卡片像空面板。 | cards 根据数量调整卡片宽高;少内容卡片可居中收窄或加入图标/编号。 |
| 建议修 | cards | slide 14 | 4 卡片排版基本可读,但灰底过重、红色顶边过抢,正文层级弱于卡片装饰。 | 降低灰底存在感,缩短或变细红色顶边,让卡片标题成为视觉主导。 |
| 建议修 | chart | slide 16 性能趋势与阈值 | 阈值线比上一轮克制,但标签仍放在 plot 中央偏右,靠近柱顶数据标签和柱形区域;侧栏小表位置清楚。 | 阈值标签优先放 plot 右上外侧或侧栏上方;避免与柱顶数据标签共享同一区域。 |
| 建议修 | image | slide 17-18 | 占位框很大但说明文字靠左且偏小,视觉像空灰框;长占位说明没有形成醒目的“待替换”状态。 | 占位说明居中或左上加标签条,caption 与占位框间距再收紧;长说明可拆成主标签 + 副说明。 |
| 建议修 | conclusion | slide 19 | 少内容结论页只有一条 bullet 和底部 CTA,中间空白过多,CTA 与结论关系弱。 | 少内容 conclusion 可改为居中大结论 + CTA,或用强调框承接主结论。 |
| 建议修 | conclusion | slide 20 | 多要点结论可读,但 CTA 在底部左侧显得孤立,不像最终行动项。 | CTA 可放到要点下方同一信息组,或右侧使用醒目的下一步块。 |

## 最严重的 5 个

1. chart 简单折线图阈值线位置错误,穿到图表标题/图例区域,属于视觉和数据语义双重问题。
2. 性能图侧边结论与数据不一致,会误导读者对阈值达标情况的判断。
3. image 占位页低对比度文字触发 `HW-W09`,肉眼也不够清晰。
4. 决策矩阵分组表头出现空白红块,像缺失表头,影响增强 table 的可信度。
5. 全局多数版式触发 `HW-W06/HW-W07`,说明视觉 token 与 lint 规则没有统一。

## 本轮边界

- 我检查的是 LibreOffice/PDF 渲染后的 JPEG,不是 Windows PowerPoint 真机截图;字体和细节可能与 Windows 有差异。
- 本轮没有打开真实源 PPTX 对照,只检查当前 renderer 的输出是否自洽。
- 本轮只写报告,不修 renderer、theme、schema、IR、测试或样例。
