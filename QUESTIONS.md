# QUESTIONS

## 人工待办

1. 真实业务语料:需要提供脱敏后的真实 docx / xlsx / pptx 各至少 3 个,放入 `samples/input/real/`,用于解析与模板生成回归。
   - 当前默认值:使用构造样例、固定公开样例和 HIT 模板覆盖结构与边界。
   - TODO:导师或业务侧提供真实语料后纳入 fixtures,不得用构造样例冒充真实验收。
2. PowerPoint 最终审美签字:需要人在目标 Windows PowerPoint 和目标字体环境中判断模板继承、字体观感、信息密度与专业度是否可交付。
   - 当前结果:自动 lint、包校验和 PowerPoint 16 导出均已执行,HIT 联系表位于 `output/hit_template_acceptance/powerpoint_visual_20260729/contact_sheet.png`；双引擎最终对照联系表位于 `output/html2pptx-final-office/`，均为 `manual_pending`。
   - TODO:业务评审人对最终样例签字;自动检查通过不等于人工审美终审完成。
3. 真实图片语料:需要提供可在交付材料中使用的 PNG/JPEG/WebP，明确版权/来源、署名、替代文本和关键焦点，用于横图、竖图、透明图、低分辨率与 2-4 图网格验收。
   - 当前默认值:使用仓库公开截图和合成图片验证解码、裁切、哈希、DPI 与审计，不把它们冒充业务图片。
   - TODO:业务侧提供脱敏且授权明确的图片后，补真实图文页、图片网格和模板图片槽的 PowerPoint 人工签字。
4. 全新 Windows 物理断网验收证据:需要在未预装项目依赖的干净 Windows 机器上，从发布包和 wheelhouse 完成离线安装并执行 `verify.ps1`。
   - 当前结果:本机 Python 3.12、29 个锁定 wheel 的 `--no-index --require-hashes --dry-run`、`verify.ps1` 和工作台浏览器回归均已通过。
   - TODO:交付人员在物理断网目标机保存 Python/Office/字体版本、安装日志、验收日志和结果截图；本机验证不得冒充该证据。
