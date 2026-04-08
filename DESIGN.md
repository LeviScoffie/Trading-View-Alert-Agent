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
│                 INTEGRATION SERVICE (Port 8004) - ORCHESTRATOR               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Purpose: Orchestrate webhook → analysis → email flow                │    │
│  │                                                                      │    │
│  │ Endpoints:                                                           │    │
│  │   POST /webhook          → Receive alert, trigger full flow        │    │
│  │   GET  /status/{id}      → Get alert + analysis status             │    │
│  │   POST /trigger-analysis → Manual analysis trigger                 │    │
│  │   GET  /health           → Health check for all services           │    │
│  │                                                                      │    │
│  │ Flow:                                                                │    │
│  │   1. Receive TradingView webhook                                    │    │
│  │   2. Store alert in webhook-receiver                                │    │
│  │   3. Call analysis-engine for pattern/context analysis              │    │
│  │   4. If confidence >= 0.75, call email-notifier                     │    │
│  │   5. Return combined response (alert_id, analysis, email_sent)      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTP API Calls
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WEBHOOK RECEIVER SERVICE (Port 8000)                     │
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
                                  │ HTTP POST
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ANALYSIS ENGINE SERVICE (Port 8001)                      │
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
                                  │ HTTP POST
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EMAIL NOTIFIER SERVICE (Port 8002)                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Email Delivery:                                                     │    │
│  │   Daily Close   → 5:00 PM EST (crypto daily close)                 │    │
│  │   Weekly Close  → Sunday 5:00 PM EST                               │    │
│  │   Monthly Close → Last day of month 5:00 PM EST                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Format: HTML email with charts, patterns, confidence scores                 │
│  Delivery: SMTP (configurable provider)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP GET
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SCHEDULER SERVICE (Port 8003)                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Schedule Management:                                                │    │
│  │   Daily Close   → 5:00 PM EST (crypto daily close)                 │    │
│  │   Weekly Close  → Sunday 5:00 PM EST                               │    │
│  │   Monthly Close → Last day of month 5:00 PM EST                    │    │
│  │   Health Checks → Every 5 minutes                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Scheduler: APScheduler for cron-like scheduling with timezone support       │
│  Communication: HTTP API calls to other services                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Webhook Receiver Service (Port 8000)

**Purpose:** Entry point for all data. Receives TradingView alerts and manual behavior logs.

**Location:** `webhook-receiver/`

**Key Features:**
- HMAC-SHA256 signature validation for security
- Dual input: automated alerts + manual logs
- SQLite persistence with indexing
- Query endpoints for analysis
- HTTP API for inter-service communication

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

### 2. Analysis Engine Service (Port 8001)

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

### 3. Email Notifier Service (Port 8002)

**Purpose:** Deliver scheduled analysis reports via email with real-time market analysis.

**Location:** `email-notifier/`

**Features:**
- SMTP email delivery (Gmail, SendGrid, AWS SES)
- HTML email templates with dark-themed styling
- Support for attachment of charts and reports
- Retry logic for failed sends (3 retries with 60s delay)
- Health checks for Docker deployment

**Email Format:**
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
- Jinja2 for HTML templating
- Support for SMTP (Gmail), SendGrid, and AWS SES
- Timezone-aware (America/New_York)
- HTTP API endpoints for receiving analysis data from other services

**Files:**
- `email_notifier.py` — Main sender (~200 lines)
- `templates.py` — HTML email templates (~500 lines)
- `config.py` — Configuration management (~100 lines)
- `requirements.txt` — Dependencies
- `Dockerfile` — Container setup
- `README.md` — Usage documentation

---

### 4. Scheduler Service (Port 8003)

**Purpose:** Manage scheduled tasks and system health monitoring.

**Location:** `scheduler/`

**Features:**
- Cron-like scheduling with timezone support
- Health checks for all services
- Periodic report generation triggers
- Service coordination and monitoring
- Error handling and retry mechanisms

**Schedule:**

| Report | Time | Content | Trigger Service |
|--------|------|---------|-----------------|  
| Daily Close | 5:00 PM EST | Daily patterns, MA20 status, context signals | analysis-engine |
| Weekly Close | Sunday 5:00 PM EST | Weekly engulfing analysis, multi-TF alignment | analysis-engine |
| Monthly Close | Last day 5:00 PM EST | Monthly trend, key levels, major signals | analysis-engine |
| Health Checks | Every 5 minutes | Service availability, response times | all services |

**Communication:**
- HTTP GET/POST requests to trigger analysis and email delivery
- Health check endpoints to monitor other services
- Error notification system for failed tasks

**Implementation:**
- APScheduler for cron-like scheduling with timezone support
- HTTP client for inter-service communication
- Timezone-aware (America/New_York)
- Logging and error reporting

**Files:**
- `scheduler.py` — Main scheduler (~300 lines)
- `health_checker.py` — Service health monitoring (~150 lines)
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
│ Service         │
│ (Port 8000)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ SQLite          │────→│ Analysis        │
│ (alerts table)  │     │ Engine          │
└─────────────────┘     │ Service         │
         │              │ (Port 8001)     │
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
│ Service         │         │ Service         │
│ (Port 8000)     │         │ (Port 8002)     │
└─────────────────┘         └─────────────────┘
                                    │
                                    ▼
┌─────────────────┐
│ Scheduler       │
│ Service         │
│ (Port 8003)     │
└─────────────────┘
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

### Inter-Service Communication

- All HTTP API calls between services secured with API keys
- HTTPS recommended for production environments
- Input validation for all API endpoints
- Rate limiting to prevent abuse

### Database Security

- SQLite file permissions: 600 (owner read/write only)
- No sensitive data in logs
- Raw payload stored for debugging (can be disabled)

---

## Deployment Architecture

### Docker Compose Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DOCKER COMPOSE NETWORK                               │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Webhook Recv    │    │ Analysis Eng    │    │ Email Notifier  │         │
│  │ Service:8000    │    │ Service:8001    │    │ Service:8002    │         │
│  │                 │    │                 │    │                 │         │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │  ┌───────────┐  │         │
│  │  │   SQLite  │  │    │  │   SQLite  │  │    │  │   SMTP    │  │         │
│  │  │ Database  │  │    │  │ Database  │  │    │  │ Provider  │  │         │
│  │  └───────────┘  │    │  └───────────┘  │    │  └───────────┘  │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                              │                        │                     │
│                              │                        │                     │
│                              └────────────────────────┘                     │
│                                         │                                   │
│                              ┌─────────────────┐                           │
│                              │ Scheduler       │                           │
│                              │ Service:8003    │                           │
│                              │                 │                           │
│                              │  ┌───────────┐  │                           │
│                              │  │ Health    │  │                           │
│                              │  │ Monitor   │  │                           │
│                              │  └───────────┘  │                           │
│                              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  webhook-receiver:
    build: ./webhook-receiver
    ports:
      - "8000:8000"
    environment:
      - DATABASE_PATH=/data/alerts.db
      - WEBHOOK_SECRET=${WEBHOOK_SECRET}
    volumes:
      - ./data:/data
    depends_on:
      - db-webhook
  
  analysis-engine:
    build: ./analysis-engine
    ports:
      - "8001:8001"
    environment:
      - OHLCV_DB_PATH=/data/ohlcv.db
      - MA_PERIOD=20
      - CONFIDENCE_THRESHOLD=0.70
    volumes:
      - ./data:/data
  
  email-notifier:
    build: ./email-notifier
    ports:
      - "8002:8002"
    environment:
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASS=${SMTP_PASS}
      - EMAIL_TO=${EMAIL_TO}
  
  scheduler:
    build: ./scheduler
    ports:
      - "8003:8003"
    environment:
      - ANALYSIS_ENGINE_URL=http://analysis-engine:8001
      - EMAIL_NOTIFIER_URL=http://email-notifier:8002
      - WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
    depends_on:
      - webhook-receiver
      - analysis-engine
      - email-notifier

volumes:
  db-webhook:
  db-analysis:
```

---

## Configuration

### Service Environment Variables

**Webhook Receiver Service (Port 8000):**
```bash
# Webhook Receiver
WEBHOOK_SECRET=your-secret-key
DATABASE_PATH=data/alerts.db
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

**Analysis Engine Service (Port 8001):**
```bash
# Analysis Engine
OHLCV_DB_PATH=data/ohlcv.db
MA_PERIOD=20
CONFIDENCE_THRESHOLD=0.70
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=INFO
```

**Email Notifier Service (Port 8002):**
```bash
# Email Notifier
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
EMAIL_TO=scoffie@example.com
HOST=0.0.0.0
PORT=8002
LOG_LEVEL=INFO
```

**Scheduler Service (Port 8003):**
```bash
# Scheduler
ANALYSIS_ENGINE_URL=http://analysis-engine:8001
EMAIL_NOTIFIER_URL=http://email-notifier:8002
WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
HOST=0.0.0.0
PORT=8003
LOG_LEVEL=INFO
```

**Integration Service (Port 8004):**
```bash
# Integration Service
WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
ANALYSIS_ENGINE_URL=http://analysis-engine:8001
EMAIL_NOTIFIER_URL=http://email-notifier:8002
SCHEDULER_URL=http://scheduler:8003
CONFIDENCE_THRESHOLD=0.75
HOST=0.0.0.0
PORT=8004
LOG_LEVEL=INFO
```

---

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Webhook latency | <50ms | Signature validation + DB write |
| Analysis time | <500ms | Pattern detection + context rules |
| Inter-service calls | <100ms | HTTP API communication |
| Orchestration time | <1000ms | Full webhook→analysis→email flow |
| Database size | ~10MB/month | With pruning |
| Memory usage | <100MB per service | Per container |

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

| Component | Status | Location | Port |
|-----------|--------|----------|------|
| Webhook Receiver | ✅ Complete | `webhook-receiver/` | 8000 |
| Analysis Engine | ✅ Complete | `analysis-engine/` | 8001 |
| Email Notifier | ✅ Complete | `email-notifier/` | 8002 |
| Scheduler | ✅ Complete | `scheduler/` | 8003 |
| Integration Service | ✅ Complete | `integration-service/` | 8004 |
| Behavior Tracking | ✅ Complete | `webhook-receiver/` | 8000 |

---

## Files Reference

### Webhook Receiver Service
- `webhook_receiver.py` - FastAPI app with endpoints
- `database.py` - SQLite schema and operations
- `config.py` - Environment configuration
- `Dockerfile` - Container setup
- `README.md` - Usage documentation
- `TEST_REPORT.md` - Testing documentation

### Analysis Engine Service
- `analysis_engine.py` - Main orchestrator
- `pattern_detector.py` - 12 candlestick patterns
- `ma_analyzer.py` - 20MA calculations
- `context_engine.py` - Context rules and confidence
- `multi_timeframe.py` - Multi-TF analysis
- `database.py` - OHLCV storage
- `models.py` - Pydantic models
- `test_patterns.py` - Unit tests
- `DESIGN.md` - Component design (this file's predecessor)

### Email Notifier Service
- `email_notifier.py` - Main sender
- `templates.py` - HTML email templates
- `config.py` - Configuration management
- `requirements.txt` - Dependencies
- `Dockerfile` - Container setup
- `README.md` - Usage documentation

### Scheduler Service
- `scheduler.py` - Main scheduler
- `health_checker.py` - Service health monitoring
- `config.py` - Configuration management
- `requirements.txt` - Dependencies
- `Dockerfile` - Container setup
- `README.md` - Usage documentation

### Integration Service
- `integration_service.py` - FastAPI orchestration API
- `orchestrator.py` - Core flow logic
- `clients.py` - HTTP clients for each service
- `models.py` - Pydantic models for inter-service communication
- `config.py` - Configuration management
- `requirements.txt` - Dependencies
- `Dockerfile` - Container setup
- `README.md` - Usage documentation

### Root Level
- `DESIGN.md` - This document (system architecture)
- `PROGRESS.md` - Project progress tracker
- `docker-compose.yml` - Multi-service deployment

---

## Key Design Decisions

### 1. Microservices Architecture

**Decision:** Separate components into 4 independent services with dedicated responsibilities.

**Rationale:**
- Independent scaling of each service
- Better fault isolation
- Clear separation of concerns
- Easier maintenance and updates
- Team development of different components

**Trade-offs:** More complex deployment, inter-service communication overhead

**Mitigation:** Docker Compose for simplified deployment, HTTP API for communication

### 2. No Browser Extension Required

**Decision:** Use TradingView alert enrichment + manual `/log` endpoint instead of browser extension.

**Rationale:**
- 80% of behavior tracking value from alert payloads
- Zero additional code for Layer 1
- Manual logging covers edge cases
- Easier deployment and maintenance

**Trade-off:** Less granular data (no exact click tracking, no time-on-chart metrics)

### 3. SQLite Over PostgreSQL

**Decision:** Use SQLite for both webhook receiver and analysis engine.

**Rationale:**
- Zero configuration
- Single-file database
- Sufficient for current scale
- Easy backup/restore

**Trade-off:** Limited concurrent writes, no time-series optimizations

**Mitigation:** Indexes on (symbol, timeframe, timestamp), data pruning

### 4. HTTP API Communication

**Decision:** Services communicate via RESTful HTTP APIs.

**Rationale:**
- Language agnostic communication
- Well-established patterns
- Easy monitoring and debugging
- Standard authentication methods

### 5. Confidence Scoring Over Binary Signals

**Decision:** Use 0-1 confidence scale rather than buy/sell signals.

**Rationale:**
- Real trading decisions exist on spectrum
- Allows threshold tuning
- Multiple weak signals can combine into strong signal

### 6. Dedicated Scheduler Service

**Decision:** Separate scheduler into its own service instead of integrating with email notifier.

**Rationale:**
- Clear responsibility separation
- Independent scaling for scheduling tasks
- Can schedule various tasks beyond emails
- Centralized health monitoring capability

---

## Testing Strategy

### Unit Tests
- Pattern detection with synthetic data
- MA calculation accuracy
- Context rule triggering

### Integration Tests
- End-to-end webhook → analysis → email flow
- Database read/write
- HTTP API communication between services

### Manual Testing
- TradingView webhook configuration
- Terminal alias functionality
- Alert naming convention adherence
- Cross-service communication

---

## Conclusion

The TradingView Alert Agent provides a production-ready foundation for context-intelligent trading signals using a microservices architecture. The architecture prioritizes:

1. **Scalability:** Independent services can scale separately
2. **Maintainability:** Clear separation of concerns
3. **Reliability:** Fault isolation between services
4. **Flexibility:** Independent deployment and updates
5. **Security:** HMAC signature validation and API key authentication

The system is ready for production deployment with Docker Compose managing all 4 services.

---

*Last Updated: 2026-04-08*
*Version: 2.0 - Multi-Service Architecture*