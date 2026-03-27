from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, env="TELEGRAM_CHAT_ID")

    poll_interval_seconds: int = Field(20, env="POLL_INTERVAL_SECONDS")
    max_concurrent_checks: int = Field(15, env="MAX_CONCURRENT_CHECKS")

    proxy_url: Optional[str] = Field(None, env="PROXY_URL")

    database_url: str = Field(
        "sqlite+aiosqlite:///./stockbot.db", env="DATABASE_URL"
    )
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("logs/stockbot.log", env="LOG_FILE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
