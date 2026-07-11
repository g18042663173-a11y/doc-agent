# Expected 结构基线

本目录只保存可审阅的结构事实,不把 DOCX/PPTX 二进制当 golden:

- `appendix_b_document_ir.expected.json`:附录 B 三个固定 Office 输入的 DocumentIR 摘要。
- `项目汇报.pptx.expected.json`:8 页 PPTX 的逐页标题、正文/表格计数和备注。
- `word_official_outputs.expected.json`:3 个官方 WordIR 渲染后的段落、样式、表格、页眉页脚和主题色事实。
- `deck_valid_full.expected.json`:全版式 Deck 的 layout、可编辑表格/图表页和 lint 汇总。
- `deck_lint_violation.expected.json`:稳定违规 PPTX 应命中的 HW 码。
- `manifest.json`:上述 JSON 的 SHA-256。

更新必须显式运行 `PYTHONPATH=backend python scripts/build_delivery_assets.py`,检查 diff 后再提交。测试不会自动更新 expected。
