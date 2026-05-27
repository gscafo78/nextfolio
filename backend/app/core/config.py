from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://nextfolio:nextfolio@localhost:5432/nextfolio"
    DATABASE_URL_SYNC: str = "postgresql://nextfolio:nextfolio@localhost:5432/nextfolio"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: str = "http://localhost:5173"

    COINGECKO_API_KEY: str = ""
    OPENFIGI_APY_KEY: str = ""  # nota: typo intenzionale nel .env

    # Email / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM: str = ""
    APP_URL: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def email_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.EMAILS_FROM)


settings = Settings()
