from __future__ import annotations

import os
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from doc_agent.api import aicoding_router, charts_router, colors_router, generate_router, profiles_router, smartart_router, system_router, templates_router, users_router
from doc_agent.config import get_settings
from doc_agent.utils.logging_utils import configure_json_logging, get_logger
from doc_agent.utils.metrics import app_metrics
from doc_agent.workflow import run_generate


configure_json_logging()
request_logger = get_logger("doc_agent.api.requests")
app = FastAPI(title="doc-agent-mvp", version="0.1.0")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "ppt-agent-frontend" / "dist"
default_cors_origins = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]
extra_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[*default_cors_origins, *extra_cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(aicoding_router)
app.include_router(generate_router)
app.include_router(profiles_router)
app.include_router(users_router)
app.include_router(templates_router)
app.include_router(colors_router)
app.include_router(charts_router)
app.include_router(smartart_router)
app.include_router(system_router)


@app.middleware("http")
async def request_metrics_and_logging(request: Request, call_next):
    request_id = uuid4().hex
    started = time.perf_counter()
    status_code = 500
    app_metrics.begin_request()
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        request_logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "request_id": request_id,
                "client": request.client.host if request.client else None,
            },
        )
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        app_metrics.finish_request(request.url.path, status_code, duration_ms)
        log_method = request_logger.error if status_code >= 500 else request_logger.info
        log_method(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
                "client": request.client.host if request.client else None,
            },
        )


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "ppt_renderer": settings.ppt_renderer,
        "ppt_compliance_gate": settings.ppt_compliance_gate,
    }


@app.post("/generate")
async def generate(request: Request) -> dict[str, object]:
    settings = get_settings()
    form = await request.form()
    upload = form.get("file")
    target = str(form.get("target", "pptx"))
    try:
        slides = int(form.get("slides", settings.default_target_slides))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="slides must be a positive integer") from exc
    if slides < 1:
        raise HTTPException(status_code=400, detail="slides must be a positive integer")
    if target not in {"pptx", "docx"}:
        raise HTTPException(status_code=400, detail="target must be pptx or docx")
    if upload is None or not hasattr(upload, "filename"):
        raise HTTPException(status_code=400, detail="multipart form field 'file' is required")

    api_dir = settings.output_dir / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    source_suffix = Path(upload.filename).suffix.lower()
    if source_suffix not in {".md", ".docx", ".pptx", ".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="file must be md, docx, pptx, xlsx, or xlsm")

    file_id = uuid4().hex
    input_path = api_dir / f"{file_id}{source_suffix}"
    output_path = api_dir / f"{file_id}.{target}"
    input_path.write_bytes(await upload.read())

    try:
        result = run_generate(input_path, target, output_path, target_slide_count=slides)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "file_id": result.name,
        "download_url": f"/download/{result.name}",
        "warnings": [],
    }


@app.get("/download/{file_id}")
def download(file_id: str) -> FileResponse:
    output_dir = get_settings().output_dir / "api"
    safe_name = Path(file_id).name
    if safe_name != file_id:
        raise HTTPException(status_code=400, detail="file_id must be a file name")
    path = output_dir / safe_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, filename=path.name)


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="frontend dist not found; run npm run build or use scripts/export-runtime-bundle.sh")
    return FileResponse(index_path)


@app.get("/{frontend_path:path}", include_in_schema=False)
def frontend_asset_or_spa(frontend_path: str) -> FileResponse:
    if frontend_path.startswith(("api/", "download/")) or frontend_path in {"health", "generate"}:
        raise HTTPException(status_code=404, detail="not found")
    candidate = (FRONTEND_DIST / frontend_path).resolve()
    try:
        candidate.relative_to(FRONTEND_DIST.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid frontend path") from exc
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return frontend_index()
