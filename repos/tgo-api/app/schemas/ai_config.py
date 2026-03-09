"""Schemas for AI reply integration configuration endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


class _AIConfigPayloadBase(BaseSchema):
    """Common fields for AI reply configuration payloads."""

    provider: Optional[str] = Field(
        default=None,
        description="Provider identifier (e.g., custom, fastgpt, openai)",
        min_length=1,
        max_length=100,
    )
    api_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for the provider's OpenAI-compatible endpoint",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key used to authenticate requests",
    )
    model: Optional[str] = Field(
        default=None,
        description="Default model identifier to use for completions",
        max_length=200,
    )
    completions_path: Optional[str] = Field(
        default=None,
        description="Relative path for the chat completions endpoint",
        max_length=200,
    )
    timeout: Optional[int] = Field(
        default=None,
        ge=5,
        le=600,
        description="Request timeout in seconds",
    )

    @field_validator("api_base_url")
    @classmethod
    def validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        """Ensure provided base URL is non-empty and uses HTTP/S."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("API base URL cannot be empty")
        if not trimmed.lower().startswith(("http://", "https://")):
            raise ValueError("API base URL must start with http:// or https://")
        return trimmed.rstrip("/")

    @field_validator("api_key")
    @classmethod
    def normalize_api_key(cls, value: Optional[str]) -> Optional[str]:
        """Trim whitespace from API keys."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("completions_path")
    @classmethod
    def normalize_completions_path(cls, value: Optional[str]) -> Optional[str]:
        """Ensure the completions path starts with a slash."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if not trimmed.startswith("/"):
            trimmed = f"/{trimmed}"
        return trimmed


class AIConfigResponse(BaseSchema):
    """Serialized AI reply configuration item."""

    id: str
    name: str
    provider: str
    api_base_url: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    completions_path: Optional[str] = None
    timeout: Optional[int] = None
    is_default: bool = False


class AIConfigOptionResponse(BaseSchema):
    """Lightweight AI reply configuration option for selectors."""

    id: str
    name: str
    provider: str
    is_default: bool = False


class AIConfigOptionListResponse(BaseSchema):
    """Response wrapper for listing AI reply configuration options."""

    items: list[AIConfigOptionResponse] = Field(default_factory=list)


class AIConfigCreateRequest(_AIConfigPayloadBase):
    """Payload for creating a new AI reply configuration."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name shown in settings and channel selection",
    )
    provider: str = Field(
        default="custom",
        description="Provider identifier (e.g., custom, fastgpt, openai)",
        min_length=1,
        max_length=100,
    )
    api_base_url: str = Field(
        ...,
        description="Base URL for the provider's OpenAI-compatible endpoint",
    )
    is_default: bool = Field(
        default=False,
        description="Whether this configuration is the system default",
    )


class AIConfigUpdateRequest(_AIConfigPayloadBase):
    """Payload for updating an existing AI reply configuration."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Display name shown in settings and channel selection",
    )
    is_default: Optional[bool] = Field(
        default=None,
        description="Whether this configuration is the system default",
    )


class AIConfigListResponse(BaseSchema):
    """Response wrapper for listing AI reply configurations."""

    items: list[AIConfigResponse] = Field(default_factory=list)
