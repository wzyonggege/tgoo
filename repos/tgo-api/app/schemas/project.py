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


class ProjectBridgeObservabilitySummary(BaseSchema):
    """Aggregated Telegram bridge observability for a project."""

    total_bindings: int = Field(0, description="Total bridge bindings for this project")
    pending_outbox: int = Field(0, description="Pending outbox records")
    processing_outbox: int = Field(0, description="Processing outbox records")
    failed_outbox: int = Field(0, description="Failed outbox records")
    completed_outbox: int = Field(0, description="Completed outbox records")
    last_binding_at: Optional[datetime] = Field(None, description="Latest binding update time")
    last_outbox_at: Optional[datetime] = Field(None, description="Latest outbox fetched time")
    last_failed_at: Optional[datetime] = Field(None, description="Latest outbox failure time")


class ProjectBridgeObservabilityFailure(BaseSchema):
    """A recent Telegram bridge outbox failure."""

    outbox_id: str = Field(..., description="Outbox record ID")
    binding_id: str = Field(..., description="Binding record ID")
    status: str = Field(..., description="Outbox status")
    retry_count: int = Field(..., description="Retry count")
    error_message: Optional[str] = Field(None, description="Recent error message")
    dedupe_key: str = Field(..., description="Outbox dedupe key")
    fetched_at: datetime = Field(..., description="When the outbox row was created")
    processed_at: Optional[datetime] = Field(None, description="When the outbox row was last processed")
    source_platform_id: Optional[str] = Field(None, description="Source platform ID")
    source_platform_name: Optional[str] = Field(None, description="Source platform name")
    source_display_name: Optional[str] = Field(None, description="Visitor display name")
    source_from_uid: Optional[str] = Field(None, description="Visitor external UID")
    telegram_chat_id: Optional[str] = Field(None, description="Target Telegram chat ID")
    topic_id: Optional[int] = Field(None, description="Telegram topic thread ID")
    topic_name: Optional[str] = Field(None, description="Telegram topic title")


class ProjectBridgeObservabilityBinding(BaseSchema):
    """A recent bridge binding snapshot."""

    binding_id: str = Field(..., description="Binding ID")
    source_platform_id: str = Field(..., description="Source platform ID")
    source_platform_name: Optional[str] = Field(None, description="Source platform name")
    source_platform_type: str = Field(..., description="Source platform type")
    source_display_name: Optional[str] = Field(None, description="Visitor display name")
    source_from_uid: str = Field(..., description="Visitor external UID")
    telegram_chat_id: str = Field(..., description="Target Telegram chat ID")
    topic_id: Optional[int] = Field(None, description="Telegram topic thread ID")
    topic_name: Optional[str] = Field(None, description="Telegram topic title")
    last_message_at: Optional[datetime] = Field(None, description="Latest message time for this binding")
    updated_at: datetime = Field(..., description="Latest binding update time")


class ProjectBridgeObservabilityResponse(BaseSchema):
    """Project-level Telegram bridge observability response."""

    project_id: UUID = Field(..., description="Project ID")
    summary: ProjectBridgeObservabilitySummary = Field(..., description="Aggregated bridge metrics")
    recent_failures: list[ProjectBridgeObservabilityFailure] = Field(
        default_factory=list,
        description="Most recent bridge outbox failures",
    )
    recent_bindings: list[ProjectBridgeObservabilityBinding] = Field(
        default_factory=list,
        description="Most recent bridge bindings",
    )
