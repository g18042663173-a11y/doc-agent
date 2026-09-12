from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from doc_agent.api.task_history import TaskHistoryManager, TaskMetadata
from doc_agent.api.deps import get_user_manager
from doc_agent.agent import AgentRunRequest, AgentRunner
from doc_agent.config import get_settings
from doc_agent.users.manager import UserManager


router = APIRouter(prefix="/api/generate", tags=["文档生成"])


class GenerateResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ProgressResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    current_step: str
    result: str | None = None
    error: str | None = None
    error_type: str | None = None
    friendly_error: str | None = None
    compliance_report: dict | None = None
    metadata: dict | None = None


@router.post("/start")
async def start_generation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target: Literal["pptx", "docx"] = Form("pptx"),
    slides: int = Form(8),
    template_id: str | None = Form(None),
    color_scheme_id: str | None = Form(None),
    user_id: str | None = Form(None),
    profile_id: str | None = Form(None),
    user_manager: UserManager = Depends(get_user_manager),
) -> GenerateResponse:
    source_suffix = Path(file.filename or "").suffix.lower()
    if source_suffix not in {".md", ".docx", ".pptx", ".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="仅支持 .md、.docx、.pptx、.xlsx、.xlsm 文件，请重新选择输入文件。")
    if slides < 1:
        raise HTTPException(status_code=400, detail="页数必须是正整数，请重新选择生成页数。")
    active_profile_id = profile_id or user_id
    if active_profile_id and user_manager.get_user(active_profile_id) is None:
        raise HTTPException(status_code=404, detail="模型配置档案不存在，请重新选择或先保存配置档案。")

    task_id = uuid.uuid4().hex
    settings = get_settings()
    upload_dir = settings.data_dir / "uploads" / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    input_path = upload_dir / Path(file.filename or f"input{source_suffix}").name
    input_path.write_bytes(await file.read())

    output_path = settings.output_dir / task_id / f"generated.{target}"
    task_metadata = TaskMetadata(
        original_filename=file.filename,
        source_type=source_suffix.lstrip("."),
        target=target,
        slides=slides,
        template_id=template_id,
        color_scheme_id=color_scheme_id,
        user_id=active_profile_id,
        profile_id=active_profile_id,
    )
    _write_task(task_id, "queued", 0, "任务已创建", metadata=task_metadata)
    background_tasks.add_task(
        _run_generation_task,
        task_id,
        AgentRunRequest(
            input_path=input_path,
            target=target,
            output_path=output_path,
            slides=slides,
            template_id=template_id,
            color_scheme_id=color_scheme_id,
            user_id=active_profile_id,
            profile_id=active_profile_id,
        ),
    )
    return GenerateResponse(task_id=task_id, status="processing", message="文档生成任务已启动")


@router.get("/history")
async def list_history(limit: int = 50) -> dict:
    tasks = TaskHistoryManager().list_tasks(limit=max(1, min(limit, 200)))
    return {"tasks": [task.model_dump(mode="json") for task in tasks]}


@router.get("/history/{task_id}")
async def get_history(task_id: str) -> dict:
    task = TaskHistoryManager().get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="生成记录不存在，请刷新历史列表后重试。")
    return task.model_dump(mode="json")


@router.delete("/history/{task_id}")
async def delete_history(task_id: str, delete_files: bool = False) -> dict:
    deleted = TaskHistoryManager().delete_task(task_id, delete_files=delete_files)
    return {"success": deleted}


@router.get("/progress/{task_id}")
async def get_progress(task_id: str) -> ProgressResponse:
    task = _read_task(task_id)
    if task is None:
        return ProgressResponse(task_id=task_id, status="not_found", progress=0, current_step="Unknown", error="Task not found")
    return ProgressResponse(**task)


@router.get("/download/{task_id}")
async def download_result(task_id: str) -> FileResponse:
    task = _read_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="生成记录不存在，请刷新历史列表后重试。")
    result = task.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="该任务还没有可下载结果，请等待生成完成后再试。")
    path = Path(result)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="结果文件已丢失，请复用历史参数重新生成。")
    return FileResponse(path, filename=path.name)


@router.websocket("/ws/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            task = _read_task(task_id) or {
                "task_id": task_id,
                "status": "not_found",
                "progress": 0,
                "current_step": "Unknown",
                "result": None,
                "error": "Task not found",
            }
            await websocket.send_json(task)
            if task.get("status") in {"completed", "failed", "not_found"}:
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


def _run_generation_task(task_id: str, request: AgentRunRequest) -> None:
    AgentRunner().run_task(task_id, request)


def _write_task(
    task_id: str,
    status: str,
    progress: int,
    current_step: str,
    result: str | None = None,
    error: str | None = None,
    error_type: str | None = None,
    friendly_error: str | None = None,
    compliance_report: dict | None = None,
    metadata: TaskMetadata | dict | None = None,
) -> None:
    manager = TaskHistoryManager()
    if metadata is not None:
        manager.create_task(task_id, status, progress, current_step, metadata)
    else:
        manager.update_task(task_id, status, progress, current_step, result, error, error_type, friendly_error, compliance_report)


def _read_task(task_id: str) -> dict | None:
    task = TaskHistoryManager().get_task(task_id)
    if task is None:
        return None
    return task.model_dump(mode="json")
