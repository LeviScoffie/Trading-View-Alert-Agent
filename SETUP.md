# TradingView Alert Agent — Setup Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (local development only)
- TradingView account (Essential+ for webhooks)
- SMTP email credentials (Gmail recommended)

---

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/LeviScoffie/Trading-View-Alert-Agent.git
cd tradingview-alert-agent

cp .env.example .env
nano .env   # Add SMTP credentials (see section below)
```

### 2. Configure Email (Required)

**Gmail:**
1. Go to https://myaccount.google.com/apppasswords
2. Generate an app password for "Mail"
3. Add to `.env`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=your_email@gmail.com
```

### 3. Start All Services

```bash
docker-compose up -d

# Single health check covers all 5 services
curl http://localhost:8004/health
```

Expected:
```json
{
  "status": "healthy",
  "services": [
    {"name": "webhook-receiver", "status": "healthy", "response_time_ms": 12},
    {"name": "analysis-engine",  "status": "healthy", "response_time_ms": 45},
    {"name": "email-notifier",   "status": "healthy", "response_time_ms": 8},
    {"name": "scheduler",        "status": "healthy", "response_time_ms": 6}
  ]
}
```

### 4. Configure TradingView

**Webhook URL** (point all your TradingView alerts here):
```
http://your-server-ip:8004/webhook
```

**Message template** (paste into the TradingView alert "Message" box):
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

> **Note:** Webhook alerts require TradingView Essential+ plan.

**Alert naming convention** (encodes your conviction into behaviour tracking):
```
BTCUSD - high conviction - weekly engulfing
MORPHOUSDT - watching - support test
ETHUSD - set and forget - 200MA
```

### 5. Test the System

**Send a test webhook:**
```bash
curl -s -X POST http://localhost:8004/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSD","price":65000,"timeframe":"1D","message":"Test alert"}' \
  | python3 -m json.tool
```

Expected response:
```json
{
  "status": "processed",
  "alert_id": 1,
  "symbol": "BTCUSD",
  "confidence": 0.0,
  "email_sent": false,
  "processing_time_ms": 85,
  "services": {
    "webhook": "success",
    "analysis": "success",
    "email": "skipped"
  }
}
```

> **Note:** `confidence: 0.0` is expected on a fresh install — the analysis engine needs OHLCV history to detect patterns. Confidence rises as alert data accumulates.

**Manually trigger a daily report:**
```bash
curl -X POST http://localhost:8002/reports/daily
```

**Manually trigger a job via scheduler:**
```bash
curl http://localhost:8003/jobs                          # list job IDs
curl -X POST http://localhost:8003/jobs/daily_report/trigger
```

**Check recent alerts:**
```bash
curl http://localhost:8000/alerts | python3 -m json.tool
```

**Check analysis results:**
```bash
curl http://localhost:8000/analysis | python3 -m json.tool
curl http://localhost:8000/analysis/BTCUSD | python3 -m json.tool
```

**Query SQLite directly:**
```bash
docker-compose exec webhook-receiver sqlite3 /app/data/alerts.db \
  "SELECT id, symbol, price, received_at FROM alerts ORDER BY received_at DESC LIMIT 5;"
```

---

## Service Ports

| Port | Service | Expose Publicly? |
|------|---------|-----------------|
| 8004 | integration-service | **Yes** — TradingView webhook target |
| 8000 | webhook-receiver | No (internal) |
| 8001 | analysis-engine | No (internal) |
| 8002 | email-notifier | No (internal) |
| 8003 | scheduler | No (internal) |

---

## VPS Deployment (Hetzner / DigitalOcean)

### 1. Transfer Files

```bash
scp -r tradingview-alert-agent user@your-vps-ip:/home/user/
```

### 2. Configure for Production

```bash
# .env — set a strong webhook secret
WEBHOOK_SECRET=your-strong-random-secret
```

**Open only port 8004 on the firewall:**
```bash
sudo ufw allow 8004/tcp
sudo ufw reload
```

### 3. Start

```bash
cd /home/user/tradingview-alert-agent
docker-compose up -d
```

### 4. Optional — HTTPS with nginx + certbot

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

nginx config (proxy only port 8004):
```nginx
server {
    server_name your-domain.com;
    location / {
        proxy_pass http://localhost:8004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

TradingView webhook URL:
```
https://your-domain.com/webhook
```

---

## Local Development

```bash
# Develop a single service locally
python -m venv venv
source venv/bin/activate

# webhook-receiver
pip install -r webhook-receiver/requirements.txt
cd webhook-receiver && uvicorn webhook_receiver:app --reload --port 8000

# analysis-engine
pip install -r analysis-engine/requirements.txt
cd analysis-engine && uvicorn api:app --reload --port 8001

# integration-service
pip install -r integration-service/requirements.txt
cd integration-service && uvicorn integration_service:app --reload --port 8004
```

---

## Manual Behaviour Logging

Add this alias to `~/.zshrc` or `~/.bashrc`:

```bash
alias tv='function _tv(){ curl -s -X POST "http://localhost:8000/log" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$1\",\"timeframe\":\"$2\",\"note\":\"$3\"}" | python3 -m json.tool; }; _tv'
```

Usage:
```bash
tv BTCUSD 4H "accumulation at support"
tv MORPHOUSDT 1D "watching weekly close"
```

---

## Troubleshooting

### Services won't start

```bash
docker-compose logs integration-service
docker-compose logs analysis-engine
docker-compose logs webhook-receiver
docker-compose logs email-notifier
docker-compose logs scheduler

# Port conflict
lsof -i :8004
```

### Emails not sending

```bash
# Test SMTP connection
docker-compose exec email-notifier python -c "
import smtplib
s = smtplib.SMTP('smtp.gmail.com', 587)
s.starttls()
s.login('your_email@gmail.com', 'your_app_password')
print('SMTP OK')
s.quit()
"

# Trigger test report
curl -X POST http://localhost:8002/reports/daily
```

### Webhook not processing

```bash
# Check integration service pipeline
curl -s -X POST http://localhost:8004/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"TEST","price":100}' | python3 -m json.tool

# The response shows per-service status
# services.webhook: "success" → alert was stored
# services.analysis: "success" → analysis ran
# services.email: "skipped" → confidence below threshold (expected)
```

### Analysis always returns confidence 0.0

This is expected on a fresh install. The analysis engine needs OHLCV history in `ohlcv.db` to detect patterns. Confidence rises as TradingView alert payloads include OHLCV candle data that gets stored. Use the full template with `{{open}}`, `{{high}}`, `{{low}}`, `{{close}}`, `{{volume}}` fields to feed data to the engine.

### Scheduler not triggering reports

```bash
curl http://localhost:8003/jobs       # view next run times
curl http://localhost:8003/dashboard  # system overview

# Manually trigger
curl -X POST http://localhost:8003/jobs/daily_report/trigger
```

---

## Maintenance

### View logs

```bash
docker-compose logs -f                      # all services
docker-compose logs -f integration-service  # specific service
```

### Restart a service

```bash
docker-compose restart integration-service
```

### Backup databases

```bash
mkdir -p backups
docker run --rm \
  -v tradingview-alert-agent_tv_data:/data \
  -v $(pwd)/backups:/backup \
  alpine sh -c "cp /data/*.db /backup/ && echo 'Backup done'"
```

### Rebuild after code changes

```bash
docker-compose build
docker-compose up -d
```

### Stop everything

```bash
docker-compose down
```

---

## Environment Variables Reference

```bash
# ── Required ──────────────────────────────────────────────────────────
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_FROM=your_email@gmail.com
EMAIL_TO=recipient@example.com

# ── Analysis ──────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD=0.75    # Email sent when confidence >= this (0–1)

# ── Schedule (defaults shown) ─────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
DAILY_REPORT_HOUR=17
WEEKLY_REPORT_HOUR=17
MONTHLY_REPORT_HOUR=17
SCHEDULE_TIMEZONE=America/New_York

# ── Security (recommended for production) ─────────────────────────────
WEBHOOK_SECRET=your-hmac-secret

# ── Logging ───────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

---

## Next Steps

1. Set `WEBHOOK_SECRET` in `.env` for production security
2. Create TradingView alerts for your tracked assets using the naming convention
3. Verify the first daily report arrives at 5 PM EST
4. Tune `CONFIDENCE_THRESHOLD` to control email sensitivity
5. Add the terminal `tv` alias for manual behaviour logging

---

**Support:** See [DESIGN.md](DESIGN.md) for architecture details and [CAVEATS.md](CAVEATS.md) for known limitations.
