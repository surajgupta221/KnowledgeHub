"""Compatibility exports for the LLM client module name."""

from app.services.llm_client import CircuitBreakerState, LlmClient

__all__ = ["LlmClient", "CircuitBreakerState"]
