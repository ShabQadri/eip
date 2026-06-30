"""
Configuration settings for the Entertainment Intelligence Platform.
Loads environment variables and sets path structures using pathlib.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Define directory roots using pathlib
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Resolve path to the .env file in the root directory
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback to system env if .env is missing

class Settings:
    """
    Encapsulates application settings with type hints.
    """
    def __init__(self) -> None:
        # Core Directory Paths
        self.BASE_DIR: Path = BASE_DIR
        self.DATA_DIR: Path = BASE_DIR / "data"
        self.SQLITE_DIR: Path = self.DATA_DIR / "sqlite"
        self.IMAGE_DIR: Path = self.DATA_DIR / "images"
        self.LOG_DIR: Path = self.DATA_DIR / "logs"
        self.BACKUP_DIR: Path = self.DATA_DIR / "backups"
        self.CACHE_DIR: Path = self.DATA_DIR / "cache"

        # Logger Settings
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        # Telegram Bot Placeholders
        self.TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
        self.TELEGRAM_CHANNEL_ID: str | None = os.getenv("TELEGRAM_CHANNEL_ID")

        # Gemini API Key Placeholder
        self.GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

        # Database Settings (Defaults to SQLite in data directory)
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", 
            f"sqlite:///{self.SQLITE_DIR.as_posix()}/entertainment.db"
        )

# Global configuration instance
settings = Settings()
