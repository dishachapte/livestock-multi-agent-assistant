"""Loads settings from the .env file and from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

# farm-assistant/ folder (one level above backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str) -> str:
    """Return the environment value, or the default if it is missing or blank."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


class Settings:
    GEMINI_API_KEY: str = _env("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = _env("GEMINI_MODEL", "gemini-2.5-flash")
    DATABASE_URL: str = _env(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'farm.db').as_posix()}"
    )
    MAX_UPLOAD_MB: int = int(_env("MAX_UPLOAD_MB", "5"))
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in _env(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if origin.strip()
    ]

    @property
    def gemini_enabled(self) -> bool:
        """True when a Gemini key is set. The app then tries live AI calls."""
        return bool(self.GEMINI_API_KEY)


settings = Settings()
