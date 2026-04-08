"""Configuration management for TradingView Webhook Receiver."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    
    # Database configuration
    database_path: str = os.getenv("DATABASE_PATH", "data/alerts.db")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Security (optional webhook secret for basic validation)
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def ensure_data_directory() -> None:
    """Ensure the data directory exists for SQLite database."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
