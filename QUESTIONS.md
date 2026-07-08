# QUESTIONS

## 人工待办

1. 真实文件语料:需要提供脱敏后的真实 docx / xlsx / pptx 各至少 3 个,放入 `samples/input/real/`,用于解析回归。
   - 当前默认值:使用构造样例与测试动态生成样例覆盖边界。
   - TODO:导师或业务侧提供真实语料后纳入 fixtures。
2. Windows 离线验收:需要在干净 Windows + Python 3.12 环境中执行 wheelhouse 安装与 `python scripts/verify.py`。
   - 当前默认值:已提供 `scripts/make_wheelhouse.py` 和接入说明,但未在 Windows 真机验证。
   - TODO:人工记录 Windows 版本、Python 版本、安装输出和截图。
3. PPTX 视觉终审:需要人在 Windows PowerPoint 中打开生成产物做字体、观感、专业度判断。
   - 当前默认值:lint 通过代表硬规则通过,不代表最终视觉可交付。
   - TODO:内网字体/CI 校准后复核 `backend/app/rendering/themes/hw_theme.json`。
