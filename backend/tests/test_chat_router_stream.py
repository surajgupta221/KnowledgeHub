"""Router-level test: /api/chat/stream must stream SSE events end to end."""

from typing import AsyncIterator

from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.routers import chat_router


class FakeChatService:
    def __init__(self, db: object, llm_client: object) -> None:
        pass

    async def verify_document_ownership(
        self, document_ids: list[int], user_id: str
    ) -> bool:
        return True

    async def stream_answer(
        self, question: str, document_ids: list[int], user_id: str
    ) -> AsyncIterator[str]:
        yield 'data: {"event": "token", "data": "Rotate "}\n\n'
        yield 'data: {"event": "token", "data": "90 days"}\n\n'
        yield 'data: {"event": "done", "data": null}\n\n'


def _client(app, monkeypatch) -> TestClient:
    async def fake_db():
        yield None

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: "user_a"
    monkeypatch.setattr(chat_router, "ChatService", FakeChatService)
    return TestClient(app)


def test_chat_stream_returns_sse_events(app, monkeypatch) -> None:
    client = _client(app, monkeypatch)

    response = client.post(
        "/api/chat/stream", json={"question": "How often?", "document_ids": [1]}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"data": "Rotate "' in response.text
    assert '"event": "done"' in response.text
    assert '"event": "error"' not in response.text
