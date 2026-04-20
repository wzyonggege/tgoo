from __future__ import annotations

import os
import sys
import unittest
import uuid
from types import ModuleType
from types import SimpleNamespace

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

if "app.domain.services.dispatcher" not in sys.modules:
    dispatcher_module = ModuleType("app.domain.services.dispatcher")

    async def _placeholder_process_message(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    async def _placeholder_select_adapter_for_target(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    dispatcher_module.process_message = _placeholder_process_message
    dispatcher_module.select_adapter_for_target = _placeholder_select_adapter_for_target
    sys.modules["app.domain.services.dispatcher"] = dispatcher_module

if "app.api.wecom_utils" not in sys.modules:
    wecom_utils_module = ModuleType("app.api.wecom_utils")
    wecom_utils_module.wecom_get_access_token = lambda *args, **kwargs: None
    wecom_utils_module.wecom_kf_send_msg = lambda *args, **kwargs: None
    wecom_utils_module.wecom_upload_temp_media = lambda *args, **kwargs: None
    wecom_utils_module.resolve_visitor_platform_open_id = lambda *args, **kwargs: None
    wecom_utils_module.resolve_wecom_open_kfid = lambda *args, **kwargs: None
    sys.modules["app.api.wecom_utils"] = wecom_utils_module

if "app.api.slack_utils" not in sys.modules:
    slack_utils_module = ModuleType("app.api.slack_utils")
    slack_utils_module.slack_send_text = lambda *args, **kwargs: None
    slack_utils_module.slack_send_file = lambda *args, **kwargs: None
    slack_utils_module.slack_get_dm_channel = lambda *args, **kwargs: None
    sys.modules["app.api.slack_utils"] = slack_utils_module

from app.api.v1 import messages
from app.domain.entities import NormalizedMessage


class _DummyRequest:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = body
        self.state = SimpleNamespace(request_id="req-test")
        self.app = SimpleNamespace(
            state=SimpleNamespace(
                tgo_api_client=object(),
                sse_manager=object(),
            )
        )

    async def json(self) -> dict[str, object]:
        return self._body


class _DummyDB:
    def __init__(self, platform: SimpleNamespace | None) -> None:
        self.platform = platform
        self.calls = 0

    async def scalar(self, stmt: object) -> SimpleNamespace | None:
        _ = stmt
        self.calls += 1
        return self.platform


class _RecordingBridgeService:
    calls: list[dict[str, object]] = []

    def __init__(self, session_factory: object) -> None:
        self.session_factory = session_factory

    async def enqueue_inbound(self, **kwargs: object) -> None:
        self.__class__.calls.append(kwargs)


class BridgeIngestTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_custom_bridge_falls_back_to_platform_api_key_when_fields_missing(self) -> None:
        platform = SimpleNamespace(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            type="custom",
            api_key="ak_live_custom",
            deleted_at=None,
            is_active=True,
        )
        db = _DummyDB(platform)
        request = _DummyRequest({"hello": "world"})

        original_normalize = messages.normalizer.normalize
        original_process_message = messages.process_message

        import app.domain.services.telegram_bridge as telegram_bridge_module

        original_bridge_service = telegram_bridge_module.TelegramBridgeService
        captured_messages: list[NormalizedMessage] = []

        async def fake_normalize(raw: dict[str, object]) -> NormalizedMessage:
            _ = raw
            return NormalizedMessage(
                source="webhook",
                from_uid="user-42",
                content="hello from custom",
                platform_api_key="ak_live_custom",
                platform_type="",
                platform_id="",
                extra={"platform_open_id": "user-42", "channel_id": "user-42-vtr", "channel_type": 251},
            )

        async def fake_process_message(
            msg: NormalizedMessage,
            db_obj: object,
            tgo_api_client: object,
            sse_manager: object,
        ) -> str | None:
            _ = (db_obj, tgo_api_client, sse_manager)
            captured_messages.append(msg)
            return None

        _RecordingBridgeService.calls = []
        messages.normalizer.normalize = fake_normalize
        messages.process_message = fake_process_message
        telegram_bridge_module.TelegramBridgeService = _RecordingBridgeService
        try:
            result = await messages.ingest(request, db)
        finally:
            messages.normalizer.normalize = original_normalize
            messages.process_message = original_process_message
            telegram_bridge_module.TelegramBridgeService = original_bridge_service

        self.assertEqual(result, {"ok": True})
        self.assertEqual(db.calls, 1)
        self.assertEqual(len(_RecordingBridgeService.calls), 1)
        enqueue_call = _RecordingBridgeService.calls[0]
        self.assertEqual(enqueue_call["source_platform_api_key"], "ak_live_custom")
        self.assertEqual(enqueue_call["source_platform_id"], platform.id)
        self.assertEqual(enqueue_call["project_id"], platform.project_id)
        self.assertEqual(len(captured_messages), 1)
        self.assertEqual(captured_messages[0].platform_id, str(platform.id))
        self.assertEqual(captured_messages[0].platform_type, "custom")

    async def test_ingest_returns_not_found_when_platform_cannot_be_resolved(self) -> None:
        db = _DummyDB(None)
        request = _DummyRequest({"hello": "world"})

        original_normalize = messages.normalizer.normalize
        original_process_message = messages.process_message
        captured_messages: list[NormalizedMessage] = []

        async def fake_normalize(raw: dict[str, object]) -> NormalizedMessage:
            _ = raw
            return NormalizedMessage(
                source="webhook",
                from_uid="user-missing",
                content="hello from missing custom",
                platform_api_key="ak_live_missing",
                platform_type="",
                platform_id="",
                extra={"platform_open_id": "user-missing", "channel_id": "user-missing-vtr", "channel_type": 251},
            )

        async def fake_process_message(
            msg: NormalizedMessage,
            db_obj: object,
            tgo_api_client: object,
            sse_manager: object,
        ) -> str | None:
            _ = (db_obj, tgo_api_client, sse_manager)
            captured_messages.append(msg)
            return None

        messages.normalizer.normalize = fake_normalize
        messages.process_message = fake_process_message
        try:
            response = await messages.ingest(request, db)
        finally:
            messages.normalizer.normalize = original_normalize
            messages.process_message = original_process_message

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.body.decode("utf-8"), '{"error":{"code":"PLATFORM_NOT_FOUND","message":"Platform not found","details":null},"request_id":"req-test"}')
        self.assertEqual(db.calls, 1)
        self.assertEqual(captured_messages, [])

    async def test_ingest_custom_api_bridge_only_skips_process_message(self) -> None:
        platform = SimpleNamespace(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            type="custom",
            api_key="ak_live_custom",
            name="自定义",
            deleted_at=None,
            is_active=True,
        )
        db = _DummyDB(platform)
        request = _DummyRequest({"source": "custom_api"})

        original_normalize = messages.normalizer.normalize
        original_process_message = messages.process_message

        import app.domain.services.telegram_bridge as telegram_bridge_module

        original_bridge_service = telegram_bridge_module.TelegramBridgeService
        captured_messages: list[NormalizedMessage] = []

        async def fake_normalize(raw: dict[str, object]) -> NormalizedMessage:
            return NormalizedMessage(
                source=str(raw.get("source") or "webhook"),
                from_uid="user-bridge",
                content="hello bridge only",
                platform_api_key="ak_live_custom",
                platform_type="custom",
                platform_id="",
                extra={"platform_open_id": "user-bridge", "channel_id": "user-bridge-vtr", "channel_type": 251},
            )

        async def fake_process_message(
            msg: NormalizedMessage,
            db_obj: object,
            tgo_api_client: object,
            sse_manager: object,
        ) -> str | None:
            _ = (db_obj, tgo_api_client, sse_manager)
            captured_messages.append(msg)
            return None

        _RecordingBridgeService.calls = []
        messages.normalizer.normalize = fake_normalize
        messages.process_message = fake_process_message
        telegram_bridge_module.TelegramBridgeService = _RecordingBridgeService
        try:
            result = await messages.ingest(request, db)
        finally:
            messages.normalizer.normalize = original_normalize
            messages.process_message = original_process_message
            telegram_bridge_module.TelegramBridgeService = original_bridge_service

        self.assertEqual(result, {"ok": True, "bridge_only": True})
        self.assertEqual(db.calls, 1)
        self.assertEqual(len(_RecordingBridgeService.calls), 1)
        self.assertEqual(captured_messages, [])


if __name__ == "__main__":
    unittest.main()
