# Deployment Guide

## Local Development

Backend:

```bash
scripts/setup.sh
scripts/start-backend.sh
```

Frontend:

```bash
scripts/start-frontend.sh
```

Open:

```text
http://127.0.0.1:3000/
```

## Environment

Copy `.env.example` to `.env` and adjust:

```env
LLM_PROVIDER=stub
PPT_RENDERER=stub
PPT_COMPLIANCE_GATE=warn
USE_LANGGRAPH=false
DATA_DIR=data
OUTPUT_DIR=outputs
LOG_DIR=data/logs
LOG_LEVEL=INFO
CORS_ORIGINS=http://127.0.0.1:3000
```

`mock` and `python_pptx` are accepted as compatibility aliases.

For local relay testing of the main agent model call:

```bash
.venv/bin/python scripts/local_llm_relay.py
```

```env
LLM_PROVIDER=local_relay
LLM_BASE_URL=http://127.0.0.1:8765/v1
LLM_API_KEY=EMPTY
LLM_MODEL=glm-4.7
PPT_RENDERER=stub
```

The built-in relay returns deterministic stub JSON over HTTP. Replace the relay internals with a real local model proxy when one is available; the main generation workflow does not change.

For company NGA/GLM deployment:

```env
LLM_PROVIDER=nga
LLM_BASE_URL=http://internal-nga
LLM_API_KEY=replace-me
LLM_MODEL=glm-4.7
PPT_RENDERER=hw_skill
PPT_COMPLIANCE_GATE=error
```

The external build does not implement the real `NGAClient` or `HuaweiSkillRenderer` calls. Wire those two adapters inside the intranet, then run the smoke tests below.

## Intranet Fast Paths

Fastest path for Windows 11 desktops:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export-windows-runtime.ps1
```

Build this on an external-network Windows 11 machine with the same CPU architecture as the intranet target. Transfer `release/doc-agent-win11-runtime-*.zip` to the intranet machine, unzip it, and run:

```powershell
Start-DocAgent.cmd
```

Open:

```text
http://127.0.0.1:8000/
```

No Python, pip, Node.js, or npm install runs on the target machine.

Fastest path when Docker is allowed:

```bash
scripts/export-docker-images.sh
```

Transfer the image tar and project files to the intranet machine:

```bash
docker load -i release/doc-agent-mvp-docker-images-YYYYMMDD-HHMMSS.tar
docker compose up -d
```

No pip or npm install runs on the target machine.

Generic fast path without Docker:

```bash
scripts/export-runtime-bundle.sh
```

Build this on a machine matching the intranet target OS, CPU, and Python version. On the target:

```bash
scripts/setup-runtime.sh
scripts/start-backend.sh
```

Open:

```text
http://127.0.0.1:8000/
```

The backend serves `ppt-agent-frontend/dist/` directly, so Node.js/npm is not needed for normal use. This path still runs offline pip on the target machine; use the Windows runtime zip above when you want a pure unzip-and-run workflow.

## Production Shape

Recommended production layout:

```text
Option A: FastAPI serves built frontend dist directly
└── http://host:8000/

Option B: Nginx serves frontend dist and reverse proxies /api and /download

FastAPI
└── gunicorn/uvicorn workers

Local filesystem
├── data/
└── outputs/
```

Build frontend:

```bash
cd ppt-agent-frontend
VITE_API_BASE_URL=https://your-domain/api npm run build
```

Run backend:

```bash
gunicorn app.api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

The backend needs a WebSocket protocol implementation for `/api/generate/ws/{task_id}`. The project includes `websockets` in `requirements-runtime.txt`; keep it installed in production.

## Docker Deployment

For a portable local/container deployment:

```bash
docker compose up --build
```

Frontend:

```text
http://127.0.0.1:3000/
```

Backend:

```text
http://127.0.0.1:8000/
```

Compose persists backend state through local bind mounts:

```text
./data    -> /app/data
./outputs -> /app/outputs
```

Set `VITE_API_BASE_URL` before `docker compose up --build` if the browser should call a different public API URL.

## Production Smoke Test

For a local production-like smoke, build the frontend against a temporary backend and serve the static bundle:

```bash
scripts/preview-production.sh
```

Open `http://127.0.0.1:3200/generate/smart`, upload a Markdown file, generate a PPTX, and confirm WebSocket completion plus a non-empty download.

## Operational Checks

```bash
curl http://127.0.0.1:8000/api/system/health
curl http://127.0.0.1:8000/api/system/metrics
```

Logs are JSON lines in `data/logs/app.log`, rotated daily with 30 retained files.

## Backup

Back up these directories:

```text
data/users
data/templates
data/colors
outputs
```

Do not publish `.env`, `data/users/.encryption_key`, real API keys, or confidential generated files.
