"""
API Module

FastAPI endpoints for job management, monitoring, and manual triggers.
Provides REST API for the scheduler.
"""

import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from scheduler import get_scheduler, TradingViewScheduler
from jobs import execute_job, list_jobs as get_available_jobs
from monitor import get_status, get_all_statuses, get_health, get_alerts, get_dashboard
from timezone_utils import now, format_est
from config import API_HOST, API_PORT

logger = logging.getLogger(__name__)

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class JobInfo(BaseModel):
    """Job information model."""
    id: str
    name: str
    next_run_time: Optional[str]
    trigger: str


class JobStatus(BaseModel):
    """Job status model."""
    job_id: str
    health: str
    consecutive_failures: int
    success_rate: float
    total_runs: int
    last_run: Optional[str]
    last_status: Optional[str]
    last_error: Optional[str]


class TriggerResponse(BaseModel):
    """Job trigger response model."""
    success: bool
    message: str
    job_id: str
    triggered_at: str


class PauseResponse(BaseModel):
    """Job pause/resume response model."""
    success: bool
    message: str
    job_id: str
    action: str


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    scheduler: str
    timestamp: str
    timezone: str


class DashboardResponse(BaseModel):
    """Dashboard data response model."""
    system_health: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    uptime_24h: Dict[str, Any]
    generated_at: str


# =============================================================================
# FASTAPI APP
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting scheduler API")
    scheduler = get_scheduler()
    scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down scheduler API")
    scheduler.shutdown()


app = FastAPI(
    title="TradingView Alert Agent Scheduler",
    description="APScheduler-based job scheduler with timezone support and monitoring",
    version="1.0.0",
    lifespan=lifespan
)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "TradingView Alert Agent Scheduler",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Get scheduler health status.
    
    Returns overall health, job statuses, and timestamp.
    """
    scheduler = get_scheduler()
    system_health = get_health()
    
    return HealthResponse(
        status="ok" if system_health["overall_health"] == "unknown"
                     else system_health["overall_health"],
        scheduler="running" if scheduler.running else "stopped",
        timestamp=now().isoformat(),
        timezone="America/New_York"
    )


@app.get("/jobs", response_model=List[JobInfo])
async def list_jobs():
    """
    List all scheduled jobs.
    
    Returns job IDs, names, next run times, and trigger details.
    """
    scheduler = get_scheduler()
    jobs = scheduler.list_jobs()
    
    return [
        JobInfo(
            id=job["id"],
            name=job["name"],
            next_run_time=job["next_run_time"],
            trigger=job["trigger"]
        )
        for job in jobs
    ]


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_details(job_id: str):
    """
    Get detailed status for a specific job.
    
    Args:
        job_id: The job identifier
        
    Returns:
        Job status including health, run history, and statistics
    """
    # Check if job exists
    available_jobs = get_available_jobs()
    if job_id not in available_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    status = get_status(job_id)
    
    return JobStatus(
        job_id=status["job_id"],
        health=status["health"],
        consecutive_failures=status["consecutive_failures"],
        success_rate=status["success_rate"],
        total_runs=status["total_runs"],
        last_run=status["last_run"],
        last_status=status["last_status"],
        last_error=status["last_error"]
    )


@app.post("/jobs/{job_id}/trigger", response_model=TriggerResponse)
async def trigger_job(job_id: str, background_tasks: BackgroundTasks):
    """
    Manually trigger a job to run immediately.
    
    Args:
        job_id: The job identifier
        
    Returns:
        Trigger confirmation with timestamp
    """
    # Check if job exists
    available_jobs = get_available_jobs()
    if job_id not in available_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    scheduler = get_scheduler()
    success = scheduler.trigger_job(job_id)
    
    if success:
        return TriggerResponse(
            success=True,
            message=f"Job {job_id} triggered successfully",
            job_id=job_id,
            triggered_at=now().isoformat()
        )
    else:
        raise HTTPException(status_code=500, detail=f"Failed to trigger job {job_id}")


@app.post("/jobs/{job_id}/pause", response_model=PauseResponse)
async def pause_job(job_id: str):
    """
    Pause a scheduled job.
    
    Args:
        job_id: The job identifier
        
    Returns:
        Pause confirmation
    """
    # Check if job exists
    available_jobs = get_available_jobs()
    if job_id not in available_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    scheduler = get_scheduler()
    success = scheduler.pause_job(job_id)
    
    if success:
        return PauseResponse(
            success=True,
            message=f"Job {job_id} paused successfully",
            job_id=job_id,
            action="pause"
        )
    else:
        raise HTTPException(status_code=500, detail=f"Failed to pause job {job_id}")


@app.post("/jobs/{job_id}/resume", response_model=PauseResponse)
async def resume_job(job_id: str):
    """
    Resume a paused job.
    
    Args:
        job_id: The job identifier
        
    Returns:
        Resume confirmation
    """
    # Check if job exists
    available_jobs = get_available_jobs()
    if job_id not in available_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    scheduler = get_scheduler()
    success = scheduler.resume_job(job_id)
    
    if success:
        return PauseResponse(
            success=True,
            message=f"Job {job_id} resumed successfully",
            job_id=job_id,
            action="resume"
        )
    else:
        raise HTTPException(status_code=500, detail=f"Failed to resume job {job_id}")


@app.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_data():
    """
    Get monitoring dashboard data.
    
    Returns system health, alerts, and uptime statistics.
    """
    dashboard = get_dashboard()
    
    return DashboardResponse(
        system_health=dashboard["system_health"],
        alerts=dashboard["alerts"],
        uptime_24h=dashboard["uptime_24h"],
        generated_at=dashboard["generated_at"]
    )


@app.get("/alerts")
async def get_active_alerts():
    """
    Get active alerts for jobs needing attention.
    
    Returns list of jobs with consecutive failures.
    """
    alerts = get_alerts()
    return {"alerts": alerts, "count": len(alerts)}


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle generic exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    uvicorn.run(
        "api:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_level="info"
    )