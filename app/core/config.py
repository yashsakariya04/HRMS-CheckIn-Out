"""
app/core/config.py — Application Configuration
================================================
Loads all environment variables from the .env file and exposes them
as a single typed `settings` object used throughout the application.

Non-technical summary:
----------------------
Think of this file as the "settings panel" of the app. Instead of
hardcoding sensitive values (like database passwords or API keys)
directly in the code, we store them in a .env file and read them here.
This keeps secrets out of the codebase and makes it easy to change
settings per environment (development vs production).

Key settings managed here:
  - Database connection URL
  - JWT secret keys and token expiry times
  - Google OAuth credentials (for employee login)
  - Allowed email domain (optional company restriction)
  - CORS origins (which frontend URLs can call this API)
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed settings class — each field maps to an environment variable.

    Pydantic automatically reads values from the .env file and validates
    their types. If a required variable is missing, the app will fail
    to start with a clear error message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",           # Read from .env file in the project root
        env_file_encoding="utf-8",
        extra="ignore",            # Ignore any extra variables in .env
    )

    # ── Database ──────────────────────────────────────────────────────────────
    # Full async PostgreSQL connection string.
    # Example: postgresql+asyncpg://user:password@localhost:5432/hrms_db
    DATABASE_URL: str

    # ── JWT (JSON Web Tokens) — used for authentication ───────────────────────
    # JWT_SECRET_KEY: the secret used to sign access tokens. Keep this private.
    # JWT_ALGORITHM: signing algorithm (HS256 is standard).
    # ACCESS_TOKEN_EXPIRE_MINUTES: how long an access token is valid (default 15 min).
    # REFRESH_TOKEN_EXPIRE_DAYS: how long a refresh token lasts (default 365 days = 1 year).
    #   Employees stay logged in until they manually log out.
    # SECRET_KEY: optional legacy key — if tokens were signed with a different key
    #   in the past, this allows them to still be verified during transition.
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 365
    SECRET_KEY: Optional[str] = None

    # ── Google OAuth ──────────────────────────────────────────────────────────
    # Credentials from Google Cloud Console for the OAuth 2.0 app.
    # Employees log in using their Google account — no passwords stored.
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    # ── Domain restriction (optional) ─────────────────────────────────────────
    # Set to your company domain (e.g. "company.com") to only allow logins
    # from that domain. Leave empty/unset to allow any Google account.
    ALLOWED_EMAIL_DOMAIN: Optional[str] = None

    # ── App environment ───────────────────────────────────────────────────────
    # APP_ENV: "development" or "production" — used for conditional behaviour.
    # CORS_ORIGINS: comma-separated list of frontend URLs allowed to call the API.
    #   Example: "http://localhost:5173,https://app.company.com"
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"

    def get_cors_origins(self) -> list[str]:
        """
        Parse the CORS_ORIGINS string into a Python list.

        Example:
            "http://localhost:5173,https://app.company.com"
            → ["http://localhost:5173", "https://app.company.com"]
        """
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Return the Settings singleton, cached after the first call.

    lru_cache ensures the .env file is only read once, not on every request.
    This is the recommended pattern for FastAPI dependency injection.
    """
    return Settings()


# Module-level singleton — import this anywhere in the app:
#   from app.core.config import settings
settings = get_settings()
