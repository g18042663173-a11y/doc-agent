# Findings

## Current Baseline

- Project is not a git repository, so `git diff` is unavailable unless the repo is initialized later.
- Current project now includes the Python backend MVP plus a React/Vite/TypeScript frontend under `ppt-agent-frontend`.
- Current workflow lives in `doc_agent/workflow.py` and falls back to sequential execution when LangGraph is missing.
- Current API lives in `app/api.py` with `/health`, legacy `/generate`, and `/download/{file_id}`.
- Current dependencies installed in `.venv` cover core tests but not the full `requirements.txt`; the full install previously stalled on a slow LangGraph dependency download.
- Current backend tests pass with `.venv/bin/python -m pytest`: 22 passed, 1 Starlette TestClient/httpx deprecation warning.
- Obsolete collaboration tooling was uninstalled on 2026-07-06 at the user's request because it affected performance. Do not rely on that toolchain for this project.

## Pasted Design Requirements Summary

- Add backend modules: users, templates, colors, charts, SmartArt. Implemented in current backend slice.
- Add API modules: generation task API, template API, color API, user API, WebSocket progress, chart/smartart endpoints implied by API list. Implemented in current backend slice.
- Add file-system data storage under `data/` for users, templates, colors, tasks, uploads. Implemented; `data/` is ignored by git.
- Add system observability and configuration portability. Implemented with `/api/system/health`, `/api/system/metrics`, `/api/config/export`, `/api/config/import`, JSON request logs, and README/docs coverage.
- Later add React/Vite/TypeScript frontend with dashboard, generator, design system, config, and user management.
- Preserve md/docx/pptx input and editable pptx/docx output.
- Support multiple local NGA/OpenAI-compatible model profiles. Implemented for stored profile configs and generation runtime settings; API responses mask auth tokens by default.
- Provide async generation progress and download. Implemented under `/api/generate/start`, `/api/generate/progress/{task_id}`, `/api/generate/download/{task_id}`, and `/api/generate/ws/{task_id}`.

## Implementation Notes

- The pasted user encryption pseudocode uses `cryptography.fernet`, but `cryptography` is not in the current dependencies. Implemented a local HMAC-checked reversible token seal using a random key file under `data/users/.encryption_key`; it prevents plaintext leakage at rest and through list/get API responses, but is not a replacement for audited production key management.
- Existing `Settings` is frozen, so the pasted design's direct mutation of settings would fail. User-specific LLM config should be passed explicitly or applied via environment/context, not by mutating a frozen dataclass.
- Some pasted frontend code contains syntax errors and should be treated as design intent, not literal source.
- FastAPI/httpx/python-multipart were missing from the local `.venv` even though FastAPI/python-multipart were listed in requirements. Installed minimal API test dependencies directly in `.venv` and added `httpx` to project dependencies for TestClient coverage.
- Frontend was absent. Added `ppt-agent-frontend` and built it successfully with Vite. The production bundle is about 1.2 MB minified due to Ant Design and related dependencies; Vite reports this as a chunk-size warning but the build succeeds.
- The initial frontend generation page used HTTP polling even though a WebSocket helper existed. It now uses WebSocket progress as the primary channel and HTTP polling as fallback.
- Ant Design 6 emits runtime error-level deprecation logs for `Space direction`; replacing it with `orientation` removes the warning on a clean browser tab.
- The in-app browser control API still cannot drive the native file picker, but repo-native Playwright E2E now covers the real upload/generate/download browser flow by setting the file input directly.
- Added repo-native Playwright E2E coverage outside the browser plugin limitation. `npm run test:e2e` starts isolated backend/frontend servers, uses Chrome to set the upload input file directly, triggers generation, waits for WebSocket completion, and verifies the downloaded PPTX is non-empty.
- Added responsive/page-load Playwright coverage for desktop `1440x900` and mobile `390x844` viewports across dashboard, smart generation, NGA config, users, templates, colors, charts, SmartArt, and settings routes. It enforces visible route anchors, under-3-second usability, no document-level horizontal overflow, and no console errors.
- Added interaction-level Playwright coverage for settings import/export, user create/test/list/switch, template import, color recommendation/create, chart IR generation, and SmartArt IR generation.
- Responsive E2E exposed two UI issues: mobile navigation pushed page content below the first viewport, and the colors page table/inline form caused horizontal overflow. Fixed with a mobile horizontal navigation bar plus constrained table and inline-form styles.
- Real Uvicorn WebSocket support requires a WebSocket protocol implementation. The E2E test exposed that `uvicorn` alone was not enough in this environment, so `websockets>=12.0` is now a backend dependency.
- Ant Design 6 static `message` calls emit error-level dynamic-theme warnings. Components now use `App.useApp()` message instances under the AntD `App` provider.
- Playwright now uses per-run `.e2e-data/<runId>` directories and disables web server reuse so current-user/config state from failed runs cannot affect later generation tests.
- Color recommendation order is data-dependent once custom business schemes exist, so E2E asserts that a recommendation is rendered rather than hard-coding `business_blue` as first.
- System/config endpoints are covered by tests and live curl checks: health includes service/storage/task snapshots, metrics include request counts and durations, config export masks secrets, and config import accepts model profile configs plus custom color schemes.
- JSON logging writes request completion/failure events with request ids to `data/logs/app.log` by default. Tests configure a temporary log directory to verify file creation and request log output without relying on the developer's local `data/`.
- Project documentation now exists under `docs/` for API, architecture, deployment, user guide, and development workflow. README links the docs and aligns FastAPI examples with the frontend's default `http://127.0.0.1:8000/api` backend.
- The installed `planning-with-files` skill only contains `SKILL.md`, `examples.md`, and `reference.md`; the documented `scripts/session-catchup.py` helper is missing in this environment. Continue by reading and updating the three project planning files directly.
- Formal coverage measurement is configured. Backend uses `pytest-cov` with `--cov-fail-under=80` and currently reports 85.50%. Frontend uses Vitest/V8 coverage with 70% thresholds and currently reports Statements 90.32%, Branches 74.30%, Functions 83.90%, Lines 93.96%.
- Performance/concurrency checks are covered in `tests/test_quality_gates.py`: 10-slide PPT generation must finish under 30 seconds, and 3 concurrent generation tasks must finish under 30 seconds.
- Production deployment smoke passed against a built frontend served by `vite preview` on `127.0.0.1:3200` and a temporary backend on `127.0.0.1:8200`; the browser observed production `/api/*` calls, WebSocket completion, and a non-empty `generated.pptx` download.
- The previously tracked final quality gaps from the original design have been addressed locally: production smoke, formal coverage measurement, and performance/concurrency gates all pass.

## Migration Findings

- Source migration is the right baseline: copy the project without `.venv`, `node_modules`, generated reports, local caches, or real `.env`, then reinstall dependencies on the target machine.
- Existing `package-lock.json` enables deterministic frontend installs through `npm ci`.
- Backend dependency versions are range-based in `requirements.txt` and `pyproject.toml`; reproducible offline handoff should use a generated wheelhouse or a future lock file.
- Existing user data can be migrated by copying `data/`, but `data/users/.encryption_key` must travel with user JSON files or stored auth tokens cannot be decrypted.
- `outputs/` contains generated artifacts and should normally be excluded from portable handoff archives unless explicitly needed.
- Added `scripts/setup.*`, `scripts/start-backend.*`, `scripts/start-frontend.*`, `scripts/export-portable.*`, and `scripts/preview-production.sh` for cross-machine setup and smoke testing.
- Added Docker backend/frontend build files plus `docker-compose.yml`; Docker itself is not installed on this machine, so runtime execution could not be tested here.
- Portable archive export was tested. The generated archive excluded `.venv`, `node_modules`, `.env`, `data`, `outputs`, `dist`, coverage reports, and E2E reports by default.
- `scripts/start-backend.sh`, `scripts/start-frontend.sh`, and `scripts/preview-production.sh` were smoke-tested locally on alternate ports and returned healthy HTTP responses.

## Personal Workbench Findings

- The app is now product-shaped as a single-user, local-first workbench. No login, roles, teams, permissions, or multiplayer/online collaboration were added.
- `/api/users/*` remains the backend compatibility namespace, but the frontend now presents those records as model configuration profiles.
- Task history is file-backed under `data/tasks` and can be migrated independently. Completed history downloads still depend on the referenced generated files under `outputs/`.
- Generation failures now preserve both a user-facing `friendly_error` and the technical `error`/`error_type` in task JSON.
- PPTX template import is intentionally lightweight: it validates/imports the file and extracts slide size, master count, font candidates, and colors for style application. It does not clone full PowerPoint masters, animations, complex placeholders, or embedded SmartArt behavior.
- Frontend E2E needed stricter locators after adding history, because completed state and download actions now appear both in the current result panel and the history table.
