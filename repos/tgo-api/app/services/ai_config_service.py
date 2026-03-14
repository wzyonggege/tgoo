"""Service utilities for managing AI reply integration configuration."""

from __future__ import annotations

from typing import NotRequired, Optional, TypedDict, cast
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Platform, SystemSetup


class AIConfigRecord(TypedDict):
    """Runtime-ready AI reply configuration."""

    id: str
    name: str
    provider: str
    api_base_url: str
    api_key: Optional[str]
    model: Optional[str]
    completions_path: Optional[str]
    timeout: Optional[int]
    is_default: bool


class AIConfigRecordInput(TypedDict):
    """Stored AI reply configuration input from JSON payloads."""

    id: NotRequired[str]
    name: NotRequired[str]
    provider: NotRequired[str]
    api_base_url: NotRequired[str]
    api_key: NotRequired[Optional[str]]
    model: NotRequired[Optional[str]]
    completions_path: NotRequired[Optional[str]]
    timeout: NotRequired[Optional[int]]
    is_default: NotRequired[bool]


DEFAULT_AI_CONFIG_NAME = "默认 AI 回复"
AI_REPLY_CONFIGS_KEY = "ai_reply_configs"
LEGACY_AI_PROVIDER_KEY = "ai_provider"
PLATFORM_AI_REPLY_ID_KEY = "ai_reply_id"

DEFAULT_AI_CONFIG: AIConfigRecord = {
    "id": "system-default",
    "name": DEFAULT_AI_CONFIG_NAME,
    "provider": "custom",
    "api_base_url": settings.FASTGPT_API_BASE.rstrip("/"),
    "api_key": settings.FASTGPT_API_KEY or None,
    "model": settings.FASTGPT_MODEL or None,
    "completions_path": settings.FASTGPT_COMPLETIONS_PATH or None,
    "timeout": settings.FASTGPT_TIMEOUT,
    "is_default": True,
}


class AIConfigNotFoundError(ValueError):
    """Raised when an AI reply configuration cannot be found."""



def _get_or_create_system_setup(db: Session) -> SystemSetup:
    """Ensure there is always a SystemSetup row available."""
    setup = db.query(SystemSetup).order_by(SystemSetup.created_at.asc()).first()
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



def _default_config_seed_available() -> bool:
    """Return whether env-level AI defaults are available for fallback seeding."""
    return bool(DEFAULT_AI_CONFIG["api_base_url"])



def _normalize_record(raw: AIConfigRecordInput, index: int) -> AIConfigRecord:
    """Normalize a raw config item from JSON storage."""
    default_name = f"AI 回复 {index + 1}"
    provider = (raw.get("provider") or DEFAULT_AI_CONFIG["provider"] or "custom").strip()
    api_base_url = (raw.get("api_base_url") or DEFAULT_AI_CONFIG["api_base_url"] or "").strip().rstrip("/")
    completions_path_raw = raw.get("completions_path")
    completions_path = None
    if isinstance(completions_path_raw, str):
        trimmed_path = completions_path_raw.strip()
        if trimmed_path:
            completions_path = trimmed_path if trimmed_path.startswith("/") else f"/{trimmed_path}"
    elif DEFAULT_AI_CONFIG["completions_path"]:
        completions_path = DEFAULT_AI_CONFIG["completions_path"]

    timeout_raw = raw.get("timeout")
    timeout = timeout_raw if isinstance(timeout_raw, int) and timeout_raw > 0 else DEFAULT_AI_CONFIG["timeout"]

    name = (raw.get("name") or default_name).strip() or default_name
    config_id = (raw.get("id") or uuid4().hex).strip() or uuid4().hex
    api_key = raw.get("api_key")
    if isinstance(api_key, str):
        api_key = api_key.strip() or None

    model = raw.get("model")
    if isinstance(model, str):
        model = model.strip() or None

    return {
        "id": config_id,
        "name": name,
        "provider": provider,
        "api_base_url": api_base_url,
        "api_key": api_key,
        "model": model,
        "completions_path": completions_path,
        "timeout": timeout,
        "is_default": bool(raw.get("is_default", False)),
    }



def _get_stored_config_list(setup: SystemSetup) -> Optional[list[AIConfigRecordInput]]:
    """Read stored AI reply configs if the multi-config key exists."""
    config = setup.config or {}
    if AI_REPLY_CONFIGS_KEY not in config:
        return None
    raw_items = config.get(AI_REPLY_CONFIGS_KEY)
    if not isinstance(raw_items, list):
        return []

    records: list[AIConfigRecordInput] = []
    for raw_item in raw_items:
        if isinstance(raw_item, dict):
            records.append(cast(AIConfigRecordInput, raw_item))
    return records



def _get_legacy_seed_config(setup: SystemSetup) -> Optional[AIConfigRecord]:
    """Build a single config from legacy storage or env defaults."""
    config = setup.config or {}
    legacy_raw = config.get(LEGACY_AI_PROVIDER_KEY)
    if isinstance(legacy_raw, dict):
        legacy_record = _normalize_record(cast(AIConfigRecordInput, legacy_raw), 0)
        legacy_record["id"] = "legacy-default"
        legacy_record["name"] = legacy_record["name"] or DEFAULT_AI_CONFIG_NAME
        legacy_record["is_default"] = True
        return legacy_record

    if _default_config_seed_available():
        return dict(DEFAULT_AI_CONFIG)
    return None



def _normalize_records(raw_items: list[AIConfigRecordInput]) -> list[AIConfigRecord]:
    """Normalize stored items and ensure a single default item."""
    records = [_normalize_record(raw, index) for index, raw in enumerate(raw_items)]
    if not records:
        return []

    default_index = -1
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        if record["id"] in seen_ids:
            record["id"] = uuid4().hex
        seen_ids.add(record["id"])
        if record["is_default"] and default_index == -1:
            default_index = index
        elif record["is_default"]:
            record["is_default"] = False

    if default_index == -1:
        records[0]["is_default"] = True
    return records



def _serialize_records(records: list[AIConfigRecord]) -> list[AIConfigRecordInput]:
    """Convert normalized records back to JSON-storable dicts."""
    serialized: list[AIConfigRecordInput] = []
    for record in records:
        serialized.append(
            AIConfigRecordInput(
                id=record["id"],
                name=record["name"],
                provider=record["provider"],
                api_base_url=record["api_base_url"],
                api_key=record["api_key"],
                model=record["model"],
                completions_path=record["completions_path"],
                timeout=record["timeout"],
                is_default=record["is_default"],
            )
        )
    return serialized



def _set_config_records(db: Session, setup: SystemSetup, records: list[AIConfigRecord]) -> list[AIConfigRecord]:
    """Persist AI reply configs and refresh setup flags."""
    existing_config = dict(setup.config or {})
    existing_config[AI_REPLY_CONFIGS_KEY] = _serialize_records(records)
    existing_config.pop(LEGACY_AI_PROVIDER_KEY, None)
    setup.config = existing_config
    setup.llm_configured = any(bool(record["api_key"]) for record in records)
    db.add(setup)
    db.commit()
    db.refresh(setup)
    return records



def list_ai_configs(db: Session) -> list[AIConfigRecord]:
    """List all AI reply configurations."""
    setup = _get_or_create_system_setup(db)
    stored_items = _get_stored_config_list(setup)
    if stored_items is not None:
        return _normalize_records(stored_items)

    legacy_config = _get_legacy_seed_config(setup)
    if legacy_config is None:
        return []
    return [legacy_config]



def get_ai_config(db: Session) -> AIConfigRecord:
    """Return the default AI reply configuration for runtime compatibility."""
    configs = list_ai_configs(db)
    for config in configs:
        if config["is_default"]:
            return config
    if configs:
        return configs[0]

    setup = _get_or_create_system_setup(db)
    fallback = _get_legacy_seed_config(setup)
    if fallback is not None:
        return fallback
    return dict(DEFAULT_AI_CONFIG)



def get_ai_config_by_id(db: Session, config_id: str) -> AIConfigRecord:
    """Return a specific AI reply configuration by ID."""
    normalized_id = config_id.strip()
    for config in list_ai_configs(db):
        if config["id"] == normalized_id:
            return config
    raise AIConfigNotFoundError(f"AI config not found: {normalized_id}")



def create_ai_config(
    db: Session,
    *,
    name: str,
    provider: str,
    api_base_url: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    completions_path: Optional[str] = None,
    timeout: Optional[int] = None,
    is_default: bool = False,
) -> AIConfigRecord:
    """Create a new AI reply configuration."""
    setup = _get_or_create_system_setup(db)
    records = list_ai_configs(db)
    new_record = _normalize_record(
        AIConfigRecordInput(
            id=uuid4().hex,
            name=name,
            provider=provider,
            api_base_url=api_base_url,
            api_key=api_key,
            model=model,
            completions_path=completions_path,
            timeout=timeout,
            is_default=is_default or not records,
        ),
        len(records),
    )
    if new_record["is_default"]:
        for record in records:
            record["is_default"] = False
    records.append(new_record)
    normalized_records = _normalize_records(_serialize_records(records))
    _set_config_records(db, setup, normalized_records)
    return get_ai_config_by_id(db, new_record["id"])



def update_ai_config(
    db: Session,
    config_id: str,
    *,
    name: Optional[str] = None,
    provider: Optional[str] = None,
    api_base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    completions_path: Optional[str] = None,
    timeout: Optional[int] = None,
    is_default: Optional[bool] = None,
) -> AIConfigRecord:
    """Update an existing AI reply configuration and return it."""
    setup = _get_or_create_system_setup(db)
    records = list_ai_configs(db)
    normalized_id = config_id.strip()
    found = False
    for record in records:
        if record["id"] != normalized_id:
            continue
        found = True
        if name is not None:
            record["name"] = name.strip() or record["name"]
        if provider is not None:
            record["provider"] = provider.strip() or record["provider"]
        if api_base_url is not None:
            record["api_base_url"] = api_base_url.strip().rstrip("/")
        if api_key is not None:
            record["api_key"] = api_key.strip() or None
        if model is not None:
            record["model"] = model.strip() or None
        if completions_path is not None:
            trimmed_path = completions_path.strip()
            record["completions_path"] = trimmed_path if not trimmed_path or trimmed_path.startswith("/") else f"/{trimmed_path}"
        if timeout is not None:
            record["timeout"] = timeout
        if is_default is not None:
            record["is_default"] = is_default
        if record["is_default"]:
            for other_record in records:
                if other_record["id"] != normalized_id:
                    other_record["is_default"] = False
        break

    if not found:
        raise AIConfigNotFoundError(f"AI config not found: {normalized_id}")

    normalized_records = _normalize_records(_serialize_records(records))
    _set_config_records(db, setup, normalized_records)
    return get_ai_config_by_id(db, normalized_id)



def delete_ai_config(db: Session, config_id: str) -> None:
    """Delete an AI reply configuration."""
    setup = _get_or_create_system_setup(db)
    normalized_id = config_id.strip()
    records = [record for record in list_ai_configs(db) if record["id"] != normalized_id]
    if len(records) == len(list_ai_configs(db)):
        raise AIConfigNotFoundError(f"AI config not found: {normalized_id}")

    normalized_records = _normalize_records(_serialize_records(records)) if records else []
    _set_config_records(db, setup, normalized_records)



def get_platform_ai_reply_id(platform: Platform) -> Optional[str]:
    """Extract selected AI reply config ID from platform config."""
    platform_config = platform.config
    if not isinstance(platform_config, dict):
        return None
    selected_id = platform_config.get(PLATFORM_AI_REPLY_ID_KEY)
    if isinstance(selected_id, str):
        normalized = selected_id.strip()
        return normalized or None
    return None



def get_ai_config_for_platform(
    db: Session,
    platform: Platform,
    override_ai_reply_id: Optional[str] = None,
) -> AIConfigRecord:
    """Return the effective AI reply config for a platform, with optional visitor override."""
    selected_id = (override_ai_reply_id or "").strip() or get_platform_ai_reply_id(platform)
    if selected_id:
        try:
            return get_ai_config_by_id(db, selected_id)
        except AIConfigNotFoundError:
            pass
    return get_ai_config(db)



def set_platform_ai_reply_id(existing_config: object, ai_reply_id: Optional[str]) -> dict[str, object]:
    """Return merged platform config with updated AI reply selection."""
    merged: dict[str, object] = {}
    if isinstance(existing_config, dict):
        for key, value in existing_config.items():
            merged[str(key)] = value

    normalized_id = (ai_reply_id or "").strip()
    if normalized_id:
        merged[PLATFORM_AI_REPLY_ID_KEY] = normalized_id
    else:
        merged.pop(PLATFORM_AI_REPLY_ID_KEY, None)
    return merged
