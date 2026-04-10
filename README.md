# TradingView Alert Agent

Intelligent trading analysis system that receives TradingView webhook alerts, runs multi-layer pattern analysis, and delivers context-aware insights via email. Built as a 5-service Docker architecture with a central integration layer.

## Features

- **Pattern Detection:** 12 candlestick patterns with confidence scoring (engulfing, doji, hammer, morning/evening star, three soldiers/crows)
- **Context-Aware Analysis:** "Past 2–3 days bearish + weekly engulfing = buying opportunity"
- **Immediate Alerts:** Email triggered when confidence ≥ threshold (default 0.75)
- **Scheduled Reports:** Daily (5 PM EST), Weekly (Sunday 5 PM EST), Monthly (last day 5 PM EST)
- **Behavior Tracking:** Manual `/log` endpoint + enriched alert payloads
- **20+ Assets:** SPX500, BTCUSD, ETHUSD, NVDA, DeFi tokens, and more
- **Docker Ready:** One-command deployment with 5 coordinated microservices

## Quick Start

```bash
git clone https://github.com/LeviScoffie/Trading-View-Alert-Agent.git
cd tradingview-alert-agent

# Configure
cp .env.example .env
nano .env  # Add SMTP credentials

# Deploy
docker-compose up -d

# Verify all services
curl http://localhost:8004/health   # integration-service (full health check)
```

The integration-service health endpoint reports the status of all downstream services in one call.

See [SETUP.md](SETUP.md) for detailed instructions.

## Architecture

TradingView points webhooks at the **Integration Service** (port 8004). It orchestrates the full pipeline synchronously and returns a unified response.

```
┌──────────────────┐
│   TradingView    │
│   (Webhooks)     │
└────────┬─────────┘
         │  POST /webhook
         ▼
┌─────────────────────────────────────────────────────────────┐
│              INTEGRATION SERVICE  :8004                      │
│          (Primary entry point — orchestrates all)            │
│                                                             │
│  1. Store alert   → webhook-receiver:8000/webhook           │
│  2. Run analysis  → analysis-engine:8001/analyze            │
│  3. Persist result→ webhook-receiver:8000/analysis/{id}     │
│  4. Email?        → email-notifier:8002/send-alert          │
│                     (only if confidence ≥ 0.75)             │
│  5. Return unified JSON response (always HTTP 200)          │
└──────────┬──────────────┬──────────────────┬────────────────┘
           │              │                  │
           ▼              ▼                  ▼
  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
  │  Webhook    │  │  Analysis   │  │    Email     │
  │  Receiver   │  │  Engine     │  │   Notifier   │
  │  :8000      │  │  :8001      │  │   :8002      │
  │             │  │             │  │              │
  │ • Store     │  │ • 12 pattern│  │ • Immediate  │
  │   alerts    │  │   detection │  │   alerts     │
  │ • Store     │  │ • MA20      │  │ • Scheduled  │
  │   analysis  │  │ • Context   │  │   reports    │
  │ • Behavior  │  │   rules     │  │ • SMTP/SG/   │
  │   logs      │  │ • Multi-TF  │  │   AWS SES    │
  └──────┬──────┘  └──────┬──────┘  └──────────────┘
         │                │
         ▼                ▼
  ┌──────────────────────────────┐    ┌────────────┐
  │     SQLite (shared volume)   │    │  Scheduler │
  │   alerts.db  │  ohlcv.db     │    │   :8003    │
  └──────────────────────────────┘    │ Cron jobs  │
                                      │ for reports│
                                      └────────────┘
```

## Service Ports

| Port | Service | Role |
|------|---------|------|
| `8000` | webhook-receiver | Alert & analysis result storage, behavior logs |
| `8001` | analysis-engine | Pattern detection, MA20, context, multi-timeframe |
| `8002` | email-notifier | Immediate alerts + scheduled reports |
| `8003` | scheduler | Cron-based report scheduling + maintenance |
| **`8004`** | **integration-service** | **Primary TradingView webhook entry point** |

## TradingView Webhook URL

Point your TradingView alerts to:
```
http://your-server-ip:8004/webhook
```

**Message template:**
```json
{
  "symbol":   "{{ticker}}",
  "open":     {{open}},
  "high":     {{high}},
  "low":      {{low}},
  "close":    {{close}},
  "volume":   {{volume}},
  "time":     "{{time}}",
  "interval": "{{interval}}",
  "message":  "{{strategy.order.action}}"
}
```

## API Endpoints

### Integration Service (port 8004) — Primary Entry Point

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Receive TradingView alert, run full pipeline |
| `/health` | GET | Health check for all downstream services |
| `/status/{alert_id}` | GET | Get processing status of a stored alert |
| `/trigger-analysis` | POST | Manually trigger analysis without a webhook |

### Webhook Receiver (port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhook` | POST | Store alert (called by integration-service) |
| `/analysis/{alert_id}` | POST | Store analysis result (called by integration-service) |
| `/webhook/tradingview` | POST | Alternative webhook endpoint |
| `/log` | POST | Manual behavior logging |
| `/logs` | GET | Recent behavior logs |
| `/logs/{symbol}` | GET | Symbol behavior logs |
| `/alerts` | GET | Recent alerts |
| `/alerts/{symbol}` | GET | Symbol-specific alerts |
| `/attention` | GET | Attention heatmap |
| `/analysis` | GET | Recent analysis results |
| `/analysis/{symbol}` | GET | Symbol analysis results |
| `/stats` | GET | Database statistics |

### Analysis Engine (port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/analyze` | POST | Run full analysis pipeline for a symbol |

### Email Notifier (port 8002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/send-alert` | POST | Send immediate alert email (called by integration-service) |
| `/reports/daily` | POST | Trigger daily report |
| `/reports/weekly` | POST | Trigger weekly report |
| `/reports/monthly` | POST | Trigger monthly report |

### Scheduler (port 8003)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/dashboard` | GET | System dashboard |
| `/jobs` | GET | List all scheduled jobs |
| `/jobs/{id}/trigger` | POST | Manually trigger a job |
| `/jobs/{id}/pause` | POST | Pause a job |
| `/jobs/{id}/resume` | POST | Resume a job |

## Webhook Response

The integration service always returns HTTP 200 (prevents TradingView retry spam):

```json
{
  "status": "processed",
  "alert_id": 42,
  "symbol": "BTCUSD",
  "confidence": 0.85,
  "email_sent": true,
  "processing_time_ms": 312,
  "timestamp": "2026-04-09T12:00:00Z",
  "services": {
    "webhook": "success",
    "analysis": "success",
    "email": "success"
  }
}
```

## Context-Aware Insights

| Condition | Insight | Confidence |
|-----------|---------|------------|
| Past 2–3 days bearish + weekly bullish engulfing | Buying Opportunity | 85% |
| Price above 20MA + bullish engulfing in uptrend | Trend Continuation | 75–90% |
| Price below 20MA + bearish engulfing in downtrend | Trend Continuation | 75–90% |
| Multi-timeframe alignment (1W/1D/4H/1H) | Confluence Signal | 60–80% |
| Doji at support/resistance | Potential Reversal | 70–75% |

## Tracked Assets

**Indices:** SPX500, US10Y  
**Commodities:** XAUUSD  
**Stocks:** NVDA, AMZN, ORCL, MSTR, PURR  
**Crypto:** BTCUSD, ETHUSD, ETHBTC, BTC.D  
**DeFi Tokens:** HYPEUSDT, MONUSD, PUMPUSDT, ASTERUSDT, MORPHOUSDT, FARTCOINUSDT, ZROUSDT, TAOUSDT, VVYUSDT, STGUSDT

## Project Structure

```
tradingview-alert-agent/
├── docker-compose.yml
├── .env.example
├── DESIGN.md
├── SETUP.md
├── CAVEATS.md
├── PROGRESS.md
└── README.md
│
├── integration-service/         # NEW — Port 8004 (TradingView entry point)
│   ├── integration_service.py   # FastAPI app — /webhook, /health, /status, /trigger-analysis
│   ├── orchestrator.py          # Core pipeline: store → analyze → persist → email
│   ├── clients.py               # Async httpx wrappers with retry
│   ├── models.py                # Pydantic request/response models
│   ├── config.py                # pydantic-settings config
│   ├── Dockerfile
│   └── requirements.txt
│
├── webhook-receiver/            # Port 8000 — alert & result storage
│   ├── webhook_receiver.py      # FastAPI app (storage + behavior log endpoints)
│   ├── analysis_bridge.py       # Legacy analysis bridge (kept for reference)
│   ├── database.py              # SQLite operations
│   ├── config.py                # Environment config
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── analysis-engine/             # Port 8001 — standalone analysis microservice
│   ├── api.py                   # FastAPI app — POST /analyze entry point
│   ├── analysis_engine.py       # Main orchestrator
│   ├── pattern_detector.py      # 12 candlestick patterns
│   ├── ma_analyzer.py           # 20MA calculations
│   ├── context_engine.py        # Context rules + confidence scoring
│   ├── multi_timeframe.py       # 1W/1D/4H/1H analysis
│   ├── database.py              # OHLCV SQLite storage
│   ├── models.py                # Pydantic models
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── email-notifier/              # Port 8002 — alerts + scheduled reports
│   ├── email_notifier.py        # FastAPI app — /send-alert + /reports/*
│   ├── report_generator.py      # Report data queries + symbol analysis
│   ├── templates.py             # Jinja2 HTML email templates
│   ├── config.py                # SMTP/SendGrid/SES config
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
└── scheduler/                   # Port 8003 — cron jobs
    ├── scheduler.py             # APScheduler setup
    ├── api.py                   # FastAPI job management endpoints
    ├── jobs.py                  # Job implementations (HTTP calls)
    ├── job_store.py             # SQLite job persistence
    ├── monitor.py               # Health monitoring
    ├── config.py                # Schedule configuration
    ├── timezone_utils.py        # EST/EDT DST handling
    ├── Dockerfile
    ├── requirements.txt
    └── README.md
```

## Configuration

Key environment variables (set in `.env`):

```bash
# Email (required)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient@example.com

# Analysis threshold
CONFIDENCE_THRESHOLD=0.75   # Send email when confidence >= this value

# Schedule
DAILY_REPORT_HOUR=17
WEEKLY_REPORT_HOUR=17
MONTHLY_REPORT_HOUR=17
SCHEDULE_TIMEZONE=America/New_York

# Security (recommended for production)
WEBHOOK_SECRET=your-hmac-secret
```

## Documentation

- [DESIGN.md](DESIGN.md) — Architecture and design decisions
- [SETUP.md](SETUP.md) — Detailed setup and deployment instructions
- [PROGRESS.md](PROGRESS.md) — Project status tracker
- [CAVEATS.md](CAVEATS.md) — Known limitations and recommendations

## Requirements

- Docker + Docker Compose
- TradingView account (Essential+ for webhooks)
- SMTP email credentials

## License

MIT License — see LICENSE file for details.

---

**Built for Scoffie** | DeFi Analytics & On-Chain Analysis  
**Version:** 2.0.0 | **Date:** April 2026
