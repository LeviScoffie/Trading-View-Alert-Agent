# Analysis Engine — Microservice

Context-aware candlestick pattern analysis with multi-timeframe intelligence.

**Port:** 8001  
**Role:** Standalone analysis microservice — called by the Integration Service for every alert.

---

## Overview

The Analysis Engine transforms raw symbol + timeframe inputs into intelligent trading signals:

- **12 candlestick patterns** — engulfing, doji, hammer, morning/evening star, three soldiers/crows
- **20-period moving average** — trend direction, slope, distance from price
- **Context rules** — 5 rules combining patterns + MA + multi-timeframe into a confidence score
- **Multi-timeframe confluence** — 1W/1D/4H/1H alignment detection

---

## HTTP API

### POST /analyze

**Request:**
```json
{
  "symbol": "BTCUSD",
  "timeframe": "1D",
  "lookback_days": 30,
  "candle": {
    "timestamp": "2026-04-09T12:00:00Z",
    "open": 64000,
    "high": 66000,
    "low": 63500,
    "close": 65000,
    "volume": 123456
  }
}
```

`candle` is optional — if provided, the candle is stored in `ohlcv.db` before analysis runs so the engine always has the latest data point.

**Response:**
```json
{
  "symbol": "BTCUSD",
  "timestamp": "2026-04-09T12:00:01Z",
  "patterns": [
    {
      "type": "bullish_engulfing",
      "confidence": 0.85,
      "timeframe": "1D",
      "direction": "bullish"
    }
  ],
  "ma20": {
    "price": 65000,
    "ma20": 63000,
    "distance_pct": 3.17,
    "trend": "bullish",
    "slope": "rising"
  },
  "context": {
    "sentiment": "bullish",
    "confidence": 0.82,
    "reasoning": "Weekly bullish engulfing + past 3 days bearish pullback",
    "recommendation": "consider_long"
  },
  "multi_timeframe": {
    "weekly": {"trend": "bullish", "alignment": true},
    "daily":  {"trend": "bullish", "alignment": true},
    "4h":     {"trend": "bearish", "alignment": false}
  }
}
```

> **Note:** If `ohlcv.db` has insufficient history (fresh install), the engine returns `confidence: 0.0` and empty patterns. Confidence grows as OHLCV candle data accumulates from real TradingView alerts.

### GET /health

```json
{"status": "healthy", "service": "analysis-engine", "db_path": "/app/data/ohlcv.db"}
```

---

## Pattern Detection (12 Patterns)

| Pattern | Type | Base Confidence |
|---------|------|-----------------|
| Bullish Engulfing | Reversal | 0.85 |
| Bearish Engulfing | Reversal | 0.85 |
| Doji | Indecision | 0.70 |
| Dragonfly Doji | Bullish reversal | 0.75 |
| Gravestone Doji | Bearish reversal | 0.75 |
| Hammer | Bullish reversal | 0.80 |
| Inverted Hammer | Bullish reversal | 0.75 |
| Morning Star | Bullish reversal | 0.85 |
| Evening Star | Bearish reversal | 0.85 |
| Three White Soldiers | Bullish continuation | 0.85 |
| Three Black Crows | Bearish continuation | 0.85 |

---

## Context Rules

| Rule | Condition | Confidence |
|------|-----------|------------|
| 1 | Past 2–3 days bearish + weekly bullish engulfing | 0.85 |
| 2 | Price > 20MA + bullish engulfing | 0.75–0.90 |
| 3 | Price < 20MA + bearish engulfing | 0.75–0.90 |
| 4 | Multi-timeframe alignment | 0.60–0.80 |
| 5 | Doji at support/resistance | 0.70–0.75 |

---

## Timeframe Weights

| Timeframe | Weight |
|-----------|--------|
| Weekly (1W) | 40% |
| Daily (1D) | 30% |
| 4-Hour (4H) | 20% |
| 1-Hour (1H) | 10% |

---

## Recommendations

| Value | Meaning |
|-------|---------|
| `strong_long` | High confidence bullish signal |
| `consider_long` | Moderate bullish signal |
| `neutral` | No clear direction |
| `consider_short` | Moderate bearish signal |
| `strong_short` | High confidence bearish signal |
| `wait` | Conflicting signals — no action |

---

## Docker

```bash
docker build -t analysis-engine .

docker run -d \
  -p 8001:8001 \
  -v tv_data:/app/data \
  -e OHLCV_DB_PATH=/app/data/ohlcv.db \
  analysis-engine
```

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `OHLCV_DB_PATH` | `/app/data/ohlcv.db` | Path to OHLCV SQLite database |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8001` | Listen port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Local Development

```bash
pip install -r requirements.txt
uvicorn api:app --reload --port 8001
```

---

## File Reference

| File | Purpose |
|------|---------|
| `api.py` | FastAPI HTTP entry point — wraps AnalysisEngine for HTTP access |
| `analysis_engine.py` | Main orchestrator — coordinates all analysis components |
| `pattern_detector.py` | Candlestick pattern detection logic |
| `ma_analyzer.py` | 20MA calculation, trend direction, slope analysis |
| `context_engine.py` | Context rules + confidence scoring |
| `multi_timeframe.py` | Multi-TF confluence detection (1W/1D/4H/1H) |
| `database.py` | OHLCV SQLite read/write (`ohlcv.db`) |
| `models.py` | Pydantic data models for all analysis types |
| `test_patterns.py` | Unit tests for pattern detection |
| `example_usage.py` | Library usage examples |

---

*Part of TradingView Alert Agent v2.0*
