# CLAUDE.md — Governance & Procedures

## 7 Core Rules (Every Step)

1. **Layering**: Router → Service → Repository. Routers never touch repositories, SQLAlchemy models, or sessions. API contracts are Pydantic schemas; ORM models never leave the service layer.

2. **Dependency Injection**: Constructor injection via `__init__` and FastAPI `Depends()` only. No module-level singletons or global state.

3. **Testing First**: Every new service method gets a unit test before code. Tests run before declaring any task done.

4. **Migrations Are Read-Only**: Files under `db/migrations/` or `alembic/versions/` are read-only. Schema changes require a NEW numbered migration with human approval.

5. **No Secrets in Code**: Configuration via environment variables (pydantic-settings). Never log API keys, tokens, or document contents. Add tests proving keys are redacted.

6. **Scope & Files**: Touch only files named in the task. Ask before changing anything else. Show a plan before editing.

7. **Type Hints & Linting**: All code must pass `ruff check .` and `mypy` (if configured). Add type hints everywhere.

---

## Build, Run, Test Commands

```bash
# Start all services (Postgres, mock LLM, backend, frontend)
docker compose up

# Run backend tests
pytest -q

# Run frontend tests
npm test

# Lint backend
ruff check .

# Type-check backend
mypy . --ignore-missing-imports

# Format backend (if ruff formatter enabled)
ruff format .

# Build frontend
npm run build
```

---

## Folder Structure & Naming Conventions

### Backend (`backend/`)
```
backend/
  app/
    routers/              # FastAPI routers (dependency injection, no business logic)
      ├── __init__.py
      ├── document_router.py
      ├── chat_router.py
      └── job_router.py
    services/             # Business logic (service name = *_service.py)
      ├── __init__.py
      ├── document_service.py
      ├── chat_service.py
      ├── llm_client.py
      └── job_service.py
    repositories/         # Data access (name = *_repository.py)
      ├── __init__.py
      ├── document_repository.py
      ├── chunk_repository.py
      └── job_repository.py
    schemas/              # Pydantic request/response schemas
      ├── __init__.py
      ├── document_schemas.py
      ├── chat_schemas.py
      └── job_schemas.py
    models/               # SQLAlchemy ORM models (never exported from services)
      ├── __init__.py
      ├── document.py
      ├── chunk.py
      └── job.py
    config.py             # Settings from environment (pydantic-settings)
    dependencies.py       # FastAPI dependency injection
    main.py               # FastAPI app setup
  db/
    migrations/           # Alembic migrations (read-only once committed)
      └── versions/
  tests/
    ├── conftest.py       # Pytest fixtures
    ├── test_document_service.py
    ├── test_chat_service.py
    ├── test_llm_client.py
    └── test_document_router.py
  pyproject.toml
  poetry.lock (or requirements.txt)
```

### Frontend (`frontend/`)
```
frontend/
  src/
    components/
      ├── DocumentList.jsx
      ├── ChatPanel.jsx
      ├── UploadForm.jsx
      └── StatusBar.jsx
    services/
      ├── api.js          # HTTP client (async, error handling)
      └── auth.js
    hooks/
      └── useAbortController.js
    __tests__/
      ├── DocumentList.test.jsx
      └── ChatPanel.test.jsx
  vite.config.js
  vitest.config.js
  package.json
```

---

## Definition of Done Checklist

- [ ] `docker compose up` brings all services online (backend, frontend, Postgres, mock LLM)
- [ ] All tests pass: `pytest -q` (backend) + `npm test` (frontend)
- [ ] Full flow works: upload document → ask question → stream answer → Stop button works
- [ ] Multi-user isolation: User A cannot list, read, summarize, or delete User B's documents (returns 404)
- [ ] Resilience: Slow or rate-limited LLM (429/503) does not freeze the app; queue fills, rejects with 429, AbortController stops stream
- [ ] No secrets leak: API keys redacted from logs; Pydantic validation on all inputs
- [ ] Code quality: `ruff check .` passes, type hints present, no linting errors

---

## Recording Decisions & Defects

- **PROMPTS.md**: Document every prompt used, file limitations, plan confirmation, behaviour preservation method, git diff output, and rejected agent changes
- **REVIEW.md**: Every discovered issue with severity (Critical/High/Medium/Low), location, impact, and fix
- **DESIGN.md**: Architectural decisions (e.g., queue rejection policy, why bounded executor, virtual thread trade-offs)

---

## Key Files (Must Explain Line by Line)

To be filled after Step 4.

---

## Micro-Changes (Examples for Defense Prep)

To be filled after Step 4.
