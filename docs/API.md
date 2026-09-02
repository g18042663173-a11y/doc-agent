# API Reference

Base URL: `http://127.0.0.1:8000`

## Health and System

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Legacy health check |
| `GET` | `/api/system/health` | System health and active runtime settings |
| `GET` | `/api/system/metrics` | Request, task, and local storage metrics |
| `GET` | `/api/config/export` | Export masked runtime, user, template, and color configuration |
| `POST` | `/api/config/import` | Import users with plaintext tokens and custom color schemes |

`/api/config/export` masks `llm_api_key` and user `auth_token`. Exported masked users are not directly re-importable as live credentials.

## Generation

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/generate/start` | Start async generation from `md/docx/pptx/xlsx/xlsm` upload |
| `GET` | `/api/generate/progress/{task_id}` | Read task progress JSON |
| `GET` | `/api/generate/download/{task_id}` | Download completed output |
| `GET` | `/api/generate/history` | List local generation history newest first |
| `GET` | `/api/generate/history/{task_id}` | Read one task record |
| `DELETE` | `/api/generate/history/{task_id}` | Delete one task record; pass `delete_files=true` to also delete generated files |
| `WS` | `/api/generate/ws/{task_id}` | Receive progress updates |
| `POST` | `/generate` | Legacy synchronous-compatible API |
| `GET` | `/download/{file_id}` | Legacy download API |

Async generation form fields:

```text
file: md/docx/pptx/xlsx/xlsm upload
target: pptx | docx
slides: 5..12
template_id: optional
color_scheme_id: optional
user_id: optional
profile_id: optional alias for user_id
```

History records include `task_id`, `status`, `progress`, `current_step`, `result`, `error`, `error_type`, `friendly_error`, `compliance_report`, and `metadata`. Metadata stores `original_filename`, `source_type`, `target`, `slides`, `template_id`, `color_scheme_id`, `user_id`, `profile_id`, `created_at`, and `updated_at`.

`compliance_report` is present for PPTX tasks when `PPT_COMPLIANCE_GATE` is not `off`:

```json
{
  "score": 88,
  "summary": "0 Error, 2 Warning, 0 Info",
  "items": [
    {
      "severity": "Warning",
      "code": "font.size.unexpected",
      "message": "Found non-standard font sizes: 18.",
      "slide_index": 2
    }
  ]
}
```

DOCX tasks also include a Word format report with the same `score/summary/items` shape.

## AICoding Manual Bridge

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/aicoding/prompt` | Parse `md/docx/pptx/xlsx/xlsm` and return a copyable AICoding prompt |
| `POST` | `/api/aicoding/render` | Validate pasted AICoding JSON as `WordIR` or `DeckIR`, render output, and write local history |

Prompt form fields:

```text
file: md/docx/pptx/xlsx/xlsm upload
target: docx | pptx
slides: optional PPT target slide count
```

Render JSON:

```json
{
  "target": "docx",
  "model_output": "{\"title\":\"Demo\",\"blocks\":[{\"type\":\"paragraph\",\"text\":\"...\"}]}",
  "original_filename": "input.xlsx",
  "slides": 8
}
```

Excel parsing extracts sheet names, table preview rows, merged-cell/formula counts, and numeric column statistics. It does not claim chart, pivot table, VBA, or complex formula understanding.

## Model Profiles

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/users/create` | Create an NGA model profile |
| `GET` | `/api/users/list` | List model profiles with masked tokens |
| `GET` | `/api/users/{user_id}` | Get model profile details with masked token |
| `PUT` | `/api/users/{user_id}` | Update model profile |
| `DELETE` | `/api/users/{user_id}` | Delete model profile |
| `POST` | `/api/users/switch/{user_id}` | Set current model profile |
| `POST` | `/api/users/test-connection` | Validate endpoint/token shape |
| `POST` | `/api/profiles/create` | Create a model profile using product-facing naming |
| `GET` | `/api/profiles/list` | List model profiles as `profiles` with `profile_id` |
| `GET` | `/api/profiles/{profile_id}` | Get one model profile |
| `PUT` | `/api/profiles/{profile_id}` | Update one model profile |
| `DELETE` | `/api/profiles/{profile_id}` | Delete one model profile |
| `POST` | `/api/profiles/switch/{profile_id}` | Set current model profile |
| `POST` | `/api/profiles/test-connection` | Validate endpoint/token shape |

The route prefix `/api/users` remains for backward compatibility. `/api/profiles` is the product-facing alias and returns `profile_id` while keeping `user_id` for compatibility. Tokens are encrypted at rest under `data/users/` and are never returned by list/get endpoints. New profiles default to `llm_provider=nga` and `ppt_renderer=stub`; external-network generation should use the default stub flow until the intranet NGA adapter is implemented.

## DeckIR v1.1

Deck generation uses `DeckIR v1.1` as the stable model-to-renderer contract. Existing layouts remain valid, and the extended layouts `cards`, `chart`, and `image` are accepted. Optional fields such as `source_refs`, `intent`, `importance`, `cards`, `visuals`, `chart`, `footer`, and `confidentiality` let the intranet Huawei Skill map content to richer layouts without changing upstream parsing or planning.

## Design System

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/templates/list` | List templates |
| `GET` | `/api/templates/{template_id}` | Get template metadata |
| `POST` | `/api/templates/import` | Import a custom `.pptx` template |
| `GET` | `/api/colors/list` | List color schemes |
| `GET` | `/api/colors/recommend?scenario=...` | Recommend color schemes |
| `GET` | `/api/colors/{scheme_id}` | Get a color scheme |
| `POST` | `/api/colors/create` | Create a custom color scheme |
| `POST` | `/api/charts/recommend` | Recommend a chart type |
| `POST` | `/api/charts/generate` | Return chart IR |
| `GET` | `/api/smartart/types` | List SmartArt types |
| `POST` | `/api/smartart/generate` | Return SmartArt IR |

Imported template responses include `style_summary` with slide size, slide/master counts, font candidates, and theme/common colors when they can be extracted. This is a style-apply feature; it does not clone full slide masters, animations, or arbitrary placeholder behavior.

## Examples

```bash
curl http://127.0.0.1:8000/api/system/health

curl -F "file=@examples/input.md" \
  -F "target=pptx" \
  -F "slides=8" \
  -F "template_id=business_report" \
  -F "color_scheme_id=business_blue" \
  http://127.0.0.1:8000/api/generate/start

curl http://127.0.0.1:8000/api/generate/history
curl http://127.0.0.1:8000/api/generate/history/{task_id}
curl -X DELETE "http://127.0.0.1:8000/api/generate/history/{task_id}?delete_files=false"
```
