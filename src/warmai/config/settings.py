from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WARMAI_",
        extra="ignore",
    )

    api_key: SecretStr
    database_path: Path = Path("data/warmai.db")
    adapter_kind: Literal["mock", "llama_cpp"] = "mock"
    llama_cpp_base_url: str = "http://127.0.0.1:8080"
    llama_cpp_model: str = "warmai-base-001"
    # Optional inference overrides. Default None -> use model_config values.
    # Set WARMAI_LLAMA_CPP_TEMPERATURE=0 (and a seed) on an evaluation-only server
    # to make suite runs reproducible without changing production sampling.
    llama_cpp_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    llama_cpp_seed: int | None = None
    internal_deadline_seconds: float = Field(default=4.5, gt=0, le=4.5)
    pii_idempotency_ttl_seconds: int = Field(default=300, ge=1)
    circuit_failure_threshold: int = Field(default=3, ge=1)
    circuit_recovery_seconds: float = Field(default=30.0, gt=0)
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
