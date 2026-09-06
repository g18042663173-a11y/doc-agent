# 模仿 2.0.0

Agent 从用户材料改写源 PPTX 的全部页，保留原布局、图片、SmartArt 和原生图表。目录、结束页和图片页都计入完整页清单，评分不会删除页面。

## Windows 便携使用

解压模仿.zip，使用包内 run.cmd doctor --json。包内 Python 3.12 与锁定依赖独立运行，不依赖开发仓库、系统 Python、生成.zip 或 Docker。安装使用同目录 install.ps1。PowerPoint 用于目标 Office 视觉验收，未完成导出和逐页复核时输出标为 needs_visual_review。

命令入口：doctor、extract、seal、plan、finalize、accept、library。完整步骤见 SKILL.md。所有 CLI 输出采用 UTF-8。

## 内容与保留

材料支持 md/txt/json/docx/xlsx/pptx/pdf。PDF 证据使用物理页码；扫描页或读取问题明确列为警告。每个填充值带 evidence_refs，计算数据附 derivation。引用检查证明来源可追溯，语义与计算还须独立复核。

source-shell 保留所有源页及次序；原生表格、SmartArt、图表和文字仍可编辑。图表数据、缓存与内嵌工作簿同步。截图像素不改，截图中文字作为逐页保留项，不作为新材料事实。动画仍移除并记录。

seal 后源件参考、逐页抽取和内部 shell 保留在当前工作目录，供对照与修复；这些文件不进入分发 Skill 或最终文档目录。工作目录含源信息，不宣称已完全消毒。内部 shell 的图表缓存必须在 finalize 全部替换，不能单独交付。

DeckSkeleton / FillContent 使用 2.0。旧 1.0 输入只在内存迁移并按完整页规则重新检查，不覆盖旧文件。DeckIR 2.2 保持跨 Skill 交接。

finalize 生成待视觉复核的结果及证据、原生对象、回读、残留检查报告。缺页、缺槽、缺材料或文字溢出不能标为完成；preview 只生成内部草稿。accept 将完整逐页复核记录及 PNG 哈希绑定到最终 PPTX；文件后改会令验收失效。

## 构建

开发使用 Python 3.12；同步冻结引擎后运行 package_rhetoric_deck_skill.py。便携发布通过统一 release 脚本完成，归档、SHA-256、依赖锁和安装副本一致性均需检查。工作台继续只提供生成功能。
