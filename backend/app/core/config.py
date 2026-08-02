"""Application configuration, loaded from environment variables / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Kompromap"
    environment: str = "development"
    debug: bool = True

    # Database
    postgres_user: str = "kompromap"
    postgres_password: str = "kompromap"
    postgres_db: str = "kompromap"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # CORS — kept as a plain string field rather than list[str]. pydantic-
    # settings JSON-decodes list-typed fields at the env-extraction layer
    # (before any field_validator runs), which means a plain
    # CORS_ORIGINS=https://a.com,https://b.com env var — the natural way to
    # set this in a .env file or docker-compose `environment:` block —
    # would hard-fail with a JSONDecodeError. Parsing it ourselves in
    # cors_origin_list below avoids that footgun.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Optional API-key auth. Unset (default) = no auth, which is fine for
    # localhost. Set it for any deployment reachable off your machine —
    # see app/core/security.py and DEPLOYMENT.md.
    api_key: str | None = None

    # Optional: Anthropic API key for narrative generation
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    @property
    def cors_origin_list(self) -> list[str]:
        stripped = self.cors_origins.strip()
        if stripped.startswith("["):
            import json

            return json.loads(stripped)
        return [origin.strip() for origin in stripped.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
