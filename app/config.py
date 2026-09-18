"""
app/config.py
=============
Centralized application configuration (Member 4 deliverable).

Uses Pydantic V2 `BaseSettings` to read from:
  1. Process environment variables (highest priority)
  2. .env file in the project root (lowest priority)

This module is the single source of truth for runtime configuration.
Member 2 MUST import `settings` from here (never call `os.getenv` directly).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — loaded once at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # LLM Provider (Groq — locked decision, see member4/PLAN.md)
    # -------------------------------------------------------------------------
    GROQ_API_KEY: str = Field(
        ...,
        description="Groq API key. Get one at https://console.groq.com/keys",
    )
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-20b",
        description="Groq model identifier. Defaults to openai/gpt-oss-20b.",
    )
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="OpenAI-compatible base URL for the Groq API.",
    )
    LLM_PROVIDER: Literal["groq", "mock"] = Field(
        default="groq",
        description="Active LLM provider. 'mock' uses a deterministic keyword parser (useful for tests/offline demos).",
    )

    # -------------------------------------------------------------------------
    # Latency & Reliability
    # -------------------------------------------------------------------------
    LLM_TIMEOUT_SEC: float = Field(
        default=4.0,
        ge=0.1,
        le=30.0,
        description="Hard timeout (seconds) for a single LLM call. Rubric requires p95 <= 5s.",
    )

    # -------------------------------------------------------------------------
    # Observability
    # -------------------------------------------------------------------------
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="production",
        description="Drives fail-fast validation of required secrets.",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("GROQ_API_KEY")
    @classmethod
    def _no_placeholder_in_production(cls, v: str, info) -> str:
        """Refuse to boot in production with an empty or placeholder key."""
        app_env = info.data.get("APP_ENV", "production") if hasattr(info, "data") else "production"
        if app_env == "production":
            v_stripped = v.strip()
            if not v_stripped or v_stripped.lower().startswith("your_") or v_stripped == "changeme":
                raise ValueError(
                    "GROQ_API_KEY is missing or a placeholder. "
                    "Set it in your .env file or Render Environment Variables."
                )
        return v

    @field_validator("GROQ_MODEL")
    @classmethod
    def _known_model(cls, v: str) -> str:
        # Soft warning — Groq deprecates models often. We don't crash, just log.
        known = {
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768",
        }
        if v not in known:
            # Non-fatal: surface a log message but allow boot
            import logging
            logging.getLogger(__name__).warning(
                "GROQ_MODEL=%r is not in the known-good list %s. "
                "Verify the model exists on https://console.groq.com/docs/models",
                v,
                sorted(known),
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton accessor. Import this in your module:

        from app.config import get_settings
        settings = get_settings()
    """
    return Settings()  # type: ignore[call-arg]


# Convenience module-level binding so callers can simply do:
#     from app.config import settings
# without paying the lru_cache call cost in hot paths.
settings = get_settings()