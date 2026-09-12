# User Guide

## Start

1. Start the backend on `http://127.0.0.1:8000`.
2. Start the React frontend on `http://127.0.0.1:3000`.
3. Open the frontend. The default landing page is the personal workbench dashboard.

## Personal Workbench

The dashboard shows model profile status, recent generation history, template count, color count, and quick actions for generation, model setup, and template import.

## Generate a Document

1. Go to `生成 -> 智能生成`.
2. Upload a `.md`, `.docx`, or `.pptx` file.
3. Choose output type: `PPTX` or `DOCX`.
4. Pick slide count, template, color scheme, and optional model profile.
5. Click `生成`.
6. Watch progress in the progress panel.
7. Download the generated file when the task completes.
8. Use `个人生成历史` to download completed tasks again, reuse parameters, or delete a local history record.

The generated file is editable Office output, not an image-only export.

## Configure Model Profiles

1. Go to `配置 -> 模型档案` or `模型配置`.
2. Add a profile name, NGA endpoint, token, and model.
3. Use `测试连接` to validate URL/token shape.
4. Save and switch to the model profile in the header.

Profile tokens are stored encrypted and are displayed as `***HIDDEN***`.

## Manage Design Assets

- `设计 -> 模板`: list system templates and import `.pptx` templates for style cues.
- `设计 -> 颜色`: list schemes, request recommendations, and create custom schemes.
- `设计 -> 图表`: recommend chart types and generate chart IR.
- `设计 -> SmartArt`: generate SmartArt IR from line-based nodes.

Imported PPTX templates are used for slide size, font candidates, and theme/common colors. They do not fully reproduce master layouts, animation, complex placeholders, or embedded SmartArt behavior.

## Import and Export Configuration

Go to `配置 -> 设置`.

- `导出个人配置` downloads masked settings, model profiles, templates, and colors.
- `恢复个人配置` accepts JSON with plaintext tokens for profiles that should be usable.

Masked exported tokens are intentionally skipped on import.

## Troubleshooting

- If generation fails, check the on-screen actionable message or `/api/generate/history/{task_id}` for `friendly_error`, `error_type`, and technical `error`.
- If the frontend shows empty data, confirm the backend is running and CORS allows `http://127.0.0.1:3000`.
- If logs are needed, inspect `data/logs/app.log`.
- If a real LLM call should not happen, keep `LLM_PROVIDER=stub`.
- If an NGA or Huawei Skill placeholder error appears, the intranet adapter has not been wired yet; switch back to the stub default for external-network testing.
