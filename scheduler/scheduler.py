"""
Main Scheduler Module

APScheduler-based job scheduler with timezone support, persistence, and monitoring.
Coordinates all scheduled tasks for the TradingView Alert Agent.
"""

import logging
import signal
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED,
    JobExecutionEvent, JobEvent
)

# In newer APScheduler versions, specific event types are not directly available
# Using JobEvent as base type for type hints
JobErrorEvent = JobEvent
JobMissedEvent = JobEvent

from config import (
    TIMEZONE, SCHEDULE_CONFIG, JOB_STORE_CONFIG,
    get_cron_trigger_args, LOG_LEVEL, LOG_FORMAT
)
from timezone_utils import tz_manager, now, format_est
from jobs import JOB_REGISTRY, execute_job
from job_store import job_store, log_job_execution
from monitor import monitor

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT
)
logger = logging.getLogger(__name__)


class TradingViewScheduler:
    """
    Main scheduler for TradingView Alert Agent.
    
    Features:
    - Timezone-aware scheduling (EST/EDT with DST)
    - Job persistence via SQLite
    - Automatic retry on failure
    - Health monitoring
    - REST API for management
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler: Optional[BackgroundScheduler] = None
        self.running = False
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def _on_job_executed(self, event: JobExecutionEvent):
        """Handle job execution completion."""
        job_id = event.job_id
        duration_ms = int(event.retval.get("duration_ms", 0)) if isinstance(event.retval, dict) else None
        
        logger.info(f"Job {job_id} executed successfully")
        
        log_job_execution(
            job_id=job_id,
            status="success",
            duration_ms=duration_ms,
            metadata={"retval": event.retval}
        )
    
    def _on_job_error(self, event: JobErrorEvent):
        """Handle job execution error."""
        job_id = event.job_id
        exception = str(event.exception) if event.exception else "Unknown error"
        
        logger.error(f"Job {job_id} failed: {exception}")
        
        log_job_execution(
            job_id=job_id,
            status="failed",
            error_message=exception,
            metadata={"traceback": event.traceback if hasattr(event, 'traceback') else None}
        )
    
    def _on_job_missed(self, event: JobMissedEvent):
        """Handle missed job execution."""
        job_id = event.job_id
        logger.warning(f"Job {job_id} missed its scheduled run time")
        
        log_job_execution(
            job_id=job_id,
            status="failed",
            error_message="Job missed scheduled run time",
            metadata={"scheduled_run_time": str(event.scheduled_run_time) if hasattr(event, 'scheduled_run_time') else None}
        )
    
    def _register_event_listeners(self):
        """Register event listeners for job monitoring."""
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._on_job_missed,
            EVENT_JOB_MISSED
        )
    
    def _add_monthly_report_job(self):
        """
        Add the monthly report job with special handling for 'last day of month'.
        
        APScheduler doesn't directly support 'last day of month', so we use
        a workaround: schedule for the 1st of each month and adjust logic.
        """
        # Schedule for the 1st of each month at 5 PM
        # The job logic will handle generating the report for the previous month
        trigger = CronTrigger(
            day="1",
            hour=17,
            minute=0,
            timezone=TIMEZONE
        )
        
        self.scheduler.add_job(
            execute_job,
            trigger=trigger,
            id="monthly_report",
            name="Monthly Analysis Report",
            args=["monthly_report"],
            replace_existing=True,
            misfire_grace_time=3600  # 1 hour grace period
        )
        
        logger.info("Added monthly report job (runs 1st of month at 5:00 PM EST)")
    
    def _add_scheduled_jobs(self):
        """Add all scheduled jobs to the scheduler."""
        for job_id, job_func in JOB_REGISTRY.items():
            if job_id == "monthly_report":
                # Special handling for monthly report
                self._add_monthly_report_job()
                continue
            
            # Get cron trigger arguments from config
            cron_args = get_cron_trigger_args(job_id)
            
            if not cron_args:
                logger.warning(f"No schedule config found for job {job_id}, skipping")
                continue
            
            # Create cron trigger
            trigger = CronTrigger(**cron_args)
            
            # Add job to scheduler
            self.scheduler.add_job(
                execute_job,
                trigger=trigger,
                id=job_id,
                name=job_func.__doc__ or job_id,
                args=[job_id],
                replace_existing=True,
                misfire_grace_time=3600  # 1 hour grace period
            )
            
            next_run = self.scheduler.get_job(job_id).next_run_time
            logger.info(
                f"Added job {job_id}: {job_func.__doc__ or job_id}. "
                f"Next run: {format_est(next_run) if next_run else 'N/A'}"
            )
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("Starting TradingView Alert Agent Scheduler")
        logger.info(f"Timezone: {TIMEZONE} (EST/EDT with DST)")
        
        # Create scheduler with job store
        self.scheduler = BackgroundScheduler(
            jobstores={
                'default': {
                    'type': 'sqlalchemy',
                    'url': JOB_STORE_CONFIG["url"]
                }
            },
            timezone=TIMEZONE
        )
        
        # Register event listeners
        self._register_event_listeners()
        
        # Add scheduled jobs
        self._add_scheduled_jobs()
        
        # Start the scheduler
        self.scheduler.start()
        self.running = True
        
        logger.info("Scheduler started successfully")
        logger.info(f"Jobs: {len(self.scheduler.get_jobs())}")
    
    def shutdown(self, wait: bool = True):
        """
        Shutdown the scheduler gracefully.
        
        Args:
            wait: Whether to wait for running jobs to complete
        """
        if not self.running or not self.scheduler:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Shutting down scheduler...")
        self.scheduler.shutdown(wait=wait)
        self.running = False
        logger.info("Scheduler shutdown complete")
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a scheduled job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            Job information dictionary, or None if not found
        """
        if not self.scheduler:
            return None
        
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        
        return {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        }
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """
        List all scheduled jobs.
        
        Returns:
            List of job information dictionaries
        """
        if not self.scheduler:
            return []
        
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            }
            for job in self.scheduler.get_jobs()
        ]
    
    def pause_job(self, job_id: str) -> bool:
        """
        Pause a scheduled job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.scheduler:
            return False
        
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """
        Resume a paused job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.scheduler:
            return False
        
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False
    
    def trigger_job(self, job_id: str) -> bool:
        """
        Manually trigger a job to run immediately.
        
        Args:
            job_id: The job identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.scheduler:
            return False
        
        try:
            self.scheduler.modify_job(job_id, next_run_time=now())
            logger.info(f"Triggered job {job_id} to run now")
            return True
        except Exception as e:
            logger.error(f"Failed to trigger job {job_id}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status.
        
        Returns:
            Status dictionary
        """
        return {
            "running": self.running,
            "timezone": TIMEZONE,
            "jobs_count": len(self.scheduler.get_jobs()) if self.scheduler else 0,
            "jobs": self.list_jobs()
        }


# Global scheduler instance
_scheduler: Optional[TradingViewScheduler] = None


def get_scheduler() -> TradingViewScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TradingViewScheduler()
    return _scheduler


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    scheduler = get_scheduler()
    
    try:
        scheduler.start()
        
        # Keep the main thread alive
        logger.info("Scheduler is running. Press Ctrl+C to exit.")
        while scheduler.running:
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        scheduler.shutdown()