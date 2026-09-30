"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings, loaded from environment variables / .env file."""

    # Demo mode — default True so dashboard works without real API credentials
    demo_mode: bool = True

    # Douyin Open Platform credentials
    douyin_client_key: str = ""
    douyin_client_secret: str = ""
    douyin_redirect_uri: str = "https://example.com/oauth/callback"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/douyin.db"

    # Cache TTL in minutes
    cache_ttl_minutes: int = 30

    # Secret key for token obfuscation
    secret_key: str = "change-me-in-production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
