"""Schemas for quick reply endpoints."""

from datetime import datetime
import re
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema, PaginatedResponse, PaginationMetadata, PaginationParams

_SHORTCUT_PATTERN = re.compile(r"^[a-z0-9_-]{1,64}$")


class QuickReplyCreate(BaseSchema):
    """Request schema for creating a quick reply."""

    title: str = Field(..., min_length=1, max_length=120)
    shortcut: str = Field(..., min_length=1, max_length=64)
    content: str = Field(..., min_length=1, max_length=2000)
    category: Optional[str] = Field(None, max_length=64)
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=100, ge=0, le=9999)

    @field_validator("shortcut")
    @classmethod
    def validate_shortcut(cls, value: str) -> str:
        normalized = value.strip().lstrip("/").lower()
        if not _SHORTCUT_PATTERN.match(normalized):
            raise ValueError("shortcut must match [a-z0-9_-], length 1-64")
        return normalized


class QuickReplyUpdate(BaseSchema):
    """Request schema for updating a quick reply."""

    title: Optional[str] = Field(None, min_length=1, max_length=120)
    shortcut: Optional[str] = Field(None, min_length=1, max_length=64)
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = Field(None, max_length=64)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0, le=9999)

    @field_validator("shortcut")
    @classmethod
    def validate_shortcut(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lstrip("/").lower()
        if not _SHORTCUT_PATTERN.match(normalized):
            raise ValueError("shortcut must match [a-z0-9_-], length 1-64")
        return normalized


class QuickReplyResponse(BaseSchema):
    """Response schema for a quick reply."""

    id: UUID
    project_id: UUID
    title: str
    shortcut: str
    content: str
    category: Optional[str]
    is_active: bool
    sort_order: int
    usage_count: int
    last_used_at: Optional[datetime]
    created_by: Optional[UUID]
    updated_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class QuickReplyListParams(PaginationParams):
    """Query params for quick reply list."""

    q: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=64)
    active_only: bool = Field(default=False)


class QuickReplyListResponse(PaginatedResponse):
    """Paginated quick reply list response."""

    data: list[QuickReplyResponse]
    pagination: PaginationMetadata
