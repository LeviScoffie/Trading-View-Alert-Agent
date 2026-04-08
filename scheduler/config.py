"""
Scheduler Configuration Module

Centralized configuration for the TradingView Alert Agent Scheduler.
All schedule settings, timezone configuration, and integration endpoints.
"""

import os
from typing import Dict, Any

# =============================================================================
# TIMEZONE CONFIGURATION
# =============================================================================

TIMEZONE = "America/New_York"  # EST/EDT with automatic DST handling

# =============================================================================
# SCHEDULE CONFIGURATION
# =============================================================================

SCHEDULE_CONFIG: Dict[str, Any] = {
    "timezone": TIMEZONE,
    "jobs": {
        "daily_report": {
            "hour": 17,
            "minute": 0,
            "description": "Generate and send daily analysis report at market close (5:00 PM EST)"
        },
        "weekly_report": {
            "day_of_week": "sun",
            "hour": 17,
            "minute": 0,
            "description": "Generate and send weekly analysis report (Sunday 5:00 PM EST)"
        },
        "monthly_report": {
            "day": "last",
            "hour": 17,
            "minute": 0,
            "description": "Generate and send monthly analysis report (last day of month 5:00 PM EST)"
        },
        "cleanup": {
            "day_of_week": "sun",
            "hour": 3,
            "minute": 0,
            "description": "Prune old alerts and behavior logs (Sunday 3:00 AM EST, keep 90 days)"
        },
        "health_check": {
            "minute": 0,
            "description": "Verify webhook receiver and email notifier health (every hour)"
        }
    },
    "retention_days": 90,
    "retry_attempts": 3,
    "retry_delay_minutes": 5,
    "retry_max_delay_minutes": 60,
    "retry_backoff_multiplier": 2
}

# =============================================================================
# INTEGRATION ENDPOINTS
# =============================================================================

# Service URLs (can be overridden via environment variables)
WEBHOOK_RECEIVER_URL = os.getenv(
    "WEBHOOK_RECEIVER_URL",
    "http://webhook-receiver:8000"
)

EMAIL_NOTIFIER_URL = os.getenv(
    "EMAIL_NOTIFIER_URL",
    "http://email-notifier:8001"
)

ANALYSIS_ENGINE_URL = os.getenv(
    "ANALYSIS_ENGINE_URL",
    "http://analysis-engine:8002"
)

# Health check endpoints
HEALTH_ENDPOINTS = {
    "webhook_receiver": f"{WEBHOOK_RECEIVER_URL}/health",
    "email_notifier": f"{EMAIL_NOTIFIER_URL}/health",
    "analysis_engine": f"{ANALYSIS_ENGINE_URL}/health"
}

# Report generation endpoints
REPORT_ENDPOINTS = {
    "daily": f"{EMAIL_NOTIFIER_URL}/reports/daily",
    "weekly": f"{EMAIL_NOTIFIER_URL}/reports/weekly",
    "monthly": f"{EMAIL_NOTIFIER_URL}/reports/monthly"
}

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DATABASE_PATH = os.getenv(
    "SCHEDULER_DB_PATH",
    "/data/scheduler.db"
)

# SQL Queries for cleanup
CLEANUP_QUERIES = {
    "alerts": """
        DELETE FROM alerts 
        WHERE received_at < datetime('now', '-{retention_days} days')
    """,
    "behavior_logs": """
        DELETE FROM behavior_logs 
        WHERE created_at < datetime('now', '-{retention_days} days')
    """,
    "job_executions": """
        DELETE FROM job_executions 
        WHERE executed_at < datetime('now', '-{retention_days} days')
    """
}

# =============================================================================
# SCHEDULER API CONFIGURATION
# =============================================================================

API_HOST = os.getenv("SCHEDULER_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("SCHEDULER_API_PORT", "8003"))
API_WORKERS = int(os.getenv("SCHEDULER_API_WORKERS", "1"))

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOG_LEVEL = os.getenv("SCHEDULER_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# JOB STORE CONFIGURATION
# =============================================================================

JOB_STORE_CONFIG = {
    "url": f"sqlite:///{DATABASE_PATH}",
    "tablename": "apscheduler_jobs"
}

JOB_EXECUTION_STORE_CONFIG = {
    "db_path": DATABASE_PATH,
    "table_name": "job_executions"
}

# =============================================================================
# MONITORING CONFIGURATION
# =============================================================================

MONITORING_CONFIG = {
    "max_execution_history": 100,  # Keep last N executions per job
    "alert_on_consecutive_failures": 3,
    "health_check_timeout_seconds": 10,
    "request_timeout_seconds": 30
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_job_config(job_id: str) -> Dict[str, Any]:
    """Get configuration for a specific job."""
    return SCHEDULE_CONFIG["jobs"].get(job_id, {})

def get_cron_trigger_args(job_id: str) -> Dict[str, Any]:
    """
    Get APScheduler cron trigger arguments for a job.
    
    Args:
        job_id: The job identifier (e.g., 'daily_report')
        
    Returns:
        Dictionary of cron trigger arguments
    """
    config = get_job_config(job_id)
    args = {"timezone": TIMEZONE}
    
    # Map config keys to APScheduler cron arguments
    if "minute" in config:
        args["minute"] = str(config["minute"])
    if "hour" in config:
        args["hour"] = str(config["hour"])
    if "day_of_week" in config:
        args["day_of_week"] = config["day_of_week"]
    if "day" in config:
        if config["day"] == "last":
            args["day"] = "last"  # APScheduler supports 'last' for month end
        else:
            args["day"] = str(config["day"])
    
    return args

def get_retry_config() -> Dict[str, Any]:
    """Get retry configuration."""
    return {
        "max_attempts": SCHEDULE_CONFIG["retry_attempts"],
        "delay_minutes": SCHEDULE_CONFIG["retry_delay_minutes"],
        "max_delay_minutes": SCHEDULE_CONFIG["retry_max_delay_minutes"],
        "backoff_multiplier": SCHEDULE_CONFIG["retry_backoff_multiplier"]
    }
