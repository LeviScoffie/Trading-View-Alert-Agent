"""Integration Service — central orchestrator for TradingView Alert Agent.

Entry point on port 8004. Coordinates:
  1. Webhook Receiver  (port 8000) — alert storage + analysis
  2. Email Notifier    (port 8001) — immediate alert emails
  3. Scheduler         (port 8003) — health check only (optional)
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import clients
import orchestrator
from config import settings
from models import (
    AlertStatusResponse,
    HealthResponse,
    TriggerAnalysisRequest,
    WebhookPayload,
    WebhookResponse,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Integration Service",
    description="Central orchestrator — receives TradingView alerts and coordinates analysis + email",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    logger.info("Integration Service started on %s:%d", settings.host, settings.port)
    logger.info(
        "Downstream: webhook-receiver=%s  analysis-engine=%s  email-notifier=%s",
        settings.webhook_receiver_url,
        settings.analysis_engine_url,
        settings.email_notifier_url,
    )
    logger.info("Confidence threshold: %.2f", settings.confidence_threshold)


# ── Core endpoint ─────────────────────────────────────────────────────────────

@app.post("/webhook", response_model=WebhookResponse)
async def receive_webhook(payload: WebhookPayload, request: Request):
    """Primary entry point — receives TradingView webhook and orchestrates the full pipeline.

    Always returns HTTP 200 (even on partial failures) to prevent TradingView retry spam.
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info("Webhook received from %s — symbol=%s timeframe=%s",
                client_ip, payload.symbol, payload.effective_timeframe())

    result = await orchestrator.process_webhook(payload)

    logger.info(
        "Webhook processed — alert_id=%s confidence=%.2f email_sent=%s services=%s time=%dms",
        result.alert_id, result.confidence, result.email_sent, result.services, result.processing_time_ms,
    )
    return result


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health of this service and all downstream services."""
    checks = await asyncio.gather(
        clients.health_check(settings.webhook_receiver_url, "webhook-receiver"),
        clients.health_check(settings.analysis_engine_url, "analysis-engine"),
        clients.health_check(settings.email_notifier_url, "email-notifier"),
        clients.health_check(settings.scheduler_url, "scheduler"),
    )

    all_healthy = all(s["status"] == "healthy" for s in checks)
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=list(checks),
    )


@app.get("/")
async def root():
    return {"service": "integration-service", "status": "running", "port": settings.port}


# ── Alert status ──────────────────────────────────────────────────────────────

@app.get("/status/{alert_id}", response_model=AlertStatusResponse)
async def get_alert_status(alert_id: int):
    """Return processing status for a stored alert (proxied from webhook-receiver)."""
    url = f"{settings.webhook_receiver_url}/alerts"
    result = await clients._get_with_timeout(url, "webhook-receiver/alerts")

    if "_error" in result:
        return JSONResponse(
            status_code=503,
            content={"error": "Webhook Receiver unavailable", "detail": result["_error"]},
        )

    # Scan the returned alerts list for this alert_id
    alerts = result.get("alerts", [])
    for alert in alerts:
        if alert.get("id") == alert_id:
            return AlertStatusResponse(
                alert_id=alert_id,
                symbol=alert.get("symbol", ""),
                status=alert.get("status", "unknown"),
                stored=True,
                analyzed=alert.get("status") in ("processed", "analyzed"),
                email_sent=bool(alert.get("email_sent", False)),
                confidence=float(alert.get("confidence", 0)),
            )

    return JSONResponse(status_code=404, content={"error": f"Alert {alert_id} not found"})


# ── Manual trigger ────────────────────────────────────────────────────────────

@app.post("/trigger-analysis", response_model=WebhookResponse)
async def trigger_analysis(req: TriggerAnalysisRequest):
    """Manually trigger analysis for a symbol without a webhook alert.

    Useful for testing or scheduled re-analysis.
    """
    logger.info("Manual analysis trigger — symbol=%s timeframe=%s force_email=%s",
                req.symbol, req.timeframe, req.force_email)
    return await orchestrator.run_analysis_only(req.symbol, req.timeframe, req.force_email)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "integration_service:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
