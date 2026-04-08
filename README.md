# TradingView Alert Agent

Intelligent trading analysis system that combines TradingView webhook alerts with behavior tracking to deliver context-aware trading insights via email.

## Features

- **Pattern Detection:** 12 candlestick patterns with confidence scoring (engulfing, doji, hammer, morning/evening star, three soldiers/crows, and more)
- **Context-Aware Analysis:** "Past 2-3 days bearish + weekly engulfing = buying opportunity"
- **Email Notifications:** Immediate alerts on high-confidence signals + daily/weekly/monthly summary reports
- **Scheduled Reports:** Daily (5 PM EST), Weekly (Sunday 5 PM EST), Monthly (Last day 5 PM EST)
- **Behavior Tracking:** Manual `/log` endpoint + enriched alert payloads (no browser extension required)
- **20+ Assets:** SPX500, BTCUSD, ETHUSD, NVDA, and more
- **Docker Ready:** One-command deployment with 3 coordinated services

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
curl http://localhost:8000/health   # webhook-receiver
curl http://localhost:8001/health   # email-notifier
curl http://localhost:8003/health   # scheduler
```

See [SETUP.md](SETUP.md) for detailed instructions.

## Architecture

```
┌─────────────────┐    ┌──────────────────────────────┐
│ TradingView     │───▶│ Webhook Receiver :8000        │
│ Webhooks        │    │ (FastAPI + alert_processor)   │
└─────────────────┘    └───────────┬──────────────────┘
                                   │  background task
                                   ▼
                        ┌─────────────────────┐
                        │ Analysis Engine     │
                        │ (embedded library)  │
                        │ 12 patterns, 20MA,  │
                        │ multi-TF, context   │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │ SQLite              │
                        │ alerts.db           │
                        │ ohlcv.db            │
                        │ (shared volume)     │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                                         │
              ▼                                         ▼
┌─────────────────────┐                   ┌─────────────────────┐
│ Scheduler :8003     │──── HTTP POST ───▶│ Email Notifier :8001│
│ (APScheduler)       │                   │ (FastAPI + Jinja2)  │
│ Daily 5PM EST       │                   │                     │
│ Weekly Sun 5PM      │                   │                     │
│ Monthly Last Day    │                   └──────────┬──────────┘
│ Cleanup Sun 3AM     │                              │
└─────────────────────┘                              ▼
                                         ┌─────────────────────┐
                                         │ Email Delivery      │
                                         │ (SMTP / SendGrid /  │
                                         │  AWS SES)           │
                                         └─────────────────────┘
```

## Tracked Assets

**Indices:** SPX500, US10Y  
**Commodities:** XAUUSD  
**Stocks:** NVDA, AMZN, ORCL, MSTR, PURR  
**Crypto:** BTCUSD, ETHUSD, ETHBTC, BTC.D  
**DeFi Tokens:** HYPEUSDT, MONUSD, PUMPUSDT, ASTERUSDT, MORPHOUSDT, FARTCOINUSDT, ZROUSDT, TAOUSDT, VVYUSDT, STGUSDT

## API Endpoints

### Webhook Receiver (port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhook` | POST | TradingView webhook receiver |
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

### Email Notifier (port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
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

## Example TradingView Webhook

```json
{
  "symbol": "{{ticker}}",
  "price": {{close}},
  "timeframe": "{{interval}}",
  "alert_name": "{{alertname}}",
  "message": "Alert triggered for {{ticker}}"
}
```

## Context-Aware Insights

| Condition | Insight Type | Confidence |
|-----------|--------------|------------|
| Past 2-3 days bearish + weekly bullish engulfing | Buying Opportunity | 85% |
| Price above 20MA + bullish engulfing in uptrend | Trend Continuation | 75–90% |
| Price below 20MA + bearish engulfing in downtrend | Trend Continuation | 75–90% |
| Multi-timeframe alignment (1W/1D/4H/1H) | Confluence Signal | 60–80% |
| Doji at support/resistance | Potential Reversal | 70–75% |

## Project Structure

```
tradingview-alert-agent/
├── docker-compose.yml
├── .env.example
├── DESIGN.md
├── SETUP.md
├── CAVEATS.md
├── PROGRESS.md
├── README.md
│
├── webhook-receiver/            # Service 1 — port 8000
│   ├── webhook_receiver.py      # FastAPI app (10 endpoints)
│   ├── alert_processor.py       # Background analysis pipeline
│   ├── analysis_bridge.py       # Embeds analysis-engine as library
│   ├── database.py              # SQLite operations
│   ├── config.py                # Environment config
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── email-notifier/              # Service 2 — port 8001
│   ├── email_notifier.py        # FastAPI app + report endpoints
│   ├── report_generator.py      # Queries DB, detects patterns, builds report
│   ├── templates.py             # Jinja2 HTML email templates
│   ├── config.py                # SMTP/SendGrid/SES config
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── scheduler/                   # Service 3 — port 8003
│   ├── scheduler.py             # APScheduler setup
│   ├── api.py                   # FastAPI job management endpoints
│   ├── jobs.py                  # Job implementations (HTTP calls to services)
│   ├── job_store.py             # SQLite job persistence
│   ├── monitor.py               # Health monitoring
│   ├── config.py                # Schedule configuration
│   ├── timezone_utils.py        # EST/EDT DST handling
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
└── analysis-engine/             # Library (not a running container)
    ├── analysis_engine.py       # Main orchestrator
    ├── pattern_detector.py      # 12 candlestick patterns
    ├── ma_analyzer.py           # 20MA calculations
    ├── context_engine.py        # Context rules + confidence scoring
    ├── multi_timeframe.py       # 1W/1D/4H/1H analysis
    ├── database.py              # OHLCV SQLite storage
    ├── models.py                # Pydantic models
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

# Schedule (defaults)
DAILY_REPORT_HOUR=17       # 5 PM EST
WEEKLY_REPORT_HOUR=17      # Sunday 5 PM EST
MONTHLY_REPORT_HOUR=17     # Last day of month 5 PM EST
SCHEDULE_TIMEZONE=America/New_York

# Analysis
CONFIDENCE_THRESHOLD=0.75  # Threshold for immediate email alert

# Security (optional but recommended)
WEBHOOK_SECRET=your-hmac-secret
```

## Development

```bash
# Local development (webhook-receiver only)
python -m venv venv
source venv/bin/activate
pip install -r webhook-receiver/requirements.txt
cd webhook-receiver && uvicorn webhook_receiver:app --reload
```

## Documentation

- [DESIGN.md](DESIGN.md) — Architecture and design decisions
- [PROGRESS.md](PROGRESS.md) — Project progress tracker
- [SETUP.md](SETUP.md) — Detailed setup instructions
- [CAVEATS.md](CAVEATS.md) — Known limitations and issues
- [webhook-receiver/README.md](webhook-receiver/README.md) — Webhook receiver docs
- [analysis-engine/README.md](analysis-engine/README.md) — Analysis engine docs
- [email-notifier/README.md](email-notifier/README.md) — Email notifier docs
- [scheduler/README.md](scheduler/README.md) — Scheduler docs

## Requirements

- Docker + Docker Compose
- TradingView account (Essential+ for webhooks)
- SMTP email credentials

## License

MIT License — see LICENSE file for details.

## Support

For issues:
1. Check [CAVEATS.md](CAVEATS.md) for known limitations
2. Review logs: `docker-compose logs -f`
3. Test endpoints: `curl http://localhost:8000/health`

---

**Built for Scoffie** | DeFi Analytics & On-Chain Analysis  
**Version:** 1.1.0 | **Date:** April 2026
