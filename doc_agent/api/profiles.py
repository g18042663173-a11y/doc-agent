from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException

from doc_agent.api.deps import get_user_manager
from doc_agent.api.users import CreateUserRequest, TestConnectionRequest, UpdateUserRequest
from doc_agent.users.manager import UserManager
from doc_agent.users.models import UserConfig


router = APIRouter(prefix="/api/profiles", tags=["模型配置档案"])


def _profile_payload(user: UserConfig) -> dict:
    payload = user.model_dump(mode="json")
    payload["profile_id"] = user.user_id
    return payload


@router.post("/create")
async def create_profile(request: CreateUserRequest, manager: UserManager = Depends(get_user_manager)) -> dict:
    try:
        profile = manager.create_user(UserConfig(**request.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = _profile_payload(profile)
    return {"success": True, "profile_id": profile.user_id, "user_id": profile.user_id, "profile": payload, "user": profile.model_dump(mode="json")}


@router.get("/list")
async def list_profiles(manager: UserManager = Depends(get_user_manager)) -> dict:
    profiles = [_profile_payload(user) for user in manager.list_users()]
    return {"profiles": profiles, "users": [dict(profile, user_id=profile["user_id"]) for profile in profiles]}


@router.get("/{profile_id}")
async def get_profile(profile_id: str, manager: UserManager = Depends(get_user_manager)) -> dict:
    profile = manager.get_user(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _profile_payload(profile)


@router.put("/{profile_id}")
async def update_profile(profile_id: str, request: UpdateUserRequest, manager: UserManager = Depends(get_user_manager)) -> dict:
    updates = {key: value for key, value in request.model_dump().items() if value is not None}
    try:
        profile = manager.update_user(profile_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _profile_payload(profile)


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, manager: UserManager = Depends(get_user_manager)) -> dict:
    return {"success": manager.delete_user(profile_id)}


@router.post("/switch/{profile_id}")
async def switch_profile(profile_id: str, manager: UserManager = Depends(get_user_manager)) -> dict:
    try:
        profile = manager.switch_user(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _profile_payload(profile)


@router.post("/test-connection")
async def test_profile_connection(request: TestConnectionRequest) -> dict:
    parsed = urlparse(request.nga_endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"success": False, "message": "NGA endpoint must be an absolute http(s) URL"}
    if not request.auth_token:
        return {"success": False, "message": "Auth token is required"}
    return {"success": True, "message": "配置格式有效；外网阶段仅校验模型配置档案参数格式，真实调用进内网后接入"}
