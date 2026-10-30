"""Tests for LLM client resilience (retry, backoff, circuit breaker)."""

import pytest
import asyncio
import time

import respx
import httpx

from app.services.llm_client import LlmClient


class TestLlmClientRetry:
    """Test retry logic on transient errors (429, 503)."""

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_errors(self):
        """Test that non-retryable 4xx errors fail immediately."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        with respx.mock:
            respx.post("http://localhost:8001/v1/chat/completions").mock(
                return_value=httpx.Response(400, json={"error": "Bad request"})
            )

            # Should fail immediately without retries
            with pytest.raises(Exception):
                async for _ in llm_client.stream_completion(
                    messages=[{"role": "user", "content": "Test"}]
                ):
                    pass

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that request fails after max retries."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        with respx.mock:
            # All requests return 429
            respx.post("http://localhost:8001/v1/chat/completions").mock(
                return_value=httpx.Response(429, headers={"Retry-After": "0.01"})
            )

            # Should raise exception after exhausting retries
            with pytest.raises(Exception):
                async for _ in llm_client.stream_completion(
                    messages=[{"role": "user", "content": "Test"}]
                ):
                    pass

    @pytest.mark.asyncio
    async def test_respects_retry_after_header(self):
        """Test that Retry-After header is respected."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        start_time = time.time()

        with respx.mock:
            # Return 429 with Retry-After: 0.1
            respx.post("http://localhost:8001/v1/chat/completions").mock(
                return_value=httpx.Response(429, headers={"Retry-After": "0.1"})
            )

            with pytest.raises(Exception):
                async for _ in llm_client.stream_completion(
                    messages=[{"role": "user", "content": "Test"}]
                ):
                    pass

            elapsed = time.time() - start_time
            # Should have waited at least once (even though all retries fail)
            # First retry-after: 0.1s
            assert elapsed >= 0.08


class TestLlmClientTimeout:
    """Test timeout handling."""

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_fast(self):
        """Test that non-retryable errors fail without retries."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        with respx.mock:
            respx.post("http://localhost:8001/v1/chat/completions").mock(
                return_value=httpx.Response(401, json={"error": "Unauthorized"})
            )

            start = time.time()
            with pytest.raises(Exception):
                async for _ in llm_client.stream_completion(
                    messages=[{"role": "user", "content": "Test"}]
                ):
                    pass
            elapsed = time.time() - start
            
            # Should fail quickly (< 1 second, no retries)
            assert elapsed < 1.0


class TestLlmClientCircuitBreaker:
    """Test circuit breaker pattern (stop retrying after N consecutive failures)."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_tracking(self):
        """Test that circuit breaker tracks failure state."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        # Initially closed
        assert llm_client._check_circuit_breaker() is True

        # Record failures
        for _ in range(5):
            llm_client._record_failure()

        # Should be open now
        assert llm_client._check_circuit_breaker() is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_timeout(self):
        """Test that circuit breaker resets after timeout period."""
        llm_client = LlmClient(
            base_url="http://localhost:8001",
            timeout=30,
            circuit_breaker_timeout=0.05,  # 50ms reset timeout
        )

        # Open the circuit breaker
        for _ in range(5):
            llm_client._record_failure()

        assert llm_client._check_circuit_breaker() is False

        # Wait for reset timeout
        await asyncio.sleep(0.1)

        # Should be half-open and allow retry
        assert llm_client._check_circuit_breaker() is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_on_success(self):
        """Test that circuit breaker closes when half-open request succeeds."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        # Simulate half-open state
        for _ in range(5):
            llm_client._record_failure()
        
        # Fast-track to half-open
        await asyncio.sleep(0.01)  # Small delay
        llm_client._circuit_breaker_open_at = time.time() - 31  # Pretend it's been open
        
        # Check circuit - should transition to half-open
        assert llm_client._check_circuit_breaker() is True
        
        # Simulate success
        llm_client._record_success()
        
        # Should be closed now
        assert llm_client._check_circuit_breaker() is True
        assert llm_client._circuit_breaker_failures == 0


class TestLlmClientExponentialBackoff:
    """Test exponential backoff calculation."""

    def test_exponential_backoff_calculation(self):
        """Test that backoff delays increase exponentially."""
        llm_client = LlmClient(base_url="http://localhost:8001")

        delay_0 = llm_client._get_retry_delay(0)
        delay_1 = llm_client._get_retry_delay(1)
        delay_2 = llm_client._get_retry_delay(2)
        delay_3 = llm_client._get_retry_delay(3)

        # Should be roughly exponential (with jitter, allow ±20%)
        assert 0.8 <= delay_0 <= 1.2
        assert 1.6 <= delay_1 <= 2.4
        assert 3.2 <= delay_2 <= 4.8
        assert 6.4 <= delay_3 <= 8.0  # Capped at MAX_DELAY

    def test_retry_after_header_override(self):
        """Test that Retry-After header overrides exponential backoff."""
        llm_client = LlmClient(base_url="http://localhost:8001")

        delay = llm_client._get_retry_delay(attempt=5, retry_after="0.5")
        assert delay == 0.5


class TestLlmClientIntegration:
    """Integration tests with real streaming responses."""

    @pytest.mark.asyncio
    async def test_stream_success_with_proper_sse(self):
        """Test streaming with properly formatted SSE response."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30)

        response_text = (
            'data: {"choices": [{"delta": {"content": "Hello "}, "index": 0, "finish_reason": null}]}\n\n'
            'data: {"choices": [{"delta": {"content": "world"}, "index": 0, "finish_reason": null}]}\n\n'
            'data: {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}\n\n'
            "data: [DONE]\n\n"
        )

        with respx.mock:
            respx.post("http://localhost:8001/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    text=response_text,
                    headers={"content-type": "text/event-stream"},
                )
            )

            tokens = []
            async for token in llm_client.stream_completion(
                messages=[{"role": "user", "content": "Test"}]
            ):
                if token:
                    tokens.append(token)

            assert len(tokens) > 0
            combined = "".join(tokens)
            assert "Hello" in combined
            assert "world" in combined

    @pytest.mark.asyncio
    async def test_retryable_error_then_success(self):
        """Test that client retries on 503 and eventually succeeds."""
        llm_client = LlmClient(base_url="http://localhost:8001", timeout=30, max_retries=1)

        response_text = (
            'data: {"choices": [{"delta": {"content": "Success"}, "index": 0, "finish_reason": null}]}\n\n'
            "data: [DONE]\n\n"
        )

        call_count = 0

        async def mock_endpoint(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: 503
                return httpx.Response(503)
            else:
                # Second call: success
                return httpx.Response(
                    200,
                    text=response_text,
                    headers={"content-type": "text/event-stream"},
                )

        with respx.mock:
            respx.post("http://localhost:8001/v1/chat/completions").mock(
                side_effect=mock_endpoint
            )

            tokens = []
            async for token in llm_client.stream_completion(
                messages=[{"role": "user", "content": "Test"}]
            ):
                if token:
                    tokens.append(token)

            assert call_count == 2  # Should have retried once
            assert "Success" in "".join(tokens)
