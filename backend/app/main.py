"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.workers.job_worker import start_worker, stop_worker
from app.routers import document_router, chat_router, job_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="KnowledgeHub",
        description="Policy document assistant with streaming QA",
        version="0.1.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers (they already have their prefixes and tags)
    app.include_router(document_router.router)
    app.include_router(chat_router.router)
    app.include_router(job_router.router)

    # Health check
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    # Startup: Initialize DB and start worker
    @app.on_event("startup")
    async def startup():
        """Initialize database and start background worker."""
        await init_db()
        await start_worker()

    # Shutdown: Close DB and stop worker
    @app.on_event("shutdown")
    async def shutdown():
        """Stop background worker and close database."""
        await stop_worker()
        await close_db()

    return app


app = create_app()

