"""Email Notifier Configuration."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class EmailSettings(BaseSettings):
    """Email configuration settings."""
    
    # SMTP Configuration
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")
    
    # Alternative: SendGrid
    sendgrid_api_key: Optional[str] = Field(default=None, alias="SENDGRID_API_KEY")
    
    # Alternative: AWS SES
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    
    # Email Recipients
    email_to: str = Field(default="", alias="EMAIL_TO")
    email_from: str = Field(default="", alias="EMAIL_FROM")
    email_cc: Optional[str] = Field(default=None, alias="EMAIL_CC")
    
    # Provider selection: "smtp", "sendgrid", "aws_ses"
    email_provider: str = Field(default="smtp", alias="EMAIL_PROVIDER")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ScheduleSettings(BaseSettings):
    """Schedule configuration for report delivery."""
    
    # Timezone for all schedules (EST/EDT - New York)
    timezone: str = Field(default="America/New_York", alias="SCHEDULE_TIMEZONE")
    
    # Daily report time (5:00 PM EST)
    daily_report_hour: int = Field(default=17, alias="DAILY_REPORT_HOUR")
    daily_report_minute: int = Field(default=0, alias="DAILY_REPORT_MINUTE")
    
    # Weekly report time (Sunday 5:00 PM EST)
    weekly_report_day: int = Field(default=6, alias="WEEKLY_REPORT_DAY")  # 6 = Sunday
    weekly_report_hour: int = Field(default=17, alias="WEEKLY_REPORT_HOUR")
    weekly_report_minute: int = Field(default=0, alias="WEEKLY_REPORT_MINUTE")
    
    # Monthly report time (Last day of month 5:00 PM EST)
    monthly_report_hour: int = Field(default=17, alias="MONTHLY_REPORT_HOUR")
    monthly_report_minute: int = Field(default=0, alias="MONTHLY_REPORT_MINUTE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    # Path to webhook-receiver SQLite database
    database_path: str = Field(
        default="../webhook-receiver/data/alerts.db",
        alias="EMAIL_NOTIFIER_DB_PATH"
    )
    
    # Path to analysis-engine OHLCV database
    ohlcv_db_path: str = Field(
        default="../analysis-engine/ohlcv.db",
        alias="EMAIL_NOTIFIER_OHLCV_DB_PATH"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class AppSettings(BaseSettings):
    """Application settings."""
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Retry configuration
    max_retries: int = Field(default=3, alias="EMAIL_MAX_RETRIES")
    retry_delay_seconds: int = Field(default=60, alias="EMAIL_RETRY_DELAY_SECONDS")
    
    # Report configuration
    report_lookback_days: int = Field(default=30, alias="REPORT_LOOKBACK_DAYS")
    top_symbols_limit: int = Field(default=10, alias="REPORT_TOP_SYMBOLS_LIMIT")
    
    # Analysis Engine API (if running separately)
    analysis_engine_url: Optional[str] = Field(
        default=None,
        alias="ANALYSIS_ENGINE_URL"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instances
email_settings = EmailSettings()
schedule_settings = ScheduleSettings()
database_settings = DatabaseSettings()
app_settings = AppSettings()
