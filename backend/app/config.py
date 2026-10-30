from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://knowledge_user:knowledge_pass@localhost/knowledge_hub"

    # LLM
    mock_llm_url: str = "http://localhost:8001"
    llm_api_key: Optional[str] = None
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 4

    # Job queue
    job_queue_size: int = 100
    job_worker_count: int = 4
    job_max_concurrent_llm_calls: int = 2

    # RAG
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    retrieval_top_k: int = 5

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
