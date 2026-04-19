from __future__ import annotations

import asyncio
import os
import sys
import unittest
from types import ModuleType
from types import SimpleNamespace

import httpx

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

from app.api.v1 import messages


class _DummyDB:
    def __init__(self, platform: SimpleNamespace) -> None:
        self.platform = platform

    async def scalar(self, stmt: object) -> SimpleNamespace:
        _ = stmt
        return self.platform


class CustomPlatformAsyncCallbackTests(unittest.IsolatedAsyncioTestCase):
    def _build_request(self) -> messages.SendMessageRequest:
        return messages.SendMessageRequest(
            platform_api_key="ak_live_test",
            from_uid="staff-1",
            channel_id="visitor-1-vtr",
            channel_type=251,
            platform_open_id="third-party-user-1",
            payload={"type": 1, "content": "hello"},
            client_msg_no="client-msg-1",
        )

    def _build_db(self) -> _DummyDB:
        platform = SimpleNamespace(
            type="custom",
            config={"callback_url": "https://callback.example.com/webhook"},
            api_key="ak_live_test",
            id="platform-1",
            is_active=True,
        )
        return _DummyDB(platform)

    async def test_custom_callback_is_queued_without_blocking_main_response(self) -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        created_tasks: list[asyncio.Task[None]] = []

        class DelayedAsyncClient:
            def __init__(self, timeout: int) -> None:
                self.timeout = timeout

            async def __aenter__(self) -> DelayedAsyncClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
                _ = (exc_type, exc, tb)
                return False

            async def post(self, url: str, json: dict[str, object]) -> httpx.Response:
                _ = (url, json, self.timeout)
                started.set()
                await release.wait()
                request = httpx.Request("POST", url)
                return httpx.Response(200, request=request, json={"ok": True})

        original_async_client = messages.httpx.AsyncClient
        original_create_task = messages.asyncio.create_task

        def capture_create_task(coro: object) -> asyncio.Task[None]:
            task = original_create_task(coro)
            created_tasks.append(task)
            return task

        messages.httpx.AsyncClient = DelayedAsyncClient
        messages.asyncio.create_task = capture_create_task
        try:
            result = await asyncio.wait_for(
                messages.send_message(
                    self._build_request(),
                    SimpleNamespace(state=SimpleNamespace(request_id="req-1")),
                    self._build_db(),
                ),
                timeout=0.03,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["callback_status"], "queued")
            self.assertEqual(result["client_msg_no"], "client-msg-1")
            self.assertEqual(len(created_tasks), 1)

            await asyncio.wait_for(started.wait(), timeout=0.03)
            release.set()
            await asyncio.gather(*created_tasks)
        finally:
            messages.httpx.AsyncClient = original_async_client
            messages.asyncio.create_task = original_create_task

    async def test_custom_callback_timeout_does_not_fail_main_response(self) -> None:
        created_tasks: list[asyncio.Task[None]] = []

        class TimeoutAsyncClient:
            def __init__(self, timeout: int) -> None:
                self.timeout = timeout

            async def __aenter__(self) -> TimeoutAsyncClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
                _ = (exc_type, exc, tb)
                return False

            async def post(self, url: str, json: dict[str, object]) -> httpx.Response:
                _ = (url, json, self.timeout)
                raise httpx.TimeoutException("timed out")

        original_async_client = messages.httpx.AsyncClient
        original_create_task = messages.asyncio.create_task

        def capture_create_task(coro: object) -> asyncio.Task[None]:
            task = original_create_task(coro)
            created_tasks.append(task)
            return task

        messages.httpx.AsyncClient = TimeoutAsyncClient
        messages.asyncio.create_task = capture_create_task
        try:
            result = await messages.send_message(
                self._build_request(),
                SimpleNamespace(state=SimpleNamespace(request_id="req-2")),
                self._build_db(),
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["callback_status"], "queued")
            await asyncio.gather(*created_tasks)
        finally:
            messages.httpx.AsyncClient = original_async_client
            messages.asyncio.create_task = original_create_task

    async def test_custom_callback_http_error_does_not_fail_main_response(self) -> None:
        created_tasks: list[asyncio.Task[None]] = []

        class HttpErrorAsyncClient:
            def __init__(self, timeout: int) -> None:
                self.timeout = timeout

            async def __aenter__(self) -> HttpErrorAsyncClient:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
                _ = (exc_type, exc, tb)
                return False

            async def post(self, url: str, json: dict[str, object]) -> httpx.Response:
                _ = (json, self.timeout)
                request = httpx.Request("POST", url)
                return httpx.Response(500, request=request)

        original_async_client = messages.httpx.AsyncClient
        original_create_task = messages.asyncio.create_task

        def capture_create_task(coro: object) -> asyncio.Task[None]:
            task = original_create_task(coro)
            created_tasks.append(task)
            return task

        messages.httpx.AsyncClient = HttpErrorAsyncClient
        messages.asyncio.create_task = capture_create_task
        try:
            result = await messages.send_message(
                self._build_request(),
                SimpleNamespace(state=SimpleNamespace(request_id="req-3")),
                self._build_db(),
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["callback_status"], "queued")
            await asyncio.gather(*created_tasks)
        finally:
            messages.httpx.AsyncClient = original_async_client
            messages.asyncio.create_task = original_create_task
