# Analysis Engine for TradingView Alert Agent

Context-aware candlestick pattern analysis with multi-timeframe intelligence.

## Overview

This engine transforms raw TradingView alerts into intelligent trading signals by adding:
- **Candlestick pattern detection** (12+ patterns)
- **20-period moving average analysis**
- **Context intelligence** with confidence scoring
- **Multi-timeframe confluence** detection

## Why This Matters

Raw alerts ("BTC Bullish Engulfing") are noise. Context intelligence ("past 3 days bearish + weekly engulfing = high-confidence buy") is the signal.

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from analysis_engine import AnalysisEngine, Timeframe

# Initialize engine
engine = AnalysisEngine(db_path="ohlcv.db")

# Store OHLCV data (from your data source)
engine.store_ohlcv_data("BTCUSD", Timeframe.DAILY, [
    {"timestamp": "2026-04-08T00:00:00", "open": 45000, "high": 46000, 
     "low": 44500, "close": 45500, "volume": 1000000}
])

# Analyze symbol
result = engine.analyze_symbol("BTCUSD", Timeframe.DAILY)

# Print results
print(f"Sentiment: {result.context.sentiment}")
print(f"Confidence: {result.context.confidence}")
print(f"Recommendation: {result.context.recommendation}")
print(f"Reasoning: {result.context.reasoning}")
```

### Quick Analysis Function

```python
from analysis_engine import analyze, Timeframe

result = analyze("BTCUSD", Timeframe.DAILY)
print(result.model_dump_json(indent=2))
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AnalysisEngine                            │
│  (Main Orchestrator)                                         │
└──────────────┬──────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┬──────────────┬─────────────┐
    │          │          │              │             │
    ▼          ▼          ▼              ▼             ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Pattern │ │  MA20  │ │ Context  │ │   Multi  │ │Database  │
│Detector│ │Analyzer│ │  Engine  │ │Timeframe │ │  (SQLite)│
└────────┘ └────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Components

### 1. Pattern Detector (`pattern_detector.py`)

Detects 12+ candlestick patterns:

| Pattern | Type | Significance |
|---------|------|--------------|
| Bullish/Bearish Engulfing | 2-candle | Reversal signal |
| Doji (Standard, Dragonfly, Gravestone) | 1-candle | Indecision/reversal |
| Hammer / Inverted Hammer | 1-candle | Reversal |
| Morning Star / Evening Star | 3-candle | Strong reversal |
| Three White Soldiers / Three Black Crows | 3-candle | Strong trend |

### 2. MA Analyzer (`ma_analyzer.py`)

- Calculates 20-period moving average
- Determines trend (above/below MA)
- Tracks slope (rising, falling, flat)
- Identifies support/resistance levels

### 3. Context Engine (`context_engine.py`)

Implements 5 context rules:

1. **Rule 1**: Past 2-3 days bearish + weekly bullish engulfing = buying opportunity
2. **Rule 2**: Price > 20MA + bullish engulfing = high confidence bullish
3. **Rule 3**: Price < 20MA + bearish engulfing = high confidence bearish
4. **Rule 4**: Multiple timeframe alignment = higher confidence
5. **Rule 5**: Doji at support/resistance = potential reversal

### 4. Multi-Timeframe Analyzer (`multi_timeframe.py`)

- Analyzes Weekly, Daily, 4H, 1H together
- Weights higher timeframes more heavily (Weekly: 40%, Daily: 30%, 4H: 20%, 1H: 10%)
- Detects timeframe divergences
- Calculates overall alignment score

## Output Format

```json
{
  "symbol": "BTCUSD",
  "timestamp": "2026-04-08T10:30:00Z",
  "patterns": [
    {"type": "bullish_engulfing", "confidence": 0.85, "timeframe": "1D"}
  ],
  "ma20": {
    "price": 45000,
    "ma20": 44000,
    "distance_pct": 2.27,
    "trend": "bullish",
    "slope": "rising"
  },
  "context": {
    "sentiment": "bullish",
    "confidence": 0.82,
    "reasoning": "Weekly bullish engulfing + past 3 days bearish pullback = buying opportunity",
    "key_levels": [42000, 48000],
    "recommendation": "consider_long"
  },
  "multi_timeframe": {
    "weekly": {"trend": "bullish", "alignment": true},
    "daily": {"trend": "bullish", "alignment": true},
    "4h": {"trend": "bearish", "alignment": false},
    "overall_alignment": 0.75,
    "divergence_detected": true
  }
}
```

## Running Tests

```bash
# Run all tests
python -m pytest test_patterns.py -v

# Run with coverage
python -m pytest test_patterns.py --cov=. --cov-report=html

# Run specific test
python -m pytest test_patterns.py::TestPatternDetector::test_bullish_engulfing -v
```

## Docker Usage

```bash
# Build image
docker build -t analysis-engine .

# Run tests in container
docker run --rm analysis-engine

# Run analysis (interactive)
docker run --rm -it analysis-engine python -c \
  "from analysis_engine import analyze; print(analyze('BTCUSD'))"
```

## Configuration

Create a custom config:

```python
from models import Config

config = Config(
    db_path="custom.db",
    ma_period=20,
    slope_threshold=0.001,
    doji_threshold=0.01,
    hammer_threshold=0.3,
    pattern_lookback=5,
    confidence_weights={
        "weekly": 0.4,
        "daily": 0.3,
        "4h": 0.2,
        "1h": 0.1
    }
)

engine = AnalysisEngine(config=config)
```

## Integration with TradingView

1. Set up TradingView alerts with webhook to your backend
2. Backend receives alert and calls `engine.process_alert()`
3. Analysis result is sent back as notification (Discord, Telegram, email)

Example webhook handler:

```python
from fastapi import FastAPI
from analysis_engine import AnalysisEngine, AlertInput

app = FastAPI()
engine = AnalysisEngine()

@app.post("/webhook/tradingview")
async def tradingview_alert(alert: dict):
    alert_input = AlertInput(
        symbol=alert["symbol"],
        alert_message=alert["message"],
        alert_price=alert["price"],
        alert_time=datetime.utcnow(),
        timeframe=Timeframe(alert["timeframe"])
    )
    
    result = engine.process_alert(alert_input)
    
    # Send notification with context
    send_notification(f"""
    🚨 {alert['symbol']} Alert
    
    Pattern: {alert['message']}
    Confidence: {result.context.confidence:.0%}
    Recommendation: {result.context.recommendation}
    
    Reasoning: {result.context.reasoning}
    """)
    
    return {"status": "ok"}
```

## License

MIT
