"""
Job Functions Module

Individual job implementations for the TradingView Alert Agent Scheduler.
Each job is a standalone function that can be scheduled and executed.
"""

import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from functools import wraps

from config import (
    HEALTH_ENDPOINTS,
    REPORT_ENDPOINTS,
    CLEANUP_QUERIES,
    SCHEDULE_CONFIG,
    get_retry_config
)
from job_store import job_store, log_job_execution
from timezone_utils import now, now_utc, to_local, format_est

logger = logging.getLogger(__name__)


# =============================================================================
# RETRY DECORATOR
# =============================================================================

def with_retry(max_attempts: Optional[int] = None, delay_minutes: Optional[int] = None):
    """
    Decorator that adds retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts (default from config)
        delay_minutes: Initial delay between retries in minutes (default from config)
    """
    retry_config = get_retry_config()
    max_attempts = max_attempts or retry_config["max_attempts"]
    delay_minutes = delay_minutes or retry_config["delay_minutes"]
    max_delay = retry_config["max_delay_minutes"]
    multiplier = retry_config["backoff_multiplier"]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            job_id = func.__name__
            last_error = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    duration_ms = int((time.time() - start_time) * 1000)
                    
                    # Log successful execution
                    log_job_execution(
                        job_id=job_id,
                        status="success",
                        job_name=func.__doc__ or job_id,
                        duration_ms=duration_ms,
                        retry_count=attempt - 1,
                        metadata={"attempt": attempt}
                    )
                    
                    logger.info(f"Job {job_id} completed successfully (attempt {attempt})")
                    return result
                    
                except Exception as e:
                    last_error = str(e)
                    duration_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else None
                    
                    if attempt < max_attempts:
                        # Log retry
                        log_job_execution(
                            job_id=job_id,
                            status="retry",
                            job_name=func.__doc__ or job_id,
                            duration_ms=duration_ms,
                            error_message=last_error,
                            retry_count=attempt,
                            metadata={"attempt": attempt, "next_attempt": attempt + 1}
                        )
                        
                        # Calculate delay with exponential backoff
                        current_delay = min(delay_minutes * (multiplier ** (attempt - 1)), max_delay)
                        logger.warning(
                            f"Job {job_id} failed (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {current_delay} minutes..."
                        )
                        time.sleep(current_delay * 60)
                    else:
                        # Log final failure
                        log_job_execution(
                            job_id=job_id,
                            status="failed",
                            job_name=func.__doc__ or job_id,
                            duration_ms=duration_ms,
                            error_message=last_error,
                            retry_count=attempt - 1,
                            metadata={"attempt": attempt, "final": True}
                        )
                        
                        logger.error(f"Job {job_id} failed after {max_attempts} attempts: {e}")
                        raise
            
            return None  # Should never reach here
        
        return wrapper
    return decorator


# =============================================================================
# REPORT JOBS
# =============================================================================

@with_retry()
def daily_report_job():
    """Generate and send daily analysis report at market close (5:00 PM EST)."""
    logger.info("Starting daily report job")
    
    url = REPORT_ENDPOINTS["daily"]
    response = requests.post(
        url,
        timeout=SCHEDULE_CONFIG.get("request_timeout_seconds", 30),
        json={
            "timestamp": now_utc().isoformat(),
            "timezone": "America/New_York",
            "report_type": "daily"
        }
    )
    response.raise_for_status()
    
    result = response.json()
    logger.info(f"Daily report generated and sent: {result}")
    return result


@with_retry()
def weekly_report_job():
    """Generate and send weekly analysis report (Sunday 5:00 PM EST)."""
    logger.info("Starting weekly report job")
    
    url = REPORT_ENDPOINTS["weekly"]
    response = requests.post(
        url,
        timeout=SCHEDULE_CONFIG.get("request_timeout_seconds", 30),
        json={
            "timestamp": now_utc().isoformat(),
            "timezone": "America/New_York",
            "report_type": "weekly",
            "week_ending": format_est(now(), "%Y-%m-%d")
        }
    )
    response.raise_for_status()
    
    result = response.json()
    logger.info(f"Weekly report generated and sent: {result}")
    return result


@with_retry()
def monthly_report_job():
    """Generate and send monthly analysis report (last day of month 5:00 PM EST)."""
    logger.info("Starting monthly report job")
    
    url = REPORT_ENDPOINTS["monthly"]
    
    # Calculate the month being reported
    current = now()
    if current.day == 1:
        # If today is the 1st, the report is for the previous month
        if current.month == 1:
            report_month = 12
            report_year = current.year - 1
        else:
            report_month = current.month - 1
            report_year = current.year
    else:
        report_month = current.month
        report_year = current.year
    
    response = requests.post(
        url,
        timeout=SCHEDULE_CONFIG.get("request_timeout_seconds", 30),
        json={
            "timestamp": now_utc().isoformat(),
            "timezone": "America/New_York",
            "report_type": "monthly",
            "report_month": f"{report_year}-{report_month:02d}"
        }
    )
    response.raise_for_status()
    
    result = response.json()
    logger.info(f"Monthly report generated and sent: {result}")
    return result


# =============================================================================
# MAINTENANCE JOBS
# =============================================================================

@with_retry()
def cleanup_old_data():
    """Prune old alerts and behavior logs (Sunday 3:00 AM EST, keep 90 days)."""
    logger.info("Starting data cleanup job")
    
    retention_days = SCHEDULE_CONFIG["retention_days"]
    deleted_counts = {}
    
    # Import sqlite3 here to avoid circular imports
    import sqlite3
    from config import DATABASE_PATH
    
    # Connect to the database
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # Cleanup alerts
        if "alerts" in CLEANUP_QUERIES:
            query = CLEANUP_QUERIES["alerts"].format(retention_days=retention_days)
            cursor = conn.execute(query)
            deleted_counts["alerts"] = cursor.rowcount
            logger.info(f"Deleted {cursor.rowcount} old alerts")
        
        # Cleanup behavior logs
        if "behavior_logs" in CLEANUP_QUERIES:
            query = CLEANUP_QUERIES["behavior_logs"].format(retention_days=retention_days)
            cursor = conn.execute(query)
            deleted_counts["behavior_logs"] = cursor.rowcount
            logger.info(f"Deleted {cursor.rowcount} old behavior logs")
        
        # Cleanup job executions (keep history but not forever)
        if "job_executions" in CLEANUP_QUERIES:
            query = CLEANUP_QUERIES["job_executions"].format(retention_days=retention_days)
            cursor = conn.execute(query)
            deleted_counts["job_executions"] = cursor.rowcount
            logger.info(f"Deleted {cursor.rowcount} old job execution records")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error during cleanup: {e}")
        raise
    finally:
        conn.close()
    
    logger.info(f"Cleanup completed: {deleted_counts}")
    return {"deleted": deleted_counts, "retention_days": retention_days}


# =============================================================================
# HEALTH CHECK JOB
# =============================================================================

@with_retry()
def health_check():
    """Verify webhook receiver and email notifier health (every hour)."""
    logger.info("Starting health check job")
    
    results = {}
    timeout = SCHEDULE_CONFIG.get("health_check_timeout_seconds", 10)
    
    for service_name, url in HEALTH_ENDPOINTS.items():
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            results[service_name] = {
                "status": "healthy",
                "status_code": response.status_code,
                "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }
            logger.info(f"Health check passed for {service_name}")
            
        except requests.exceptions.RequestException as e:
            results[service_name] = {
                "status": "unhealthy",
                "error": str(e)
            }
            logger.error(f"Health check failed for {service_name}: {e}")
    
    # Check if any service is unhealthy
    unhealthy_services = [name for name, result in results.items() if result["status"] != "healthy"]
    
    if unhealthy_services:
        error_msg = f"Health check failed for services: {', '.join(unhealthy_services)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    logger.info("All health checks passed")
    return {"status": "healthy", "services": results}


# =============================================================================
# JOB REGISTRY
# =============================================================================

# Map of job IDs to job functions
JOB_REGISTRY: Dict[str, Any] = {
    "daily_report": daily_report_job,
    "weekly_report": weekly_report_job,
    "monthly_report": monthly_report_job,
    "cleanup": cleanup_old_data,
    "health_check": health_check
}

def get_job_function(job_id: str):
    """Get the job function for a given job ID."""
    return JOB_REGISTRY.get(job_id)

def list_jobs() -> Dict[str, str]:
    """List all available jobs with their descriptions."""
    return {
        job_id: func.__doc__ or job_id
        for job_id, func in JOB_REGISTRY.items()
    }

def execute_job(job_id: str) -> Any:
    """
    Execute a job by ID.
    
    Args:
        job_id: The job identifier
        
    Returns:
        Job result
        
    Raises:
        ValueError: If job_id is not found
        Exception: If job execution fails
    """
    job_func = get_job_function(job_id)
    if not job_func:
        raise ValueError(f"Unknown job ID: {job_id}")
    
    return job_func()


# =============================================================================
# MANUAL TRIGGER ENDPOINTS (for testing)
# =============================================================================

if __name__ == "__main__":
    # Allow running jobs manually for testing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python jobs.py <job_id>")
        print("\nAvailable jobs:")
        for job_id, desc in list_jobs().items():
            print(f"  {job_id}: {desc}")
        sys.exit(1)
    
    job_id = sys.argv[1]
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    try:
        result = execute_job(job_id)
        print(f"\nJob {job_id} completed successfully:")
        print(result)
    except Exception as e:
        print(f"\nJob {job_id} failed: {e}")
        sys.exit(1)
