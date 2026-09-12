from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from doc_agent.api.deps import get_user_manager
from doc_agent.users.manager import UserManager
from doc_agent.users.models import UserConfig


router = APIRouter(prefix="/api/users", tags=["模型配置档案"])


class CreateUserRequest(BaseModel):
    user_name: str
    nga_endpoint: str
    auth_token: str
    llm_provider: str = "nga"
    llm_model: str = "glm-4.7"
    ppt_renderer: str = "stub"
    default_template: str | None = None
    default_color_scheme: str | None = None


class UpdateUserRequest(BaseModel):
    user_name: str | None = None
    nga_endpoint: str | None = None
    auth_token: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    ppt_renderer: str | None = None
    default_template: str | None = None
    default_color_scheme: str | None = None
    preferences: dict | None = None


class TestConnectionRequest(BaseModel):
    nga_endpoint: str
    auth_token: str


@router.post("/create")
async def create_user(request: CreateUserRequest, manager: UserManager = Depends(get_user_manager)) -> dict:
    try:
        user = manager.create_user(UserConfig(**request.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "user_id": user.user_id, "user": user.model_dump(mode="json")}


@router.get("/list")
async def list_users(manager: UserManager = Depends(get_user_manager)) -> dict:
    return {"users": [user.model_dump(mode="json") for user in manager.list_users()]}


@router.get("/{user_id}")
async def get_user(user_id: str, manager: UserManager = Depends(get_user_manager)) -> dict:
    user = manager.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user.model_dump(mode="json")


@router.put("/{user_id}")
async def update_user(user_id: str, request: UpdateUserRequest, manager: UserManager = Depends(get_user_manager)) -> dict:
    updates = {key: value for key, value in request.model_dump().items() if value is not None}
    try:
        user = manager.update_user(user_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return user.model_dump(mode="json")


@router.delete("/{user_id}")
async def delete_user(user_id: str, manager: UserManager = Depends(get_user_manager)) -> dict:
    return {"success": manager.delete_user(user_id)}


@router.post("/switch/{user_id}")
async def switch_user(user_id: str, manager: UserManager = Depends(get_user_manager)) -> dict:
    try:
        user = manager.switch_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return user.model_dump(mode="json")


@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest) -> dict:
    parsed = urlparse(request.nga_endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"success": False, "message": "NGA endpoint must be an absolute http(s) URL"}
    if not request.auth_token:
        return {"success": False, "message": "Auth token is required"}
    return {"success": True, "message": "配置格式有效；外网阶段仅校验 NGA 连接参数格式，真实调用进内网后接入"}
