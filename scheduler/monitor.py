"""
Monitor Module

Health checks and job status monitoring for the scheduler.
Provides status tracking, alerting, and monitoring dashboard data.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from job_store import job_store, get_all_stats, get_failures
from timezone_utils import now, format_est, tz_manager
from config import SCHEDULE_CONFIG, MONITORING_CONFIG

logger = logging.getLogger(__name__)


class JobMonitor:
    """
    Monitors job execution and provides status information.
    
    Tracks:
    - Job health status
    - Consecutive failures
    - Last run times
    - Success/failure rates
    """
    
    def __init__(self):
        self.alert_threshold = MONITORING_CONFIG["alert_on_consecutive_failures"]
        self.max_history = MONITORING_CONFIG["max_execution_history"]
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get comprehensive status for a single job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            Status dictionary with health, last run, stats, etc.
        """
        stats = job_store.get_job_stats(job_id)
        consecutive_failures = job_store.get_consecutive_failures(job_id)
        last_execution = job_store.get_last_execution(job_id)
        history = job_store.get_execution_history(job_id, limit=self.max_history)
        
        # Determine health status
        if consecutive_failures >= self.alert_threshold:
            health = "critical"
        elif consecutive_failures > 0:
            health = "warning"
        elif stats["total_count"] == 0:
            health = "unknown"
        else:
            health = "healthy"
        
        # Calculate success rate
        total = stats["total_count"]
        success_rate = (stats["success_count"] / total * 100) if total > 0 else 0
        
        return {
            "job_id": job_id,
            "health": health,
            "consecutive_failures": consecutive_failures,
            "success_rate": round(success_rate, 2),
            "total_runs": total,
            "successful_runs": stats["success_count"],
            "failed_runs": stats["failure_count"],
            "last_run": last_execution["executed_at"] if last_execution else None,
            "last_run_local": last_execution.get("executed_at_local") if last_execution else None,
            "last_status": last_execution["status"] if last_execution else None,
            "last_error": stats.get("last_error"),
            "history": [
                {
                    "executed_at": h["executed_at"],
                    "status": h["status"],
                    "duration_ms": h.get("duration_ms"),
                    "error_message": h.get("error_message")
                }
                for h in history
            ]
        }
    
    def get_all_job_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status for all jobs.
        
        Returns:
            Dictionary mapping job_id to status
        """
        from jobs import list_jobs
        
        job_ids = list(list_jobs().keys())
        return {
            job_id: self.get_job_status(job_id)
            for job_id in job_ids
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health status.
        
        Returns:
            System health summary
        """
        all_statuses = self.get_all_job_statuses()
        
        # Count jobs by health status
        health_counts = {"healthy": 0, "warning": 0, "critical": 0, "unknown": 0}
        for status in all_statuses.values():
            health_counts[status["health"]] += 1
        
        # Determine overall health
        if health_counts["critical"] > 0:
            overall_health = "critical"
        elif health_counts["warning"] > 0:
            overall_health = "warning"
        elif health_counts["unknown"] == len(all_statuses):
            overall_health = "unknown"
        else:
            overall_health = "healthy"
        
        # Get jobs needing attention
        attention_needed = [
            {
                "job_id": job_id,
                "health": status["health"],
                "consecutive_failures": status["consecutive_failures"],
                "last_error": status["last_error"]
            }
            for job_id, status in all_statuses.items()
            if status["health"] in ("warning", "critical")
        ]
        
        return {
            "overall_health": overall_health,
            "timestamp": now().isoformat(),
            "timezone": "America/New_York",
            "job_counts": health_counts,
            "total_jobs": len(all_statuses),
            "attention_needed": attention_needed,
            "jobs": all_statuses
        }
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check for jobs that need alerting.
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        all_statuses = self.get_all_job_statuses()
        
        for job_id, status in all_statuses.items():
            if status["consecutive_failures"] >= self.alert_threshold:
                alerts.append({
                    "severity": "critical",
                    "job_id": job_id,
                    "message": f"Job {job_id} has failed {status['consecutive_failures']} times consecutively",
                    "last_error": status["last_error"],
                    "timestamp": now().isoformat()
                })
            elif status["consecutive_failures"] > 0:
                alerts.append({
                    "severity": "warning",
                    "job_id": job_id,
                    "message": f"Job {job_id} has failed {status['consecutive_failures']} time(s) consecutively",
                    "last_error": status["last_error"],
                    "timestamp": now().isoformat()
                })
        
        return alerts
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for the monitoring dashboard.
        
        Returns:
            Dashboard data dictionary
        """
        system_health = self.get_system_health()
        alerts = self.check_alerts()
        
        # Calculate uptime percentage (last 24 hours)
        uptime_stats = self._calculate_uptime(hours=24)
        
        return {
            "system_health": system_health,
            "alerts": alerts,
            "uptime_24h": uptime_stats,
            "generated_at": now().isoformat(),
            "timezone": "America/New_York"
        }
    
    def _calculate_uptime(self, hours: int = 24) -> Dict[str, Any]:
        """
        Calculate uptime statistics for the given time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Uptime statistics
        """
        from jobs import list_jobs
        
        cutoff = now() - timedelta(hours=hours)
        job_ids = list(list_jobs().keys())
        
        uptime_by_job = {}
        total_expected = 0
        total_success = 0
        
        for job_id in job_ids:
            # Get executions in the time period
            history = job_store.get_execution_history(job_id, limit=100)
            recent = [h for h in history if datetime.fromisoformat(h["executed_at"].replace("Z", "+00:00")) >= cutoff]
            
            if recent:
                successful = sum(1 for h in recent if h["status"] == "success")
                total = len(recent)
                uptime_pct = (successful / total * 100) if total > 0 else 0
                
                uptime_by_job[job_id] = {
                    "successful": successful,
                    "total": total,
                    "uptime_percentage": round(uptime_pct, 2)
                }
                
                total_success += successful
                total_expected += total
        
        overall_uptime = (total_success / total_expected * 100) if total_expected > 0 else 0
        
        return {
            "period_hours": hours,
            "overall_uptime_percentage": round(overall_uptime, 2),
            "total_executions": total_expected,
            "successful_executions": total_success,
            "by_job": uptime_by_job
        }


# Global monitor instance
monitor = JobMonitor()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_status(job_id: str) -> Dict[str, Any]:
    """Get status for a single job."""
    return monitor.get_job_status(job_id)

def get_all_statuses() -> Dict[str, Dict[str, Any]]:
    """Get status for all jobs."""
    return monitor.get_all_job_statuses()

def get_health() -> Dict[str, Any]:
    """Get overall system health."""
    return monitor.get_system_health()

def get_alerts() -> List[Dict[str, Any]]:
    """Get active alerts."""
    return monitor.check_alerts()

def get_dashboard() -> Dict[str, Any]:
    """Get dashboard data."""
    return monitor.get_dashboard_data()