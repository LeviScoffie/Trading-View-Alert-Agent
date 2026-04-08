# 🦀 TradingView Alert Agent

Intelligent trading analysis system that processes TradingView webhook alerts through a multi-service architecture to deliver context-aware trading insights via email.

## Features

- **📊 Pattern Detection:** Automatic engulfing pattern recognition with confidence scoring
- **🧠 Context-Aware Analysis:** "Past 2-3 days bearish + weekly engulfing = buying opportunity"
- **📧 Email Notifications:** Immediate alerts + daily/weekly/monthly summary reports
- **🕐 Scheduled Reports:** Daily (5 PM EST), Weekly (Sunday 5 PM EST), Monthly (Last day 5 PM EST)
- **📈 20+ Assets:** SPX500, BTCUSD, ETHUSD, NVDA, and more
- **🐳 Docker Ready:** One-command deployment
- **🔧 Microservices:** 5-service architecture for scalability and maintainability
- **🔗 Integration Layer:** Orchestrates webhook → analysis → email flow automatically

## Quick Start

```bash
cd /home/node/.openclaw/workspace/projects/tradingview-alert-agent

# Configure
cp .env.example .env
nano .env  # Add SMTP credentials

# Deploy
docker-compose up -d

# Verify all services
curl http://localhost:8000/health  # webhook-receiver
curl http://localhost:8001/health  # analysis-engine
curl http://localhost:8002/health  # email-notifier
curl http://localhost:8003/health  # scheduler
curl http://localhost:8004/health  # integration-service (orchestrator)
```

See [SETUP.md](SETUP.md) for detailed instructions.

## Architecture

```
┌─────────────────┐    ┌─────────────────────────┐
│ TradingView     │───▶│ integration-service   │
│ Webhooks        │    │ Port: 8004            │
│                 │    │ Purpose: Orchestrate  │
└─────────────────┘    │       webhook→analysis│
                       │       →email flow     │
                       └──────────┬──────────────┘
                                  │ HTTP
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ webhook-receiver │  │ analysis-engine  │  │ email-notifier   │
│ Port: 8000       │  │ Port: 8001       │  │ Port: 8002       │
│ Purpose: Store   │  │ Purpose: Pattern │  │ Purpose: Send    │
│       alerts     │  │       detection  │  │       emails     │
└──────────────────┘  └──────────────────┘  └──────────────────┘
                                                        ▲
                                                        │
                                               ┌────────┴────────┐
                                               │   scheduler     │
                                               │   Port: 8003    │
                                               │   Purpose:      │
                                               │   Scheduled     │
                                               │   reports       │
                                               └─────────────────┘

Shared Database: SQLite (alerts.db, ohlcv.db)
Communication: HTTP REST API between services
Integration: Integration Service orchestrates the flow
```

## Tracked Assets

**Indices:** SPX500, US10Y  
**Commodities:** XAUUSD  
**Stocks:** NVDA, AMZN, ORCL, MSTR, PURR  
**Crypto:** BTCUSD, ETHUSD, ETHBTC, BTC.D  
**DeFi Tokens:** HYPEUSDT, MONUSD, PUMPUSDT, ASTERUSDT, MORPHOUSDT, FARTCOINUSDT, ZROUSDT, TAOUSDT, VVYUSDT, STGUSDT

## API Endpoints

| Service | Endpoint | Method | Description |
|---------|----------|--------|-------------|
| webhook-receiver (8000) | `/health` | GET | Health check |
| webhook-receiver (8000) | `/webhook/tradingview` | POST | TradingView webhook receiver |
| analysis-engine (8001) | `/health` | GET | Health check |
| analysis-engine (8001) | `/api/analyze/{symbol}` | POST | Perform pattern analysis |
| analysis-engine (8001) | `/api/insights/{symbol}` | GET | Get contextual insights |
| email-notifier (8002) | `/health` | GET | Health check |
| email-notifier (8002) | `/api/email/send` | POST | Send email notification |
| scheduler (8003) | `/health` | GET | Health check |
| scheduler (8003) | `/api/schedule/report` | POST | Schedule report generation |
| scheduler (8003) | `/api/reports/daily` | POST | Trigger daily report |
| scheduler (8003) | `/api/reports/weekly` | POST | Trigger weekly report |
| scheduler (8003) | `/api/reports/monthly` | POST | Trigger monthly report |
| **integration-service (8004)** | **`/health`** | **GET** | **Health check + service statuses** |
| **integration-service (8004)** | **`/webhook`** | **POST** | **Receive alert, orchestrate flow** |
| **integration-service (8004)** | **`/status/{id}`** | **GET** | **Get alert + analysis status** |
| **integration-service (8004)** | **`/trigger-analysis`** | **POST** | **Manually trigger analysis** |

## Example TradingView Webhook

```json
{
  "symbol": "BTCUSD",
  "price": 65000,
  "timeframe": "1D",
  "alert_name": "BTC Bullish Engulfing",
  "message": "Bullish engulfing pattern detected"
}
```

## Context-Aware Insights

The analysis engine generates intelligent insights based on market context:

| Condition | Insight Type | Confidence |
|-----------|--------------|------------|
| Past 2-3 days bearish + weekly bullish engulfing | Buying Opportunity | 85% |
| Price above 20MA + bullish engulfing in uptrend | Trend Continuation | 75% |
| Price below 20MA + bearish engulfing in downtrend | Trend Continuation | 70% |
| No clear signals | Neutral | 50% |

## Project Structure

```
tradingview-alert-agent/
├── webhook-receiver/
│   ├── webhook_receiver.py  # FastAPI webhook endpoints
│   ├── database.py          # SQLite operations
│   ├── config.py            # Configuration
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile           # Container build
│   └── README.md            # Documentation
├── analysis-engine/
│   ├── analysis_engine.py   # Main orchestrator
│   ├── pattern_detector.py  # 12 candlestick patterns
│   ├── ma_analyzer.py       # 20MA calculations
│   ├── context_engine.py    # Context rules
│   ├── multi_timeframe.py   # Multi-TF analysis
│   ├── database.py          # OHLCV storage
│   ├── models.py            # Pydantic models
│   └── requirements.txt     # Dependencies
├── email-notifier/
│   ├── email_notifier.py    # Email sender
│   ├── templates.py         # HTML email templates
│   ├── config.py            # Configuration
│   ├── requirements.txt     # Dependencies
│   ├── Dockerfile           # Container build
│   └── README.md            # Documentation
├── scheduler/
│   ├── scheduler.py         # APScheduler implementation
│   ├── report_scheduler.py  # Report scheduling logic
│   ├── config.py            # Configuration
│   ├── requirements.txt     # Dependencies
│   ├── Dockerfile           # Container build
│   └── README.md            # Documentation
├── integration-service/
│   ├── integration_service.py  # FastAPI orchestration API
│   ├── orchestrator.py         # Core flow logic
│   ├── clients.py              # Service HTTP clients
│   ├── models.py               # Pydantic models
│   ├── config.py               # Configuration
│   ├── requirements.txt        # Dependencies
│   ├── Dockerfile              # Container build
│   └── README.md               # Documentation
├── docker-compose.yml    # Docker orchestration
├── test_integration.py   # End-to-end test script
├── .env.example          # Configuration template
├── DESIGN.md             # Architecture documentation
├── SETUP.md              # Deployment guide
├── CAVEATS.md            # Limitations & issues
├── PROGRESS.md           # Project progress tracker
└── README.md             # This file
```

## Configuration

Key environment variables for all services:

```bash
# Email Configuration (used by email-notifier)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
EMAIL_TO=recipient@example.com

# Schedule Configuration (used by scheduler)
DAILY_REPORT_HOUR=17        # 5 PM EST
WEEKLY_REPORT_DAY=6         # Sunday
WEEKLY_REPORT_HOUR=18       # 6 PM EST
MONTHLY_REPORT_DAY=-1       # Last day of month

# Service Communication
WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
ANALYSIS_ENGINE_URL=http://analysis-engine:8001
EMAIL_NOTIFIER_URL=http://email-notifier:8002
SCHEDULER_URL=http://scheduler:8003

# Database
DATABASE_URL=sqlite:///./alerts.db

# Assets
ASSETS=SPX500,BTCUSD,ETHUSD,NVDA,...
```

## Development

```bash
# Local development
# Start all services
docker-compose up --build

# Or develop individual services
# webhook-receiver
cd webhook-receiver && pip install -r requirements.txt && python webhook_receiver.py

# analysis-engine
cd analysis-engine && pip install -r requirements.txt && python analysis_engine.py

# email-notifier
cd email-notifier && pip install -r requirements.txt && python email_notifier.py

# scheduler
cd scheduler && pip install -r requirements.txt && python scheduler.py

# integration-service
cd integration-service && pip install -r requirements.txt && python integration_service.py
```

## Documentation

- [DESIGN.md](DESIGN.md) - Architecture and design decisions
- [PROGRESS.md](PROGRESS.md) - Project progress tracker
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [CAVEATS.md](CAVEATS.md) - Known limitations and issues
- [webhook-receiver/README.md](webhook-receiver/README.md) - Webhook receiver docs
- [analysis-engine/README.md](analysis-engine/README.md) - Analysis engine docs
- [email-notifier/README.md](email-notifier/README.md) - Email notifier docs
- [integration-service/README.md](integration-service/README.md) - Integration service docs

## Integration Service

The **Integration Service** (port 8004) is the orchestration layer that connects all services:

### Flow
1. Receives TradingView webhook at `/webhook`
2. Stores alert in webhook-receiver
3. Triggers analysis via analysis-engine
4. If confidence >= 0.75, sends immediate email via email-notifier
5. Returns combined response with alert ID, analysis, and email status

### Testing
```bash
# Test the integration service
curl -X POST http://localhost:8004/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSD", "price": 45000, "message": "Test alert", "timeframe": "1D"}'

# Run end-to-end test
python test_integration.py
```

## Requirements

- Docker + Docker Compose
- TradingView account (Essential+ for webhooks)
- SMTP email credentials

## License

MIT License - See LICENSE file for details.

## Support

For issues or questions:
1. Check [CAVEATS.md](CAVEATS.md) for known limitations
2. Review logs: `docker-compose logs -f`
3. Test endpoints:
   - `curl http://localhost:8000/health` (webhook-receiver)
   - `curl http://localhost:8001/health` (analysis-engine)
   - `curl http://localhost:8002/health` (email-notifier)
   - `curl http://localhost:8003/health` (scheduler)

---

**Built for Scoffie** | DeFi Analytics & On-Chain Analysis  
**Version:** 1.0.0 | **Date:** April 2025
