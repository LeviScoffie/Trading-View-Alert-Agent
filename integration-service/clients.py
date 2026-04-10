"""Async HTTP clients for downstream services with retry + timeout.

Service topology (matching PRD):
  webhook-receiver  :8000  — alert storage + analysis result persistence
  analysis-engine   :8001  — pattern detection, MA20, multi-timeframe context
  email-notifier    :8002  — immediate alert emails + scheduled reports
  scheduler         :8003  — health check only (optional)
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(settings.request_timeout_seconds)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _post_with_retry(url: str, payload: Dict[str, Any], label: str) -> Dict[str, Any]:
    """POST with exponential backoff retry. Returns error dict on total failure."""
    last_error: Optional[str] = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException:
            last_error = "timeout"
            logger.warning("%s attempt %d/%d timed out", label, attempt, settings.max_retries)
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}"
            logger.warning("%s attempt %d/%d failed: %s", label, attempt, settings.max_retries, last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning("%s attempt %d/%d error: %s", label, attempt, settings.max_retries, last_error)

        if attempt < settings.max_retries:
            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))  # 0.5s → 1s → 2s

    logger.error("%s failed after %d attempts: %s", label, settings.max_retries, last_error)
    return {"_error": last_error}


async def _get_with_timeout(url: str, label: str) -> Dict[str, Any]:
    """Single GET with timeout. Returns error dict on failure."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("%s unreachable: %s", label, str(e))
        return {"_error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

async def store_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
    """FR-002: POST alert to webhook-receiver /webhook for storage."""
    url = f"{settings.webhook_receiver_url}/webhook"
    return await _post_with_retry(url, payload, "webhook-receiver/store")


async def analyze(symbol: str, timeframe: str) -> Dict[str, Any]:
    """FR-003: POST to analysis-engine /analyze to run analysis pipeline."""
    url = f"{settings.analysis_engine_url}/analyze"
    payload = {"symbol": symbol, "timeframe": timeframe}
    return await _post_with_retry(url, payload, "analysis-engine/analyze")


async def store_analysis(alert_id: int, symbol: str, timeframe: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """FR-004: POST analysis result to webhook-receiver /analysis/{alert_id} for persistence."""
    url = f"{settings.webhook_receiver_url}/analysis/{alert_id}"
    payload = {"symbol": symbol, "timeframe": timeframe, "result": result}
    return await _post_with_retry(url, payload, "webhook-receiver/store-analysis")


async def send_alert_email(symbol: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """FR-005: POST to email-notifier /send-alert for immediate alert email."""
    url = f"{settings.email_notifier_url}/send-alert"
    payload = {"symbol": symbol, "analysis": analysis}
    return await _post_with_retry(url, payload, "email-notifier/send-alert")


async def health_check(base_url: str, service_name: str) -> Dict[str, Any]:
    """GET /health from a downstream service. Returns status + response time."""
    url = f"{base_url}/health"
    start = time.monotonic()
    result = await _get_with_timeout(url, service_name)
    elapsed_ms = round((time.monotonic() - start) * 1000, 1)

    if "_error" in result:
        return {"name": service_name, "status": "unhealthy", "error": result["_error"], "response_time_ms": elapsed_ms}
    return {"name": service_name, "status": "healthy", "response_time_ms": elapsed_ms}
