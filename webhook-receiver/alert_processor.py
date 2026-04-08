"""
Alert Processor — orchestrates the full Webhook → Analysis → Email pipeline.

Designed to run as a FastAPI BackgroundTask so the /webhook endpoint
returns in < 50 ms while the heavy lifting happens asynchronously.

Flow:
    receive_webhook()
        └─ background: process_alert()
                ├─ analysis_bridge.run_analysis()   (store candle + detect patterns)
                ├─ db.store_analysis_result()        (persist for history/reports)
                ├─ db.mark_as_processed()
                └─ if confidence >= threshold → _trigger_alert_email()
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Confidence level above which an immediate email is fired — driven by config/env
from config import settings  # noqa: E402 (import after logger setup is intentional)
CONFIDENCE_THRESHOLD: float = settings.confidence_threshold

# Add email-notifier to path once at module load
_EMAIL_NOTIFIER_DIR = str(Path(__file__).parent.parent / "email-notifier")
if _EMAIL_NOTIFIER_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_NOTIFIER_DIR)


# ── Public entry-point ────────────────────────────────────────────────────────

def process_alert(
    alert_id: int,
    symbol: str,
    tv_interval: str,
    candle: Optional[Dict[str, Any]],
    db,           # AlertDatabase instance (from database.py)
) -> None:
    """
    Background task triggered after every webhook is stored.

    Args:
        alert_id:    Primary key of the stored alert row.
        symbol:      Normalised symbol, e.g. "BTCUSD".
        tv_interval: TradingView interval string, e.g. "1D", "4H".
        candle:      Optional OHLCV dict extracted from the webhook payload.
        db:          AlertDatabase instance for result persistence.
    """
    logger.info("Processing alert %d — %s [%s]", alert_id, symbol, tv_interval)

    try:
        from analysis_bridge import run_analysis

        result = run_analysis(symbol, tv_interval, candle)

        if result is None:
            logger.warning("Analysis returned None for alert %d (%s)", alert_id, symbol)
            return

        context      = result.get("context") or {}
        confidence   = float(context.get("confidence", 0))
        recommendation = str(context.get("recommendation", "neutral"))

        # ── Persist result ───────────────────────────────────────────────────
        db.store_analysis_result(
            alert_id=alert_id,
            symbol=symbol,
            timeframe=tv_interval,
            result=result,
        )
        db.mark_as_processed(alert_id)

        logger.info(
            "Alert %d processed — confidence=%.2f recommendation=%s",
            alert_id, confidence, recommendation,
        )

        # ── Conditional email ────────────────────────────────────────────────
        if confidence >= CONFIDENCE_THRESHOLD:
            _trigger_alert_email(symbol, result, confidence, recommendation)
        else:
            logger.info(
                "Confidence %.2f below threshold %.2f — no email for %s",
                confidence, CONFIDENCE_THRESHOLD, symbol,
            )

    except Exception:
        logger.exception("Unhandled error processing alert %d (%s)", alert_id, symbol)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _trigger_alert_email(
    symbol: str,
    analysis_result: Dict[str, Any],
    confidence: float,
    recommendation: str,
) -> None:
    """Fire an immediate email for a high-confidence signal."""
    try:
        from email_notifier import EmailNotifier  # noqa: PLC0415

        notifier = EmailNotifier()
        success = notifier.send_alert_email(symbol, analysis_result)

        if success:
            logger.info(
                "Alert email sent — %s (confidence=%.0f%%, recommendation=%s)",
                symbol, confidence * 100, recommendation,
            )
        else:
            logger.warning("Email send returned False for %s", symbol)

    except Exception:
        logger.exception("Failed to send alert email for %s", symbol)
