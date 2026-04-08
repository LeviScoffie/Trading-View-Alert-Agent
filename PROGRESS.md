# TradingView Alert Agent — Progress Tracker

## Project Overview
Build an intelligent TradingView alert system that learns Scoffie's chart-reading behavior and provides contextual analysis via email.

---

## Components Status

| # | Component | Status | Date Completed | Notes |
|---|-----------|--------|----------------|-------|
| 1 | **Webhook Receiver** | ✅ COMPLETE | 2026-04-08 | FastAPI + SQLite + Docker + HMAC signatures + background analysis |
| 2 | **Analysis Engine** | ✅ COMPLETE | 2026-04-08 | 12 patterns, 20MA, context rules, confidence scoring, multi-TF |
| 3 | **Behavior Tracking** | ✅ COMPLETE | 2026-04-08 | Alert enrichment + `/log` endpoint (no extension needed) |
| 4 | **Email Notifier** | ✅ COMPLETE | 2026-04-08 | FastAPI endpoints, HTML templates, SMTP/SendGrid/SES, Jinja2 |
| 5 | **Scheduler** | ✅ COMPLETE | 2026-04-08 | Standalone service (port 8003), orchestrates email-notifier via HTTP |
| 6 | **Documentation** | ✅ COMPLETE | 2026-04-08 | DESIGN.md, PROGRESS.md, SETUP.md, CAVEATS.md, README.md, component docs |

---

## Webhook Receiver Details

**Location:** `webhook-receiver/`

**Files:**
- ✅ `webhook_receiver.py` — FastAPI app with 10+ endpoints
- ✅ `alert_processor.py` — Background analysis pipeline (~200 lines)
- ✅ `analysis_bridge.py` — Embeds analysis-engine as library (~80 lines)
- ✅ `database.py` — SQLite operations (alerts + behavior_logs + analysis_results)
- ✅ `config.py` — Environment config
- ✅ `Dockerfile` — Container setup
- ✅ `requirements.txt` — Dependencies
- ✅ `README.md` — Documentation
- ✅ `.env.example` — Environment template

**Endpoints:**
- `POST /webhook` + `POST /webhook/tradingview` — receive TradingView alerts
- `POST /log` — manual behavior logging
- `GET /logs`, `/logs/{symbol}` — behavior log queries
- `GET /alerts`, `/alerts/{symbol}` — alert queries
- `GET /attention` — attention heatmap
- `GET /analysis`, `/analysis/{symbol}` — analysis results
- `GET /stats` — database statistics
- `GET /health` — health check

**Background Pipeline:** On each alert, `alert_processor.py` calls `analysis_bridge.run_analysis()` → stores result in `analysis_results` → triggers immediate email if `confidence >= CONFIDENCE_THRESHOLD`.

**Testing Status:** ✅ CODE VALIDATED — Runtime testing pending (requires Docker environment)

---

## Analysis Engine Details

**Location:** `analysis-engine/`

**Deployment:** NOT a standalone container. Imported as a Python library inside webhook-receiver via `analysis_bridge.py`. Code resides in `analysis-engine/` but runs in the webhook-receiver container.

**Files:**
- ✅ `analysis_engine.py` — Main orchestrator
- ✅ `pattern_detector.py` — 12 candlestick patterns
- ✅ `ma_analyzer.py` — 20MA calculations (trend + slope)
- ✅ `context_engine.py` — 5 context rules + confidence scoring
- ✅ `multi_timeframe.py` — 1W/1D/4H/1H analysis with weighting
- ✅ `database.py` — OHLCV SQLite storage
- ✅ `models.py` — Pydantic data models
- ✅ `test_patterns.py` — Unit tests
- ✅ `example_usage.py` — Usage examples
- ✅ `requirements.txt` — Dependencies (pandas, numpy, pydantic)

**Patterns Detected (12):** Bullish/Bearish Engulfing, Doji, Dragonfly Doji, Gravestone Doji, Hammer, Inverted Hammer, Morning Star, Evening Star, Three White Soldiers, Three Black Crows

---

## Email Notifier Details

**Location:** `email-notifier/`

**Deployment:** Standalone Docker service on port 8001. Does NOT self-schedule — Scheduler service triggers it via HTTP POST.

**Files:**
- ✅ `email_notifier.py` — FastAPI app with report endpoints (~280 lines)
- ✅ `templates.py` — HTML email templates with Jinja2 (~500 lines)
- ✅ `report_generator.py` — Database queries, OHLCV analysis, pattern detection (~450 lines)
- ✅ `config.py` — Email and schedule configuration (~100 lines)
- ✅ `Dockerfile` — Container setup with health checks
- ✅ `requirements.txt` — Dependencies
- ✅ `README.md` — Usage documentation
- ✅ `.env.example` — Environment template
- ✅ `test_email_notifier.py` — Unit tests

**Endpoints:**
- `POST /reports/daily` — Generate and send daily report
- `POST /reports/weekly` — Generate and send weekly report
- `POST /reports/monthly` — Generate and send monthly report
- `GET /health` — Health check

**Features:**
- HTML email with dark-themed design (Jinja2)
- Pattern badges with confidence scores (color-coded)
- MA20 status with visual indicator
- Multi-timeframe alignment grid (1W/1D/4H/1H)
- 5-level recommendation (strong_long → strong_short)
- Email providers: SMTP (Gmail), SendGrid, AWS SES
- Retry logic: 3x with 60s delay

**Testing Status:** ✅ CODE VALIDATED — Ready for integration testing

---

## Scheduler Details

**Location:** `scheduler/`

**Deployment:** Standalone Docker service on port 8003. APScheduler with SQLite persistence. Depends on webhook-receiver and email-notifier.

**Files:**
- ✅ `scheduler.py` — APScheduler setup
- ✅ `api.py` — FastAPI endpoints for job management
- ✅ `jobs.py` — Job function implementations (HTTP calls to services)
- ✅ `job_store.py` — SQLite job persistence
- ✅ `monitor.py` — Health monitoring
- ✅ `config.py` — Schedule configuration
- ✅ `timezone_utils.py` — EST/EDT DST handling
- ✅ `Dockerfile` — Multi-stage build with non-root user
- ✅ `requirements.txt` — Dependencies (APScheduler, SQLAlchemy, pytz)
- ✅ `README.md` — Usage documentation

**Scheduled Jobs:**

| Job | Schedule | Action |
|-----|----------|--------|
| Daily Report | 5:00 PM EST (daily) | `POST /reports/daily` → email-notifier |
| Weekly Report | 5:00 PM EST (Sunday) | `POST /reports/weekly` → email-notifier |
| Monthly Report | 5:00 PM EST (last day) | `POST /reports/monthly` → email-notifier |
| Data Cleanup | 3:00 AM EST (Sunday) | Prune records older than 90 days |
| Health Check | Every hour | Ping all services, log status |

**Management Endpoints:**
- `GET /jobs` — List all jobs with next run times
- `POST /jobs/{id}/trigger` — Manually fire a job
- `POST /jobs/{id}/pause` / `/resume`
- `GET /dashboard` — System overview
- `GET /health` — Health check

**Testing Status:** ✅ CODE VALIDATED — Runtime testing pending

---

## Requirements Summary

| Setting | Value |
|---------|-------|
| **Integration** | TradingView webhooks + manual `/log` endpoint |
| **Behaviors Tracked** | Alert payloads (`{{interval}}`), manual logs, conviction tags |
| **Analysis** | 12 patterns, 20MA, context rules, multi-TF confluence |
| **Immediate Alerts** | Email sent when confidence ≥ `CONFIDENCE_THRESHOLD` (default 0.75) |
| **Scheduled Reports** | Daily close (5PM EST), Weekly (Sun 5PM), Monthly (last day 5PM) |
| **Timezone** | EST/EDT (America/New_York) |
| **Delivery** | Email (SMTP / SendGrid / AWS SES) |
| **Assets** | 20+ (SPX500, BTCUSD, ETHUSD, alts, DeFi tokens) |
| **Data Retention** | 90 days (auto-pruned by scheduler) |

---

## Architecture

See `DESIGN.md` for complete system architecture, data flow, and design decisions.

**Key Decisions:**
1. No browser extension — behavior tracking via alert enrichment + `/log` endpoint
2. Analysis engine embedded as library in webhook-receiver (not standalone container)
3. Scheduler as separate service — clean separation from email delivery logic

---

## Next Steps

1. ✅ Webhook Receiver — Complete
2. ✅ Analysis Engine — Complete
3. ✅ Behavior Tracking — Complete
4. ✅ Email Notifier — Complete
5. ✅ Scheduler — Complete
6. ✅ Documentation — Complete
7. ⏳ Integration testing (end-to-end: webhook → analysis → email delivery)
8. ⏳ Deploy to production VPS
9. ⏳ Configure TradingView webhooks for 20+ assets

---

*Last updated: 2026-04-08*
