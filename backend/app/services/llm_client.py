"""LLM client for streaming chat completions."""

import asyncio
import json
import logging
from typing import AsyncGenerator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LlmClient:
    """HTTP client for LLM API with streaming support."""

    def __init__(self, base_url: str = "", timeout: int = 30):
        """
        Initialize LLM client.

        Args:
            base_url: Mock LLM server URL (or empty string to use settings)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or settings.mock_llm_url
        self.timeout = timeout

    async def stream_completion(
        self,
        messages: list[dict],
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion tokens from LLM.

        Yields tokens as they arrive. On client disconnect (asyncio.CancelledError),
        the upstream connection is closed.

        Args:
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens in response

        Yields:
            Token strings (potentially empty for heartbeats)

        Raises:
            asyncio.CancelledError: On client disconnect (normal cleanup)
            Exception: On LLM errors (e.g., 429, 503, timeouts)
        """
        payload = {
            "model": "gpt-4",
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._get_api_key()}"},
                ) as response:
                    if response.status_code != 200:
                        error_msg = f"LLM error {response.status_code}"
                        logger.error(error_msg, extra={"status": response.status_code})
                        raise Exception(error_msg)

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        # Parse SSE format: "data: {...}"
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data_str)
                                # Extract token from OpenAI format
                                token = (
                                    chunk.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                logger.warning(
                                    "Failed to parse LLM chunk",
                                    extra={"line": line},
                                )
                                continue

        except asyncio.CancelledError:
            logger.info("LLM streaming cancelled (client disconnected)")
            raise

    def _get_api_key(self) -> str:
        """Get API key from settings (or mock key)."""
        # TODO: Implement real key retrieval with redaction in logs
        return settings.llm_api_key or "mock-key"
