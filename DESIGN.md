# TradingView Alert Agent - Architecture Design Document

## Overview

A context-intelligent trading alert system that transforms raw TradingView signals into actionable insights with behavioral tracking and multi-timeframe analysis.

**Core Philosophy:** Raw alerts ("BTC Bullish Engulfing") are noise. Context intelligence ("past 3 days bearish + weekly engulfing = high-confidence buy") is the signal.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRADINGVIEW ALERT AGENT                            │
└─────────────────────────────────────────────────────────────────────────────┘

                                    INPUTS
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ TradingView     │         │ Manual Logs     │         │ Scheduled       │
│ Webhooks        │         │ (Terminal)      │         │ Analysis        │
│                 │         │                 │         │ (Daily/Weekly)  │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WEBHOOK RECEIVER (Layer 1)                            │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Endpoints:                                                          │    │
│  │   POST /webhook          → Receive TradingView alerts              │    │
│  │   POST /webhook/tradingview → Alternative endpoint                 │    │
│  │   POST /log              → Manual behavior logging                 │    │
│  │   GET  /logs             → Query behavior logs                     │    │
│  │   GET  /logs/{symbol}    → Symbol-specific logs                    │    │
│  │   GET  /attention        → Attention heatmap                       │    │
│  │   GET  /health           → Health check                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Security: HMAC-SHA256 signature validation (optional for local testing)     │
│  Storage: SQLite (alerts + behavior_logs tables)                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ANALYSIS ENGINE (Layer 2)                               │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Pattern   │  │    MA20     │  │   Context   │  │    Multi    │        │
│  │  Detector   │  │  Analyzer   │  │   Engine    │  │ Timeframe   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         └────────────────┴────────────────┴────────────────┘               │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Context Rules:                                                      │   │
│  │   Rule 1: Bearish pullback + weekly engulfing = buy opportunity    │   │
│  │   Rule 2: Price > 20MA + bullish engulfing = high confidence       │   │
│  │   Rule 3: Price < 20MA + bearish engulfing = high confidence       │   │
│  │   Rule 4: Multi-timeframe alignment = higher confidence            │   │
│  │   Rule 5: Doji at support/resistance = potential reversal          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Output: JSON with patterns, MA20 analysis, context, confidence     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EMAIL NOTIFIER (Layer 3) - COMPLETE                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Scheduled Reports:                                                  │    │
│  │   Daily Close   → 5:00 PM EST (crypto daily close)                 │    │
│  │   Weekly Close  → Sunday 5:00 PM EST                               │    │
│  │   Monthly Close → Last day of month 5:00 PM EST                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Format: HTML email with charts, patterns, confidence scores                 │
│  Delivery: SMTP (configurable provider)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Webhook Receiver

**Purpose:** Entry point for all data. Receives TradingView alerts and manual behavior logs.

**Location:** `webhook-receiver/`

**Key Features:**
- HMAC-SHA256 signature validation for security
- Dual input: automated alerts + manual logs
- SQLite persistence with indexing
- Query endpoints for analysis

**Behavior Tracking (No Extension Required):**

TradingView alerts encode behavior through enriched payloads:

```json
{
  "symbol": "{{ticker}}",
  "price": {{close}},
  "timeframe": "{{interval}}",
  "volume": {{volume}},
  "time": "{{time}}",
  "message": "{{strategy.order.action}}"
}
```

Alert naming convention encodes intent:
```
{SYMBOL} - {conviction} - {context}

BTCUSD - high conviction - weekly engulfing
MORPHOUSDT - watching - support test
ETHUSD - set and forget - 200MA
```

Manual logging via terminal alias:
```bash
alias tv='function _tv(){ curl -s -X POST "http://localhost:8000/log" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$1\",\"timeframe\":\"$2\",\"note\":\"$3\"}" | python3 -m json.tool; }; _tv'

tv BTCUSD 4H "looks like accumulation"
```

**Database Schema:**

```sql
-- Alerts from TradingView
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price REAL,
    message TEXT,
    alert_time TEXT,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_payload TEXT
);

-- Manual behavior logs
CREATE TABLE behavior_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    note TEXT,
    source TEXT DEFAULT 'manual'
);
```

---

### 2. Analysis Engine

**Purpose:** Transform raw alerts into context-intelligent signals.

**Location:** `analysis-engine/`

**Modules:**

| Module | Purpose |
|--------|---------|
| `pattern_detector.py` | Detect 12 candlestick patterns |
| `ma_analyzer.py` | 20MA calculations and trend analysis |
| `context_engine.py` | Apply context rules with confidence scoring |
| `multi_timeframe.py` | Multi-TF confluence detection |
| `analysis_engine.py` | Main orchestrator |

**Pattern Detection (12 Patterns):**

| Pattern | Type | Confidence Base |
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

**20MA Analysis:**

```python
{
    "price": 45000,
    "ma20": 44000,
    "distance_pct": 2.27,        # How far from MA
    "trend": "bullish",          # above/below MA
    "slope": "rising"            # rising/falling/flat
}
```

**Context Rules (The Signal):**

| Rule | Condition | Confidence | Output |
|------|-----------|------------|--------|
| 1 | Past 2-3 days bearish + weekly engulfing | 0.85 | "Buying opportunity - bullish context" |
| 2 | Price > 20MA + bullish engulfing | 0.75-0.90 | "High confidence long" |
| 3 | Price < 20MA + bearish engulfing | 0.75-0.90 | "High confidence short" |
| 4 | Multi-timeframe alignment | 0.60-0.80 | "Confluence signal" |
| 5 | Doji at support/resistance | 0.70-0.75 | "Potential reversal" |

**Timeframe Weights:**

| Timeframe | Weight | Rationale |
|-----------|--------|-----------|
| Weekly | 40% | Primary trend direction |
| Daily | 30% | Secondary confirmation |
| 4H | 20% | Entry timing |
| 1H | 10% | Fine-tuning |

**Output Format:**

```json
{
  "symbol": "BTCUSD",
  "timestamp": "2026-04-08T10:30:00Z",
  "patterns": [
    {
      "type": "bullish_engulfing",
      "confidence": 0.85,
      "timeframe": "1D"
    }
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
    "4h": {"trend": "bearish", "alignment": false}
  }
}
```

---

### 3. Email Notifier (Complete)

**Purpose:** Deliver scheduled analysis reports via email with real-time market analysis.

**Location:** `email-notifier/`

**Schedule:**

| Report | Time | Content |
|--------|------|---------|  
| Daily Close | 5:00 PM EST | Daily patterns, MA20 status, context signals |
| Weekly Close | Sunday 5:00 PM EST | Weekly engulfing analysis, multi-TF alignment |
| Monthly Close | Last day 5:00 PM EST | Monthly trend, key levels, major signals |

**Email Format:**
- HTML with dark-themed styling
- Header with TradingView Alert Agent branding
- Summary metrics (total alerts, symbols, bullish/bearish signals)
- Pattern badges with confidence scores (color-coded green/yellow/red)
- MA20 status with visual indicator (green/red dot)
- Context reasoning section explaining the analysis
- Multi-timeframe alignment grid (Weekly/Daily/4H/1H)
- Actionable recommendations (5 levels: strong_long → strong_short)
- Recent alerts list
- Plain text fallback

**Implementation:**
- APScheduler for cron-like scheduling with timezone support
- Jinja2 for HTML templating
- Support for SMTP (Gmail), SendGrid, and AWS SES
- Timezone-aware (America/New_York)
- Retry logic for failed sends (3 retries with 60s delay)
- Health checks for Docker deployment

**Analysis Integration:**
The report generator connects to the analysis-engine OHLCV database:
- `get_ohlcv_data()` — Fetch price data for any symbol/timeframe
- `calculate_ma20()` — Calculate 20-period moving average
- `detect_patterns()` — Detect candlestick patterns (engulfing, doji, hammer, shooting star)
- `analyze_multi_timeframe()` — Analyze across 1W/1D/4H/1H timeframes
- `generate_context_analysis()` — Apply context rules and calculate confidence
- `generate_symbol_analysis()` — Complete analysis pipeline for a symbol

**Files:**
- `email_notifier.py` — Main scheduler and sender (~280 lines)
- `templates.py` — HTML email templates (~500 lines)
- `report_generator.py` — Database queries, OHLCV analysis, pattern detection (~450 lines)
- `config.py` — Configuration management (~100 lines)
- `requirements.txt` — Dependencies
- `Dockerfile` — Container setup
- `README.md` — Usage documentation

---

## Data Flow

```
TradingView Alert
       │
       ▼
┌─────────────────┐
│ Webhook         │
│ Receiver        │
│ (validate &     │
│  store)         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ SQLite          │────→│ Analysis        │
│ (alerts table)  │     │ Engine          │
└─────────────────┘     │ (fetch OHLCV,   │
         │              │  run analysis)  │
         │              └────────┬────────┘
         │                       │
         │              ┌────────┴────────┐
         │              │                 │
         │              ▼                 ▼
         │     ┌─────────────┐   ┌─────────────┐
         │     │ Pattern     │   │ Context     │
         │     │ Detector    │   │ Engine      │
         │     └─────────────┘   └──────┬──────┘
         │                            │
         │                            ▼
         │                   ┌─────────────────┐
         │                   │ JSON Output     │
         │                   │ (confidence,    │
         │                   │  recommendation)│
         │                   └────────┬────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐         ┌─────────────────┐
│ Behavior Logs   │         │ Email Notifier  │
│ (attention      │         │ (scheduled      │
│  heatmap)       │         │  delivery)      │
└─────────────────┘         └─────────────────┘
```

---

## Security Considerations

### Webhook Signature Validation

```python
# HMAC-SHA256 of raw request body
expected = hmac.new(
    WEBHOOK_SECRET.encode(),
    request_body,
    hashlib.sha256
).hexdigest()

# Constant-time comparison prevents timing attacks
if not hmac.compare_digest(expected, received_signature):
    raise HTTPException(401, "Invalid signature")
```

### Database Security

- SQLite file permissions: 600 (owner read/write only)
- No sensitive data in logs
- Raw payload stored for debugging (can be disabled)

---

## Deployment Architecture

### Option 1: Single Container (Recommended for MVP)

```
┌─────────────────────────────────────┐
│           Docker Container          │
│                                     │
│  ┌─────────────┐  ┌─────────────┐  │
│  │   Webhook   │  │  Analysis   │  │
│  │   Receiver  │──→│   Engine    │  │
│  │   :8000     │  │             │  │
│  └─────────────┘  └─────────────┘  │
│         │                  │        │
│  ┌──────┴──────────────────┴──────┐│
│  │         SQLite Database         ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### Option 2: Microservices (Future)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Webhook   │───→│   Message   │───→│  Analysis   │
│   Receiver  │    │   Queue     │    │   Engine    │
│   :8000     │    │  (Redis)    │    │             │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                              │
                                     ┌────────┴────────┐
                                     │   PostgreSQL    │
                                     │   + TimescaleDB │
                                     └─────────────────┘
```

---

## Configuration

### Environment Variables

```bash
# Webhook Receiver
WEBHOOK_SECRET=your-secret-key
DATABASE_PATH=data/alerts.db
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Analysis Engine
OHLCV_DB_PATH=data/ohlcv.db
MA_PERIOD=20
CONFIDENCE_THRESHOLD=0.70

# Email Notifier (future)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_TO=scoffie@example.com
```

---

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Webhook latency | <50ms | Signature validation + DB write |
| Analysis time | <500ms | Pattern detection + context rules |
| Database size | ~10MB/month | With pruning |
| Memory usage | <100MB | Per container |

---

## Future Enhancements

### Phase 2
- Volume analysis integration
- RSI/MACD momentum indicators
- Automated support/resistance detection
- Backtesting framework

### Phase 3
- ML-based pattern success prediction
- Portfolio correlation analysis
- Risk management recommendations
- Smart alert routing based on confidence

---

## Project Status

| Component | Status | Location |
|-----------|--------|----------|
| Webhook Receiver | ✅ Complete | `webhook-receiver/` |
| Analysis Engine | ✅ Complete | `analysis-engine/` |
| Behavior Tracking | ✅ Complete | `webhook-receiver/` (Layer 2) |
| Email Notifier | ✅ Complete | `email-notifier/` |
| Scheduler | ✅ Complete | `email-notifier/` (integrated) |

---

## Files Reference

### Webhook Receiver
- `webhook_receiver.py` - FastAPI app with endpoints
- `database.py` - SQLite schema and operations
- `config.py` - Environment configuration
- `Dockerfile` - Container setup
- `README.md` - Usage documentation
- `TEST_REPORT.md` - Testing documentation

### Analysis Engine
- `analysis_engine.py` - Main orchestrator
- `pattern_detector.py` - 12 candlestick patterns
- `ma_analyzer.py` - 20MA calculations
- `context_engine.py` - Context rules and confidence
- `multi_timeframe.py` - Multi-TF analysis
- `database.py` - OHLCV storage
- `models.py` - Pydantic models
- `test_patterns.py` - Unit tests
- `DESIGN.md` - Component design (this file's predecessor)

### Root Level
- `DESIGN.md` - This document (system architecture)
- `PROGRESS.md` - Project progress tracker

---

## Key Design Decisions

### 1. No Browser Extension Required

**Decision:** Use TradingView alert enrichment + manual `/log` endpoint instead of browser extension.

**Rationale:**
- 80% of behavior tracking value from alert payloads
- Zero additional code for Layer 1
- Manual logging covers edge cases
- Easier deployment and maintenance

**Trade-off:** Less granular data (no exact click tracking, no time-on-chart metrics)

### 2. SQLite Over PostgreSQL

**Decision:** Use SQLite for both webhook receiver and analysis engine.

**Rationale:**
- Zero configuration
- Single-file database
- Sufficient for current scale
- Easy backup/restore

**Trade-off:** Limited concurrent writes, no time-series optimizations

**Mitigation:** Indexes on (symbol, timeframe, timestamp), data pruning

### 3. Modular Architecture

**Decision:** Separate components into distinct modules with clear interfaces.

**Rationale:**
- Independent testing
- Easier maintenance
- Can replace components (e.g., swap SQLite for TimescaleDB)

### 4. Confidence Scoring Over Binary Signals

**Decision:** Use 0-1 confidence scale rather than buy/sell signals.

**Rationale:**
- Real trading decisions exist on spectrum
- Allows threshold tuning
- Multiple weak signals can combine into strong signal

### 5. Rule-Based Over ML

**Decision:** Hard-coded context rules instead of machine learning.

**Rationale:**
- Transparent and explainable
- No training data required
- Fast execution
- Deterministic results

**Future:** ML can be added in Phase 3 for pattern success prediction

---

## Testing Strategy

### Unit Tests
- Pattern detection with synthetic data
- MA calculation accuracy
- Context rule triggering

### Integration Tests
- End-to-end webhook → analysis flow
- Database read/write
- Email delivery (future)

### Manual Testing
- TradingView webhook configuration
- Terminal alias functionality
- Alert naming convention adherence

---

## Conclusion

The TradingView Alert Agent provides a production-ready foundation for context-intelligent trading signals. The architecture prioritizes:

1. **Simplicity:** No browser extension, minimal dependencies
2. **Transparency:** Every signal is explainable
3. **Flexibility:** Modular design allows easy updates
4. **Security:** HMAC signature validation
5. **Scalability:** Can grow from single container to microservices

The system is ready for Phase 1 deployment (webhook receiver + analysis engine) with Email Notifier and Scheduler as Phase 2 enhancements.

---

*Last Updated: 2026-04-08*
*Version: 1.0*
