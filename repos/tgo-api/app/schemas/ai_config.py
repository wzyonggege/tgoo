"""Schemas for AI provider configuration endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, validator


class AIConfigResponse(BaseModel):
    """Serialized AI provider configuration."""

    provider: str
    api_base_url: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    completions_path: Optional[str] = None
    timeout: Optional[int] = None


class AIConfigUpdateRequest(BaseModel):
    """Payload for updating AI provider configuration."""

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

    @validator("api_base_url")
    def validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        """Ensure provided base URL is non-empty and uses HTTP/S."""
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("API base URL cannot be empty")
        if not trimmed.lower().startswith(("http://", "https://")):
            raise ValueError("API base URL must start with http:// or https://")
        return trimmed

    @validator("api_key")
    def normalize_api_key(cls, value: Optional[str]) -> Optional[str]:
        """Trim whitespace from API keys."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @validator("completions_path")
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
