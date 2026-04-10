"""Configuration for Integration Service."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8004"))

    # Downstream services
    webhook_receiver_url: str = os.getenv("WEBHOOK_RECEIVER_URL", "http://webhook-receiver:8000")
    analysis_engine_url: str = os.getenv("ANALYSIS_ENGINE_URL", "http://analysis-engine:8001")
    email_notifier_url: str = os.getenv("EMAIL_NOTIFIER_URL", "http://email-notifier:8002")
    scheduler_url: str = os.getenv("SCHEDULER_URL", "http://scheduler:8003")

    # Orchestration
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
