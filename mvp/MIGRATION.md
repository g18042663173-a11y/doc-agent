# Migration Guide

This project supports four transfer modes:

1. Windows 11 runtime zip: best path for Windows intranet desktops. It includes embedded Python, installed runtime dependencies, and built frontend assets. No pip/npm install runs on the target machine.
2. Docker image tar: fastest when Docker is available. No pip/npm install runs on the target machine.
3. Runtime offline bundle: includes Python wheels and built frontend assets. The target machine runs offline pip only and does not need Node.js/npm for normal use.
4. Source archive: smallest package, but target machine must install Python and npm dependencies.

Do not copy machine-local dependency folders such as `.venv/` or `ppt-agent-frontend/node_modules/`; use the Windows runtime zip, Docker images, or a platform-matched `wheelhouse/` instead.

## What To Send

Use the source export script to create a clean archive:

```bash
scripts/export-portable.sh
```

The archive is written to `release/` and excludes local secrets, virtualenvs, node modules, build outputs, test reports, `data/`, and generated `outputs/`.

For a faster intranet setup, build a runtime archive on a machine that matches the target OS, CPU architecture, and Python version:

```bash
scripts/export-runtime-bundle.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export-runtime-bundle.ps1
```

For Windows 11 intranet desktops, prefer the no-install runtime zip. Build it on an external-network Windows 11 machine with the same CPU architecture:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export-windows-runtime.ps1
```

If the build machine cannot download Python from python.org, download the matching Python embeddable zip once and pass it explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export-windows-runtime.ps1 -PythonEmbedZip C:\packages\python-3.12.2-embed-amd64.zip
```

The runtime archive includes:

- `wheelhouse/` for offline Python installation in the generic runtime bundle
- `ppt-agent-frontend/dist/` so the backend can serve the UI directly
- source code, templates, examples, docs, and scripts

The Windows runtime zip additionally includes:

- `runtime/python/` with the Python embeddable runtime
- Python packages already installed under `runtime/python/Lib/site-packages`
- `Start-DocAgent.cmd` for one-step startup

It still excludes `.env`, `.venv/`, `node_modules/`, `data/`, and `outputs/` by default.

If Docker is available on both sides, export images instead:

```bash
scripts/export-docker-images.sh
```

Transfer the generated `.tar` plus this project directory. On the intranet machine:

```bash
docker load -i release/doc-agent-mvp-docker-images-YYYYMMDD-HHMMSS.tar
docker compose up -d
```

To include existing app state such as users, custom templates, and color schemes:

```bash
INCLUDE_DATA=1 scripts/export-portable.sh
```

When including users, keep `data/users/.encryption_key` together with the user JSON files. Stored auth tokens cannot be decrypted without that key.

Generated documents are excluded by default. Include them only when needed:

```bash
INCLUDE_OUTPUTS=1 scripts/export-portable.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export-portable.ps1
powershell -ExecutionPolicy Bypass -File scripts/export-portable.ps1 -IncludeData
```

## Target Machine Requirements

Windows runtime zip:

- Windows 11 x64 or matching architecture
- No Python, Node.js, npm, or pip install required

Source install:

- Python 3.11 or newer
- Node.js with npm
- Network access to install Python/npm dependencies, unless using a runtime offline bundle

Docker install:

- Docker with Compose support

## macOS/Linux Source Install

From the unpacked project directory:

```bash
scripts/setup.sh
```

Start backend and frontend in two terminals:

```bash
scripts/start-backend.sh
scripts/start-frontend.sh
```

Open:

```text
http://127.0.0.1:3000/
```

Useful overrides:

```bash
HOST=0.0.0.0 PORT=8000 scripts/start-backend.sh
HOST=0.0.0.0 PORT=3000 scripts/start-frontend.sh
SKIP_FRONTEND=1 scripts/setup.sh
OFFLINE=1 scripts/setup.sh
```

## macOS/Linux Runtime Offline Install

Use this when you received a `doc-agent-mvp-runtime-*.zip` built on a matching platform:

```bash
scripts/setup-runtime.sh
scripts/start-backend.sh
```

Open:

```text
http://127.0.0.1:8000/
```

In this mode the backend serves `ppt-agent-frontend/dist/`, so Node.js/npm is not needed on the target machine for normal use.

## Windows Source Install

From PowerShell in the unpacked project directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Start backend and frontend in two terminals:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-frontend.ps1
```

Open:

```text
http://127.0.0.1:3000/
```

## Windows Runtime Offline Install

Use this when the runtime bundle was built on a matching Windows/Python environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-runtime.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

Open:

```text
http://127.0.0.1:8000/
```

## Windows No-Install Runtime

Use this for Windows 11 intranet desktops when you received `doc-agent-win11-runtime-*.zip`:

```text
1. Unzip the archive.
2. Double-click Start-DocAgent.cmd.
3. Open http://127.0.0.1:8000/ if the browser does not open automatically.
```

This path uses the embedded Python under `runtime/python/` and the built frontend under `ppt-agent-frontend/dist/`. It does not run pip or npm on the intranet machine.

## Docker Run

From the project root:

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:3000/
```

The backend is exposed at:

```text
http://127.0.0.1:8000/
```

Docker Compose mounts local `data/` and `outputs/` into the backend container, so model profiles and generated files persist across container restarts.

To point the frontend build at a different browser-visible API URL:

```bash
VITE_API_BASE_URL=http://your-host:8000/api docker compose up --build
```

## Production-Like Local Preview

This builds the frontend static bundle, starts a temporary backend, and serves the built files through Vite preview:

```bash
scripts/preview-production.sh
```

Open:

```text
http://127.0.0.1:3200/
```

## Existing Data Migration

Copy these directories when you want to keep local application state:

```text
data/users
data/templates
data/colors
data/tasks
outputs
```

Copy `data/uploads` only if you need the original uploaded source files as well as generated outputs. History records in `data/tasks` can still download completed results when the referenced files under `outputs/` are present.

Do not publish real `.env` files, API keys, confidential input files, or generated confidential documents. If you copy `data/users`, include `data/users/.encryption_key` or recreate model profile tokens on the target machine.

## Offline Python Dependencies

On a machine with internet access:

```bash
python -m pip wheel -r requirements-runtime.txt -w wheelhouse
```

Include `wheelhouse/` in the transfer and install on the target:

```bash
OFFLINE=1 scripts/setup.sh
```

For Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Offline
```

Important: Python wheels are platform-specific. A wheelhouse built on macOS may not install on Windows or Linux. Build the runtime bundle on the same OS/CPU/Python line as the intranet machine, or use Docker image export.
