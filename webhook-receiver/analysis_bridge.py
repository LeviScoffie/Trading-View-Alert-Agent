"""
Analysis Bridge — connects the webhook receiver to the analysis engine.

Handles sys.path injection so the analysis-engine package can be imported
without installing it. Stores incoming OHLCV candles then runs the full
AnalysisEngine pipeline, returning a plain dict result.
"""

import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Path injection ────────────────────────────────────────────────────────────
_ANALYSIS_ENGINE_DIR = Path(__file__).parent.parent / "analysis-engine"
if str(_ANALYSIS_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_ENGINE_DIR))

# Default shared OHLCV database (lives inside the analysis-engine directory)
_DEFAULT_OHLCV_DB = str(_ANALYSIS_ENGINE_DIR / "ohlcv.db")

# TradingView interval string → Timeframe enum value
_TF_MAP: Dict[str, str] = {
    "1W":  "1W", "W":   "1W",
    "1D":  "1D", "D":   "1D",
    "4H":  "4H", "240": "4H",
    "1H":  "1H", "60":  "1H",
}


def _parse_timeframe(tv_interval: str):
    """Return the Timeframe enum member matching a TradingView interval string."""
    from models import Timeframe  # imported here to keep top-level import-free

    tf_value = _TF_MAP.get(tv_interval.upper(), "1D")
    return Timeframe(tf_value)


def _enrich_patterns(patterns: list) -> list:
    """
    Add a 'direction' field to each pattern dict so email templates
    can colour-code them without knowing every enum value.
    """
    BULLISH_TYPES = {
        "bullish_engulfing", "hammer", "inverted_hammer",
        "morning_star", "three_white_soldiers", "dragonfly_doji",
    }
    BEARISH_TYPES = {
        "bearish_engulfing", "evening_star",
        "three_black_crows", "gravestone_doji",
    }

    enriched = []
    for p in patterns:
        p = dict(p)
        ptype = p.get("type", "")
        if ptype in BULLISH_TYPES:
            p["direction"] = "bullish"
        elif ptype in BEARISH_TYPES:
            p["direction"] = "bearish"
        else:
            p["direction"] = "neutral"
        enriched.append(p)
    return enriched


def run_analysis(
    symbol: str,
    tv_interval: str,
    candle: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Store an optional incoming OHLCV candle then run the full analysis pipeline.

    Args:
        symbol:      Trading symbol, e.g. "BTCUSD"
        tv_interval: TradingView interval string, e.g. "1D", "4H", "240"
        candle:      Optional dict with keys open/high/low/close/volume/timestamp.
                     When present the candle is written to the OHLCV DB before
                     analysis so the engine always has the freshest data point.
        db_path:     Override path to the OHLCV SQLite database.

    Returns:
        AnalysisResult serialised as a plain dict, or None on failure.
    """
    ohlcv_db = db_path or _DEFAULT_OHLCV_DB

    try:
        from analysis_engine import AnalysisEngine  # noqa: PLC0415

        timeframe = _parse_timeframe(tv_interval)
        engine = AnalysisEngine(db_path=ohlcv_db)

        try:
            # ── 1. Persist the incoming candle ───────────────────────────────
            if candle:
                # Normalise timestamp field
                ts = candle.get("timestamp") or candle.get("time") or datetime.utcnow().isoformat()
                normalised = {
                    "timestamp": ts,
                    "open":   float(candle["open"]),
                    "high":   float(candle["high"]),
                    "low":    float(candle["low"]),
                    "close":  float(candle["close"]),
                    "volume": float(candle.get("volume", 0)),
                }
                engine.store_ohlcv_data(symbol, timeframe, [normalised])
                logger.info("Stored OHLCV candle for %s [%s]", symbol, tv_interval)

            # ── 2. Run analysis ──────────────────────────────────────────────
            result = engine.analyze_symbol(symbol, timeframe)
            serialised = result.model_dump()

            # Enrich patterns with direction for email templates
            serialised["patterns"] = _enrich_patterns(serialised.get("patterns") or [])

            logger.info(
                "Analysis complete — %s confidence=%.2f recommendation=%s",
                symbol,
                (serialised.get("context") or {}).get("confidence", 0),
                (serialised.get("context") or {}).get("recommendation", "n/a"),
            )
            return serialised

        finally:
            engine.close()

    except Exception:
        logger.exception("Analysis failed for %s", symbol)
        return None
