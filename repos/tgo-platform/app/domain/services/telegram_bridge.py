from __future__ import annotations

import asyncio
import hashlib
import httpx
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.telegram_utils import (
    telegram_create_forum_topic,
    telegram_is_chat_admin,
    telegram_send_photo,
    telegram_send_text,
)
from app.core.config import settings
from app.db.models import Platform, TelegramBridgeBinding, TelegramBridgeOutbox, TelegramBridgeState
from app.domain.entities import NormalizedMessage
from app.domain.services.dispatcher import select_adapter_for_target

TELEGRAM_API_BASE = "https://api.telegram.org"
_BRIDGE_FALLBACK_TEXT = "[unsupported message type]"
logger = logging.getLogger(__name__)
_PLATFORM_LABELS: dict[str, str] = {
    "email": "Email",
    "wecom": "WeCom",
    "wecom_bot": "WeCom Bot",
    "website": "Website",
    "feishu_bot": "Feishu",
    "dingtalk_bot": "DingTalk",
    "telegram": "Telegram",
    "slack": "Slack",
    "custom": "Custom",
}


class TelegramBridgeConfig(BaseModel):
    bot_token: str = ""
    bridge_chat_id: str | None = None
    bridge_admin_only: bool = True
    bridge_processing_batch_size: int = 20
    bridge_max_retry_attempts: int = 3
    bridge_poll_interval_seconds: int = 5
    bridge_polling_timeout_seconds: int = 2


class ProjectBridgeConfig(BaseModel):
    project_id: uuid.UUID
    bridge_enabled: bool = False
    bridge_bot_token: str | None = None
    bridge_chat_id: str | None = None
    bridge_admin_only: bool = True


class _BridgePayloadEnvelope(BaseModel):
    kind: str = "text"
    text: str | None = None
    media_url: str | None = None
    caption: str | None = None
    legacy_text: bool = False


@dataclass
class _BridgeProjectEntry:
    project_id: uuid.UUID
    cfg: TelegramBridgeConfig
    auth_platform_api_key: str


@dataclass
class _ProjectBridgeCacheEntry:
    expires_at: float
    config: ProjectBridgeConfig | None


def _compact_text(content: str | None) -> str:
    text = (content or "").strip()
    return text or _BRIDGE_FALLBACK_TEXT


def _display_platform_name(platform_type: str) -> str:
    return _PLATFORM_LABELS.get((platform_type or "").lower(), platform_type or "Platform")


def _copy_jsonable(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return json.loads(json.dumps(value))


def _sanitize_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    cleaned = _copy_jsonable(extra)
    cleaned.pop("visitor_profile", None)
    cleaned.pop("system_message", None)
    return cleaned


def _looks_like_image_url(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return False
    return True


def _extract_msg_type(extra: dict[str, Any]) -> int | None:
    raw_msg_type = extra.get("msg_type")
    if isinstance(raw_msg_type, int):
        return raw_msg_type
    if isinstance(raw_msg_type, str) and raw_msg_type.isdigit():
        return int(raw_msg_type)
    return None


def _extract_bridge_channel_id(extra: dict[str, Any]) -> str | None:
    channel_id = str(extra.get("channel_id") or "").strip()
    return channel_id or None


def _extract_bridge_platform_open_id(extra: dict[str, Any], fallback_uid: str) -> str:
    direct = str(extra.get("platform_open_id") or "").strip()
    if direct:
        return direct
    return fallback_uid


def _source_key(platform_type: str, platform_id: uuid.UUID | str, from_uid: str, extra: dict[str, Any]) -> str:
    parts: list[str] = [f"type={platform_type}", f"platform={platform_id}", f"uid={from_uid}"]
    ptype = (platform_type or "").lower()

    if ptype in {"website", "custom"}:
        channel_id = str(extra.get("channel_id") or "").strip()
        channel_type = str(extra.get("channel_type") or "").strip()
        if channel_id:
            parts.append(f"channel={channel_id}")
        if channel_type:
            parts.append(f"channel_type={channel_type}")
        platform_open_id = str(extra.get("platform_open_id") or "").strip()
        if platform_open_id:
            parts.append(f"open={platform_open_id}")
    elif ptype == "telegram":
        tg = extra.get("telegram") or {}
        chat_id = str(tg.get("chat_id") or "").strip()
        if chat_id:
            parts.append(f"chat={chat_id}")
    elif ptype == "slack":
        slack = extra.get("slack") or {}
        channel = str(slack.get("channel") or "").strip()
        thread_ts = str(slack.get("thread_ts") or slack.get("ts") or "").strip()
        if channel:
            parts.append(f"channel={channel}")
        if thread_ts:
            parts.append(f"thread={thread_ts}")
    elif ptype == "dingtalk_bot":
        ding = extra.get("dingtalk") or {}
        conversation_id = str(ding.get("conversation_id") or "").strip()
        if conversation_id:
            parts.append(f"conversation={conversation_id}")
    elif ptype == "feishu_bot":
        feishu = extra.get("feishu") or {}
        chat_id = str(feishu.get("chat_id") or "").strip()
        if chat_id:
            parts.append(f"chat={chat_id}")
    elif ptype in {"wecom", "wecom_bot"}:
        wecom = extra.get("wecom") or {}
        source_type = str(extra.get("source_type") or wecom.get("source_type") or "").strip()
        open_kfid = str(wecom.get("open_kfid") or "").strip()
        external_userid = str(wecom.get("external_userid") or "").strip()
        chat_id = str(wecom.get("chat_id") or "").strip()
        if source_type:
            parts.append(f"source={source_type}")
        if open_kfid:
            parts.append(f"kfid={open_kfid}")
        if external_userid:
            parts.append(f"external={external_userid}")
        if chat_id:
            parts.append(f"chat={chat_id}")
    elif ptype == "email":
        subject = str(extra.get("subject") or "").strip()
        if subject:
            parts.append(f"subject={subject}")

    return "|".join(parts)


def _topic_title(binding: TelegramBridgeBinding) -> str:
    platform_name = _display_platform_name(binding.source_platform_type)
    label = (binding.source_display_name or binding.source_from_uid or "visitor").strip()
    short_hash = hashlib.sha1(binding.source_key.encode("utf-8")).hexdigest()[:6]
    return f"{platform_name} · {label} · {short_hash}"[:128]


def _format_bridge_text(
    platform_type: str,
    display_name: str | None,
    from_uid: str,
    content: str,
) -> str:
    header = f"[{_display_platform_name(platform_type)}] {(display_name or from_uid).strip()}"
    return f"{header}\nID: {from_uid}\n\n{_compact_text(content)}"


def _format_outbound_bridge_text(sender_label: str, content: str) -> str:
    return f"[{sender_label}]\n\n{_compact_text(content)}"


def _serialize_payload(payload: _BridgePayloadEnvelope) -> str:
    return payload.model_dump_json(exclude_none=True)


def _deserialize_payload(raw_payload: str) -> _BridgePayloadEnvelope:
    try:
        data = json.loads(raw_payload)
    except Exception:
        return _BridgePayloadEnvelope(kind="text", text=raw_payload, legacy_text=True)
    if not isinstance(data, dict) or "kind" not in data:
        return _BridgePayloadEnvelope(kind="text", text=raw_payload, legacy_text=True)
    try:
        return _BridgePayloadEnvelope(**data)
    except Exception:
        return _BridgePayloadEnvelope(kind="text", text=raw_payload, legacy_text=True)


def _build_inbound_payload(
    *,
    platform_type: str,
    display_name: str | None,
    from_uid: str,
    content: str,
    extra: dict[str, Any],
) -> str:
    header = f"[{_display_platform_name(platform_type)}] {(display_name or from_uid).strip()}\nID: {from_uid}"
    msg_type = _extract_msg_type(extra)
    if msg_type == 2 and _looks_like_image_url(content):
        return _serialize_payload(
            _BridgePayloadEnvelope(
                kind="image",
                media_url=content.strip(),
                caption=header,
            )
        )
    return _serialize_payload(
        _BridgePayloadEnvelope(
            kind="text",
            text=_format_bridge_text(
                platform_type=platform_type,
                display_name=display_name,
                from_uid=from_uid,
                content=content,
            ),
        )
    )


def _build_outbound_payload(
    *,
    sender_label: str,
    content: str,
    msg_type: int = 1,
) -> str:
    if msg_type == 2 and _looks_like_image_url(content):
        return _serialize_payload(
            _BridgePayloadEnvelope(
                kind="image",
                media_url=content.strip(),
                caption=f"[{sender_label}]",
            )
        )
    return _serialize_payload(
        _BridgePayloadEnvelope(
            kind="text",
            text=_format_outbound_bridge_text(sender_label, content),
        )
    )


def _extract_update_message(update: dict[str, Any]) -> dict[str, Any] | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None

    chat = message.get("chat") or {}
    from_user = message.get("from") or {}

    content = ""
    if "text" in message:
        content = str(message.get("text") or "")
    elif "caption" in message:
        content = str(message.get("caption") or "")
    elif "photo" in message:
        content = "[Photo]"
    elif "document" in message:
        content = "[Document]"
    elif "voice" in message:
        content = "[Voice message]"
    elif "video" in message:
        content = "[Video]"
    else:
        content = _BRIDGE_FALLBACK_TEXT

    return {
        "update_id": int(update.get("update_id") or 0),
        "message_id": int(message.get("message_id") or 0),
        "chat_id": str(chat.get("id") or ""),
        "from_user_id": str(from_user.get("id") or ""),
        "from_is_bot": bool(from_user.get("is_bot", False)),
        "message_thread_id": message.get("message_thread_id"),
        "is_topic_message": bool(message.get("is_topic_message", False)),
        "content": content,
    }


async def _telegram_delete_webhook(bot_token: str) -> None:
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/deleteWebhook"
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url)


async def _telegram_get_updates(bot_token: str, offset: int, timeout_seconds: int) -> list[dict[str, Any]]:
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
    params = {
        "offset": offset,
        "timeout": max(0, int(timeout_seconds)),
        "allowed_updates": ["message"],
    }
    try:
        async with httpx.AsyncClient(timeout=max(5, timeout_seconds + 3)) as client:
            resp = await client.get(url, params=params)
        result = resp.json()
        if result.get("ok"):
            items = result.get("result")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    except Exception:
        return []
    return []


class TelegramBridgeService:
    _PROJECT_CONFIG_CACHE_TTL_SECONDS = 30.0
    _PROJECT_CONFIG_TIMEOUT_SECONDS = 2.5

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._project_config_cache: dict[uuid.UUID, _ProjectBridgeCacheEntry] = {}

    async def enqueue_inbound(
        self,
        *,
        project_id: uuid.UUID,
        source_platform_id: uuid.UUID,
        source_platform_api_key: str | None,
        source_platform_type: str,
        from_uid: str,
        content: str,
        extra: dict[str, Any] | None,
        dedupe_key: str,
        display_name: str | None = None,
    ) -> None:
        cleaned_extra = _sanitize_extra(extra)
        source_key = _source_key(source_platform_type, source_platform_id, from_uid, cleaned_extra)

        async with self._session_factory() as session:
            bridge_project = await self._load_bridge_project(
                project_id=project_id,
                platform_api_key=source_platform_api_key,
            )
            if bridge_project is None:
                return

            binding = await self._get_or_create_binding(
                session=session,
                bridge_project=bridge_project,
                source_platform_id=source_platform_id,
                source_platform_type=source_platform_type,
                source_key=source_key,
                from_uid=from_uid,
                display_name=display_name,
                extra=cleaned_extra,
            )

            payload_text = _build_inbound_payload(
                platform_type=source_platform_type,
                display_name=display_name,
                from_uid=from_uid,
                content=content,
                extra=cleaned_extra,
            )
            outbox = TelegramBridgeOutbox(
                project_id=project_id,
                binding_id=binding.id,
                dedupe_key=dedupe_key,
                payload_text=payload_text,
            )
            session.add(outbox)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()

    async def enqueue_outbound_mirror(
        self,
        *,
        project_id: uuid.UUID,
        source_platform_id: uuid.UUID,
        source_platform_api_key: str | None,
        source_platform_type: str,
        from_uid: str,
        extra: dict[str, Any] | None,
        dedupe_key: str,
        sender_label: str,
        content: str,
        msg_type: int = 1,
    ) -> None:
        cleaned_extra = _sanitize_extra(extra)
        source_key = _source_key(source_platform_type, source_platform_id, from_uid, cleaned_extra)

        async with self._session_factory() as session:
            bridge_project = await self._load_bridge_project(
                project_id=project_id,
                platform_api_key=source_platform_api_key,
            )
            if bridge_project is None:
                return

            binding = await self._find_binding_for_outbound(
                session=session,
                project_id=project_id,
                source_platform_id=source_platform_id,
                source_key=source_key,
                from_uid=from_uid,
            )
            if binding is None:
                logger.info(
                    "[TELEGRAM_BRIDGE] skip outbound mirror: binding not found project=%s platform=%s from_uid=%s",
                    project_id,
                    source_platform_id,
                    from_uid,
                )
                return

            outbox = TelegramBridgeOutbox(
                project_id=project_id,
                binding_id=binding.id,
                dedupe_key=dedupe_key,
                payload_text=_build_outbound_payload(
                    sender_label=sender_label,
                    content=content,
                    msg_type=msg_type,
                ),
            )
            session.add(outbox)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()

    async def _find_binding_for_outbound(
        self,
        *,
        session: AsyncSession,
        project_id: uuid.UUID,
        source_platform_id: uuid.UUID,
        source_key: str,
        from_uid: str,
    ) -> TelegramBridgeBinding | None:
        binding = await session.scalar(
            select(TelegramBridgeBinding).where(
                TelegramBridgeBinding.project_id == project_id,
                TelegramBridgeBinding.source_key == source_key,
            )
        )
        if binding is not None:
            return binding

        return await session.scalar(
            select(TelegramBridgeBinding)
            .where(
                TelegramBridgeBinding.project_id == project_id,
                TelegramBridgeBinding.source_platform_id == source_platform_id,
                TelegramBridgeBinding.source_from_uid == from_uid,
            )
            .order_by(TelegramBridgeBinding.last_message_at.desc().nullslast())
            .limit(1)
        )

    async def route_topic_reply(
        self,
        *,
        project_id: uuid.UUID,
        bot_token: str,
        bridge_chat_id: str,
        bridge_admin_only: bool,
        from_user_id: str,
        topic_id: int,
        text: str,
    ) -> bool:
        reply_text = _compact_text(text)

        if bridge_admin_only:
            is_admin = await telegram_is_chat_admin(
                bot_token=bot_token,
                chat_id=bridge_chat_id,
                user_id=from_user_id,
            )
            if not is_admin:
                return False

        async with self._session_factory() as session:
            binding = await session.scalar(
                select(TelegramBridgeBinding).where(
                    TelegramBridgeBinding.project_id == project_id,
                    TelegramBridgeBinding.topic_id == topic_id,
                )
            )
            if binding is None:
                return False

            source_platform = await session.get(Platform, binding.source_platform_id)
            if source_platform is None:
                return False

            msg = NormalizedMessage(
                source="telegram_bridge",
                from_uid=binding.source_from_uid,
                content=reply_text,
                platform_api_key=source_platform.api_key or "",
                platform_type=binding.source_platform_type,
                platform_id=str(source_platform.id),
                extra=binding.source_extra or {},
            )
            adapter = await select_adapter_for_target(msg, platform=source_platform)
            await adapter.send_final({"text": reply_text})
            asyncio.create_task(
                self._mirror_topic_reply_to_backoffice(
                    source_platform=source_platform,
                    binding=binding,
                    reply_text=reply_text,
                )
            )

            binding.last_message_at = datetime.now(timezone.utc)
            await session.commit()
            return True

    async def load_bridge_project(
        self,
        project_id: uuid.UUID,
        *,
        platform_api_key: str | None,
    ) -> _BridgeProjectEntry | None:
        return await self._load_bridge_project(project_id=project_id, platform_api_key=platform_api_key)

    async def _load_bridge_project(
        self,
        *,
        project_id: uuid.UUID,
        platform_api_key: str | None,
    ) -> _BridgeProjectEntry | None:
        project_cfg = await self._get_project_bridge_config(project_id, platform_api_key=platform_api_key)
        if project_cfg is None or not project_cfg.bridge_enabled or not platform_api_key:
            return None

        bot_token = str(project_cfg.bridge_bot_token or "").strip()
        bridge_chat_id = str(project_cfg.bridge_chat_id or "").strip()
        if not bot_token or not bridge_chat_id:
            return None

        return _BridgeProjectEntry(
            project_id=project_id,
            auth_platform_api_key=platform_api_key,
            cfg=TelegramBridgeConfig(
                bot_token=bot_token,
                bridge_chat_id=bridge_chat_id,
                bridge_admin_only=project_cfg.bridge_admin_only,
            ),
        )

    async def _get_project_bridge_config(
        self,
        project_id: uuid.UUID,
        *,
        platform_api_key: str | None,
    ) -> ProjectBridgeConfig | None:
        now = time.monotonic()
        cached = self._project_config_cache.get(project_id)
        if cached is not None and cached.expires_at > now:
            return cached.config

        config = await self._fetch_project_bridge_config(project_id, platform_api_key=platform_api_key)
        self._project_config_cache[project_id] = _ProjectBridgeCacheEntry(
            expires_at=now + self._PROJECT_CONFIG_CACHE_TTL_SECONDS,
            config=config,
        )
        return config

    async def _fetch_project_bridge_config(
        self,
        project_id: uuid.UUID,
        *,
        platform_api_key: str | None,
    ) -> ProjectBridgeConfig | None:
        if not platform_api_key:
            return None

        url = f"{settings.api_base_url.rstrip('/')}/v1/projects/{project_id}/bridge-config/internal"
        try:
            async with httpx.AsyncClient(timeout=self._PROJECT_CONFIG_TIMEOUT_SECONDS) as client:
                resp = await client.get(url, headers={"X-Platform-API-Key": platform_api_key})
            if resp.status_code >= 400:
                return None
            return ProjectBridgeConfig(**resp.json())
        except Exception:
            return None

    async def _get_or_create_binding(
        self,
        *,
        session: AsyncSession,
        bridge_project: _BridgeProjectEntry,
        source_platform_id: uuid.UUID,
        source_platform_type: str,
        source_key: str,
        from_uid: str,
        display_name: str | None,
        extra: dict[str, Any],
    ) -> TelegramBridgeBinding:
        binding = await session.scalar(
            select(TelegramBridgeBinding).where(
                TelegramBridgeBinding.project_id == bridge_project.project_id,
                TelegramBridgeBinding.source_key == source_key,
            )
        )
        if binding is not None:
            binding.source_display_name = display_name or binding.source_display_name
            binding.source_extra = extra
            binding.telegram_chat_id = str(bridge_project.cfg.bridge_chat_id or "")
            binding.last_message_at = datetime.now(timezone.utc)
            await session.flush()
            return binding

        binding = TelegramBridgeBinding(
            project_id=bridge_project.project_id,
            source_platform_id=source_platform_id,
            source_platform_type=source_platform_type,
            source_key=source_key,
            source_from_uid=from_uid,
            source_display_name=display_name,
            source_extra=extra,
            telegram_chat_id=str(bridge_project.cfg.bridge_chat_id or ""),
            last_message_at=datetime.now(timezone.utc),
        )
        session.add(binding)
        try:
            await session.flush()
            return binding
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(TelegramBridgeBinding).where(
                    TelegramBridgeBinding.project_id == bridge_project.project_id,
                    TelegramBridgeBinding.source_key == source_key,
                )
            )
            if existing is None:
                raise
            return existing

    async def _mirror_topic_reply_to_backoffice(
        self,
        *,
        source_platform: Platform,
        binding: TelegramBridgeBinding,
        reply_text: str,
    ) -> None:
        platform_api_key = str(source_platform.api_key or "").strip()
        if not platform_api_key:
            return

        extra = _sanitize_extra(binding.source_extra)
        channel_id = _extract_bridge_channel_id(extra)
        platform_open_id = _extract_bridge_platform_open_id(extra, binding.source_from_uid)
        url = f"{settings.api_base_url.rstrip('/')}/v1/chat/bridge-replies/internal"

        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.post(
                    url,
                    json={
                        "source_platform_id": str(source_platform.id),
                        "platform_open_id": platform_open_id,
                        "channel_id": channel_id,
                        "channel_type": 251,
                        "content": reply_text,
                    },
                    headers={"X-Platform-API-Key": platform_api_key},
                )
            if response.status_code >= 400:
                logger.warning(
                    "[TELEGRAM_BRIDGE] mirror topic reply failed: platform=%s status=%s body=%s",
                    source_platform.id,
                    response.status_code,
                    response.text[:500],
                )
        except Exception:
            logger.exception(
                "[TELEGRAM_BRIDGE] mirror topic reply exception for platform=%s",
                source_platform.id,
            )


class TelegramBridgeWorker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._service = TelegramBridgeService(session_factory)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._deleted_webhooks: set[str] = set()

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                projects = await self._load_active_bridge_projects()
                if projects:
                    await asyncio.gather(
                        *(self._run_project_cycle(project) for project in projects),
                        return_exceptions=True,
                    )
                interval = projects[0].cfg.bridge_poll_interval_seconds if projects else 5
                await asyncio.sleep(max(1, int(interval)))
            except Exception:
                await asyncio.sleep(5)

    async def _run_project_cycle(self, project: _BridgeProjectEntry) -> None:
        try:
            await self._ensure_polling_mode(project)
            await self._process_pending_for_project(project)
            await self._poll_topic_replies(project)
        except Exception:
            return

    async def _ensure_polling_mode(self, project: _BridgeProjectEntry) -> None:
        if project.cfg.bot_token in self._deleted_webhooks:
            return
        try:
            await _telegram_delete_webhook(project.cfg.bot_token)
            self._deleted_webhooks.add(project.cfg.bot_token)
        except Exception:
            return

    async def _load_active_bridge_projects(self) -> list[_BridgeProjectEntry]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(TelegramBridgeBinding.project_id, Platform.api_key)
                    .join(Platform, Platform.id == TelegramBridgeBinding.source_platform_id)
                    .where(
                        Platform.deleted_at.is_(None),
                        Platform.api_key.is_not(None),
                    )
                    .distinct()
                )
            ).all()

        project_key_map: dict[uuid.UUID, str] = {}
        for project_id, platform_api_key in rows:
            if project_id not in project_key_map and platform_api_key:
                project_key_map[project_id] = platform_api_key

        projects: list[_BridgeProjectEntry] = []
        for project_id, platform_api_key in project_key_map.items():
            project = await self._service.load_bridge_project(
                project_id,
                platform_api_key=platform_api_key,
            )
            if project is not None:
                projects.append(project)
        return projects

    async def _process_pending_for_project(self, project: _BridgeProjectEntry) -> None:
        batch_size = max(1, int(project.cfg.bridge_processing_batch_size or 20))
        max_retries = max(0, int(project.cfg.bridge_max_retry_attempts or 3))

        async with self._session_factory() as session:
            pending = (
                await session.execute(
                    select(TelegramBridgeOutbox)
                    .where(
                        TelegramBridgeOutbox.project_id == project.project_id,
                        TelegramBridgeOutbox.status == "pending",
                    )
                    .order_by(TelegramBridgeOutbox.fetched_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).scalars().all()

            remaining = batch_size - len(pending)
            candidates: list[TelegramBridgeOutbox] = list(pending)

            if remaining > 0:
                failed = (
                    await session.execute(
                        select(TelegramBridgeOutbox)
                        .where(
                            TelegramBridgeOutbox.project_id == project.project_id,
                            TelegramBridgeOutbox.status == "failed",
                            TelegramBridgeOutbox.retry_count < max_retries,
                        )
                        .order_by(TelegramBridgeOutbox.processed_at.asc().nullsfirst())
                        .with_for_update(skip_locked=True)
                        .limit(batch_size * 3)
                    )
                ).scalars().all()
                now = datetime.now(timezone.utc)
                for record in failed:
                    delay = max(1, 2 ** int(record.retry_count or 0))
                    if not record.processed_at or (now - record.processed_at).total_seconds() >= delay:
                        candidates.append(record)
                        if len(candidates) >= batch_size:
                            break

            for record in candidates:
                if not await self._claim_record(session, record):
                    continue
                try:
                    await self._deliver_record(session, project, record)
                except Exception as exc:
                    record.status = "failed"
                    record.retry_count = int(record.retry_count or 0) + 1
                    record.error_message = str(exc)[:2000]
                    record.processed_at = datetime.now(timezone.utc)
                    await session.commit()

    async def _claim_record(self, session: AsyncSession, record: TelegramBridgeOutbox) -> bool:
        try:
            record.status = "processing"
            record.error_message = None
            await session.commit()
            return True
        except Exception:
            await session.rollback()
            return False

    async def _deliver_record(
        self,
        session: AsyncSession,
        project: _BridgeProjectEntry,
        record: TelegramBridgeOutbox,
    ) -> None:
        binding = await session.get(TelegramBridgeBinding, record.binding_id)
        if binding is None:
            raise RuntimeError("bridge binding not found")

        if binding.topic_id is None:
            topic_name = _topic_title(binding)
            topic_id = await telegram_create_forum_topic(
                bot_token=project.cfg.bot_token,
                chat_id=str(project.cfg.bridge_chat_id or ""),
                name=topic_name,
            )
            binding.topic_id = topic_id
            binding.topic_name = topic_name
            await session.commit()

        payload = _deserialize_payload(record.payload_text)
        if payload.kind == "image" and payload.media_url:
            await telegram_send_photo(
                bot_token=project.cfg.bot_token,
                chat_id=str(project.cfg.bridge_chat_id or ""),
                photo=payload.media_url,
                caption=(payload.caption or "")[:1024] or None,
                message_thread_id=int(binding.topic_id),
            )
        else:
            text = payload.text or record.payload_text
            await telegram_send_text(
                bot_token=project.cfg.bot_token,
                chat_id=str(project.cfg.bridge_chat_id or ""),
                text=text,
                message_thread_id=int(binding.topic_id),
            )

        record.status = "completed"
        record.error_message = None
        record.processed_at = datetime.now(timezone.utc)
        binding.last_message_at = record.processed_at
        await session.commit()

    async def _poll_topic_replies(self, project: _BridgeProjectEntry) -> None:
        async with self._session_factory() as session:
            state = await session.get(TelegramBridgeState, project.project_id)
            if state is None:
                state = TelegramBridgeState(project_id=project.project_id, last_update_id=0)
                session.add(state)
                await session.commit()

            offset = int(state.last_update_id or 0) + 1

        updates = await _telegram_get_updates(
            project.cfg.bot_token,
            offset=offset,
            timeout_seconds=max(0, int(project.cfg.bridge_polling_timeout_seconds or 2)),
        )
        if not updates:
            return

        max_update_id = max(int(update.get("update_id") or 0) for update in updates)
        for update in updates:
            msg = _extract_update_message(update)
            if msg is None:
                continue
            if msg["from_is_bot"]:
                continue
            if msg["chat_id"] != str(project.cfg.bridge_chat_id or ""):
                continue
            topic_id = msg.get("message_thread_id")
            if not isinstance(topic_id, int):
                continue
            try:
                await self._service.route_topic_reply(
                    project_id=project.project_id,
                    bot_token=project.cfg.bot_token,
                    bridge_chat_id=str(project.cfg.bridge_chat_id or ""),
                    bridge_admin_only=project.cfg.bridge_admin_only,
                    from_user_id=msg["from_user_id"],
                    topic_id=topic_id,
                    text=msg["content"],
                )
            except Exception:
                continue

        async with self._session_factory() as session:
            state = await session.get(TelegramBridgeState, project.project_id)
            if state is None:
                state = TelegramBridgeState(project_id=project.project_id, last_update_id=max_update_id)
                session.add(state)
            else:
                state.last_update_id = max(int(state.last_update_id or 0), max_update_id)
            await session.commit()
