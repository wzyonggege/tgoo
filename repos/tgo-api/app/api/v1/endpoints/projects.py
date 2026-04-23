"""Project endpoints."""

from datetime import datetime
import json
from typing import List
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_current_active_user
from app.models import Platform, Project, Staff
from app.schemas import (
    ProjectBridgeChatCandidate,
    ProjectBridgeChatProbeRequest,
    ProjectBridgeChatProbeResponse,
    ProjectBridgeConfigResponse,
    ProjectBridgeConfigUpdate,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.api.common_responses import LIST_RESPONSES

logger = get_logger("endpoints.projects")
router = APIRouter()
TELEGRAM_API_BASE = "https://api.telegram.org"


def _get_project_or_404(db: Session, project_id: UUID) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.deleted_at.is_(None)
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project


def _bridge_response(project: Project) -> ProjectBridgeConfigResponse:
    return ProjectBridgeConfigResponse(
        project_id=project.id,
        bridge_enabled=bool(project.bridge_enabled),
        bridge_bot_token=project.bridge_bot_token,
        bridge_chat_id=project.bridge_chat_id,
        bridge_admin_only=bool(project.bridge_admin_only),
    )


def _get_platform_by_bridge_api_key(
    db: Session,
    *,
    api_key: str,
) -> Platform:
    platform = db.query(Platform).filter(
        Platform.api_key == api_key,
        Platform.deleted_at.is_(None),
    ).first()
    if platform is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid platform_api_key",
        )
    return platform


def _get_platform_for_bridge_read(
    db: Session,
    *,
    project_id: UUID,
    api_key: str,
) -> Platform:
    platform = _get_platform_by_bridge_api_key(db, api_key=api_key)
    if platform.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform does not belong to the requested project",
        )
    return platform


async def _telegram_api_get(bot_token: str, method: str, *, params: dict | None = None) -> dict:
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/{method}"
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        result = response.json()
    if not result.get("ok"):
        description = result.get("description", "Telegram API request failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=description)
    return result


def _extract_group_chats_from_updates(updates: list[dict]) -> dict[str, dict]:
    chats: dict[str, dict] = {}
    for update in updates:
        candidates: list[dict] = []
        message = update.get("message")
        if isinstance(message, dict):
            candidates.append(message.get("chat") or {})
        edited_message = update.get("edited_message")
        if isinstance(edited_message, dict):
            candidates.append(edited_message.get("chat") or {})
        channel_post = update.get("channel_post")
        if isinstance(channel_post, dict):
            candidates.append(channel_post.get("chat") or {})
        my_chat_member = update.get("my_chat_member")
        if isinstance(my_chat_member, dict):
            candidates.append(my_chat_member.get("chat") or {})

        for chat in candidates:
            if not isinstance(chat, dict):
                continue
            chat_type = str(chat.get("type") or "")
            if chat_type not in {"group", "supergroup"}:
                continue
            chat_id = str(chat.get("id") or "").strip()
            if not chat_id:
                continue
            existing = chats.get(chat_id) or {}
            chats[chat_id] = {
                "chat_id": chat_id,
                "title": str(chat.get("title") or existing.get("title") or chat_id),
                "type": chat_type,
                "username": chat.get("username") or existing.get("username"),
            }
    return chats


@router.get(
    "",
    response_model=ProjectListResponse,
    responses=LIST_RESPONSES
)
async def list_projects(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectListResponse:
    """
    List projects.

    Retrieve a list of projects. This endpoint is typically used by system administrators
    to manage multiple tenant projects.
    """
    logger.info(f"User {current_user.username} listing projects")

    # Query projects (non-deleted)
    projects = db.query(Project).filter(
        Project.deleted_at.is_(None)
    ).all()

    project_responses = [ProjectResponse.model_validate(project) for project in projects]

    return ProjectListResponse(data=project_responses)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Create project.

    Create a new project (tenant). This automatically generates an API key for the project
    and publishes a project creation event for AI Service synchronization.
    """
    logger.info(f"User {current_user.username} creating project: {project_data.name}")

    # Generate API key
    api_key = generate_api_key()

    # Create project
    project = Project(
        name=project_data.name,
        api_key=api_key,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    logger.info(f"Created project {project.id} with name: {project.name}")

    return ProjectResponse.model_validate(project)


@router.get(
    "/bridge-config/internal/by-platform",
    response_model=ProjectBridgeConfigResponse,
    include_in_schema=False,
)
async def get_project_bridge_config_internal_by_platform(
    db: Session = Depends(get_db),
    platform_api_key: str | None = None,
    x_platform_api_key: str | None = Header(None, alias="X-Platform-API-Key"),
) -> ProjectBridgeConfigResponse:
    """Internal bridge config lookup using only the platform API key."""
    api_key = platform_api_key or x_platform_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing platform_api_key",
        )

    platform = _get_platform_by_bridge_api_key(db, api_key=api_key)
    project = _get_project_or_404(db, platform.project_id)
    return _bridge_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """Get project details."""
    logger.info(f"User {current_user.username} getting project: {project_id}")

    project = _get_project_or_404(db, project_id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectResponse:
    """
    Update project.

    Update project information. This publishes a project update event
    for AI Service synchronization.
    """
    logger.info(f"User {current_user.username} updating project: {project_id}")

    project = _get_project_or_404(db, project_id)
    # Update fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(project)

    logger.info(f"Updated project {project.id}")

    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/bridge-config", response_model=ProjectBridgeConfigResponse)
async def get_project_bridge_config(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectBridgeConfigResponse:
    """Get project-level Telegram bridge config."""
    logger.info(f"User {current_user.username} getting bridge config for project: {project_id}")
    project = _get_project_or_404(db, project_id)
    return _bridge_response(project)


@router.get(
    "/{project_id}/bridge-config/internal",
    response_model=ProjectBridgeConfigResponse,
    include_in_schema=False,
)
async def get_project_bridge_config_internal(
    project_id: UUID,
    db: Session = Depends(get_db),
    platform_api_key: str | None = None,
    x_platform_api_key: str | None = Header(None, alias="X-Platform-API-Key"),
) -> ProjectBridgeConfigResponse:
    """Internal bridge config lookup for platform service using platform API key."""
    api_key = platform_api_key or x_platform_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing platform_api_key",
        )

    _get_platform_for_bridge_read(db, project_id=project_id, api_key=api_key)
    project = _get_project_or_404(db, project_id)
    return _bridge_response(project)


@router.patch("/{project_id}/bridge-config", response_model=ProjectBridgeConfigResponse)
async def update_project_bridge_config(
    project_id: UUID,
    bridge_data: ProjectBridgeConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectBridgeConfigResponse:
    """Update project-level Telegram bridge config."""
    logger.info(f"User {current_user.username} updating bridge config for project: {project_id}")

    project = _get_project_or_404(db, project_id)
    update_data = bridge_data.model_dump(exclude_unset=True)

    if "bridge_bot_token" in update_data and isinstance(update_data["bridge_bot_token"], str):
        update_data["bridge_bot_token"] = update_data["bridge_bot_token"].strip() or None
    if "bridge_chat_id" in update_data and isinstance(update_data["bridge_chat_id"], str):
        update_data["bridge_chat_id"] = update_data["bridge_chat_id"].strip() or None

    bridge_bot_token = update_data.get("bridge_bot_token", project.bridge_bot_token)
    bridge_enabled = update_data.get("bridge_enabled", project.bridge_enabled)
    bridge_chat_id = update_data.get("bridge_chat_id", project.bridge_chat_id)

    if bridge_enabled:
        if not str(bridge_bot_token or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bridge bot token is required when bridge is enabled",
            )
        if not str(bridge_chat_id or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bridge chat ID is required when bridge is enabled",
            )

    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)

    logger.info(f"Updated bridge config for project {project.id}")
    return _bridge_response(project)


@router.post("/{project_id}/bridge-config/probe-chats", response_model=ProjectBridgeChatProbeResponse)
async def probe_project_bridge_chats(
    project_id: UUID,
    payload: ProjectBridgeChatProbeRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> ProjectBridgeChatProbeResponse:
    """Probe recent Telegram groups visible to the provided bridge bot token."""
    logger.info(f"User {current_user.username} probing Telegram bridge chats for project: {project_id}")
    _get_project_or_404(db, project_id)

    bot_token = payload.bot_token.strip()
    me_result = await _telegram_api_get(bot_token, "getMe")
    bot_info = me_result.get("result") or {}

    warning: str | None = None
    try:
        updates_result = await _telegram_api_get(
            bot_token,
            "getUpdates",
            params={
                "offset": 0,
                "limit": 100,
                "timeout": 0,
                "allowed_updates": json.dumps(["message", "edited_message", "channel_post", "my_chat_member"]),
            },
        )
    except HTTPException as exc:
        detail = str(exc.detail)
        if "can't use getUpdates method while webhook is active" in detail.lower():
            updates_result = {"result": []}
            warning = "当前 Bot 启用了 webhook，无法通过 getUpdates 列出最近群聊。请临时关闭 webhook 或先在目标群内发送一条消息后重试。"
        else:
            raise

    chats_map = _extract_group_chats_from_updates(updates_result.get("result") or [])
    chat_candidates: list[ProjectBridgeChatCandidate] = []
    for chat_id, chat in chats_map.items():
        is_forum = False
        try:
            chat_result = await _telegram_api_get(bot_token, "getChat", params={"chat_id": chat_id})
            chat_detail = chat_result.get("result") or {}
            is_forum = bool(chat_detail.get("is_forum", False))
            if not chat.get("title") and chat_detail.get("title"):
                chat["title"] = str(chat_detail.get("title"))
            if not chat.get("username") and chat_detail.get("username"):
                chat["username"] = str(chat_detail.get("username"))
        except HTTPException:
            pass
        chat_candidates.append(
            ProjectBridgeChatCandidate(
                chat_id=chat_id,
                title=str(chat.get("title") or chat_id),
                type=str(chat.get("type") or "group"),
                username=str(chat.get("username")) if chat.get("username") else None,
                is_forum=is_forum,
            )
        )

    chat_candidates.sort(key=lambda item: (item.title or "").lower())
    if not chat_candidates and warning is None:
        warning = "暂未发现可用群。先把 Bot 拉进目标群，并在群里发送一条消息或触发一次成员变更后再试。"

    return ProjectBridgeChatProbeResponse(
        bot_id=int(bot_info.get("id") or 0),
        bot_username=str(bot_info.get("username")) if bot_info.get("username") else None,
        chats=chat_candidates,
        warning=warning,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """
    Delete project (soft delete).

    Soft delete a project. This publishes a project deletion event
    for AI Service synchronization and cleanup.
    """
    logger.info(f"User {current_user.username} deleting project: {project_id}")

    project = _get_project_or_404(db, project_id)
    # Soft delete
    project.deleted_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Deleted project {project.id}")

    return None
