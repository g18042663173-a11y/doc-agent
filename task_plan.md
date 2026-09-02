# PPT Agent Development Plan

## Goal

Develop `doc-agent-mvp` toward the pasted "PPT Agent - intelligent document generation system" technical design while preserving the existing runnable MVP.

## Source Requirements

- Source design: `/Users/guoshuaiqi/.codex/attachments/6099929e-4354-48bf-bb44-275de8cf8ad5/pasted-text-1.txt`
- Current project root: `/Users/guoshuaiqi/Desktop/doc-agent-mvp`
- Existing baseline: Python MVP with CLI, FastAPI, Streamlit, parsers, planners, renderers, validators, and mock LLM.

## Scope Strategy

The pasted design is a 1-2 month full product plan. Implement it incrementally without narrowing the final objective:

1. Backend foundation and API expansion first.
2. Keep old CLI and `/generate` behavior compatible.
3. Add tests for each new module/API before calling the work complete.
4. Add frontend only after backend endpoints and data models are stable.

## Phases

| Phase | Status | Deliverable |
| --- | --- | --- |
| 0. Planning | complete | Persistent plan for staged implementation |
| 1. Backend domain modules | complete | Users, templates, colors, charts, SmartArt managers and models |
| 2. API layer | complete | `/api/users`, `/api/templates`, `/api/colors`, `/api/charts`, `/api/smartart`, `/api/generate/*`, progress tracking, download |
| 3. Workflow integration | complete | Generation accepts template/color/user options without breaking existing `run_generate` |
| 4. Tests and docs | complete | Unit/integration tests plus README/API notes |
| 5. Frontend scaffold | complete | React/Vite/TypeScript app and API client |
| 6. Frontend pages | complete | Dashboard, generator, user/config, templates, colors, charts, SmartArt |
| 7. End-to-end validation | complete | Full workflow through API and frontend |
| 8. Migration and handoff tooling | complete | Scripts, Docker, packaging guidance, and docs for running on another machine |
| 9. Personal workbench polish | complete | Single-user workbench, generation history, template style summaries, and clearer local workflow |

## First Implementation Slice

Build Phases 1-4 enough to satisfy the backend acceptance criteria in the design:

- Users can create, list, get, update, delete, and switch configurations.
- Sensitive auth tokens are stored encrypted or obfuscated at rest with no plaintext leakage through list/get responses by default.
- Template manager can list built-in templates, import valid PPTX templates, and apply template metadata to a deck IR.
- Color manager can list built-in schemes, create custom schemes, validate hex colors, and recommend schemes by scenario.
- Chart manager can recommend chart types and return chart IR.
- SmartArt manager can return process/hierarchy/cycle/timeline-style IR.
- API exposes the new module endpoints under `/api/*`.
- Async generation can start a task, write progress to `data/tasks`, and download completed output.
- Existing `POST /generate`, CLI, and tests keep working.

## Backend Implementation Completed

- Added file-backed user, template, color, chart, and SmartArt modules under `doc_agent/`.
- Added `/api/users`, `/api/templates`, `/api/colors`, `/api/charts`, `/api/smartart`, and `/api/generate/*` routers.
- Added `/api/system/health`, `/api/system/metrics`, `/api/config/export`, and `/api/config/import`.
- Added async generation task state under `data/tasks`, upload state under `data/uploads`, result download by task id, and WebSocket task progress at `/api/generate/ws/{task_id}`.
- Extended `run_generate` with optional runtime settings and style profile parameters while preserving the existing CLI and legacy API call shape.
- Added tests for user token storage, design managers, new API routes, async generation, WebSocket completion, system metrics, config import/export, request logging, legacy API error paths, parser routing, performance, and concurrency.
- Added JSON request logging with request ids, log files under `data/logs`, and in-memory metrics snapshots.
- Added docs under `docs/` for API, architecture, deployment, user guide, and development workflow.
- Verification: `.venv/bin/python -m pytest` passed with 23 tests; backend coverage passed at 85.50% with `--cov-fail-under=80`.

## Frontend Implementation Completed

- Added `ppt-agent-frontend` with React, Vite, TypeScript, Ant Design, Zustand, Axios, and React Router.
- Added API client, WebSocket progress helper, persistent user store, document progress store, and template/color store.
- Added operational pages for dashboard, smart/outline generation, template management, color schemes, chart recommendation, SmartArt IR, model profile configuration, data import/manage, preview, and export.
- Verification: `npm install` completed with no vulnerabilities; `npm run build` passed.
- Validation completed: backend and frontend dev servers run together; HTTP health/templates/generate/download work; browser-rendered dashboard loads backend template/color data after adding CORS; generation UI uses WebSocket progress with HTTP polling fallback; WebSocket completion is covered by API integration tests; Playwright E2E covers real browser Markdown upload, PPTX generation, WebSocket completion, download, settings import/export, user create/test/list/switch, template import, color recommendation/create, chart IR generation, SmartArt IR generation, and desktop/mobile smoke for dashboard, generator, NGA config, users, templates, colors, charts, SmartArt, and settings routes with 3-second usability and no document-level horizontal overflow checks.
- Final quality gates passed: production preview smoke against a built frontend, backend coverage 85.50% against an 80% target, frontend coverage Statements 90.32% / Branches 74.30% / Functions 83.90% / Lines 93.96% against 70% targets, 10-slide PPT generation under 30 seconds, and 3 concurrent generation tasks under 30 seconds.

## Personal Workbench Implementation Completed

- Reworked the dashboard into a local personal workbench with model profile status, recent generation history, template/color stats, and quick actions.
- Added `doc_agent/api/task_history.py` and history endpoints for list/detail/delete while preserving existing async generation and download APIs.
- Extended generation metadata with original filename, source/target, slide count, template, color scheme, model profile, timestamps, result path, and structured friendly errors.
- Added template import style analysis for PPTX slide size, master/slide counts, font candidates, and theme/common colors.
- Applied imported template style overrides to PPTX rendering for slide size, fonts, and colors, with fallback to the existing style profile.
- Updated the generator page with a single-page workflow: upload, parameters, model profile, progress, result download, local history, reuse parameters, and delete history.
- Reframed frontend "用户" wording as "模型配置档案" while keeping `/api/users` compatibility.
- Updated backup/restore, template import, docs, tests, and E2E locators for the personal local workflow.
- Verification: `.venv/bin/python -m pytest` passed with 23 tests; backend coverage passed at 85.50%; `.venv/bin/python -m compileall doc_agent app` passed; `npm run build` passed with the known Vite chunk-size warning; `npm run test:coverage` passed with Statements 90.32%, Branches 74.30%, Functions 83.90%, Lines 93.96%; `npm run test:e2e` passed with 8 tests.

## Review Checkpoints

The obsolete collaboration tooling has been removed at the user's request because it was affecting performance. Use local tests, direct code inspection, and user-visible summaries for review unless the user explicitly installs/enables another review mechanism.

## Migration Tooling Plan

- Add POSIX shell scripts for setup, backend start, frontend start, production preview, and portable archive creation.
- Add PowerShell setup/start scripts so Windows users are not forced through WSL.
- Add Dockerfile and docker-compose for a single-command containerized runtime with persisted `data/` and `outputs/`.
- Add `.dockerignore` and archive exclusions so generated state, virtualenvs, node modules, caches, and secrets are not copied into handoff packages.
- Add `MIGRATION.md` and update README/docs to describe source-copy, data migration, offline dependency, and Docker paths.
- Completed with shell and PowerShell scripts, Docker/Compose files, `.dockerignore`, migration archive export, and README/deployment documentation updates.

## Personal Workbench Plan

- Keep the app single-user and local-first; do not add login, roles, teams, or permissions.
- Reframe "users" in the frontend as model configuration profiles while preserving backend API compatibility.
- Add generation history on top of `data/tasks`, including generation parameters, result paths, status, and friendly errors.
- Improve template import analysis enough for style application: slide size, master count, fonts, and common colors.
- Rework the dashboard into a personal workbench and make the generation page show recent results plus actionable states.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| planning-with-files templates missing at expected path | Tried to read `templates/task_plan.md`, `templates/findings.md`, `templates/progress.md` | Created planning files manually using the skill rules |
| Obsolete collaboration tooling unavailable and later unwanted | Tried the earlier pasted collaboration flow, then found the local installer path | User requested removal; ran official uninstall and removed the project plan dependency |
| Browser context upload verification blocked | Browser control API does not expose a supported file chooser upload method, and page evaluate lacks `FormData`/`fetch` | Verified UI controls in browser, and covered upload/generate/download/WebSocket through HTTP/TestClient instead |
| planning-with-files catchup script missing | Tried to run the documented `scripts/session-catchup.py` from the installed skill path | Logged the missing helper path and continued from existing `task_plan.md`, `findings.md`, and `progress.md` |
| Real Uvicorn WebSocket handshake failed in E2E | Playwright browser connected to `/api/generate/ws/{task_id}`, but Uvicorn lacked a WebSocket protocol package and returned 404 | Added `websockets>=12.0` to backend dependencies, installed it locally, and reran Playwright E2E successfully |
| Mobile layout pushed content below full navigation and later overflowed on colors page | Added responsive page-load E2E; it failed because the mobile sidebar occupied the first viewport, and then because `/design/colors` caused document-level horizontal overflow | Replaced mobile sidebar with sticky horizontal navigation and constrained mobile tables/inline forms so route smoke tests pass on desktop and mobile |
| AntD static message warning failed no-console E2E checks | Interaction E2E exposed `Warning: [antd: message] Static function can not consume context like dynamic theme` | Wrapped the app in AntD `App` and moved component notifications to `App.useApp()` message instances |
| E2E generation inherited a previous OpenAI-compatible current user | Failed E2E runs left `.e2e-data` with a switched user, causing mock generation to use openai-compatible mode without the package installed | Made Playwright use per-run `.e2e-data/<runId>` directories and disabled server reuse |
| Color recommendation test assumed `business_blue` was always the first recommendation | Imported/custom business schemes can rank before the system scheme | Added a stable recommendation test id and asserted a non-empty recommendation instead of a hard-coded scheme id |
| Production smoke Playwright helper could not resolve frontend dev dependency from project root | Ran a one-off Node script from the backend root, where `@playwright/test` is not installed | Re-ran the script from `ppt-agent-frontend`, where the dependency is installed, and the smoke passed |
| Docker command unavailable on this machine | Tried `docker compose config` to validate the new compose runtime | Docker is not installed locally; validated `docker-compose.yml` through YAML parsing and file checks instead |
