# TradingView Alert Agent — Progress Tracker

## Project Overview
Build an intelligent TradingView alert system that learns Scoffie's chart-reading behaviour and provides contextual analysis via email.

**Current Version:** 2.0.0 — 5-service microservice architecture with central integration layer.

---

## Component Status

| # | Component | Status | Port | Date | Notes |
|---|-----------|--------|------|------|-------|
| 1 | **Webhook Receiver** | ✅ COMPLETE | 8000 | 2026-04-08 | Storage-only in v2.0; analysis pipeline removed |
| 2 | **Analysis Engine** | ✅ COMPLETE | 8001 | 2026-04-09 | Promoted from embedded library to standalone microservice |
| 3 | **Email Notifier** | ✅ COMPLETE | 8002 | 2026-04-08 | Moved from port 8001; added `/send-alert` endpoint |
| 4 | **Scheduler** | ✅ COMPLETE | 8003 | 2026-04-08 | Updated EMAIL_NOTIFIER_URL to port 8002 |
| 5 | **Integration Service** | ✅ COMPLETE | 8004 | 2026-04-09 | New in v2.0 — central orchestrator |
| 6 | **Documentation** | ✅ COMPLETE | — | 2026-04-09 | Updated for v2.0 architecture |

---

## Integration Service (v2.0 — NEW)

**Location:** `integration-service/`

**Files:**
- ✅ `integration_service.py` — FastAPI app (4 endpoints)
- ✅ `orchestrator.py` — Core pipeline: store → analyze → persist → email
- ✅ `clients.py` — Async httpx wrappers with 3-attempt exponential backoff
- ✅ `models.py` — Pydantic request/response models
- ✅ `config.py` — pydantic-settings configuration
- ✅ `Dockerfile` — python:3.11-slim, port 8004
- ✅ `requirements.txt` — fastapi, uvicorn, httpx, pydantic-settings

**Endpoints:**
- `POST /webhook` — TradingView entry point; runs full pipeline
- `GET /health` — Aggregate health of all 4 downstream services
- `GET /status/{alert_id}` — Alert processing status
- `POST /trigger-analysis` — Manual analysis without webhook alert

**Verified:** ✅ End-to-end test `{"status":"processed","alert_id":4}` — all services green

---

## Analysis Engine (v2.0 — Promoted to Microservice)

**Location:** `analysis-engine/`

**New Files:**
- ✅ `api.py` — FastAPI wrapper with `POST /analyze` endpoint

**Updated Files:**
- ✅ `requirements.txt` — added fastapi, uvicorn, pydantic-settings
- ✅ `Dockerfile` — now runs `python api.py` instead of pytest

**Existing Files (unchanged):**
- ✅ `analysis_engine.py` — Main orchestrator
- ✅ `pattern_detector.py` — 12 candlestick patterns
- ✅ `ma_analyzer.py` — 20MA calculations
- ✅ `context_engine.py` — 5 context rules + confidence scoring
- ✅ `multi_timeframe.py` — 1W/1D/4H/1H analysis
- ✅ `database.py` — OHLCV SQLite storage
- ✅ `models.py` — Pydantic data models

**Verified:** ✅ `POST /analyze` returns valid JSON; health check passes

---

## Webhook Receiver (v2.0 — Storage Only)

**Location:** `webhook-receiver/`

**Changes from v1.x:**
- ✅ Removed `alert_processor.py` background task from `/webhook` endpoint
- ✅ Removed `POST /analyze` endpoint (analysis is now analysis-engine's job)
- ✅ Added `POST /analysis/{alert_id}` — persist analysis result from integration-service
- ✅ Reverted Dockerfile to simple build (no analysis-engine copy needed)

**Endpoints:**
- `POST /webhook` — store alert (storage-only, returns `alert_id`)
- `POST /analysis/{alert_id}` — persist analysis result
- `POST /webhook/tradingview` — alternative endpoint
- `POST /log` — manual behaviour logging
- `GET /logs`, `/logs/{symbol}`, `/attention` — behaviour queries
- `GET /alerts`, `/alerts/{symbol}` — alert queries
- `GET /analysis`, `/analysis/{symbol}` — analysis result queries
- `GET /stats`, `/health`

---

## Email Notifier (v2.0 — Port Changed, New Endpoint)

**Location:** `email-notifier/`

**Changes from v1.x:**
- ✅ Port changed from 8001 → **8002**
- ✅ Added `send_alert_email()` method on `EmailNotifier` class
- ✅ Added `POST /send-alert` endpoint (called by integration-service)

**All existing report endpoints unchanged:**
- `POST /reports/daily`, `/reports/weekly`, `/reports/monthly`
- `GET /health`

---

## Scheduler (v2.0 — Bug Fixes)

**Location:** `scheduler/`

**Changes from v1.x:**
- ✅ Fixed `ImportError`: removed non-existent `JobErrorEvent`, `JobMissedEvent` imports (APScheduler 3.x uses `JobExecutionEvent` for all event types)
- ✅ Fixed `AttributeError`: `add_job()` return value used instead of `get_job()` for next_run_time
- ✅ Updated `EMAIL_NOTIFIER_URL` → `http://email-notifier:8002`

**5 scheduled jobs running:**
- Daily report: 5:00 PM EST
- Weekly report: Sunday 5:00 PM EST
- Monthly report: 1st of month 5:00 PM EST
- Data cleanup: Sunday 3:00 AM EST
- Health check: hourly

---

## Architecture Changes: v1.x → v2.0

| Aspect | v1.x | v2.0 |
|--------|------|------|
| TradingView target | port 8000 | **port 8004** |
| Services | 3 containers | **5 containers** |
| Analysis engine | Embedded library in webhook-receiver | **Standalone microservice :8001** |
| Email notifier port | 8001 | **8002** |
| Orchestration | alert_processor.py background task | **Integration service pipeline** |
| Analysis trigger | Per-alert background task | **Synchronous HTTP call from integration-service** |
| Error handling | Best-effort in background | **Retried, logged, partial-failure response** |

---

## Requirements Summary

| Setting | Value |
|---------|-------|
| TradingView entry point | `POST http://your-server:8004/webhook` |
| Patterns detected | 12 candlestick patterns |
| Analysis components | Pattern detection + MA20 + context rules + multi-TF |
| Immediate alerts | Email when confidence ≥ `CONFIDENCE_THRESHOLD` (default 0.75) |
| Scheduled reports | Daily 5PM EST, Weekly Sun 5PM, Monthly last day 5PM |
| Email providers | SMTP (Gmail), SendGrid, AWS SES |
| Data retention | 90 days (auto-pruned by scheduler) |
| Assets | 20+ (SPX500, BTCUSD, ETHUSD, alts, DeFi tokens) |

---

## Next Steps

1. ✅ Integration Service — Complete
2. ✅ Analysis Engine microservice — Complete
3. ✅ End-to-end pipeline verified
4. ✅ All services healthy
5. ⏳ Feed real TradingView OHLCV data to build up ohlcv.db for meaningful analysis
6. ⏳ Deploy to production VPS
7. ⏳ Configure TradingView webhooks for 20+ assets pointing to port 8004
8. ⏳ Integration tests (automated end-to-end coverage)

---

*Last updated: 2026-04-09 | Version: 2.0.0*
