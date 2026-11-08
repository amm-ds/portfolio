"""Configuration: pydantic-settings, env prefix ``AGENT_CHAT_``.

Every knob an adopter touches lives here — providers, models, database,
budgets, the embedder. Tests override Settings field-by-field instead of
touching the environment.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the agent, stores, and API.

    Defaults target local development with Ollama and a SQLite file — no
    docker required. ``docker compose`` overrides the database URL to
    Postgres/pgvector (see infra/docker-compose.yml).
    """

    model_config = SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        env_prefix="AGENT_CHAT_",
        extra="ignore",
    )

    # --- model provider ---------------------------------------------------
    provider: Literal["ollama", "hosted", "kimi"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_fallback_model: str = ""
    hosted_base_url: str = ""
    hosted_api_key: str = ""
    hosted_model: str = ""
    hosted_fallback_model: str = ""
    kimi_base_url: str = "https://api.kimi.com/coding/v1"
    kimi_api_key: str = ""
    kimi_model: str = "k3-256k"
    kimi_fallback_model: str = ""
    model_retries: int = 2
    executor_workers: int = Field(default=4, ge=1)

    # --- usage budgets (per run; 0 = unlimited) ----------------------------
    usage_request_limit: int = 30
    usage_input_tokens_limit: int = 100_000
    usage_output_tokens_limit: int = 20_000

    # --- storage -----------------------------------------------------------
    database_url: str = "sqlite:///./agent_chat.db"
    memory_data_dir: Path = Path("./agent_chat_memory")

    # --- model-visible conversation history -------------------------------
    history_max_turns: int = Field(default=10, ge=1)
    history_summarize_enabled: bool = False

    # --- embeddings (rag) --------------------------------------------------
    embedder: Literal["minilm", "hashing"] = "minilm"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- api ---------------------------------------------------------------
    api_key: str = ""
    approval_timeout_s: float = 120.0
    run_timeout_s: float = Field(default=90.0, gt=0)
    ingest_roots: list[Path] = Field(default_factory=lambda: [Path("docs")])
    fetch_url_enabled: bool = False

    # --- skills ------------------------------------------------------------
    skills_dir: Path = Path(__file__).resolve().parent / "skills"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so repeated calls share one validated instance."""
    return Settings()
