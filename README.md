# 🦀 TradingView Alert Agent

Intelligent trading analysis system that combines TradingView webhook alerts with browser behavior tracking to deliver context-aware trading insights via email.

## Features

- **📊 Pattern Detection:** Automatic engulfing pattern recognition with confidence scoring
- **🧠 Context-Aware Analysis:** "Past 2-3 days bearish + weekly engulfing = buying opportunity"
- **📧 Email Notifications:** Immediate alerts + daily/weekly/monthly summary reports
- **🕐 Scheduled Reports:** Daily (5 PM EST), Weekly (Sunday 5 PM EST), Monthly (Last day 5 PM EST)
- **🔍 Behavior Tracking:** Browser extension tracks timeframe switches, drawing tools, time spent
- **📈 20+ Assets:** SPX500, BTCUSD, ETHUSD, NVDA, and more
- **🐳 Docker Ready:** One-command deployment

## Quick Start

```bash
cd /home/node/.openclaw/workspace/projects/tradingview-alert-agent

# Configure
cp .env.example .env
nano .env  # Add SMTP credentials

# Deploy
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

See [SETUP.md](SETUP.md) for detailed instructions.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ TradingView     │───▶│ Webhook         │───▶│ Analysis        │
│ Webhooks        │    │ Receiver        │    │ Engine          │
│                 │    │ (FastAPI)       │    │ (Patterns)      │
└─────────────────┘    └────────┬────────┘    └────────┬────────┘
                               │                       │
                               ▼                       ▼
                        ┌─────────────────┐    ┌─────────────────┐
                        │ SQLite          │◀───│ Context Engine  │
                        │ (alerts.db)     │    │ (Intelligence)  │
                        └────────┬────────┘    └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Email Notifier  │
                        │ (APScheduler)   │
                        │                 │
                        │ Daily 5PM EST   │
                        │ Weekly Sun 5PM  │
                        │ Monthly Last Day│
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Email Delivery  │
                        │ (SMTP/SendGrid/ │
                        │  AWS SES)       │
                        └─────────────────┘
```

## Tracked Assets

**Indices:** SPX500, US10Y  
**Commodities:** XAUUSD  
**Stocks:** NVDA, AMZN, ORCL, MSTR, PURR  
**Crypto:** BTCUSD, ETHUSD, ETHBTC, BTC.D  
**DeFi Tokens:** HYPEUSDT, MONUSD, PUMPUSDT, ASTERUSDT, MORPHOUSDT, FARTCOINUSDT, ZROUSDT, TAOUSDT, VVYUSDT, STGUSDT

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/webhook/tradingview` | POST | TradingView webhook receiver |
| `/api/behavior` | POST | Browser extension data sync |
| `/api/market-data` | POST | Store market data |
| `/api/insights/{symbol}` | GET | Get contextual insights |
| `/api/reports/daily` | POST | Trigger daily report |
| `/api/reports/weekly` | POST | Trigger weekly report |

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
├── backend/
│   ├── main.py           # FastAPI application
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLite models
│   ├── analysis.py       # Technical analysis engine
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile        # Container build
├── extension/
│   ├── manifest.json     # Extension config
│   ├── background.js     # Service worker
│   ├── content.js        # DOM observer
│   ├── popup.html        # Extension UI
│   └── popup.js          # Popup logic
├── webhook-receiver/
│   ├── webhook_receiver.py  # FastAPI webhook endpoints
│   ├── database.py          # SQLite operations
│   ├── config.py            # Configuration
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
│   └── README.md            # Documentation
├── email-notifier/
│   ├── email_notifier.py    # Scheduler and sender
│   ├── templates.py         # HTML email templates
│   ├── report_generator.py  # Report data generation
│   ├── config.py            # Configuration
│   ├── requirements.txt     # Dependencies
│   ├── Dockerfile           # Container build
│   └── README.md            # Documentation
├── docker-compose.yml    # Docker orchestration
├── .env.example          # Configuration template
├── DESIGN.md             # Architecture documentation
├── SETUP.md              # Deployment guide
├── CAVEATS.md            # Limitations & issues
├── PROGRESS.md           # Project progress tracker
└── README.md             # This file
```

## Configuration

Key environment variables:

```bash
# Email (required for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
EMAIL_TO=recipient@example.com

# Schedule
DAILY_REPORT_HOUR=17      # 5 PM EST
WEEKLY_REPORT_DAY=6       # Sunday
WEEKLY_REPORT_HOUR=18     # 6 PM EST

# Assets
ASSETS=SPX500,BTCUSD,ETHUSD,NVDA,...
```

## Development

```bash
# Local development
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --reload
```

## Documentation

- [DESIGN.md](DESIGN.md) - Architecture and design decisions
- [PROGRESS.md](PROGRESS.md) - Project progress tracker
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [CAVEATS.md](CAVEATS.md) - Known limitations and issues
- [webhook-receiver/README.md](webhook-receiver/README.md) - Webhook receiver docs
- [analysis-engine/README.md](analysis-engine/README.md) - Analysis engine docs
- [email-notifier/README.md](email-notifier/README.md) - Email notifier docs

## Requirements

- Docker + Docker Compose
- TradingView account (Essential+ for webhooks)
- SMTP email credentials
- Chrome/Edge (for browser extension)

## License

MIT License - See LICENSE file for details.

## Support

For issues or questions:
1. Check [CAVEATS.md](CAVEATS.md) for known limitations
2. Review logs: `docker-compose logs -f`
3. Test endpoints: `curl http://localhost:8000/health`

---

**Built for Scoffie** | DeFi Analytics & On-Chain Analysis  
**Version:** 1.0.0 | **Date:** April 2026
