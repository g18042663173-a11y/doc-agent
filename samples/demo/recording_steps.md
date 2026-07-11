# 演示录屏操作清单

1. 在仓库根目录运行 `python scripts/record_demo.py`。
2. 展示 `samples/demo/screenshots/success.png`,说明 Word/Deck 两条 stub 链路均为 0 退出。
3. 打开 `samples/output/word/word_valid_03_table.docx`,确认文本和表格可编辑。
4. 打开 `samples/output/deck/deck_valid_full.pptx`,确认文本、表格、图表和形状可编辑。
5. 展示 `samples/demo/screenshots/failure.png`,确认非法 DeckIR 在渲染前以 D003 阻断。
6. 展示 `samples/output/deck/deck_lint_violation_report/report.json`,确认人工注入的合规违规被命中。
7. Windows 上重复打开 Office 产物并录屏;Mac 截图不替代字体和观感终审。
