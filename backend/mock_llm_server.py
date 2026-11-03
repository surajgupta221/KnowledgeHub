"""Mock LLM server for testing and development."""

import asyncio
import hashlib
import json
import math
import random
import re
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock LLM Server")


def _embed(text: str, dim: int = 1536) -> list[float]:
    """Deterministic hashed bag-of-words embedding (L2-normalised)."""
    vec = [0.0] * dim
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> dict:
    """Mock embeddings endpoint."""
    body = await request.json()
    texts = body.get("input", [])
    if isinstance(texts, str):
        texts = [texts]

    # Deterministic 1536-dim vectors so similar texts retrieve each other
    embeddings_list = [_embed(t) for t in texts]

    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": emb}
            for i, emb in enumerate(embeddings_list)
        ],
        "model": "mock-embedding",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


def _grounded_answer(user_text: str) -> str:
    """Extractive 'LLM': return the context sentences that best match the question."""
    if "Question:" not in user_text:
        return "I can answer questions about your uploaded documents."
    context, question = user_text.split("Question:", 1)
    stop = {"the", "a", "an", "of", "to", "is", "are", "we", "can", "i", "how",
            "what", "do", "does", "in", "on", "for", "and", "or", "my", "me", "you"}
    synonyms = {"yearly": "year", "annual": "year", "annually": "year",
                "annum": "year", "leaves": "leave", "vacation": "leave",
                "holiday": "leave", "holidays": "leave", "pto": "leave"}
    wants_number = bool(re.search(r"\bhow (many|much|long)\b", question.lower()))

    def norm(word: str) -> str:
        word = synonyms.get(word, word)
        for suffix in ("ation", "ing", "ed", "es", "al", "s", "e"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                return word[: -len(suffix)]
        return word

    def tokens(value: str) -> set[str]:
        return {norm(w) for w in re.findall(r"[a-z0-9]+", value.lower()) if w not in stop}

    q_words = tokens(question)

    sentences: list[str] = []
    for line in context.splitlines():
        line = line.strip()
        # Skip citation headers and retrieval footers added by the backend
        if not line or line.startswith(("Context:", "[", "Retrieved ", "(")):
            continue
        parts = re.split(r"(?<=[.!?])\s+|\s+(?=\d+\.\s+[A-Z])", line)
        sentences.extend(s.strip() for s in parts if s.strip())

    scored = sorted(
        (
            (len(q_words & tokens(s)) + (0.5 if wants_number and re.search(r"\d", s) else 0), i, s)
            for i, s in enumerate(sentences)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    best = [item for item in scored if item[0] > 0][:2]
    if not best:
        return "I could not find the answer to that in the selected documents."
    return " ".join(s for _, _, s in sorted(best, key=lambda x: x[1]))


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

    body = await request.json()
    messages = body.get("messages", [])
    wants_json = "ONLY a JSON" in json.dumps(messages)
    user_text = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    answer = _grounded_answer(user_text)

    async def generate() -> AsyncGenerator[str, None]:
        """Stream the answer word by word with a small delay (so Stop is usable)."""
        message = answer
        if wants_json:
            message = json.dumps(
                {"answer": answer, "confidence": 0.7, "citations": []}
            )
        for token in message.split(" "):
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
            await asyncio.sleep(0.2)

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
