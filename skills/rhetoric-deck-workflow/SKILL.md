---
name: rhetoric-deck-workflow
description: Preserve a supplied PPTX's native layout, pictures and diagrams while replacing its editable content from user material, or produce DeckIR for a separate generator. Use when explicitly invoked as $rhetoric-deck-workflow.
---

# 模仿

模仿源件的讲法与版式，内容只来自用户材料。保留全部源页及顺序，图片像素、裁切和位置不变；原生文字、表格、SmartArt、图表仍为原生对象。脚本不调用模型 API，宿主 Agent 负责材料理解和改写。

Windows 便携包优先用 `<skill-dir>/run.cmd`。开发环境可用 Python 3.12 执行 `bin/rdw.py`。先运行 `doctor --json`，Error 必须修复。

## 源件流程

1. `extract --source <source.pptx> --out <new-workdir>`。必须使用新目录。阅读全部页清单、`native_inventory.json`、`slot_candidates.json` 和 `skeleton_draft.json`，不能只选简单页面。
2. 按源版式修改骨架的角色和语义，区分标题、眉题、导航、正文、页脚。保留每页和每个绑定；目录、结束页及纯图片页也须纳入。不要把源句子、数据和专名放入骨架。
3. `seal --workdir <workdir> --skeleton <skeleton.json>`。修复所有缺页、漏绑和不支持对象，不以删页规避。源件及抽取数据只供当前工作目录内的核对，不进入 Skill 包或正式文档交付。
4. `plan --workdir <workdir> --skeleton <workdir>/sealed/skeleton.sealed.json --material <file> --render-mode source-shell`。支持多份 md/txt/json/docx/xlsx/pptx/pdf。阅读完整 `material.json` 的证据索引及警告，PDF 引用使用物理页码。扫描页不能当作已提取。
5. 按编译后的 FillContent 2.0 Schema 写 `content.json`。提交全部页及全部槽，每个值附 `evidence_refs`。引用 ID 来自材料索引；图表派生数据附 `derivation`，记录公式、单位、分母和实验口径。没有材料则显式 `status: missing`，不可捏造。
6. `finalize --workdir <workdir> --content <content.json> --out <new-outdir>`。缺材料、无效引用、漏页、漏槽、原生对象不一致或文字溢出均不得标为完成。`--preview` 仅用于内部草稿，不能交付为成品。
7. 使用目标 PowerPoint 打开并导出每页，检查全部原尺寸图片。逐页核对内容来源、图表数据、文字裁切、结构保留和截图保留项。使用独立 Agent 复核语义与数据口径。
8. 将复核写入 JSON：`artifact_sha256`、`reviewer`、`pass` 及有序 `pages`。每页记录 `page_id`、`pass`、导出图片绝对路径 `png`、`png_sha256` 和检查意见。执行 `accept --out <outdir> --review <review.json>`，通过后状态才是 `accepted`。任何后续修改都要重新 finalize、渲染和复核。

## 对象与材料规则

- 图片内的旧字是明确保留的像素内容，列入保留项；不能作为新内容的事实来源。不得遮字、重画图片或替换为空框。
- SmartArt 保留模型、图形及关系，同步可见缓存。无法证明显示正确时，状态保持待复核。
- 图表 value 为 categories 和 series（每系列含 name、values）；每个系列覆盖全部类目。保持图表对象、类型与布局，更新缓存和工作簿。禁止缺数据补零。
- 保留模板原字号及段落层次，优先缩短材料以适应原框。不得套用生成模式的全局标题字号。
- 评分只提供角色提示，不代表证据充分或允许删页。正式验收检查实际输出，不只看输入 JSON。
- RD-E010/011：修正完整骨架；RD-E020：修正材料；RD-E030：补齐内容和证据；RD-E040：修复源文残留；RD-E050：修复渲染、验收或目录问题。禁止绕过检查。

## 讲法库与生成 Skill 交接

没有源 PPTX 时，使用 `library list/get` 和 `plan --pattern <id> --render-mode deck-ir`。该模式只输出通过 DeckIR 2.2 校验的 JSON，不绘制华为主题。需要华为 PPT 时，把 `deck_ir.json` 交给 `$huawei-doc-workflow` 的 validate 和 finalize；Word 及从零生成也使用生成 Skill。

参见 [README.md](README.md) 的便携使用和验收边界。内部 Schema/证据检查通过不等于视觉或语义已完成。

验收用 `review.json` 须含 `artifact_sha256`、`reviewer`、`pass`，以及与源页同序的 `pages`（每页 `page_id`、`pass`、`png`、`png_sha256`）。另附 `semantic_review`：`pass`、独立复核人的 `reviewer`、本次 `content.json` 的 `content_sha256`；核对材料含义、图表口径和派生计算后才能设为通过。`accept` 核验全部最终文件和渲染图片哈希，不接受旧版内容的复核。
