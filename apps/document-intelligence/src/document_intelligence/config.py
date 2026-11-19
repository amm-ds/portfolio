"""Environment configuration; secrets are read only from explicit environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for API, worker, model, and storage."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_INTELLIGENCE_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    identity_mode: Literal["development", "gateway"] = "development"
    gateway_shared_secret: SecretStr = SecretStr("")
    gateway_max_skew_seconds: int = Field(default=300, gt=0)

    database_url: str = "postgresql+psycopg://review:review@localhost:5432/review"
    repository_backend: Literal["memory", "postgres"] = "memory"
    blob_backend: Literal["local", "s3"] = "local"
    blob_dir: Path = Path("./var/blobs")
    s3_bucket: str = ""
    s3_prefix: str = "documents"
    s3_endpoint_url: str | None = None
    s3_region: str | None = None

    analyzer_backend: Literal["fixture", "model"] = "fixture"
    provider: Literal["kimi", "openai"] = "kimi"
    model_name: str = "kimi-k2.5"
    model_base_url: str = "https://api.moonshot.ai/v1"
    model_api_key: SecretStr = SecretStr("")
    model_retries: int = Field(default=2, ge=0, le=5)
    model_timeout_seconds: float = Field(default=180.0, gt=0, le=300)
    model_total_tokens_limit: int = Field(default=32_000, ge=1000, le=100_000)
    model_chat_tokens_limit: int = Field(default=8000, ge=500, le=50_000)
    # In-process per-tenant limit on the model-cost endpoints (upload,
    # reanalyze, page chat); not shared across replicas. 0 disables.
    rate_limit_per_minute: int = Field(default=30, ge=0)

    lease_seconds: int = Field(default=60, gt=0)
    heartbeat_seconds: int = Field(default=20, gt=0)
    max_job_attempts: int = Field(default=3, ge=1, le=10)
    worker_poll_seconds: float = Field(default=1.0, gt=0)
    max_upload_bytes: int = Field(default=10_000_000, gt=0)
    page_concurrency: int = Field(default=3, ge=1, le=5)
    page_text_max_chars: int = Field(default=24_000, gt=0)
    max_pdf_pages: int = Field(default=500, ge=1, le=5000)

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """Reject unsafe or unusable production adapters during startup."""
        if self.blob_backend == "s3" and not self.s3_bucket.strip():
            raise ValueError("S3 blob storage requires DOCUMENT_INTELLIGENCE_S3_BUCKET")
        if self.environment != "production":
            return self
        problems = []
        if self.identity_mode != "gateway":
            problems.append("gateway identity is required")
        if not self.gateway_shared_secret.get_secret_value():
            problems.append("DOCUMENT_INTELLIGENCE_GATEWAY_SHARED_SECRET is required")
        if self.repository_backend != "postgres":
            problems.append("Postgres persistence is required")
        if self.analyzer_backend != "model":
            problems.append("the fixture analyzer is not allowed")
        if not self.model_api_key.get_secret_value():
            problems.append("DOCUMENT_INTELLIGENCE_MODEL_API_KEY is required")
        if not self.model_name.strip() or not self.model_base_url.strip():
            problems.append("model name and base URL are required")
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings."""
    return Settings()
