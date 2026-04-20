"""Telegram Bot consumer with async pending processing and topic bridge support."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.telegram_utils import telegram_download_file, telegram_get_file
from app.core.config import settings
from app.db.models import Platform, TelegramInbox
from app.domain.entities import NormalizedMessage
from app.domain.ports import MessageNormalizer, SSEManager, TgoApiClient
from app.domain.services.dispatcher import process_message
from app.domain.services.telegram_bridge import TelegramBridgeService
from app.infra.visitor_client import VisitorService

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramPlatformConfig(BaseModel):
    """Per-platform Telegram Bot configuration stored in Platform.config when type='telegram'."""

    bot_token: str = ""
    webhook_secret: str | None = None
    mode: Literal["polling", "webhook"] = "polling"

    polling_interval_seconds: int = 1
    polling_timeout_seconds: int = 30

    processing_batch_size: int = 10
    max_retry_attempts: int = 3
    consumer_poll_interval_seconds: int = 5


@dataclass
class _PlatformEntry:
    id: uuid.UUID
    project_id: uuid.UUID
    api_key: str | None
    cfg: TelegramPlatformConfig
    last_update_id: int = 0


class TelegramChannelListener:
    """Telegram consumer using pending inbox rows for both polling and webhook modes."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        normalizer: MessageNormalizer,
        tgo_api_client: TgoApiClient,
        sse_manager: SSEManager,
    ) -> None:
        self._session_factory = session_factory
        self._normalizer = normalizer
        self._tgo_api_client = tgo_api_client
        self._sse_manager = sse_manager
        self._bridge_service = TelegramBridgeService(session_factory)
        self._stop_event = asyncio.Event()
        self._consumer_task: asyncio.Task | None = None
        self._visitor_service = VisitorService(
            base_url=settings.api_base_url,
            cache_ttl_seconds=300,
            redis_url=settings.redis_url,
        )
        self._platform_offsets: dict[uuid.UUID, int] = {}
        self._webhook_deleted: set[uuid.UUID] = set()

    async def start(self) -> None:
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self._consumer_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def _load_active_telegram_platforms(self) -> list[_PlatformEntry]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Platform.id, Platform.project_id, Platform.api_key, Platform.config)
                    .where(Platform.is_active.is_(True), Platform.type == "telegram")
                )
            ).all()

        platforms: list[_PlatformEntry] = []
        for pid, project_id, api_key, cfg_dict in rows:
            try:
                cfg = TelegramPlatformConfig(**(cfg_dict or {}))
            except Exception as exc:
                print(f"[TELEGRAM] Skip platform {pid}: invalid config: {exc}")
                continue
            if not cfg.bot_token:
                print(f"[TELEGRAM] Skip platform {pid}: missing bot_token")
                continue
            platforms.append(
                _PlatformEntry(
                    id=pid,
                    project_id=project_id,
                    api_key=api_key,
                    cfg=cfg,
                    last_update_id=self._platform_offsets.get(pid, 0),
                )
            )
        return platforms

    async def _delete_webhook_if_exists(self, platform: _PlatformEntry) -> None:
        if platform.id in self._webhook_deleted:
            return
        try:
            url = f"{TELEGRAM_API_BASE}/bot{platform.cfg.bot_token}/deleteWebhook"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url)
                result = resp.json()
                if result.get("ok"):
                    self._webhook_deleted.add(platform.id)
                    print(f"[TELEGRAM] Webhook deleted, polling mode enabled for {platform.id}")
        except Exception as exc:
            print(f"[TELEGRAM] Warning: Could not delete webhook for {platform.id}: {exc}")

    async def _get_updates(self, bot_token: str, offset: int, timeout: int) -> list[dict[str, Any]]:
        url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
        params = {"offset": offset, "timeout": timeout, "allowed_updates": ["message", "edited_message"]}
        try:
            async with httpx.AsyncClient(timeout=timeout + 10) as client:
                resp = await client.get(url, params=params)
                result = resp.json()
            if result.get("ok"):
                return result.get("result", [])
            print(f"[TELEGRAM] getUpdates error: {result.get('description', 'Unknown error')}")
            return []
        except httpx.TimeoutException:
            return []
        except Exception as exc:
            print(f"[TELEGRAM] getUpdates request failed: {exc}")
            return []

    @staticmethod
    def _extract_photo_file_id(message: dict[str, Any]) -> str | None:
        photos = message.get("photo", [])
        if not photos:
            return None
        largest = photos[-1]
        return str(largest.get("file_id") or "") or None

    def _extract_message_data(self, update: dict[str, Any]) -> dict[str, Any] | None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        from_user = message.get("from", {})
        chat = message.get("chat", {})
        content = ""
        msg_type = 1
        file_id: str | None = None

        if "text" in message:
            content = str(message["text"])
            msg_type = 1
        elif "photo" in message:
            content = str(message.get("caption") or "[Photo]")
            msg_type = 2
            file_id = self._extract_photo_file_id(message)
        elif "document" in message:
            content = str(message.get("caption") or "[Document]")
            msg_type = 3
        elif "sticker" in message:
            content = str(message.get("sticker", {}).get("emoji") or "[Sticker]")
            msg_type = 1
        elif "voice" in message:
            content = "[Voice message]"
            msg_type = 4
        elif "video" in message:
            content = str(message.get("caption") or "[Video]")
            msg_type = 5
        else:
            content = "[Unsupported message type]"

        first_name = str(from_user.get("first_name") or "").strip()
        last_name = str(from_user.get("last_name") or "").strip()
        username = from_user.get("username")
        display_name = " ".join(part for part in [first_name, last_name] if part).strip() or str(username or from_user.get("id") or "")

        return {
            "update_id": update.get("update_id"),
            "message_id": str(message.get("message_id") or ""),
            "from_user": str(from_user.get("id") or ""),
            "from_username": str(username) if username else None,
            "from_display_name": display_name or None,
            "from_is_bot": bool(from_user.get("is_bot", False)),
            "chat_id": str(chat.get("id") or ""),
            "chat_type": str(chat.get("type") or "private"),
            "content": content,
            "msg_type": msg_type,
            "file_id": file_id,
            "message_thread_id": message.get("message_thread_id"),
            "is_topic_message": bool(message.get("is_topic_message", False)),
            "raw_payload": {"update": update, "message": message},
            "date": message.get("date"),
        }

    async def _store_to_inbox(self, session: AsyncSession, platform: _PlatformEntry, msg_data: dict[str, Any]) -> None:
        record = TelegramInbox(
            platform_id=platform.id,
            update_id=msg_data["update_id"],
            message_id=msg_data["message_id"],
            from_user=msg_data["from_user"],
            from_username=msg_data.get("from_username"),
            from_display_name=msg_data.get("from_display_name"),
            chat_id=msg_data["chat_id"],
            chat_type=msg_data["chat_type"],
            msg_type=str(msg_data["msg_type"]),
            content=msg_data["content"],
            raw_payload=msg_data["raw_payload"],
            status="pending",
            received_at=self._received_at(msg_data.get("date")),
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()

    @staticmethod
    def _received_at(raw_date: Any) -> datetime | None:
        try:
            if raw_date is None:
                return None
            return datetime.fromtimestamp(int(raw_date), tz=timezone.utc)
        except Exception:
            return None

    async def _ingest_update(self, platform: _PlatformEntry, update: dict[str, Any]) -> None:
        msg_data = self._extract_message_data(update)
        if not msg_data or not msg_data["message_id"] or not msg_data["chat_id"]:
            return

        async with self._session_factory() as session:
            try:
                await self._store_to_inbox(session, platform, msg_data)
                await session.commit()
            except IntegrityError:
                await session.rollback()
            except Exception:
                await session.rollback()
                raise

    def _build_mapped_message(self, platform: _PlatformEntry, msg_data: dict[str, Any]) -> dict[str, Any]:
        telegram_ctx: dict[str, Any] = {
            "chat_id": msg_data["chat_id"],
            "chat_type": msg_data["chat_type"],
            "from_username": msg_data.get("from_username"),
            "from_display_name": msg_data.get("from_display_name"),
            "msg_type": msg_data["msg_type"],
            "bot_token": platform.cfg.bot_token,
        }

        return {
            "source": "telegram",
            "from_uid": msg_data["from_user"],
            "content": msg_data["content"] or "",
            "platform_api_key": platform.api_key or "",
            "platform_type": "telegram",
            "platform_id": str(platform.id),
            "extra": {
                "project_id": str(platform.project_id),
                "msg_type": msg_data["msg_type"],
                "telegram": telegram_ctx,
            },
        }

    async def _get_or_register_visitor(
        self,
        platform: _PlatformEntry,
        msg_data: dict[str, Any],
    ) -> tuple[Any | None, str | None, str | None]:
        display_name: str | None = msg_data.get("from_display_name") or msg_data.get("from_username")
        avatar_url: str | None = None
        visitor = None

        try:
            cache_key = self._visitor_service.make_cache_key(str(platform.project_id), "telegram", msg_data["from_user"])
            cached = await self._visitor_service.get_cached(cache_key)
            if cached:
                display_name = cached.nickname or cached.name or display_name
                avatar_url = cached.avatar_url
                return cached, display_name, avatar_url
        except Exception as exc:
            print(f"[TELEGRAM] Visitor cache lookup failed for {platform.id}: {exc}")

        if platform.api_key:
            try:
                visitor = await self._visitor_service.register_or_get(
                    platform_api_key=platform.api_key,
                    project_id=str(platform.project_id),
                    platform_type="telegram",
                    platform_open_id=msg_data["from_user"],
                    nickname=display_name,
                    avatar_url=avatar_url,
                )
            except Exception as exc:
                print(f"[TELEGRAM] Visitor registration failed for {platform.id}: {exc}")

        return visitor, display_name, avatar_url

    async def _maybe_upload_image_to_tgo_api(
        self,
        platform: _PlatformEntry,
        msg_data: dict[str, Any],
        visitor: Any | None,
    ) -> None:
        if msg_data.get("msg_type") != 2 or not msg_data.get("file_id") or visitor is None:
            return
        try:
            file_info = await telegram_get_file(platform.cfg.bot_token, str(msg_data["file_id"]))
            if not file_info.get("ok"):
                return
            file_path = (file_info.get("result") or {}).get("file_path")
            if not file_path:
                return
            file_bytes = await telegram_download_file(platform.cfg.bot_token, file_path)
            upload_url = f"{settings.api_base_url.rstrip('/')}/v1/chat/upload"
            channel_id = visitor.channel_id or f"{visitor.id}-vtr"
            async with httpx.AsyncClient(timeout=60) as client:
                files = {"file": ("image.jpg", file_bytes, "image/jpeg")}
                data = {
                    "channel_id": channel_id,
                    "channel_type": 251,
                    "platform_api_key": platform.api_key or "",
                }
                resp = await client.post(upload_url, data=data, files=files)
            if resp.status_code == 200:
                upload_result = resp.json()
                new_url = upload_result.get("file_url") or upload_result.get("url")
                if new_url:
                    msg_data["content"] = new_url
        except Exception as exc:
            print(f"[TELEGRAM] Error handling image from Telegram: {exc}")

    def _msg_data_from_record(self, record: TelegramInbox) -> dict[str, Any]:
        raw_payload = record.raw_payload or {}
        raw_update = raw_payload.get("update") if isinstance(raw_payload, dict) else None
        if isinstance(raw_update, dict):
            parsed = self._extract_message_data(raw_update)
            if parsed is not None:
                return parsed

        raw_message = raw_payload.get("message") if isinstance(raw_payload, dict) else None
        file_id = self._extract_photo_file_id(raw_message) if isinstance(raw_message, dict) else None
        return {
            "update_id": record.update_id,
            "message_id": record.message_id,
            "from_user": record.from_user,
            "from_username": record.from_username,
            "from_display_name": record.from_display_name,
            "from_is_bot": False,
            "chat_id": record.chat_id,
            "chat_type": record.chat_type,
            "content": record.content or "",
            "msg_type": int(record.msg_type) if str(record.msg_type).isdigit() else 1,
            "file_id": file_id,
            "message_thread_id": raw_message.get("message_thread_id") if isinstance(raw_message, dict) else None,
            "is_topic_message": bool(raw_message.get("is_topic_message", False)) if isinstance(raw_message, dict) else False,
            "raw_payload": raw_payload,
            "date": None,
        }

    async def _handle_standard_message(
        self,
        db: AsyncSession,
        platform: _PlatformEntry,
        record: TelegramInbox,
        msg_data: dict[str, Any],
    ) -> None:
        visitor, display_name, avatar_url = await self._get_or_register_visitor(platform, msg_data)
        await self._maybe_upload_image_to_tgo_api(platform, msg_data, visitor)

        mapped_raw = self._build_mapped_message(platform, msg_data)
        extra = mapped_raw.get("extra") or {}
        extra["platform_open_id"] = msg_data["from_user"]
        if visitor is not None:
            extra["channel_id"] = visitor.channel_id or f"{visitor.id}-vtr"
            extra["channel_type"] = 251
        if display_name or avatar_url:
            extra["visitor_profile"] = {"nickname": display_name, "avatar_url": avatar_url}
        mapped_raw["extra"] = extra

        await self._bridge_service.enqueue_inbound(
            project_id=platform.project_id,
            source_platform_id=platform.id,
            source_platform_api_key=platform.api_key,
            source_platform_type="telegram",
            from_uid=msg_data["from_user"],
            content=msg_data["content"],
            extra=mapped_raw.get("extra"),
            dedupe_key=f"{platform.id}:telegram:{msg_data['chat_id']}:{msg_data['message_id']}",
            display_name=display_name,
        )

        msg: NormalizedMessage = await self._normalizer.normalize(mapped_raw)
        reply_text = await process_message(
            msg=msg,
            db=db,
            tgo_api_client=self._tgo_api_client,
            sse_manager=self._sse_manager,
        )
        record.ai_reply = reply_text

    async def _process_record(
        self,
        db: AsyncSession,
        platform: _PlatformEntry,
        record: TelegramInbox,
    ) -> None:
        msg_data = self._msg_data_from_record(record)
        if not msg_data["message_id"] or not msg_data["chat_id"] or msg_data.get("from_is_bot"):
            record.status = "completed"
            record.processed_at = datetime.now(timezone.utc)
            record.error_message = None
            return

        await self._handle_standard_message(
            db=db,
            platform=platform,
            record=record,
            msg_data=msg_data,
        )

        record.status = "completed"
        record.processed_at = datetime.now(timezone.utc)
        record.error_message = None

    async def _select_candidates(
        self,
        session: AsyncSession,
        platform: _PlatformEntry,
        batch_size: int,
        max_retries: int,
    ) -> list[TelegramInbox]:
        pending = (
            await session.execute(
                select(TelegramInbox)
                .where(TelegramInbox.platform_id == platform.id, TelegramInbox.status == "pending")
                .order_by(TelegramInbox.fetched_at.asc())
                .with_for_update(skip_locked=True)
                .limit(batch_size)
            )
        ).scalars().all()

        remaining = batch_size - len(pending)
        candidates: list[TelegramInbox] = list(pending)
        if remaining > 0:
            failed = (
                await session.execute(
                    select(TelegramInbox)
                    .where(
                        TelegramInbox.platform_id == platform.id,
                        TelegramInbox.status == "failed",
                        TelegramInbox.retry_count < max_retries,
                    )
                    .order_by(TelegramInbox.processed_at.asc().nullsfirst())
                    .with_for_update(skip_locked=True)
                    .limit(batch_size * 3)
                )
            ).scalars().all()
            now = datetime.now(timezone.utc)
            for rec in failed:
                delay = max(1, 2 ** int(rec.retry_count or 0))
                if not rec.processed_at or (now - rec.processed_at).total_seconds() >= delay:
                    candidates.append(rec)
                    if len(candidates) >= batch_size:
                        break

        return candidates

    async def _claim_record(self, session: AsyncSession, record: TelegramInbox) -> bool:
        try:
            record.status = "processing"
            record.error_message = None
            await session.commit()
            return True
        except Exception as exc:
            print(f"[TELEGRAM] Claiming record failed (skip): {exc}")
            await session.rollback()
            return False

    async def _process_pending_for_platform(self, platform: _PlatformEntry) -> None:
        batch_size = max(1, int(platform.cfg.processing_batch_size or 10))
        max_retries = max(0, int(platform.cfg.max_retry_attempts or 3))

        async with self._session_factory() as db:
            candidates = await self._select_candidates(db, platform, batch_size, max_retries)
            if not candidates:
                return

            for record in candidates:
                if not await self._claim_record(db, record):
                    continue
                try:
                    await self._process_record(db, platform, record)
                    await db.commit()
                except Exception as exc:
                    print(f"[TELEGRAM] Processing failed for {platform.id}: {exc}")
                    record.status = "failed"
                    record.processed_at = datetime.now(timezone.utc)
                    record.retry_count = int(record.retry_count or 0) + 1
                    record.error_message = str(exc)[:2000]
                    await db.commit()

    async def _poll_platform(self, platform: _PlatformEntry) -> int:
        offset = platform.last_update_id + 1 if platform.last_update_id else 0
        updates = await self._get_updates(
            platform.cfg.bot_token,
            offset=offset,
            timeout=platform.cfg.polling_timeout_seconds,
        )

        new_offset = platform.last_update_id
        for update in updates:
            update_id = int(update.get("update_id", 0) or 0)
            if update_id > new_offset:
                new_offset = update_id
            try:
                await self._ingest_update(platform, update)
            except Exception as exc:
                print(f"[TELEGRAM] Error ingesting update {update_id}: {exc}")
        return new_offset

    async def _consumer_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                platforms = await self._load_active_telegram_platforms()
                polling_platforms = [platform for platform in platforms if platform.cfg.mode == "polling"]

                for platform in polling_platforms:
                    await self._delete_webhook_if_exists(platform)

                if polling_platforms:
                    results = await asyncio.gather(
                        *(self._poll_platform(platform) for platform in polling_platforms),
                        return_exceptions=True,
                    )
                    for idx, platform in enumerate(polling_platforms):
                        result = results[idx]
                        if isinstance(result, int):
                            self._platform_offsets[platform.id] = result

                for platform in platforms:
                    try:
                        await self._process_pending_for_platform(platform)
                    except Exception as exc:
                        print(f"[TELEGRAM] Consumer error for platform {platform.id}: {exc}")

                interval = platforms[0].cfg.consumer_poll_interval_seconds if platforms else 5
                await asyncio.sleep(max(1, int(interval)))
            except Exception as exc:
                print(f"[TELEGRAM] Consumer supervisor error: {exc}")
                await asyncio.sleep(5)
