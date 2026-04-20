import unittest

from app.domain.services.telegram_bridge import (
    _build_inbound_payload,
    _build_outbound_payload,
    _deserialize_payload,
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

    def test_source_key_uses_channel_id_for_telegram_bridge_matching(self) -> None:
        first = _source_key(
            "telegram",
            "platform_a",
            "user_1",
            {"channel_id": "visitor_a-vtr", "channel_type": 251, "platform_open_id": "user_1", "telegram": {"chat_id": "-1001"}},
        )
        second = _source_key(
            "telegram",
            "platform_a",
            "user_1",
            {"channel_id": "visitor_b-vtr", "channel_type": 251, "platform_open_id": "user_1", "telegram": {"chat_id": "-1001"}},
        )
        self.assertNotEqual(first, second)

    def test_source_key_uses_channel_id_for_slack_bridge_matching(self) -> None:
        first = _source_key(
            "slack",
            "platform_a",
            "user_1",
            {"channel_id": "visitor_a-vtr", "channel_type": 251, "platform_open_id": "user_1", "slack": {"channel": "D123"}},
        )
        second = _source_key(
            "slack",
            "platform_a",
            "user_1",
            {"channel_id": "visitor_b-vtr", "channel_type": 251, "platform_open_id": "user_1", "slack": {"channel": "D123"}},
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
            platform_name="测试渠道",
        )
        self.assertIn("[测试渠道] Alice", text)
        self.assertIn("ID: u_1", text)
        self.assertTrue(text.endswith("hello"))

    def test_build_inbound_payload_uses_photo_for_image_url(self) -> None:
        payload = _deserialize_payload(
            _build_inbound_payload(
                platform_type="telegram",
                display_name="Alice",
                from_uid="u_1",
                content="https://example.com/a.jpg",
                extra={"msg_type": 2, "platform_name": "测试渠道"},
            )
        )
        self.assertEqual(payload.kind, "image")
        self.assertEqual(payload.media_url, "https://example.com/a.jpg")
        self.assertIn("[测试渠道] Alice", payload.caption or "")

    def test_build_outbound_payload_marks_staff_image(self) -> None:
        payload = _deserialize_payload(
            _build_outbound_payload(
                sender_label="客服",
                content="https://example.com/b.png",
                msg_type=2,
            )
        )
        self.assertEqual(payload.kind, "image")
        self.assertEqual(payload.media_url, "https://example.com/b.png")
        self.assertEqual(payload.caption, "[客服]")


if __name__ == "__main__":
    unittest.main()
