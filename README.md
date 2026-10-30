# KnowledgeHub

An internal assistant where employees upload policy documents and ask questions. Answers are grounded in their documents and streamed to the browser.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node 18+ (for frontend development)

### Start All Services

```bash
docker compose up
```

This will start:
- **Backend** (FastAPI): http://localhost:8000
- **Frontend** (React): http://localhost:5173
- **Postgres**: localhost:5432
- **Mock LLM Server**: http://localhost:8001

### Local Development

#### Backend
```bash
cd backend
poetry install
pytest -q              # Run tests
ruff check .           # Lint
python -m uvicorn app.main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm test               # Run tests
npm run dev           # Start dev server
```

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Pydantic v2
- **Database**: Postgres with pgvector
- **Frontend**: React 18, Vite, Vitest + Testing Library
- **Testing**: pytest + pytest-asyncio + respx, vitest
- **Async HTTP**: httpx (backend), fetch (frontend)

## Governance

See [CLAUDE.md](CLAUDE.md) for:
- 7 core architectural rules (layering, dependency injection, testing first, etc.)
- Build, run, and test commands
- Folder structure and naming conventions
- Definition of done checklist

## Project Status

This is the initial scaffold. See steps in the task spec:
1. ✅ STEP 1.1: CLAUDE.md + AGENTS.md created
2. ⏳ STEP 1.2: Extract DocumentPermissionService
3. ⏳ STEP 2.1: Review and rewrite DocumentController
4. ⏳ STEP 2.2: Streaming chat
5. ⏳ STEP 2.3: Fix DocumentList freezing
6. ⏳ STEP 3.1: Background job queue
7. ⏳ STEP 3.2: Resilient LLM client
8. ⏳ STEP 3.3: RAG pipeline
9. ⏳ STEP 4: Final verification and defense prep
