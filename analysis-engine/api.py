"""
Analysis Engine API — FastAPI microservice wrapper.

Exposes the AnalysisEngine library over HTTP so the Integration Service
can call it without any shared-memory or sys.path tricks.

Port: 8001
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from analysis_engine import AnalysisEngine
from models import Timeframe

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = os.getenv("OHLCV_DB_PATH", "/app/data/ohlcv.db")
HOST    = os.getenv("HOST", "0.0.0.0")
PORT    = int(os.getenv("PORT", "8001"))

# TradingView interval string → Timeframe enum value
_TF_MAP: Dict[str, str] = {
    "1W": "1W", "W":   "1W",
    "1D": "1D", "D":   "1D",
    "4H": "4H", "240": "4H",
    "1H": "1H", "60":  "1H",
}

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Analysis Engine",
    description="Candlestick pattern detection, MA20 analysis, and multi-timeframe context",
    version="1.0.0",
)


# ── Models ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., description="Trading symbol, e.g. BTCUSD")
    timeframe: str = Field("1D", description="Chart timeframe, e.g. 1D, 4H")
    lookback_days: int = Field(30, description="Days of OHLCV history to use")
    candle: Optional[Dict[str, Any]] = Field(
        None, description="Optional OHLCV candle to ingest before analysis"
    )

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_timeframe(tv_interval: str) -> Timeframe:
    tf_value = _TF_MAP.get(tv_interval.upper(), "1D")
    return Timeframe(tf_value)


def _enrich_patterns(patterns: list) -> list:
    """Add a 'direction' field to each pattern for email templates."""
    BULLISH = {"bullish_engulfing", "hammer", "inverted_hammer",
               "morning_star", "three_white_soldiers", "dragonfly_doji"}
    BEARISH = {"bearish_engulfing", "evening_star",
               "three_black_crows", "gravestone_doji"}
    enriched = []
    for p in patterns:
        p = dict(p)
        ptype = p.get("type", "")
        p["direction"] = "bullish" if ptype in BULLISH else "bearish" if ptype in BEARISH else "neutral"
        enriched.append(p)
    return enriched


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "healthy", "service": "analysis-engine", "db_path": DB_PATH}


@app.get("/")
def root():
    return {"service": "analysis-engine", "status": "running", "port": PORT}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Run the full analysis pipeline for a symbol.

    Optionally ingests an OHLCV candle before running so the engine
    always has the freshest data point.
    """
    logger.info("Analysis request — symbol=%s timeframe=%s", req.symbol, req.timeframe)

    engine = AnalysisEngine(db_path=DB_PATH)
    try:
        timeframe = _parse_timeframe(req.timeframe)

        # Ingest candle if provided
        if req.candle:
            candle = req.candle
            ts = candle.get("timestamp") or candle.get("time") or datetime.utcnow().isoformat()
            engine.store_ohlcv_data(req.symbol, timeframe, [{
                "timestamp": ts,
                "open":   float(candle["open"]),
                "high":   float(candle["high"]),
                "low":    float(candle["low"]),
                "close":  float(candle["close"]),
                "volume": float(candle.get("volume", 0)),
            }])
            logger.info("Stored OHLCV candle for %s [%s]", req.symbol, req.timeframe)

        result = engine.analyze_symbol(req.symbol, timeframe)
        serialised = result.model_dump()

        # Enrich patterns with direction field
        serialised["patterns"] = _enrich_patterns(serialised.get("patterns") or [])

        confidence = (serialised.get("context") or {}).get("confidence", 0)
        recommendation = (serialised.get("context") or {}).get("recommendation", "n/a")
        logger.info(
            "Analysis complete — %s confidence=%.2f recommendation=%s",
            req.symbol, confidence, recommendation,
        )
        return serialised

    except Exception as e:
        logger.error("Analysis failed for %s: %s", req.symbol, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        engine.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting Analysis Engine API on %s:%d", HOST, PORT)
    logger.info("OHLCV database: %s", DB_PATH)
    uvicorn.run("api:app", host=HOST, port=PORT, reload=False,
                log_level=os.getenv("LOG_LEVEL", "info").lower())
