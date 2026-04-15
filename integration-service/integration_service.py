"""Integration Service - FastAPI app with orchestration logic."""

import logging
import sys
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse
import hmac
import hashlib

from config import settings
from models import (
    TradingViewAlert,
    AnalysisRequest,
    ProcessAlertResponse,
    AlertStatusResponse,
    HealthResponse,
    ServiceHealth
)
from orchestrator import orchestrator
from clients import webhook_client, analysis_client, email_client, scheduler_client

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TradingView Integration Service",
    description="Orchestrates webhook → analysis → email flow",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Integration Service started")
    logger.info(f"Webhook Receiver: {settings.WEBHOOK_RECEIVER_URL}")
    logger.info(f"Analysis Engine: {settings.ANALYSIS_ENGINE_URL}")
    logger.info(f"Email Notifier: {settings.EMAIL_NOTIFIER_URL}")
    logger.info(f"Server: {settings.HOST}:{settings.PORT}")


async def validate_webhook_signature(request: Request) -> None:
    """Dependency to validate webhook signature."""
    if not settings.WEBHOOK_SECRET:
        return
    
    signature = request.headers.get("X-TradingView-Signature")
    
    if not signature:
        signature = request.query_params.get("signature")
    
    if not signature:
        logger.warning("Webhook request missing signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature"
        )
    
    body = await request.body()
    
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature.lower(), expected_signature.lower()):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "TradingView Integration Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/webhook - Receive and process TradingView alerts",
            "/status/{alert_id} - Get alert processing status",
            "/trigger-analysis - Manually trigger analysis",
            "/health - Health check and service statuses"
        ]
    }


@app.post("/webhook", response_model=ProcessAlertResponse)
async def receive_webhook(
    alert: TradingViewAlert,
    request: Request,
    _: None = Depends(validate_webhook_signature)
):
    """
    Receive TradingView webhook and orchestrate full processing flow.
    
    This endpoint:
    1. Stores the alert in the webhook receiver
    2. Triggers analysis via the analysis engine
    3. Sends email if confidence >= threshold
    
    Returns the complete processing result.
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Received webhook from {client_ip} for symbol: {alert.symbol}")
    
    try:
        result = await orchestrator.process_alert(alert)
        return result
    except Exception as e:
        logger.error(f"Failed to process alert: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process alert: {str(e)}"
        )


@app.get("/status/{alert_id}")
async def get_alert_status(alert_id: int):
    """
    Get the full alert + analysis status.
    
    Returns alert details and any associated analysis.
    """
    status_info = await orchestrator.get_alert_status(alert_id)
    
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    
    return status_info


@app.post("/trigger-analysis")
async def trigger_analysis(request: AnalysisRequest):
    """
    Manually trigger analysis for a symbol.
    
    This bypasses the webhook receiver and directly triggers analysis.
    """
    logger.info(f"Manual analysis triggered for {request.symbol}")
    
    try:
        result = await orchestrator.process_alert_simple(
            symbol=request.symbol,
            timeframe=request.timeframe
        )
        return result
    except Exception as e:
        logger.error(f"Failed to trigger analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger analysis: {str(e)}"
        )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint that checks all connected services.
    
    Returns health status of integration service and all downstream services.
    """
    services = []
    timestamp = datetime.utcnow().isoformat()
    
    # Check Webhook Receiver
    start = time.time()
    try:
        webhook_health = await webhook_client.health_check()
        services.append(ServiceHealth(
            name="webhook-receiver",
            url=settings.WEBHOOK_RECEIVER_URL,
            status=webhook_health.get("status", "unknown"),
            response_time_ms=(time.time() - start) * 1000
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="webhook-receiver",
            url=settings.WEBHOOK_RECEIVER_URL,
            status="unhealthy",
            error=str(e)
        ))
    
    # Check Analysis Engine
    start = time.time()
    try:
        analysis_health = await analysis_client.health_check()
        services.append(ServiceHealth(
            name="analysis-engine",
            url=settings.ANALYSIS_ENGINE_URL,
            status=analysis_health.get("status", "unknown"),
            response_time_ms=(time.time() - start) * 1000
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="analysis-engine",
            url=settings.ANALYSIS_ENGINE_URL,
            status="unhealthy",
            error=str(e)
        ))
    
    # Check Email Notifier
    start = time.time()
    try:
        email_health = await email_client.health_check()
        services.append(ServiceHealth(
            name="email-notifier",
            url=settings.EMAIL_NOTIFIER_URL,
            status=email_health.get("status", "unknown"),
            response_time_ms=(time.time() - start) * 1000
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="email-notifier",
            url=settings.EMAIL_NOTIFIER_URL,
            status="unhealthy",
            error=str(e)
        ))
    
    # Check Scheduler
    start = time.time()
    try:
        scheduler_health = await scheduler_client.health_check()
        services.append(ServiceHealth(
            name="scheduler",
            url=settings.SCHEDULER_URL,
            status=scheduler_health.get("status", "unknown"),
            response_time_ms=(time.time() - start) * 1000
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="scheduler",
            url=settings.SCHEDULER_URL,
            status="unhealthy",
            error=str(e)
        ))
    
    # Determine overall status
    all_healthy = all(s.status in ("healthy", "ok") for s in services)
    overall_status = "healthy" if all_healthy else "degraded"
    
    return HealthResponse(
        status=overall_status,
        timestamp=timestamp,
        services=services
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "integration_service:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower()
    )