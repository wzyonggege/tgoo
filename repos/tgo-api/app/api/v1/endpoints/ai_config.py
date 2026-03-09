"""Endpoints for managing AI reply integration configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin, require_permission
from app.schemas.ai_config import (
    AIConfigCreateRequest,
    AIConfigListResponse,
    AIConfigOptionListResponse,
    AIConfigOptionResponse,
    AIConfigResponse,
    AIConfigUpdateRequest,
)
from app.services.ai_config_service import (
    AIConfigNotFoundError,
    create_ai_config,
    delete_ai_config,
    get_ai_config,
    get_ai_config_by_id,
    list_ai_configs,
    update_ai_config,
)

router = APIRouter()


@router.get(
    "/config",
    response_model=AIConfigResponse,
    summary="Get default AI reply configuration",
)
async def read_ai_config(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigResponse:
    """Return the current default AI reply configuration. Admins only."""
    config = get_ai_config(db)
    return AIConfigResponse(**config)


@router.put(
    "/config",
    response_model=AIConfigResponse,
    summary="Update default AI reply configuration",
)
async def put_ai_config(
    payload: AIConfigUpdateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigResponse:
    """Backward-compatible update for the current default AI reply configuration."""
    update_fields = payload.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )

    current = get_ai_config(db)
    updated = update_ai_config(
        db,
        current["id"],
        name=update_fields.get("name"),
        provider=update_fields.get("provider"),
        api_base_url=update_fields.get("api_base_url"),
        api_key=update_fields.get("api_key"),
        model=update_fields.get("model"),
        completions_path=update_fields.get("completions_path"),
        timeout=update_fields.get("timeout"),
        is_default=True,
    )
    return AIConfigResponse(**updated)


@router.get(
    "/configs/options",
    response_model=AIConfigOptionListResponse,
    summary="List AI reply configuration options",
)
async def read_ai_config_options(
    db: Session = Depends(get_db),
    _user=Depends(require_permission("platforms:update")),
) -> AIConfigOptionListResponse:
    """Return safe AI reply config options for platform/channel selection."""
    configs = [
        AIConfigOptionResponse(
            id=item["id"],
            name=item["name"],
            provider=item["provider"],
            is_default=item["is_default"],
        )
        for item in list_ai_configs(db)
    ]
    return AIConfigOptionListResponse(items=configs)


@router.get(
    "/configs",
    response_model=AIConfigListResponse,
    summary="List AI reply configurations",
)
async def read_ai_configs(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigListResponse:
    """Return all AI reply configurations. Admins only."""
    configs = [AIConfigResponse(**item) for item in list_ai_configs(db)]
    return AIConfigListResponse(items=configs)


@router.post(
    "/configs",
    response_model=AIConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI reply configuration",
)
async def post_ai_config(
    payload: AIConfigCreateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigResponse:
    """Create a new AI reply configuration. Admins only."""
    created = create_ai_config(
        db,
        name=payload.name,
        provider=payload.provider.strip() or "custom",
        api_base_url=payload.api_base_url,
        api_key=payload.api_key,
        model=payload.model,
        completions_path=payload.completions_path,
        timeout=payload.timeout,
        is_default=payload.is_default,
    )
    return AIConfigResponse(**created)


@router.patch(
    "/configs/{config_id}",
    response_model=AIConfigResponse,
    summary="Update AI reply configuration",
)
async def patch_ai_config(
    config_id: str,
    payload: AIConfigUpdateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigResponse:
    """Update an AI reply configuration. Admins only."""
    update_fields = payload.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )

    try:
        updated = update_ai_config(
            db,
            config_id,
            name=update_fields.get("name"),
            provider=update_fields.get("provider"),
            api_base_url=update_fields.get("api_base_url"),
            api_key=update_fields.get("api_key"),
            model=update_fields.get("model"),
            completions_path=update_fields.get("completions_path"),
            timeout=update_fields.get("timeout"),
            is_default=update_fields.get("is_default"),
        )
    except AIConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI config not found") from exc
    return AIConfigResponse(**updated)


@router.delete(
    "/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete AI reply configuration",
)
async def remove_ai_config(
    config_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> Response:
    """Delete an AI reply configuration. Admins only."""
    try:
        get_ai_config_by_id(db, config_id)
        delete_ai_config(db, config_id)
    except AIConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI config not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
