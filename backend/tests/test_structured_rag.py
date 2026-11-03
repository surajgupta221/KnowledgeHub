"""Tests for the structured RAG answer and SSE formatting."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chat_service import ChatService


class FakeLlm:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def stream_completion(self, messages, **kwargs):
        out = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        for ch in out:
            yield ch


def make_service(llm: FakeLlm) -> ChatService:
    service = ChatService(MagicMock(), llm, MagicMock(), MagicMock())
    service.verify_document_ownership = AsyncMock(return_value=True)
    service._build_context = AsyncMock(return_value="ctx")
    return service


VALID = json.dumps({"answer": "42", "confidence": 0.9, "citations": []})


@pytest.mark.asyncio
async def test_valid_json_is_parsed_even_with_code_fence():
    service = make_service(FakeLlm([f"```json\n{VALID}\n```"]))
    result = await service.answer_structured("q", [1], "user_a")
    assert result.answer == "42"


@pytest.mark.asyncio
async def test_invalid_output_is_repaired_once():
    llm = FakeLlm(["not json", VALID])
    result = await make_service(llm).answer_structured("q", [1], "user_a")
    assert result.confidence == 0.9
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_schema_violation_raises_after_repair_fails():
    bad = json.dumps({"answer": "x", "confidence": 5})
    with pytest.raises(ValueError):
        await make_service(FakeLlm([bad])).answer_structured("q", [1], "user_a")


def test_sse_escapes_quotes_and_newlines():
    line = ChatService._sse("token", 'say "hi"\nnow')
    payload = json.loads(line[len("data: "):].strip())
    assert payload == {"event": "token", "data": 'say "hi"\nnow'}
