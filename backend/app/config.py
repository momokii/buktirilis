"""Validated runtime configuration.

Environment differences are centralised here and validated at startup. Missing or
unknown ``APP_ENV`` selects production-safe behaviour (no demo routes, secure cookies,
debug off) and startup fails when a required secret is absent.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ENVS = ("development", "staging", "production")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_env: str = Field(default="production", alias="APP_ENV")
    app_name: str = "BuktiRilis"
    api_base_path: str = "/api"
    public_origin: str = Field(default="http://127.0.0.1:5173", alias="PUBLIC_ORIGIN")

    database_url: str = Field(
        default="postgresql+psycopg://buktirilis:buktirilis@127.0.0.1:55432/buktirilis",
        alias="DATABASE_URL",
    )
    secret_key: str = Field(default="", alias="BUKTIRILIS_SECRET_KEY")
    session_ttl_hours: int = 12
    cookie_name: str = "br_session"
    cookie_secure: bool | None = Field(default=None, alias="COOKIE_SECURE")
    cookie_samesite: Literal["lax", "strict"] = "lax"

    artifact_root: str = Field(default="./var/artifacts", alias="ARTIFACT_ROOT")
    max_artifact_bytes: int = 10 * 1024 * 1024
    max_openapi_bytes: int = 2 * 1024 * 1024
    allowed_attachment_types: list[str] = [
        "image/png",
        "image/jpeg",
        "application/json",
        "text/plain",
    ]

    allow_loopback_lab_targets: bool | None = Field(
        default=None, alias="ALLOW_LOOPBACK_LAB_TARGETS"
    )
    lab_base_url: str = Field(default="http://127.0.0.1:8099", alias="LAB_BASE_URL")
    live_execution_enabled: bool | None = Field(default=None, alias="LIVE_EXECUTION_ENABLED")
    strix_binary: str = Field(default="strix", alias="STRIX_BINARY")
    strix_version: str = Field(default="1.7.1", alias="STRIX_VERSION")
    strix_model: str = Field(default="", alias="STRIX_MODEL")
    strix_runs_root: str = Field(default="./var/strix_runs", alias="STRIX_RUNS_ROOT")
    strix_max_budget_usd: float = Field(default=2.0, alias="STRIX_MAX_BUDGET_USD")
    strix_max_turns: int = Field(default=40, alias="STRIX_MAX_TURNS")
    worker_poll_seconds: float = 1.0
    worker_lease_seconds: int = 120
    worker_id: str = Field(default="", alias="WORKER_ID")
    job_max_attempts: int = 2
    max_upload_bytes: int = 10 * 1024 * 1024

    login_rate_limit_window_seconds: int = 300
    login_rate_limit_max_failures: int = 5

    demo_seed_enabled: bool | None = Field(default=None, alias="DEMO_SEED_ENABLED")

    @field_validator("app_env")
    @classmethod
    def _normalise_env(cls, value: str) -> str:
        value = (value or "").strip().lower()
        return value if value in APP_ENVS else "production"

    @field_validator("secret_key")
    @classmethod
    def _validate_secret(cls, value: str) -> str:
        if value and len(value) < 32:
            raise ValueError("BUKTIRILIS_SECRET_KEY must be at least 32 characters")
        return value

    @model_validator(mode="after")
    def _apply_defaults(self) -> Settings:
        env = self.app_env
        development_like = env == "development"

        if self.cookie_secure is None:
            self.cookie_secure = not development_like
        if self.cookie_secure is False and env == "production":
            raise ValueError("COOKIE_SECURE cannot be false in production")
        if self.allow_loopback_lab_targets is None:
            self.allow_loopback_lab_targets = development_like
        if self.live_execution_enabled is None:
            self.live_execution_enabled = False
        if self.demo_seed_enabled is None:
            self.demo_seed_enabled = development_like or env == "staging"
        if not development_like and not self.secret_key:
            raise ValueError("BUKTIRILIS_SECRET_KEY is required outside development")
        if development_like and not self.secret_key:
            # Deterministic-ephemeral dev key: sessions do not survive a restart.
            self.secret_key = secrets.token_urlsafe(48)
        if not self.worker_id:
            self.worker_id = f"worker-{secrets.token_hex(4)}"
        return self

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def demo_enabled(self) -> bool:
        return bool(self.demo_seed_enabled)

    @property
    def live_enabled(self) -> bool:
        """Live mode also requires a configured model and the explicit switch."""
        return bool(self.live_execution_enabled and self.strix_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
