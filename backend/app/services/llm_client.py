"""LLM client for streaming chat completions with retry and circuit breaker."""

import asyncio
import json
import logging
import time
import random
from typing import AsyncGenerator
from enum import Enum

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class LlmUnavailableError(Exception):
    """Raised when the LLM is rate limited, down, or the circuit breaker is open."""


class LlmClient:
    """HTTP client for LLM API with streaming support, retry logic, and circuit breaker."""

    # Retry configuration
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # Start with 1 second
    MAX_DELAY = 8.0   # Cap at 8 seconds
    MAX_RETRY_AFTER = 30.0  # Never sleep longer than this for a Retry-After header
    JITTER_FACTOR = 0.1  # Add ±10% jitter

    # Circuit breaker configuration
    FAILURE_THRESHOLD = 5  # Open after 5 consecutive failures
    CIRCUIT_BREAKER_TIMEOUT = 30.0  # Reset after 30 seconds

    # Retryable status codes
    RETRYABLE_CODES = {429, 503}

    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        max_retries: int = MAX_RETRIES,
        circuit_breaker_timeout: float = CIRCUIT_BREAKER_TIMEOUT,
        api_key: str | None = None,
    ):
        """
        Initialize LLM client with retry and circuit breaker support.

        Args:
            base_url: Mock LLM server URL (or empty string to use settings)
            timeout: Request timeout in seconds (per attempt)
            max_retries: Maximum number of retries for transient errors
            circuit_breaker_timeout: Seconds to wait before resetting circuit breaker
        """
        self.base_url = base_url or settings.mock_llm_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self._api_key = api_key

        # Circuit breaker state
        self._circuit_breaker_state = CircuitBreakerState.CLOSED
        self._circuit_breaker_failures = 0
        self._circuit_breaker_open_at = 0.0

    def _should_retry(self, status_code: int) -> bool:
        """Check if status code is retryable."""
        return status_code in self.RETRYABLE_CODES

    def _get_retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        """
        Calculate retry delay with exponential backoff and jitter.

        Args:
            attempt: Retry attempt number (0-indexed)
            retry_after: Retry-After header value (seconds as string)

        Returns:
            Delay in seconds
        """
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), self.MAX_RETRY_AFTER)
            except (ValueError, TypeError):
                pass

        # Exponential backoff: 1s, 2s, 4s, 8s, capped at MAX_DELAY
        delay = self.BASE_DELAY * (2 ** attempt)

        # Add jitter: ±10% before capping
        jitter = delay * self.JITTER_FACTOR
        delay = delay + random.uniform(-jitter, jitter)

        # Cap after jitter to ensure we don't exceed MAX_DELAY
        delay = min(delay, self.MAX_DELAY)

        return max(delay, 0)

    def _check_circuit_breaker(self) -> bool:
        """
        Check circuit breaker state. If open and timeout elapsed, reset to half-open.

        Returns:
            True if request should proceed, False if circuit is open
        """
        if self._circuit_breaker_state == CircuitBreakerState.CLOSED:
            return True

        if self._circuit_breaker_state == CircuitBreakerState.OPEN:
            elapsed = time.time() - self._circuit_breaker_open_at
            if elapsed >= self.circuit_breaker_timeout:
                logger.info(
                    "Circuit breaker reset (trying half-open)",
                    extra={"elapsed": elapsed},
                )
                self._circuit_breaker_state = CircuitBreakerState.HALF_OPEN
                self._circuit_breaker_failures = 0
                return True
            else:
                logger.warning(
                    "Circuit breaker open, rejecting request",
                    extra={"retry_in": self.circuit_breaker_timeout - elapsed},
                )
                return False

        # HALF_OPEN: proceed with test request
        return True

    def _record_success(self) -> None:
        """Record successful request; failures only count while consecutive."""
        if self._circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
            logger.info("Circuit breaker closed (service recovered)")
            self._circuit_breaker_state = CircuitBreakerState.CLOSED
        self._circuit_breaker_failures = 0

    def _record_failure(self) -> None:
        """Record failure; open circuit breaker if threshold reached."""
        self._circuit_breaker_failures += 1

        # A failed probe while half-open re-opens the circuit immediately
        if (
            self._circuit_breaker_state == CircuitBreakerState.HALF_OPEN
            or self._circuit_breaker_failures >= self.FAILURE_THRESHOLD
        ):
            logger.error(
                "Circuit breaker opened (too many failures)",
                extra={"failures": self._circuit_breaker_failures},
            )
            self._circuit_breaker_state = CircuitBreakerState.OPEN
            self._circuit_breaker_open_at = time.time()

    async def stream_completion(
        self,
        messages: list[dict],
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion tokens from LLM with retry and circuit breaker.

        Retries on transient errors (429, 503) with exponential backoff.
        Implements circuit breaker to prevent cascading failures.
        On client disconnect (asyncio.CancelledError), closes connection.

        Args:
            messages: List of message dicts with "role" and "content"
            max_tokens: Maximum tokens in response

        Yields:
            Token strings (potentially empty for heartbeats)

        Raises:
            asyncio.CancelledError: On client disconnect (normal cleanup)
            Exception: On LLM errors after exhausting retries or circuit breaker open
        """
        payload = {
            "model": "gpt-4",
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        # Check circuit breaker before attempting
        if not self._check_circuit_breaker():
            raise LlmUnavailableError("Circuit breaker open; LLM service unavailable")

        last_error = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0 and not self._check_circuit_breaker():
                raise LlmUnavailableError("Circuit breaker open; LLM service unavailable")
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/v1/chat/completions",
                        json=payload,
                        headers={"Authorization": self._auth_header()},
                    ) as response:
                        if response.status_code == 200:
                            # Success: record and yield tokens
                            self._record_success()

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
                            return  # Success, exit

                        elif self._should_retry(response.status_code):
                            # Transient error: record and retry
                            logger.warning(
                                f"LLM error {response.status_code}, retrying",
                                extra={
                                    "status": response.status_code,
                                    "attempt": attempt + 1,
                                    "max": self.max_retries + 1,
                                },
                            )
                            self._record_failure()
                            last_error = LlmUnavailableError(
                                f"LLM error {response.status_code}"
                            )

                            # Read retry-after header
                            retry_after = response.headers.get("retry-after")

                            if attempt < self.max_retries:
                                delay = self._get_retry_delay(attempt, retry_after)
                                logger.info(
                                    f"Waiting {delay:.2f}s before retry",
                                    extra={"delay": delay},
                                )
                                await asyncio.sleep(delay)
                                continue

                        else:
                            # Non-retryable error: fail immediately
                            error_msg = f"LLM error {response.status_code}"
                            logger.error(
                                error_msg,
                                extra={"status": response.status_code},
                            )
                            # Failure is recorded once by the generic handler below
                            raise Exception(error_msg)

            except asyncio.CancelledError:
                logger.info("LLM streaming cancelled (client disconnected)")
                raise
            except httpx.TimeoutException as e:
                logger.error(
                    "LLM request timeout",
                    extra={"attempt": attempt + 1, "timeout": self.timeout},
                )
                self._record_failure()
                last_error = e

                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt)
                    logger.info(f"Retrying after timeout (delay: {delay:.2f}s)")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise LlmUnavailableError("LLM request timed out") from e

            except Exception as e:
                logger.error(
                    f"LLM request failed: {e}",
                    extra={"attempt": attempt + 1},
                )
                self._record_failure()
                raise

        # Exhausted all retries
        if last_error:
            raise last_error
        raise LlmUnavailableError("LLM request failed after max retries")

    def _auth_header(self) -> str:
        """Build the Authorization header value (never logged)."""
        return f"Bearer {self._get_api_key()}"

    def _get_api_key(self) -> str:
        """Get API key from the constructor, settings, or the mock key."""
        return self._api_key or settings.llm_api_key or "mock-key"
