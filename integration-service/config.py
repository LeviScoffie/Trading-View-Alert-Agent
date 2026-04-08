"""Configuration for the Integration Service."""

import os
from typing import Optional


class Settings:
    """Integration service settings loaded from environment variables."""
    
    # Service URLs
    WEBHOOK_RECEIVER_URL: str = os.getenv("WEBHOOK_RECEIVER_URL", "http://webhook-receiver:8000")
    ANALYSIS_ENGINE_URL: str = os.getenv("ANALYSIS_ENGINE_URL", "http://analysis-engine:8001")
    EMAIL_NOTIFIER_URL: str = os.getenv("EMAIL_NOTIFIER_URL", "http://email-notifier:8002")
    SCHEDULER_URL: str = os.getenv("SCHEDULER_URL", "http://scheduler:8003")
    
    # Integration service settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8004"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Alert processing settings
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    
    # Webhook settings
    WEBHOOK_SECRET: Optional[str] = os.getenv("WEBHOOK_SECRET")


settings = Settings()
