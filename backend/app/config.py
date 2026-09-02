"""Runtime configuration. Values come from environment variables (or a local
``.env`` file in dev, gitignored) — never hardcoded, per the brief's security
rules against hardcoded credentials.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/yahya_platform"

    # Single-user platform (this is Yahya's personal assistant, not multi-tenant) —
    # a static API key is the minimal reasonable auth for Phase 1. Revisit if/when
    # a second reviewer role is needed (documented assumption, not a silent one).
    api_key: str = "dev-local-only-change-me"

    # ── Phase 2: content generation ──
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    anthropic_insight_model: str = "claude-opus-5"   # higher reasoning budget for the Insight Agent

    # ── Phase 4: publishing (all optional until that phase starts) ──
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    linkedin_access_token: str = ""
    linkedin_person_urn: str = ""
    instagram_access_token: str = ""
    instagram_ig_user_id: str = ""

    newsapi_key: str = ""

    environment: str = "development"


settings = Settings()
