"""Project schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, SoftDeleteMixin, TimestampMixin


class ProjectBase(BaseSchema):
    """Base project schema."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name"
    )


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    pass


class ProjectUpdate(BaseSchema):
    """Schema for updating a project."""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated project name"
    )


class ProjectBridgeConfigUpdate(BaseSchema):
    """Schema for updating project-level Telegram bridge config."""

    bridge_enabled: Optional[bool] = Field(
        None,
        description="Whether project-level Telegram bridge is enabled",
    )
    bridge_bot_token: Optional[str] = Field(
        None,
        max_length=255,
        description="Independent Telegram bridge bot token",
    )
    bridge_chat_id: Optional[str] = Field(
        None,
        max_length=255,
        description="Telegram group chat ID for the bridge target",
    )
    bridge_admin_only: Optional[bool] = Field(
        None,
        description="Whether only Telegram administrators can reply via bridge",
    )


class ProjectInDB(ProjectBase, TimestampMixin, SoftDeleteMixin):
    """Schema for project in database."""
    
    id: UUID = Field(..., description="Project ID")
    api_key: str = Field(..., description="API key for authentication")


class ProjectResponse(ProjectInDB):
    """Schema for project response."""
    pass


class ProjectListResponse(BaseSchema):
    """Schema for project list response."""
    
    data: list[ProjectResponse] = Field(..., description="List of projects")


class ProjectBridgeConfigResponse(BaseSchema):
    """Schema for project-level Telegram bridge config response."""

    project_id: UUID = Field(..., description="Project ID")
    bridge_enabled: bool = Field(..., description="Whether bridge relay is enabled")
    bridge_bot_token: Optional[str] = Field(
        None,
        description="Independent Telegram bridge bot token",
    )
    bridge_chat_id: Optional[str] = Field(
        None,
        description="Telegram target group chat ID",
    )
    bridge_admin_only: bool = Field(
        ...,
        description="Whether only Telegram administrators can reply via bridge",
    )


class ProjectBridgeChatProbeRequest(BaseSchema):
    """Request payload for probing Telegram groups with a bridge bot token."""

    bot_token: str = Field(
        ...,
        min_length=10,
        max_length=255,
        description="Telegram bot token used for probing recent visible groups",
    )


class ProjectBridgeChatCandidate(BaseSchema):
    """A Telegram group discovered from recent bot updates."""

    chat_id: str = Field(..., description="Telegram chat ID")
    title: str = Field(..., description="Telegram group title")
    type: str = Field(..., description="Chat type, usually group or supergroup")
    username: Optional[str] = Field(None, description="Public username if present")
    is_forum: bool = Field(False, description="Whether the group has forum topics enabled")


class ProjectBridgeChatProbeResponse(BaseSchema):
    """Response for bridge bot group probing."""

    bot_id: int = Field(..., description="Telegram bot user ID")
    bot_username: Optional[str] = Field(None, description="Telegram bot username")
    chats: list[ProjectBridgeChatCandidate] = Field(
        default_factory=list,
        description="Recent visible Telegram groups discovered for the bot",
    )
    warning: Optional[str] = Field(
        None,
        description="Optional warning about discovery limitations or webhook conflicts",
    )
