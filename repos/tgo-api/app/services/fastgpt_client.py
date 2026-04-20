"""FastGPT OpenAPI client for chat completions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("fastgpt_client")


class FastGPTClient:
    """Lightweight client that wraps FastGPT's OpenAPI-compatible chat endpoint."""

    def __init__(self) -> None:
        self.base_url = settings.FASTGPT_API_BASE.rstrip("/")
        self.api_key = settings.FASTGPT_API_KEY
        self.model = settings.FASTGPT_MODEL
        self.timeout = settings.FASTGPT_TIMEOUT
        self.completions_path = settings.FASTGPT_COMPLETIONS_PATH

    def _resolve_config(self, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merge runtime overrides with defaults."""
        config = {
            "api_base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model,
            "timeout": self.timeout,
            "completions_path": self.completions_path,
        }
        if override:
            config.update({k: v for k, v in override.items() if v is not None})

        api_base_url = config.get("api_base_url")
        if not api_base_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider base URL is not configured",
            )
        config["api_base_url"] = str(api_base_url).rstrip("/")

        api_key = config.get("api_key")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider API key is not configured",
            )
        config["api_key"] = api_key
        return config

    async def generate_response(
        self,
        message: str,
        *,
        system_message: Optional[str] = None,
        expected_output: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        config_override: Optional[Dict[str, Any]] = None,
        chat_id: Optional[str] = None,
        custom_uid: Optional[str] = None,
        stream: bool = False,
        detail: bool = False,
    ) -> str:
        """Call FastGPT to get a chat completion for the given message."""
        config = self._resolve_config(config_override)

        messages: List[Dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        completions_path = config.get("completions_path") or settings.FASTGPT_COMPLETIONS_PATH
        base_url = f"{config['api_base_url'].rstrip('/')}/"
        url = urljoin(base_url, completions_path.lstrip("/"))
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "X-Request-ID": str(uuid4()),
        }
        payload: Dict[str, Any] = {
            "chatId": chat_id or uuid4().hex,
            "stream": stream,
            "detail": detail,
            "messages": messages,
        }
        model = config.get("model")
        if model:
            payload["model"] = model
        if custom_uid:
            payload["customUid"] = str(custom_uid)

        try:
            async with httpx.AsyncClient(timeout=config.get("timeout", settings.FASTGPT_TIMEOUT)) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("FastGPT request timeout", extra={"url": url})
            raise HTTPException(status_code=504, detail="FastGPT request timed out") from exc
        except httpx.HTTPError as exc:
            logger.error("FastGPT request error", extra={"error": str(exc), "url": url})
            raise HTTPException(status_code=502, detail="Failed to connect to FastGPT") from exc

        if response.status_code >= 400:
            try:
                error_data = response.json()
            except Exception:
                error_data = {"error": response.text}
            logger.error(
                "FastGPT error response",
                extra={
                    "status_code": response.status_code,
                    "error": error_data,
                    "url": url,
                },
            )
            raise HTTPException(
                status_code=response.status_code,
                detail=error_data,
            )

        data: Dict[str, Any] = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise HTTPException(
                status_code=502,
                detail="FastGPT returned no completion",
            )
        message_data = choices[0].get("message") or {}
        content = message_data.get("content")
        if not content:
            raise HTTPException(
                status_code=502,
                detail="FastGPT completion missing content",
            )
        return str(content)


fastgpt_client = FastGPTClient()
