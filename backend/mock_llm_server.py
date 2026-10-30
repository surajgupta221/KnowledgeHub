"""Mock LLM server for testing and development."""

import json
import random
from typing import Generator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock LLM Server")


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> dict:
    """Mock embeddings endpoint."""
    body = await request.json()
    texts = body.get("input", [])
    if isinstance(texts, str):
        texts = [texts]

    # Return mock embeddings (1536-dim like OpenAI)
    embeddings_list = [
        [random.uniform(-1, 1) for _ in range(1536)] for _ in texts
    ]

    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": emb}
            for i, emb in enumerate(embeddings_list)
        ],
        "model": "mock-embedding",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> StreamingResponse:
    """Mock chat completions endpoint (streaming)."""
    # Randomly return 429 or 503
    if random.random() < 0.1:
        return StreamingResponse(
            iter([]),
            status_code=429,
            headers={"Retry-After": "1"},
            media_type="application/json",
        )
    if random.random() < 0.05:
        return StreamingResponse(
            iter([]),
            status_code=503,
            media_type="application/json",
        )

    async def generate() -> Generator[str, None, None]:
        """Generate mock response tokens."""
        message = (
            "This is a mock response from the policy documents. "
            "The answer has been grounded in the retrieved chunks."
        )
        for token in message.split():
            chunk = {
                "choices": [
                    {
                        "delta": {"content": f"{token} "},
                        "index": 0,
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final chunk
        yield 'data: {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
