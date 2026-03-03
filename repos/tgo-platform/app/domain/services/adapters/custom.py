"""Custom platform outbound adapter.

Posts AI replies to the platform callback_url using the same payload shape as
/v1/messages/send custom outbound.
"""
from __future__ import annotations

import uuid

import httpx

from app.core.config import settings
from app.domain.entities import StreamEvent
from app.domain.services.adapters.base import BasePlatformAdapter


class CustomPlatformAdapter(BasePlatformAdapter):
    """Outbound adapter for custom platforms (callback URL based)."""

    supports_stream = False

    def __init__(
        self,
        callback_url: str,
        platform_api_key: str,
        platform_open_id: str,
        channel_id: str,
        channel_type: int = 251,
        http_timeout: int | None = None,
    ) -> None:
        self.callback_url = callback_url.strip()
        self.platform_api_key = platform_api_key
        self.platform_open_id = platform_open_id
        self.channel_id = channel_id
        self.channel_type = channel_type
        self.http_timeout = http_timeout or settings.request_timeout_seconds

    async def send_incremental(self, ev: StreamEvent) -> None:
        # Custom callback uses non-streaming final delivery.
        return

    async def send_final(self, content: dict) -> None:
        text = str((content or {}).get("text") or "").strip()
        if not text:
            return
        if not self.callback_url:
            raise RuntimeError("Custom platform callback_url is required")
        if not self.platform_api_key:
            raise RuntimeError("Custom platform api_key is required")

        message_id = str(uuid.uuid4())
        client_msg_no = f"ai_{uuid.uuid4().hex}"

        payload = {
            "platform_api_key": self.platform_api_key,
            "message_id": message_id,
            "channel_id": self.channel_id,
            "channel_type": self.channel_type,
            "platform_open_id": self.platform_open_id,
            "client_msg_no": client_msg_no,
            "payload": {
                "type": 1,
                "content": text,
            },
        }

        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            resp = await client.post(self.callback_url, json=payload)
            resp.raise_for_status()
