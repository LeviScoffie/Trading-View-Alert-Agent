# TradingView Alert Agent — Architecture Design Document

## Overview

A context-intelligent trading alert system that transforms raw TradingView signals into actionable insights with behavioural tracking and multi-timeframe analysis.

**Core Philosophy:** Raw alerts ("BTC Bullish Engulfing") are noise. Context intelligence ("past 3 days bearish + weekly engulfing = high-confidence buy") is the signal.

**Version:** 2.0 — 5-service microservice architecture with central integration layer.

---

## System Architecture

```
                              INPUTS
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐   ┌──────────────────┐
│  TradingView    │    │   Manual Logs    │   │    Scheduler     │
│  Webhooks       │    │  (Terminal /log) │   │  (Cron reports)  │
└────────┬────────┘    └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         │                      │ direct HTTP          │ HTTP
         ▼                      ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│              INTEGRATION SERVICE  :8004                           │
│                                                                  │
│  POST /webhook          — TradingView entry point                │
│  GET  /health           — Aggregate health of all services       │
│  GET  /status/{id}      — Alert processing status               │
│  POST /trigger-analysis — Manual analysis without alert          │
│                                                                  │
│  Pipeline (orchestrator.py):                                     │
│    1. POST webhook-receiver:8000/webhook    → store alert        │
│    2. POST analysis-engine:8001/analyze     → run analysis       │
│    3. POST webhook-receiver:8000/analysis/{id} → persist result  │
│    4. POST email-notifier:8002/send-alert   → email if ≥ 0.75   │
│    5. Return unified JSON (always HTTP 200)                      │
│                                                                  │
│  Reliability:                                                    │
│    • 3-attempt exponential backoff on every downstream call      │
│    • Partial failures logged; TradingView always gets HTTP 200   │
│    • 10s timeout per call                                        │
└──────┬──────────┬──────────────────┬─────────────────────────────┘
       │          │                  │
       ▼          ▼                  ▼
┌───────────┐ ┌──────────────┐ ┌───────────────┐
│  Webhook  │ │  Analysis    │ │    Email      │
│  Receiver │ │  Engine      │ │   Notifier   │
│  :8000    │ │  :8001       │ │   :8002      │
└─────┬─────┘ └──────┬───────┘ └───────────────┘
      │               │
      └───────┬────────┘
              ▼
    ┌────────────────────┐      ┌────────────────┐
    │  SQLite (tv_data)  │      │   Scheduler    │
    │  alerts.db         │      │   :8003        │
    │  ohlcv.db          │      │  APScheduler   │
    │  scheduler.db      │      │  5 cron jobs   │
    └────────────────────┘      └────────────────┘
```

---

## Component Details

### 1. Integration Service `:8004` — NEW

**Purpose:** Central orchestrator. The only service that TradingView talks to. Coordinates all downstream services and returns a unified response.

**Location:** `integration-service/`

**Files:**

| File | Purpose |
|------|---------|
| `integration_service.py` | FastAPI app — 4 endpoints |
| `orchestrator.py` | Core pipeline logic (store → analyze → persist → email) |
| `clients.py` | Async httpx wrappers with retry + timeout |
| `models.py` | Pydantic request/response models |
| `config.py` | pydantic-settings configuration |

**Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `POST /webhook` | Receive TradingView alert, run full pipeline |
| `GET /health` | Aggregate health of all 4 downstream services |
| `GET /status/{alert_id}` | Processing status of a stored alert |
| `POST /trigger-analysis` | Manually trigger analysis without alert storage |

**Orchestration flow:**
```python
# orchestrator.py
async def process_webhook(payload):
    stored   = await clients.store_alert(payload)          # → :8000
    analysis = await clients.analyze(symbol, timeframe)    # → :8001
    _        = await clients.store_analysis(id, result)    # → :8000
    if confidence >= threshold:
        _    = await clients.send_alert_email(symbol, analysis)  # → :8002
    return unified_response   # always HTTP 200
```

**Reliability:**
- `httpx.AsyncClient` with `Timeout(10s)`
- 3-attempt exponential backoff (0.5s → 1s → 2s)
- Partial failure model: one service down never fails the whole pipeline
- Always returns HTTP 200 to TradingView (prevents retry storms)

**Environment variables:**
```bash
WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
ANALYSIS_ENGINE_URL=http://analysis-engine:8001
EMAIL_NOTIFIER_URL=http://email-notifier:8002
SCHEDULER_URL=http://scheduler:8003
CONFIDENCE_THRESHOLD=0.75
REQUEST_TIMEOUT_SECONDS=10
MAX_RETRIES=3
PORT=8004
```

---

### 2. Webhook Receiver `:8000`

**Purpose:** Durable storage for alerts, analysis results, and behaviour logs. No orchestration logic — purely a data layer.

**Location:** `webhook-receiver/`

**Key endpoints (storage only):**
- `POST /webhook` — store incoming alert, return `alert_id`
- `POST /analysis/{alert_id}` — persist analysis result from analysis-engine
- `POST /log` — manual behaviour entry
- `GET /alerts`, `/alerts/{symbol}` — alert queries
- `GET /analysis`, `/analysis/{symbol}` — analysis result queries
- `GET /logs`, `/logs/{symbol}`, `/attention` — behaviour queries
- `GET /stats`, `/health`

**Database schema (alerts.db):**

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

**Behaviour Tracking:**

TradingView alert names encode intent:
```
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

---

### 3. Analysis Engine `:8001`

**Purpose:** Run the full analysis pipeline (pattern detection, MA20, context rules, multi-timeframe) as a standalone HTTP microservice.

**Location:** `analysis-engine/`

**Deployment:** Standalone Docker container on port 8001. Shares the `tv_data` volume to read/write `ohlcv.db`. No coupling to any other service — pure input/output over HTTP.

**Endpoint:**
- `POST /analyze` — accepts `{symbol, timeframe, candle?}`, returns full analysis result

**Modules:**

| Module | Purpose |
|--------|---------|
| `api.py` | FastAPI wrapper — the HTTP entry point |
| `analysis_engine.py` | Main orchestrator |
| `pattern_detector.py` | 12 candlestick patterns |
| `ma_analyzer.py` | 20MA calculations, trend + slope |
| `context_engine.py` | 5 context rules + confidence scoring |
| `multi_timeframe.py` | 1W/1D/4H/1H confluence detection |
| `database.py` | OHLCV SQLite storage (`ohlcv.db`) |
| `models.py` | Pydantic data models |

**Pattern Detection (12 patterns):**

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

**Context Rules:**

| Rule | Condition | Output |
|------|-----------|--------|
| 1 | Past 2–3 days bearish + weekly engulfing | Buying opportunity (0.85) |
| 2 | Price > 20MA + bullish engulfing | High confidence long (0.75–0.90) |
| 3 | Price < 20MA + bearish engulfing | High confidence short (0.75–0.90) |
| 4 | Multi-timeframe alignment | Confluence signal (0.60–0.80) |
| 5 | Doji at support/resistance | Potential reversal (0.70–0.75) |

**Timeframe Weights:**

| Timeframe | Weight |
|-----------|--------|
| Weekly | 40% |
| Daily | 30% |
| 4H | 20% |
| 1H | 10% |

**Analysis Response:**
```json
{
  "symbol": "BTCUSD",
  "timestamp": "2026-04-09T12:00:00Z",
  "patterns": [
    {"type": "bullish_engulfing", "confidence": 0.85, "timeframe": "1D", "direction": "bullish"}
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
    "daily": {"trend": "bullish", "alignment": true},
    "4h": {"trend": "bearish", "alignment": false}
  }
}
```

---

### 4. Email Notifier `:8002`

**Purpose:** Send emails — either immediate high-confidence alerts triggered by the integration service, or scheduled summary reports triggered by the scheduler.

**Location:** `email-notifier/`

**Endpoints:**
- `POST /send-alert` — immediate alert email (called by integration-service)
- `POST /reports/daily` — daily summary report (called by scheduler)
- `POST /reports/weekly` — weekly summary report
- `POST /reports/monthly` — monthly summary report
- `GET /health`

**Email providers:** SMTP (Gmail), SendGrid, AWS SES  
**Retry logic:** 3 attempts with 60s delay  
**Template format:** HTML with dark theme (Jinja2) + plain-text fallback

---

### 5. Scheduler `:8003`

**Purpose:** Cron-based orchestration for scheduled reports and maintenance tasks.

**Location:** `scheduler/`

**Scheduled Jobs:**

| Job | Schedule | Action |
|-----|----------|--------|
| Daily Report | 5:00 PM EST (daily) | `POST email-notifier:8002/reports/daily` |
| Weekly Report | 5:00 PM EST (Sunday) | `POST email-notifier:8002/reports/weekly` |
| Monthly Report | 5:00 PM EST (last day) | `POST email-notifier:8002/reports/monthly` |
| Data Cleanup | 3:00 AM EST (Sunday) | Prune alerts/analysis older than 90 days |
| Health Check | Hourly | Ping all services, log status |

---

## Data Flow

```
TradingView Alert
      │
      ▼
integration-service:8004  POST /webhook
      │
      ├─① POST webhook-receiver:8000/webhook
      │       → stores in alerts table
      │       → returns alert_id
      │
      ├─② POST analysis-engine:8001/analyze
      │       → loads ohlcv.db
      │       → runs pattern_detector, ma_analyzer, context_engine, multi_timeframe
      │       → returns AnalysisResult JSON
      │
      ├─③ POST webhook-receiver:8000/analysis/{alert_id}
      │       → persists result in analysis_results table
      │       → marks alert as processed
      │
      └─④ if confidence >= CONFIDENCE_THRESHOLD:
              POST email-notifier:8002/send-alert
                  → renders HTML alert template
                  → sends via SMTP/SendGrid/SES


scheduler:8003
  [daily 5PM EST]   → POST email-notifier:8002/reports/daily
  [Sun 5PM EST]     → POST email-notifier:8002/reports/weekly
  [last day 5PM]    → POST email-notifier:8002/reports/monthly
  [Sun 3AM EST]     → db.prune_old_records() (90-day retention)
  [hourly]          → ping all service /health endpoints
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Docker Host                              │
│                                                                     │
│ ┌─────────────────┐  ┌─────────────┐  ┌───────────┐  ┌──────────┐  │
│ │ integration-    │  │  webhook-   │  │ analysis- │  │  email-  │  │
│ │ service :8004   │  │  receiver   │  │ engine    │  │ notifier │  │
│ │                 │  │  :8000      │  │ :8001     │  │ :8002    │  │
│ └────────┬────────┘  └──────┬──────┘  └─────┬─────┘  └────┬─────┘  │
│          │                  │               │              │        │
│          └──────────────────┼───────────────┘              │        │
│                             │                              │        │
│                   ┌─────────┴────────┐                    │        │
│                   │  tv_data volume  │                    │        │
│                   │  alerts.db       │◀───────────────────┘        │
│                   │  ohlcv.db        │                             │
│                   └──────────────────┘                             │
│                                                                     │
│ ┌──────────────┐                                                    │
│ │  scheduler   │  tv_data:/data  (scheduler.db)                    │
│ │  :8003       │                                                    │
│ └──────────────┘                                                    │
│                                                                     │
│  Network: tv-agent-network (bridge)                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Security

### Webhook Signature Validation
```python
expected = hmac.new(
    WEBHOOK_SECRET.encode(),
    request_body,
    hashlib.sha256
).hexdigest()

if not hmac.compare_digest(expected, received_signature):
    raise HTTPException(401, "Invalid signature")
```

### Port Exposure
- **Port 8004** — expose publicly (TradingView webhook target)
- **Ports 8000–8003** — keep internal in production (behind reverse proxy or firewall)

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Webhook latency (store only) | < 50ms |
| Full pipeline (store + analyze + email) | < 500ms typical |
| PRD target | < 2s (100 webhooks/minute) |
| Database size | ~10MB/month (auto-pruned at 90 days) |
| Memory per container | < 100MB |

---

## Design Decisions

### 1. Integration Service as Central Orchestrator
**Decision:** Dedicated service (port 8004) owns the entire pipeline. TradingView only talks to one endpoint.  
**Rationale:** Clean separation — each downstream service is a pure specialist. The integration layer adds retry, timeout, partial-failure handling, and unified response shaping in one place.  
**Trade-off:** One extra container; adds ~30–80ms of HTTP overhead vs embedded calls.

### 2. Analysis Engine as Standalone Microservice
**Decision:** `analysis-engine` runs in its own container with a FastAPI wrapper (`api.py`), not as an embedded library.  
**Rationale:** Eliminates the `sys.path` injection hack and module-name collision (`database.py` existed in both webhook-receiver and analysis-engine namespaces). Independent scaling and restarts. Clear HTTP contract.  
**Trade-off:** Slightly higher latency per analysis call (~10–30ms round trip vs in-process).

### 3. Webhook Receiver as Pure Storage
**Decision:** webhook-receiver no longer runs the analysis pipeline (removed `alert_processor.py` background task). It only stores alerts and results.  
**Rationale:** Single responsibility. The integration service is the orchestrator — having webhook-receiver also orchestrate creates a confusing dual-entry-point.

### 4. Always HTTP 200 from Integration Service
**Decision:** Integration service always returns `200 OK` to TradingView, even on partial failures.  
**Rationale:** TradingView retries non-2xx responses with exponential backoff, which can flood the pipeline. Partial failures are handled gracefully with service-level status in the response body.

### 5. SQLite Over PostgreSQL
**Decision:** SQLite for all three databases.  
**Rationale:** Zero configuration, shared Docker volume, sufficient for current scale.  
**Trade-off:** No concurrent writes from multiple processes; no time-series optimization.

### 6. Rule-Based Context Over ML
**Decision:** Hard-coded context rules for confidence scoring.  
**Rationale:** Transparent, explainable, deterministic, no training data required.  
**Future:** ML prediction model planned for Phase 3.

---

## Project Status

| Component | Status | Port | Notes |
|-----------|--------|------|-------|
| Integration Service | ✅ Complete | 8004 | New in v2.0 |
| Webhook Receiver | ✅ Complete | 8000 | Storage-only in v2.0 |
| Analysis Engine | ✅ Complete | 8001 | Promoted to microservice in v2.0 |
| Email Notifier | ✅ Complete | 8002 | Moved from 8001 in v2.0 |
| Scheduler | ✅ Complete | 8003 | Unchanged |
| Documentation | ✅ Complete | — | Updated for v2.0 |

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
- Simple web dashboard

---

*Last Updated: 2026-04-09*  
*Version: 2.0*
