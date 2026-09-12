# Development Notes

## Verification

Backend:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=doc_agent --cov=app.api --cov-report=term-missing --cov-fail-under=80
.venv/bin/python -m compileall doc_agent app
```

Frontend:

```bash
cd ppt-agent-frontend
npm run build
npm run test:coverage
npm run test:e2e
```

## Current Test Coverage

- IR schema round trips.
- DeckIR v1.1 cards/chart/image schema and stub rendering.
- Agent runner structured request/result and failed-task recording.
- Markdown parsing.
- Stub LLM deck and Word planning.
- NGA and Huawei Skill placeholder boundaries.
- PPTX and DOCX rendering.
- Huawei-style PPTX compliance checking.
- LibreOffice/Poppler preview export error handling.
- End-to-end workflow generation through Python API.
- User token masking and encrypted-at-rest storage.
- Template, color, chart, and SmartArt managers.
- FastAPI user/profile/design/generation/config/system routes.
- WebSocket progress for completed generation tasks.
- Backend coverage gate: 85.50% total coverage with `pytest-cov`, fail-under 80%.
- Backend quality gates for API response time, 10-slide PPT generation under 30 seconds, and 3 concurrent generation tasks under 30 seconds.
- Frontend unit/component coverage gate through Vitest/V8: Statements 90.32%, Branches 74.30%, Functions 83.90%, Lines 93.96%, all thresholds at 70%.
- Browser E2E for Markdown upload, PPTX generation, WebSocket completion, history refresh, and download through Playwright.
- Browser E2E for settings export/import, user creation and switching, template import, color recommendation and creation, chart IR generation, and SmartArt IR generation.
- Browser E2E smoke for dashboard, generator, NGA config, users, templates, colors, charts, SmartArt, and settings routes on desktop and mobile viewports. Each route must become usable within 3 seconds and must not cause document-level horizontal overflow.
- Production preview smoke: build with `VITE_API_BASE_URL` pointed at a temporary backend, serve `dist/` with Vite preview, then verify upload, generation, WebSocket completion, and download against that backend.

## Known Limits

- The Playwright E2E test requires a local Chrome channel and starts isolated servers on `127.0.0.1:8100` and `127.0.0.1:3100`. It writes test state to a per-run `.e2e-data/<runId>` directory.
- Current frontend bundle is large because Ant Design is bundled into the main chunk. Build passes with a Vite chunk-size warning.
- Token encryption is local and pragmatic. Use a managed secret store or KMS for production.
- PPT template application currently affects slide size, metadata, fonts, and colors; it does not yet clone arbitrary slide master layouts, animations, or complex placeholders.
- Real NGA calls and real Huawei Skill rendering are intranet-only adapter work. External development must keep `stub` as the runnable default.

## Adding API Endpoints

Add routers under `doc_agent/api/`, export them in `doc_agent/api/__init__.py`, and include them in `app/api.py`.

Add tests in `tests/test_api_routes.py` or a focused test file. Prefer temporary `DATA_DIR` and `OUTPUT_DIR` with `monkeypatch`.
