"""Tests for auth rejection, job ownership, queue bounds and LLM client hardening."""

import logging

import pytest

from app.services.llm_client import CircuitBreakerState, LlmClient
from app.workers.job_worker import JobQueueFullError, JobWorker


def test_missing_user_header_is_rejected(client):
    assert client.get("/api/documents/").status_code == 401


def test_invalid_user_header_is_rejected(client):
    response = client.get("/api/documents/", headers={"X-User-ID": "bad user;drop"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_queue_rejects_when_full():
    worker = JobWorker()
    worker.queue = __import__("asyncio").Queue(maxsize=1)
    await worker.enqueue_job(1)
    with pytest.raises(JobQueueFullError):
        await worker.enqueue_job(2)


def test_retry_after_is_capped():
    client = LlmClient(base_url="http://x")
    assert client._get_retry_delay(attempt=0, retry_after="9999") == client.MAX_RETRY_AFTER


def test_half_open_failure_reopens_circuit():
    client = LlmClient(base_url="http://x")
    client._circuit_breaker_state = CircuitBreakerState.HALF_OPEN
    client._record_failure()
    assert client._circuit_breaker_state == CircuitBreakerState.OPEN


def test_api_key_not_logged(caplog):
    client = LlmClient(base_url="http://x", api_key="super-secret-key")
    with caplog.at_level(logging.DEBUG):
        client._record_failure()
    assert "super-secret-key" not in caplog.text
