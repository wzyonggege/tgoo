"""Service utilities for managing AI provider configuration."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import SystemSetup

DEFAULT_AI_CONFIG: Dict[str, Any] = {
    "provider": "custom",
    "api_base_url": settings.FASTGPT_API_BASE.rstrip("/"),
    "api_key": settings.FASTGPT_API_KEY,
    "model": settings.FASTGPT_MODEL,
    "completions_path": settings.FASTGPT_COMPLETIONS_PATH,
    "timeout": settings.FASTGPT_TIMEOUT,
}


def _get_or_create_system_setup(db: Session) -> SystemSetup:
    """Ensure there is always a SystemSetup row available."""
    setup = (
        db.query(SystemSetup)
        .order_by(SystemSetup.created_at.asc())
        .first()
    )
    if setup:
        return setup

    setup = SystemSetup(
        is_installed=False,
        admin_created=False,
        llm_configured=False,
        skip_llm_config=True,
        config={},
    )
    db.add(setup)
    db.commit()
    db.refresh(setup)
    return setup


def _merge_with_defaults(override: Dict[str, Any] | None) -> Dict[str, Any]:
    """Merge stored configuration with defaults."""
    merged = DEFAULT_AI_CONFIG.copy()
    if override:
        merged.update({k: v for k, v in override.items() if v is not None})
    # Normalize URL by stripping trailing slash if present
    api_base = merged.get("api_base_url")
    if isinstance(api_base, str):
        merged["api_base_url"] = api_base.rstrip("/")
    return merged


def get_ai_config(db: Session) -> Dict[str, Any]:
    """Return the current AI provider configuration."""
    setup = _get_or_create_system_setup(db)
    stored = (setup.config or {}).get("ai_provider") or {}
    return _merge_with_defaults(stored)


def update_ai_config(
    db: Session,
    *,
    provider: str | None = None,
    api_base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    completions_path: str | None = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Update AI provider configuration and return the merged result."""
    setup = _get_or_create_system_setup(db)
    existing_config = setup.config or {}
    config = dict(existing_config)
    stored = dict((config.get("ai_provider") or {}))

    if provider is not None:
        stored["provider"] = provider
    if api_base_url is not None:
        stored["api_base_url"] = api_base_url.rstrip("/")
    if api_key is not None:
        stored["api_key"] = api_key
    if model is not None:
        stored["model"] = model
    if completions_path is not None:
        stored["completions_path"] = completions_path
    if timeout is not None and timeout > 0:
        stored["timeout"] = timeout

    config["ai_provider"] = stored
    setup.llm_configured = bool(stored.get("api_key"))
    setup.config = config
    db.add(setup)
    db.commit()
    db.refresh(setup)

    return _merge_with_defaults(stored)


def get_active_ai_credentials(db: Session) -> Dict[str, Any]:
    """Alias used by other services to fetch credentials for runtime calls."""
    return get_ai_config(db)
