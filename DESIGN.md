# TradingView Alert Agent - Architecture Design Document

## Overview

A context-intelligent trading alert system that transforms raw TradingView signals into actionable insights with behavioral tracking and multi-timeframe analysis.

**Core Philosophy:** Raw alerts ("BTC Bullish Engulfing") are noise. Context intelligence ("past 3 days bearish + weekly engulfing = high-confidence buy") is the signal.

---

## System Architecture

```
                                    INPUTS
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ TradingView     │         │ Manual Logs     │         │ Scheduled       │
│ Webhooks        │         │ (Terminal /log) │         │ Analysis        │
│                 │         │                 │         │ (Scheduler svc) │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     WEBHOOK RECEIVER :8000 (Layer 1)                         │
│                                                                              │
│  Endpoints:                                                                  │
│    POST /webhook              → Receive TradingView alerts                  │
│    POST /webhook/tradingview  → Alternative endpoint                        │
│    POST /log                  → Manual behavior logging                     │
│    GET  /logs                 → Query behavior logs                         │
│    GET  /logs/{symbol}        → Symbol-specific logs                        │
│    GET  /alerts               → Recent alerts                               │
│    GET  /alerts/{symbol}      → Symbol-specific alerts                      │
│    GET  /attention            → Attention heatmap                           │
│    GET  /analysis             → Recent analysis results                     │
│    GET  /analysis/{symbol}    → Symbol analysis results                     │
│    GET  /stats                → Database statistics                         │
│    GET  /health               → Health check                                │
│                                                                              │
│  Security: HMAC-SHA256 signature validation (optional for local testing)    │
│  Storage: SQLite alerts.db (alerts + behavior_logs + analysis_results)      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ background task (alert_processor.py)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  ANALYSIS ENGINE (Layer 2 — embedded library)                │
│                                                                              │
│  NOT a standalone container. Runs inside webhook-receiver via:              │
│    analysis_bridge.py  →  AnalysisEngine class                              │
│    alert_processor.py  →  orchestrates background analysis pipeline         │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Pattern   │  │    MA20     │  │   Context   │  │    Multi    │        │
│  │  Detector   │  │  Analyzer   │  │   Engine    │  │ Timeframe   │        │
│  │ 12 patterns │  │ trend/slope │  │  5 rules    │  │ 1W/1D/4H/1H │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         └────────────────┴────────────────┴────────────────┘               │
│                                   │                                         │
│                                   ▼                                         │
│  Context Rules:                                                              │
│    Rule 1: Bearish pullback + weekly engulfing = buy opportunity            │
│    Rule 2: Price > 20MA + bullish engulfing = high confidence               │
│    Rule 3: Price < 20MA + bearish engulfing = high confidence               │
│    Rule 4: Multi-timeframe alignment = higher confidence                    │
│    Rule 5: Doji at support/resistance = potential reversal                  │
│                                                                              │
│  Output → stored in analysis_results table; if confidence ≥ threshold →    │
│           immediate email triggered via alert_processor._trigger_alert_email│
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                         ┌─────────┴──────────┐
                         │   Shared SQLite    │
                         │  Volume (tv_data)  │
                         │  alerts.db         │
                         │  ohlcv.db          │
                         └─────────┬──────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
              ▼                                         ▼
┌─────────────────────────────┐           ┌─────────────────────────────────┐
│   SCHEDULER :8003            │           │   EMAIL NOTIFIER :8001          │
│                              │           │                                 │
│  APScheduler cron jobs:      │  HTTP     │  FastAPI endpoints:             │
│  Daily  → 5:00 PM EST        │  POST ───▶│  POST /reports/daily            │
│  Weekly → Sun 5:00 PM EST    │           │  POST /reports/weekly           │
│  Monthly→ Last day 5PM EST   │           │  POST /reports/monthly          │
│  Cleanup→ Sun 3:00 AM EST    │           │                                 │
│  Health → hourly             │           │  Reads: alerts.db + ohlcv.db    │
│                              │           │  Sends: SMTP/SendGrid/AWS SES   │
│  Job management API:         │           │  HTML templates via Jinja2      │
│  GET /jobs                   │           │  Retry logic (3x, 60s delay)    │
│  POST /jobs/{id}/trigger     │           └─────────────────────────────────┘
│  POST /jobs/{id}/pause       │
│  GET /dashboard              │
└──────────────────────────────┘
```

---

## Component Details

### 1. Webhook Receiver

**Purpose:** Entry point for all data. Receives TradingView alerts, runs background analysis, stores results.

**Location:** `webhook-receiver/`

**Key Features:**
- HMAC-SHA256 signature validation for security
- Dual input: automated alerts + manual `/log` endpoint
- SQLite persistence with indexing
- Background analysis via `alert_processor.py` → `analysis_bridge.py`
- Immediate email trigger when confidence ≥ `CONFIDENCE_THRESHOLD`

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
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price REAL,
    message TEXT,
    alert_time TEXT,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    raw_payload TEXT,
    processed BOOLEAN DEFAULT 0
);

CREATE TABLE behavior_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    note TEXT,
    source TEXT DEFAULT 'manual'
);

CREATE TABLE analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER,
    symbol TEXT,
    timeframe TEXT,
    confidence REAL,
    recommendation TEXT,
    patterns_json TEXT,
    ma20_json TEXT,
    context_json TEXT,
    full_result_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 2. Analysis Engine

**Purpose:** Transform raw alerts into context-intelligent signals.

**Location:** `analysis-engine/`

**Deployment:** NOT a standalone Docker container. Imported as a Python library inside the webhook-receiver container via `analysis_bridge.py`. The `alert_processor.py` background task calls `analysis_bridge.run_analysis()` after each alert is stored.

**Modules:**

| Module | Purpose |
|--------|---------|
| `pattern_detector.py` | Detect 12 candlestick patterns |
| `ma_analyzer.py` | 20MA calculations and trend analysis |
| `context_engine.py` | Apply context rules with confidence scoring |
| `multi_timeframe.py` | Multi-TF confluence detection (1W/1D/4H/1H) |
| `analysis_engine.py` | Main orchestrator |
| `database.py` | OHLCV SQLite storage |
| `models.py` | Pydantic data models |

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
    "distance_pct": 2.27,
    "trend": "bullish",   # above/below MA
    "slope": "rising"     # rising/falling/flat
}
```

**Context Rules:**

| Rule | Condition | Confidence | Output |
|------|-----------|------------|--------|
| 1 | Past 2-3 days bearish + weekly engulfing | 0.85 | "Buying opportunity - bullish context" |
| 2 | Price > 20MA + bullish engulfing | 0.75–0.90 | "High confidence long" |
| 3 | Price < 20MA + bearish engulfing | 0.75–0.90 | "High confidence short" |
| 4 | Multi-timeframe alignment | 0.60–0.80 | "Confluence signal" |
| 5 | Doji at support/resistance | 0.70–0.75 | "Potential reversal" |

**Timeframe Weights:**

| Timeframe | Weight | Rationale |
|-----------|--------|-----------|
| Weekly | 40% | Primary trend direction |
| Daily | 30% | Secondary confirmation |
| 4H | 20% | Entry timing |
| 1H | 10% | Fine-tuning |

**Analysis Output Format:**

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

### 3. Email Notifier

**Purpose:** Deliver scheduled analysis reports via email with real-time market analysis.

**Location:** `email-notifier/`

**Deployment:** Standalone Docker service on port 8001. Exposes FastAPI endpoints that the Scheduler triggers via HTTP POST. Does NOT self-schedule — all timing is controlled by the Scheduler service.

**Endpoints:**
- `POST /reports/daily` — Generate and send daily report
- `POST /reports/weekly` — Generate and send weekly report
- `POST /reports/monthly` — Generate and send monthly report
- `GET /health` — Health check

**Email Format:**
- HTML with dark-themed styling (Jinja2 templates)
- Summary metrics (total alerts, symbols, bullish/bearish signals)
- Pattern badges with confidence scores (color-coded green/yellow/red)
- MA20 status with visual indicator
- Context reasoning section
- Multi-timeframe alignment grid (1W/1D/4H/1H)
- Actionable recommendations (5 levels: strong_long → strong_short)
- Recent alerts list + plain text fallback

**Email Providers:** SMTP (Gmail), SendGrid, AWS SES  
**Retry Logic:** 3 retries with 60s delay  
**Timezone:** America/New_York

---

### 4. Scheduler

**Purpose:** Central orchestrator for all timed operations. Triggers email reports, runs data maintenance, and monitors service health.

**Location:** `scheduler/`

**Deployment:** Standalone Docker service on port 8003. Uses APScheduler with SQLite persistence for job state. Depends on webhook-receiver and email-notifier being up.

**Scheduled Jobs:**

| Job | Schedule | Action |
|-----|----------|--------|
| Daily Report | 5:00 PM EST (daily) | `POST http://email-notifier:8001/reports/daily` |
| Weekly Report | 5:00 PM EST (Sunday) | `POST http://email-notifier:8001/reports/weekly` |
| Monthly Report | 5:00 PM EST (last day) | `POST http://email-notifier:8001/reports/monthly` |
| Data Cleanup | 3:00 AM EST (Sunday) | Prune alerts/analysis older than 90 days |
| Health Check | Hourly | Ping all services; log status |

**Management API:**
- `GET /jobs` — List all jobs with next run times
- `POST /jobs/{id}/trigger` — Manually fire a job
- `POST /jobs/{id}/pause` / `/resume` — Pause/resume scheduling
- `GET /dashboard` — Overview of all jobs and service health
- `GET /alerts` — Active scheduler alerts

---

## Data Flow

```
TradingView Alert
      │
      ▼
webhook-receiver:8000
  POST /webhook → validates HMAC → stores in alerts table
      │
      ▼ (background: alert_processor.py)
  alert_processor.process_alert()
      ├─ analysis_bridge.run_analysis()
      │   └─ AnalysisEngine(pattern_detector, ma_analyzer,
      │                      context_engine, multi_timeframe)
      │   └─ stores OHLCV → ohlcv.db
      ├─ db.store_analysis_result() → analysis_results table
      └─ if confidence >= CONFIDENCE_THRESHOLD:
             _trigger_alert_email() → SMTP send


scheduler:8003
  [cron: 5PM EST daily] ──── POST /reports/daily ──▶ email-notifier:8001
  [cron: Sun 5PM EST]  ──── POST /reports/weekly ──▶ email-notifier:8001
  [cron: last day 5PM] ──── POST /reports/monthly ─▶ email-notifier:8001
  [cron: Sun 3AM EST]  ──── db.prune_old_records() (90-day retention)


email-notifier:8001
  receives HTTP POST → report_generator.generate_report()
      ├─ queries alerts.db (recent alerts by symbol)
      ├─ queries analysis_results (patterns + confidence)
      ├─ generates HTML via templates.py (Jinja2)
      └─ sends via SMTP / SendGrid / AWS SES
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

```
┌──────────────────────────────────────────────────────────────────┐
│                         Docker Host                              │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ webhook-receiver │  │  email-notifier  │  │   scheduler   │  │
│  │    :8000         │  │     :8001        │  │    :8003      │  │
│  │                  │  │                  │  │               │  │
│  │  + analysis-     │  │  (triggered by   │  │  (triggers    │  │
│  │    engine lib    │  │   scheduler)     │  │   notifier)   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                    │          │
│           └─────────────────────┴────────────────────┘          │
│                                 │                               │
│                      ┌──────────┴──────────┐                   │
│                      │  tv_data volume     │                   │
│                      │  alerts.db          │                   │
│                      │  ohlcv.db           │                   │
│                      │  scheduler.db       │                   │
│                      └─────────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

**Network:** All services on `tv-agent-network` (bridge). Services communicate by container name (e.g. `http://email-notifier:8001`).

---

## Configuration

### Environment Variables

```bash
# Webhook Receiver
WEBHOOK_SECRET=your-secret-key       # optional HMAC validation
DATABASE_PATH=/app/data/alerts.db
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
CONFIDENCE_THRESHOLD=0.75            # trigger immediate email above this

# Analysis Engine (via webhook-receiver env)
EMAIL_NOTIFIER_OHLCV_DB_PATH=/app/data/ohlcv.db

# Email Notifier
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_TO=recipient@example.com
EMAIL_NOTIFIER_DB_PATH=/app/data/alerts.db
EMAIL_NOTIFIER_OHLCV_DB_PATH=/app/data/ohlcv.db

# Scheduler
SCHEDULER_DB_PATH=/data/scheduler.db
ALERTS_DB_PATH=/data/alerts.db
WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
EMAIL_NOTIFIER_URL=http://email-notifier:8001

# Shared
DAILY_REPORT_HOUR=17
WEEKLY_REPORT_HOUR=17
MONTHLY_REPORT_HOUR=17
SCHEDULE_TIMEZONE=America/New_York
```

---

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Webhook latency | <50ms | Signature validation + DB write |
| Analysis time | <500ms | Pattern detection + context rules |
| Database size | ~10MB/month | Auto-pruned at 90 days |
| Memory usage | <100MB per container | |

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
- Telegram/Discord notification channels

---

## Project Status

| Component | Status | Location |
|-----------|--------|----------|
| Webhook Receiver | ✅ Complete | `webhook-receiver/` |
| Analysis Engine | ✅ Complete (embedded library) | `analysis-engine/` |
| Alert Processor | ✅ Complete | `webhook-receiver/alert_processor.py` |
| Email Notifier | ✅ Complete | `email-notifier/` |
| Scheduler | ✅ Complete (standalone service :8003) | `scheduler/` |
| Documentation | ✅ Complete | Root-level `.md` files |

---

## Files Reference

### Webhook Receiver
- `webhook_receiver.py` — FastAPI app with 10+ endpoints
- `alert_processor.py` — Background analysis pipeline
- `analysis_bridge.py` — Embeds analysis-engine as library
- `database.py` — SQLite schema and operations
- `config.py` — Environment configuration
- `Dockerfile` — Container setup

### Analysis Engine (library)
- `analysis_engine.py` — Main orchestrator
- `pattern_detector.py` — 12 candlestick patterns
- `ma_analyzer.py` — 20MA calculations
- `context_engine.py` — Context rules and confidence
- `multi_timeframe.py` — Multi-TF analysis (1W/1D/4H/1H)
- `database.py` — OHLCV storage
- `models.py` — Pydantic models
- `test_patterns.py` — Unit tests

### Email Notifier
- `email_notifier.py` — FastAPI app + report endpoints
- `report_generator.py` — Database queries + analysis
- `templates.py` — Jinja2 HTML email templates
- `config.py` — SMTP/SendGrid/SES configuration
- `test_email_notifier.py` — Unit tests

### Scheduler
- `scheduler.py` — APScheduler setup
- `api.py` — FastAPI endpoints for job management
- `jobs.py` — Job function implementations
- `job_store.py` — SQLite job persistence
- `monitor.py` — Health checks
- `config.py` — Schedule configuration
- `timezone_utils.py` — EST/EDT DST handling

---

## Key Design Decisions

### 1. No Browser Extension Required
**Decision:** Use TradingView alert enrichment + manual `/log` endpoint.  
**Rationale:** 80% of behavior tracking value from alert payloads. Zero additional code for Layer 1.  
**Trade-off:** No exact click tracking or time-on-chart metrics.

### 2. Analysis Engine as Embedded Library (Not Standalone Service)
**Decision:** analysis-engine runs inside webhook-receiver process via `analysis_bridge.py`.  
**Rationale:** Eliminates HTTP overhead on the critical alert processing path; shared memory for OHLCV data; simpler deployment.  
**Trade-off:** webhook-receiver image is larger; can't scale analysis independently.

### 3. Scheduler as Separate Service
**Decision:** Dedicated scheduler container (port 8003) instead of embedding APScheduler inside email-notifier.  
**Rationale:** Clean separation of concerns; scheduler can monitor all services, not just email; job state persists in its own DB; manageable via API without restarting email-notifier.  
**Trade-off:** One extra container.

### 4. SQLite Over PostgreSQL
**Decision:** SQLite for all three databases.  
**Rationale:** Zero configuration, single-file, sufficient for current scale, easy backup.  
**Trade-off:** Limited concurrent writes, no time-series optimizations.

### 5. Confidence Scoring Over Binary Signals
**Decision:** 0–1 confidence scale rather than buy/sell signals.  
**Rationale:** Real trading decisions exist on a spectrum. Allows threshold tuning.

### 6. Rule-Based Over ML
**Decision:** Hard-coded context rules.  
**Rationale:** Transparent, explainable, no training data, deterministic.  
**Future:** ML can be added in Phase 3 for pattern success prediction.

---

## Testing Strategy

### Unit Tests
- `analysis-engine/test_patterns.py` — Pattern detection with synthetic data
- `email-notifier/test_email_notifier.py` — Report generation tests

### Integration Tests (Pending)
- End-to-end webhook → analysis → email flow
- Scheduler → email-notifier HTTP trigger

### Manual Testing
- TradingView webhook configuration
- Terminal alias functionality
- Alert naming convention adherence

---

*Last Updated: 2026-04-08*  
*Version: 1.1*
