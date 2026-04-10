"""Core orchestration flow — FR-001 through FR-006.

Flow per PRD:
  1. store_alert        → webhook-receiver:8000/webhook
  2. analyze            → analysis-engine:8001/analyze
  3. store_analysis     → webhook-receiver:8000/analysis/{alert_id}
  4. send_alert_email   → email-notifier:8002/send-alert  (if confidence >= threshold)
  5. return unified response
"""

import logging
import time
from datetime import datetime, timezone

import clients
from config import settings
from models import OrchestrationResult, WebhookPayload, WebhookResponse

logger = logging.getLogger(__name__)


def _build_response(result: OrchestrationResult) -> WebhookResponse:
    overall = "processed"
    if result.analysis_status in ("failed", "timeout") or result.webhook_status == "failed":
        overall = "partial"

    return WebhookResponse(
        status=overall,
        alert_id=result.alert_id,
        symbol=result.symbol,
        confidence=result.confidence,
        email_sent=result.email_sent,
        processing_time_ms=result.processing_time_ms,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={
            "webhook": result.webhook_status,
            "analysis": result.analysis_status,
            "email": result.email_status,
        },
        error=result.error,
    )


async def process_webhook(payload: WebhookPayload) -> WebhookResponse:
    """Orchestrate the full alert pipeline for an inbound TradingView webhook."""
    start_ms = time.monotonic() * 1000
    result = OrchestrationResult(symbol=payload.symbol)
    timeframe = payload.effective_timeframe()

    # ── FR-002: Store alert ───────────────────────────────────────────────────
    logger.info("[%s] Storing alert", payload.symbol)
    stored = await clients.store_alert(payload.model_dump())

    if "_error" in stored:
        result.webhook_status = "failed"
        result.error = f"Webhook Receiver unavailable: {stored['_error']}"
        logger.error("[%s] Failed to store alert: %s", payload.symbol, stored["_error"])
    else:
        result.alert_id = stored.get("alert_id")
        result.webhook_status = "success"
        logger.info("[%s] Alert stored — id=%s", payload.symbol, result.alert_id)

    # ── FR-003: Analyze ───────────────────────────────────────────────────────
    logger.info("[%s] Running analysis [%s]", payload.symbol, timeframe)
    analysis = await clients.analyze(payload.symbol, timeframe)

    if "_error" in analysis or not analysis:
        result.analysis_status = "failed"
        result.error = result.error or f"Analysis Engine unavailable: {analysis.get('_error', 'empty response')}"
        logger.error("[%s] Analysis failed", payload.symbol)
    else:
        result.analysis = analysis
        result.confidence = float((analysis.get("context") or {}).get("confidence", 0))
        result.analysis_status = "success"
        logger.info("[%s] Analysis complete — confidence=%.2f", payload.symbol, result.confidence)

    # ── FR-004: Persist analysis result ──────────────────────────────────────
    if result.analysis_status == "success" and result.alert_id is not None:
        stored_analysis = await clients.store_analysis(
            alert_id=result.alert_id,
            symbol=payload.symbol,
            timeframe=timeframe,
            result=result.analysis,
        )
        if "_error" in stored_analysis:
            logger.warning("[%s] Failed to persist analysis: %s", payload.symbol, stored_analysis["_error"])
        else:
            logger.info("[%s] Analysis persisted for alert %s", payload.symbol, result.alert_id)

    # ── FR-005: Conditional email ─────────────────────────────────────────────
    if result.analysis_status == "success" and result.confidence >= settings.confidence_threshold:
        logger.info(
            "[%s] Confidence %.2f >= %.2f — sending alert email",
            payload.symbol, result.confidence, settings.confidence_threshold,
        )
        email_resp = await clients.send_alert_email(payload.symbol, result.analysis)
        if "_error" in email_resp or email_resp.get("status") != "sent":
            result.email_status = "failed"
            logger.error("[%s] Email failed: %s", payload.symbol, email_resp.get("_error", email_resp))
        else:
            result.email_sent = True
            result.email_status = "success"
            logger.info("[%s] Alert email sent", payload.symbol)
    else:
        result.email_status = "skipped"
        if result.analysis_status == "success":
            logger.info(
                "[%s] Confidence %.2f < %.2f — skipping email",
                payload.symbol, result.confidence, settings.confidence_threshold,
            )

    result.processing_time_ms = int(time.monotonic() * 1000 - start_ms)
    return _build_response(result)


async def run_analysis_only(
    symbol: str,
    timeframe: str,
    force_email: bool = False,
) -> WebhookResponse:
    """Trigger analysis without a webhook alert.

    Used by POST /trigger-analysis for manual or scheduled re-analysis.
    """
    start_ms = time.monotonic() * 1000
    result = OrchestrationResult(symbol=symbol)
    result.webhook_status = "skipped"

    logger.info("[%s] Manual analysis — timeframe=%s force_email=%s", symbol, timeframe, force_email)
    analysis = await clients.analyze(symbol, timeframe)

    if "_error" in analysis or not analysis:
        result.analysis_status = "failed"
        result.error = f"Analysis Engine unavailable: {analysis.get('_error', 'empty response')}"
    else:
        result.analysis = analysis
        result.confidence = float((analysis.get("context") or {}).get("confidence", 0))
        result.analysis_status = "success"

    if result.analysis_status == "success" and (force_email or result.confidence >= settings.confidence_threshold):
        email_resp = await clients.send_alert_email(symbol, result.analysis)
        result.email_sent = email_resp.get("status") == "sent"
        result.email_status = "success" if result.email_sent else "failed"
    else:
        result.email_status = "skipped"

    result.processing_time_ms = int(time.monotonic() * 1000 - start_ms)
    return _build_response(result)
