import unittest

from app.domain.services.telegram_bridge import (
    _format_bridge_text,
    _sanitize_extra,
    _source_key,
)


class TelegramBridgeHelperTests(unittest.TestCase):
    def test_source_key_distinguishes_platforms_with_same_uid(self) -> None:
        telegram_key = _source_key(
            "telegram",
            "platform_a",
            "123",
            {"telegram": {"chat_id": "456"}},
        )
        wecom_key = _source_key(
            "wecom",
            "platform_b",
            "123",
            {"wecom": {"external_userid": "123", "open_kfid": "kf_1"}, "source_type": "wecom_kf"},
        )
        self.assertNotEqual(telegram_key, wecom_key)

    def test_source_key_distinguishes_same_user_across_channels(self) -> None:
        first = _source_key(
            "custom",
            "platform_a",
            "user_1",
            {"channel_id": "channel_a", "channel_type": 251, "platform_open_id": "user_1"},
        )
        second = _source_key(
            "custom",
            "platform_a",
            "user_1",
            {"channel_id": "channel_b", "channel_type": 251, "platform_open_id": "user_1"},
        )
        self.assertNotEqual(first, second)

    def test_source_key_distinguishes_platform_instances(self) -> None:
        first = _source_key(
            "wecom_bot",
            "platform_a",
            "123",
            {"wecom": {"chat_id": "room_1"}},
        )
        second = _source_key(
            "wecom_bot",
            "platform_b",
            "123",
            {"wecom": {"chat_id": "room_1"}},
        )
        self.assertNotEqual(first, second)

    def test_sanitize_extra_removes_visitor_profile_only(self) -> None:
        extra = {
            "project_id": "p1",
            "visitor_profile": {"nickname": "alice"},
            "telegram": {"chat_id": "1"},
        }
        sanitized = _sanitize_extra(extra)
        self.assertEqual(sanitized["project_id"], "p1")
        self.assertEqual(sanitized["telegram"]["chat_id"], "1")
        self.assertNotIn("visitor_profile", sanitized)

    def test_format_bridge_text_contains_platform_and_sender(self) -> None:
        text = _format_bridge_text(
            platform_type="telegram",
            display_name="Alice",
            from_uid="u_1",
            content="hello",
        )
        self.assertIn("[Telegram] Alice", text)
        self.assertIn("ID: u_1", text)
        self.assertTrue(text.endswith("hello"))


if __name__ == "__main__":
    unittest.main()
