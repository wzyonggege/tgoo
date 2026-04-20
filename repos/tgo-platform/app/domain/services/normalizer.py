from __future__ import annotations
from app.domain.entities import NormalizedMessage
from app.domain.ports import MessageNormalizer


class DefaultMessageNormalizer(MessageNormalizer):
    async def normalize(self, raw: dict) -> NormalizedMessage:
        # /ingest callers are not all consistent about carrying platform_id/platform_type.
        # Keep the required identity fields strict, but tolerate missing platform metadata so
        # the API-key fallback in the ingest endpoint can recover the platform row.
        return NormalizedMessage(
            source=raw.get("source", "webhook"),
            from_uid=raw["from_uid"],
            content=raw["content"],
            platform_api_key=raw["platform_api_key"],
            platform_type=str(raw.get("platform_type") or ""),
            platform_id=str(raw.get("platform_id") or ""),
            extra=raw.get("extra", {}),
        )


normalizer = DefaultMessageNormalizer()
