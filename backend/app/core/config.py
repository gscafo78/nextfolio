import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"

# Priorità: variabile d'ambiente APP_VERSION (impostata via docker-compose) →
# file VERSION nella root del repo (funziona in locale / dev mount) → fallback
_VERSION_FILE = Path(__file__).parents[3] / "VERSION"
APP_VERSION: str = (
    os.environ.get("APP_VERSION")
    or (_VERSION_FILE.read_text().strip() if _VERSION_FILE.exists() else None)
    or "0.0.0"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "production"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://nextfolio:nextfolio@localhost:5432/nextfolio"
    DATABASE_URL_SYNC: str = "postgresql://nextfolio:nextfolio@localhost:5432/nextfolio"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = _DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_REMEMBER_ME_DAYS: int = 30

    CORS_ORIGINS: str = "http://localhost:5173"
    ALLOWED_HOSTS: str = "*"

    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    COINGECKO_API_KEY: str = ""
    OPENFIGI_APY_KEY: str = ""  # nota: typo intenzionale nel .env

    # Email / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM: str = ""
    APP_URL: str = "http://localhost:5173"

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.APP_ENV == "production" and self.SECRET_KEY == _DEFAULT_SECRET:
            raise ValueError(
                "SECRET_KEY must be changed in production. "
                "Run: openssl rand -hex 32"
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",")]

    @property
    def email_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.EMAILS_FROM)


settings = Settings()
