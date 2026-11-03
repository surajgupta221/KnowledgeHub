# DESIGN.md

## Layering
Router → Service → Repository. Routers exchange only Pydantic schemas.

## Authentication (limitation)
The user identity comes from the `X-User-ID` header (validated against `^[A-Za-z0-9_.@-]{1,64}$`; missing/invalid → 401). This is demo auth: production must verify a JWT/session instead. Cross-tenant access returns 404 (documents, jobs, chat) so existence is not revealed.

## Background processing
Uploads create an `embed_chunks` job processed by a pool of async workers (`JOB_WORKER_COUNT`) reading from a **bounded** queue (`JOB_QUEUE_SIZE`). Queue rejection policy: when full, `enqueue_job` raises `JobQueueFullError` and the summary endpoint returns **429 + Retry-After**. A semaphore (`JOB_MAX_CONCURRENT_LLM_CALLS`) bounds concurrent LLM calls from jobs so chat is not starved. Failed jobs retry up to `max_retries`.

## Resilient LLM client
- 429: honour `Retry-After` (capped at 30s); otherwise exponential backoff with jitter.
- 503/timeouts: retried, counted by a circuit breaker (CLOSED → OPEN after N consecutive failures → HALF_OPEN after a cool-down; a failed probe re-opens it).
- One shared client per app (`app.state`) so the breaker state persists across requests.
- Streaming errors reach the UI as a generic fallback message; internals are never leaked.

## RAG
Chunks are embedded and stored; retrieval uses pgvector cosine distance (`<=>`) on Postgres and an in-Python fallback on SQLite (tests). `POST /api/chat/answer` forces the LLM to return JSON validated by the `RagAnswer` Pydantic schema, with one repair retry, then 502.

## Known gaps
Alembic is not wired up (tables come from `create_all`; the `vector` extension is created in `init_db`). Embeddings are stored as JSON text cast to `vector` at query time (no ANN index).
