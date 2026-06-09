"""Application configuration using Pydantic BaseSettings.

Reads configuration from environment variables and .env file.
All settings are validated and typed at startup.
"""

from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Telegram credentials
    telegram_api_id: int = Field(description="Telegram API ID from my.telegram.org")
    telegram_api_hash: str = Field(description="Telegram API hash from my.telegram.org")
    telegram_phone: str = Field(description="Phone number for Telegram userbot")
    bot_token: str = Field(description="Telegram Bot API token from BotFather")
    my_telegram_id: int = Field(description="Your Telegram numeric user ID")

    # Dashboard configuration
    dashboard_secret_key: str = Field(
        default="change-me-to-a-random-secret",
        description="Secret key for JWT signing",
    )
    dashboard_port: int = Field(default=8080, description="Dashboard server port")
    dashboard_host: str = Field(default="0.0.0.0", description="Dashboard host binding")

    # Trap server configuration
    tracking_redirect_url: str = Field(
        default="https://www.google.com",
        description="URL to redirect after tracking link capture",
    )
    trap_server_port: int = Field(default=5000, description="Flask trap server port")
    trap_server_host: str = Field(
        default="0.0.0.0", description="Flask trap server host"
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/anti_stalker.db",
        description="Async SQLAlchemy database URL",
    )

    # Monitoring intervals (seconds)
    online_check_interval: int = Field(
        default=30, description="Online status check interval in seconds"
    )
    story_check_interval: int = Field(
        default=60, description="Story check interval in seconds"
    )
    analysis_interval: int = Field(
        default=3600, description="Pattern analysis interval in seconds"
    )

    # Scoring thresholds
    alert_threshold: int = Field(
        default=70, description="Suspicion score threshold for alerts (0-100)"
    )
    max_tracked_users: int = Field(
        default=50, description="Maximum number of tracked users"
    )

    # Version channel
    version_channel_id: Optional[int] = Field(
        default=None,
        description="Telegram channel ID for version update announcements",
    )
    app_version: str = Field(
        default="2.0.0", description="Current application version"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Application log level")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


def get_settings() -> Settings:
    """Create and return a Settings instance.

    Returns:
        Settings: Validated application settings.
    """
    return Settings()
