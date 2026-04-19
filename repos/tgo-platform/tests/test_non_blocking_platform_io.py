from __future__ import annotations

import asyncio
import os
import sys
import time
from types import SimpleNamespace
from types import ModuleType
import unittest

os.environ.setdefault("api_base_url", "http://example.com")
os.environ.setdefault("database_url", "postgresql+asyncpg://user:pass@localhost:5432/tgo")

if "slack_sdk" not in sys.modules:
    slack_sdk_module = ModuleType("slack_sdk")
    slack_sdk_errors_module = ModuleType("slack_sdk.errors")

    class _PlaceholderWebClient:
        def __init__(self, token: str) -> None:
            self.token = token

    class _PlaceholderSlackApiError(Exception):
        def __init__(self, message: str = "slack error") -> None:
            super().__init__(message)
            self.response = {"error": message}

    slack_sdk_module.WebClient = _PlaceholderWebClient
    slack_sdk_errors_module.SlackApiError = _PlaceholderSlackApiError
    sys.modules["slack_sdk"] = slack_sdk_module
    sys.modules["slack_sdk.errors"] = slack_sdk_errors_module

from app.api import slack_utils
import app.domain.services.adapters.email as email_adapter_module
from app.domain.services.adapters.email import EmailAdapter


class NonBlockingPlatformIOTests(unittest.IsolatedAsyncioTestCase):
    async def test_slack_send_text_does_not_block_event_loop(self) -> None:
        class DummyWebClient:
            def __init__(self, token: str) -> None:
                self.token = token

            def chat_postMessage(
                self,
                *,
                channel: str,
                text: str,
                thread_ts: str | None = None,
            ) -> SimpleNamespace:
                time.sleep(0.05)
                return SimpleNamespace(
                    data={"ok": True, "channel": channel, "text": text, "thread_ts": thread_ts}
                )

        original_web_client = slack_utils.WebClient
        slack_utils.WebClient = DummyWebClient
        try:
            send_task = asyncio.create_task(slack_utils.slack_send_text("xoxb-test", "C123", "hello"))
            heartbeat_task = asyncio.create_task(asyncio.sleep(0.01))

            await asyncio.wait_for(heartbeat_task, timeout=0.03)
            result = await send_task

            self.assertTrue(result["ok"])
            self.assertEqual(result["channel"], "C123")
        finally:
            slack_utils.WebClient = original_web_client

    async def test_email_adapter_send_final_does_not_block_event_loop(self) -> None:
        class DummySMTP:
            def __init__(self, host: str, port: int, timeout: int = 30) -> None:
                self.host = host
                self.port = port
                self.timeout = timeout

            def ehlo(self) -> None:
                time.sleep(0.01)

            def has_extn(self, name: str) -> bool:
                _ = name
                return False

            def login(self, username: str, password: str) -> None:
                _ = username
                _ = password
                time.sleep(0.01)

            def send_message(self, message: object) -> None:
                _ = message
                time.sleep(0.05)

            def quit(self) -> None:
                return None

            def close(self) -> None:
                return None

        original_smtp = email_adapter_module.smtplib.SMTP
        original_smtp_ssl = email_adapter_module.smtplib.SMTP_SSL
        email_adapter_module.smtplib.SMTP = DummySMTP
        email_adapter_module.smtplib.SMTP_SSL = DummySMTP
        try:
            adapter = EmailAdapter(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="bot@example.com",
                smtp_password="secret",
                smtp_use_tls=False,
                to_addr="user@example.com",
                from_addr="bot@example.com",
                subject="Test",
            )

            send_task = asyncio.create_task(adapter.send_final({"text": "hello"}))
            heartbeat_task = asyncio.create_task(asyncio.sleep(0.01))

            await asyncio.wait_for(heartbeat_task, timeout=0.03)
            await send_task
        finally:
            email_adapter_module.smtplib.SMTP = original_smtp
            email_adapter_module.smtplib.SMTP_SSL = original_smtp_ssl
