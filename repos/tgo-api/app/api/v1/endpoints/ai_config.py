"""Endpoints for managing AI provider configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.schemas.ai_config import AIConfigResponse, AIConfigUpdateRequest
from app.services.ai_config_service import get_ai_config, update_ai_config

router = APIRouter()


@router.get(
    "/config",
    response_model=AIConfigResponse,
    summary="Get AI provider configuration",
)
async def read_ai_config(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigResponse:
    """Return the current AI provider configuration. Admins only."""
    config = get_ai_config(db)
    return AIConfigResponse(**config)


@router.put(
    "/config",
    response_model=AIConfigResponse,
    summary="Update AI provider configuration",
)
async def put_ai_config(
    payload: AIConfigUpdateRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin()),
) -> AIConfigResponse:
    """Update AI provider configuration from the settings UI."""
    update_fields = payload.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )

    normalized_provider = update_fields.get("provider")
    if isinstance(normalized_provider, str):
        update_fields["provider"] = normalized_provider.strip() or "custom"

    normalized_base_url = update_fields.get("api_base_url")
    if normalized_base_url is not None:
        base_url = normalized_base_url.rstrip("/")
        if not base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API base URL cannot be empty",
            )
        update_fields["api_base_url"] = base_url

    api_key = update_fields.get("api_key")
    if api_key is not None:
        update_fields["api_key"] = api_key or None

    config = update_ai_config(
        db,
        provider=update_fields.get("provider"),
        api_base_url=update_fields.get("api_base_url"),
        api_key=update_fields.get("api_key"),
        model=update_fields.get("model"),
        completions_path=update_fields.get("completions_path"),
        timeout=update_fields.get("timeout"),
    )
    return AIConfigResponse(**config)
