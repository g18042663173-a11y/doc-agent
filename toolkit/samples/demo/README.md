# 演示证据包

本目录由 `python scripts/record_demo.py` 基于真实命令输出生成:

- `logs/success_word.txt`: DOCX stub 主链路命令、退出码和输出。
- `logs/success_deck.txt`: PPTX stub 主链路及 lint 命令、退出码和输出。
- `logs/failure_deck.txt`: 非法 DeckIR 被 D003 阻断的结构化失败输出。
- `screenshots/success.png`: 两条成功命令的终端证据截图。
- `screenshots/failure.png`: D003 失败提示截图。
- `recording_steps.md`: 最终录屏顺序和人工打开 Office 产物的检查点。
- `manifest.json`: 上述日志和截图的 SHA-256。

这些截图证明命令行为,不替代 Windows 字体、Office 可编辑性和视觉观感的人工终审。
