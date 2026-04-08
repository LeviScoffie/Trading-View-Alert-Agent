"""
Job Store Module

SQLite-based persistence for job execution history and state.
Provides tracking for job runs, failures, and retry attempts.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import logging

from config import JOB_EXECUTION_STORE_CONFIG, DATABASE_PATH
from timezone_utils import to_utc, to_local, tz_manager

logger = logging.getLogger(__name__)


class JobStore:
    """
    SQLite-based store for job execution history and state.
    
    Tracks:
    - Job execution history
    - Success/failure counts
    - Retry attempts
    - Last run times
    - Error messages
    """
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """
        Initialize the job store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_tables()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _ensure_tables(self):
        """Create necessary tables if they don't exist."""
        with self._get_connection() as conn:
            # Job executions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    job_name TEXT,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,  -- 'success', 'failed', 'retry'
                    duration_ms INTEGER,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    metadata TEXT  -- JSON blob for additional data
                )
            """)
            
            # Job state table (for custom state persistence)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_state (
                    job_id TEXT PRIMARY KEY,
                    state TEXT,  -- JSON blob
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_executions_job_id 
                ON job_executions(job_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_executions_executed_at 
                ON job_executions(executed_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_job_executions_status 
                ON job_executions(status)
            """)
    
    def log_execution(
        self,
        job_id: str,
        status: str,
        job_name: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log a job execution.
        
        Args:
            job_id: Unique job identifier
            status: Execution status ('success', 'failed', 'retry')
            job_name: Human-readable job name
            duration_ms: Execution duration in milliseconds
            error_message: Error message if failed
            retry_count: Number of retry attempts
            metadata: Additional data as dictionary
            
        Returns:
            The ID of the logged execution
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO job_executions 
                (job_id, job_name, status, duration_ms, error_message, retry_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job_name or job_id,
                    status,
                    duration_ms,
                    error_message,
                    retry_count,
                    json.dumps(metadata) if metadata else None
                )
            )
            return cursor.lastrowid
    
    def get_last_execution(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent execution for a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            Execution record as dictionary, or None if no executions
        """
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM job_executions 
                WHERE job_id = ? 
                ORDER BY executed_at DESC 
                LIMIT 1
                """,
                (job_id,)
            ).fetchone()
            
            if row:
                return self._row_to_dict(row)
            return None
    
    def get_execution_history(
        self,
        job_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for a job.
        
        Args:
            job_id: The job identifier
            limit: Maximum number of records to return
            
        Returns:
            List of execution records
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM job_executions 
                WHERE job_id = ? 
                ORDER BY executed_at DESC 
                LIMIT ?
                """,
                (job_id, limit)
            ).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def get_job_stats(self, job_id: str) -> Dict[str, Any]:
        """
        Get statistics for a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            Dictionary with success_count, failure_count, last_success, last_failure
        """
        with self._get_connection() as conn:
            # Get counts
            counts = conn.execute(
                """
                SELECT 
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failure_count,
                    SUM(CASE WHEN status = 'retry' THEN 1 ELSE 0 END) as retry_count,
                    COUNT(*) as total_count
                FROM job_executions 
                WHERE job_id = ?
                """,
                (job_id,)
            ).fetchone()
            
            # Get last success
            last_success = conn.execute(
                """
                SELECT executed_at FROM job_executions 
                WHERE job_id = ? AND status = 'success'
                ORDER BY executed_at DESC 
                LIMIT 1
                """,
                (job_id,)
            ).fetchone()
            
            # Get last failure
            last_failure = conn.execute(
                """
                SELECT executed_at, error_message FROM job_executions 
                WHERE job_id = ? AND status = 'failed'
                ORDER BY executed_at DESC 
                LIMIT 1
                """,
                (job_id,)
            ).fetchone()
            
            return {
                "success_count": counts["success_count"] or 0,
                "failure_count": counts["failure_count"] or 0,
                "retry_count": counts["retry_count"] or 0,
                "total_count": counts["total_count"] or 0,
                "last_success": last_success["executed_at"] if last_success else None,
                "last_failure": last_failure["executed_at"] if last_failure else None,
                "last_error": last_failure["error_message"] if last_failure else None
            }
    
    def get_consecutive_failures(self, job_id: str) -> int:
        """
        Count consecutive failures for a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            Number of consecutive failures (0 if last run was successful)
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT status FROM job_executions 
                WHERE job_id = ? 
                ORDER BY executed_at DESC
                """,
                (job_id,)
            ).fetchall()
            
            count = 0
            for row in rows:
                if row["status"] == "failed":
                    count += 1
                elif row["status"] == "success":
                    break
                # 'retry' status doesn't break the streak
            
            return count
    
    def get_all_job_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all jobs.
        
        Returns:
            Dictionary mapping job_id to stats
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT job_id FROM job_executions
                """
            ).fetchall()
            
            stats = {}
            for row in rows:
                job_id = row["job_id"]
                stats[job_id] = self.get_job_stats(job_id)
            
            return stats
    
    def save_job_state(self, job_id: str, state: Dict[str, Any]):
        """
        Save custom state for a job.
        
        Args:
            job_id: The job identifier
            state: State data as dictionary
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO job_state (job_id, state, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (job_id, json.dumps(state))
            )
    
    def get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get custom state for a job.
        
        Args:
            job_id: The job identifier
            
        Returns:
            State data as dictionary, or None if not found
        """
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT state FROM job_state WHERE job_id = ?
                """,
                (job_id,)
            ).fetchone()
            
            if row:
                return json.loads(row["state"])
            return None
    
    def cleanup_old_records(self, days: int = 90) -> int:
        """
        Delete execution records older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of records deleted
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM job_executions 
                WHERE executed_at < datetime('now', '-{} days')
                """.format(days)
            )
            return cursor.rowcount
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = dict(row)
        
        # Parse JSON metadata
        if result.get("metadata"):
            try:
                result["metadata"] = json.loads(result["metadata"])
            except json.JSONDecodeError:
                pass
        
        # Convert UTC timestamps to local time
        if result.get("executed_at"):
            # executed_at is stored as UTC string
            try:
                dt = datetime.fromisoformat(result["executed_at"].replace("Z", "+00:00"))
                result["executed_at_local"] = to_local(dt).isoformat()
            except (ValueError, AttributeError):
                pass
        
        return result


# Global job store instance
job_store = JobStore()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def log_job_execution(
    job_id: str,
    status: str,
    **kwargs
) -> int:
    """Log a job execution to the store."""
    return job_store.log_execution(job_id, status, **kwargs)

def get_job_history(job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get execution history for a job."""
    return job_store.get_execution_history(job_id, limit)

def get_last_run(job_id: str) -> Optional[Dict[str, Any]]:
    """Get the last execution for a job."""
    return job_store.get_last_execution(job_id)

def get_stats(job_id: str) -> Dict[str, Any]:
    """Get statistics for a job."""
    return job_store.get_job_stats(job_id)

def get_all_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all jobs."""
    return job_store.get_all_job_stats()

def get_failures(job_id: str) -> int:
    """Get consecutive failure count for a job."""
    return job_store.get_consecutive_failures(job_id)