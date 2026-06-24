"""
Configuration module for Znews Telegram Bot.

Loads settings from environment variables and .env file.
All settings have sensible defaults for development.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file from project root or current directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # --- Bot Settings ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    """Telegram Bot API token from @BotFather."""

    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")
    """Target Telegram channel ID or username (e.g., @znews_channel)."""

    ADMIN_IDS: list[int] = [
        int(x.strip())
        for x in os.getenv("ADMIN_IDS", "").split(",")
        if x.strip()
    ]
    """List of admin Telegram user IDs with full access to bot commands."""

    # --- Scheduler Settings ---
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "5"))
    """Interval in minutes between news source checks."""

    POST_INTERVAL: int = int(os.getenv("POST_INTERVAL", "10"))
    """Interval in minutes between auto-posts to channel."""

    # --- Database Settings ---
    DB_PATH: str = os.getenv("DB_PATH", "znews.db")
    """Path to SQLite database file."""

    # --- Localization ---
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Tashkent")
    """Timezone for scheduler cron triggers (e.g., Asia/Tashkent)."""

    # --- External APIs ---
    CBU_API_URL: str = os.getenv(
        "CBU_API_URL",
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/"
    )
    """Central Bank of Uzbekistan API endpoint for exchange rates."""

    def validate(self) -> list[str]:
        """
        Validate critical configuration values.

        Returns:
            List of validation error messages. Empty list means config is valid.
        """
        errors = []
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN is not set")
        if not self.CHANNEL_ID:
            errors.append("CHANNEL_ID is not set")
        if not self.ADMIN_IDS:
            errors.append("ADMIN_IDS is not set (at least one admin required)")
        if self.CHECK_INTERVAL < 1:
            errors.append("CHECK_INTERVAL must be at least 1 minute")
        if self.POST_INTERVAL < 1:
            errors.append("POST_INTERVAL must be at least 1 minute")
        return errors

    @property
    def async_db_url(self) -> str:
        """Return SQLAlchemy async database URL."""
        return f"sqlite+aiosqlite:///{self.DB_PATH}"


# Global config instance
config = Config()
