# Email Notifier

Sends immediate alert emails and scheduled analysis reports for the TradingView Alert Agent.

**Port:** 8002  
**Role:** Email delivery — triggered by the Integration Service (immediate alerts) and the Scheduler (scheduled reports). Does not self-schedule.

---

## Endpoints

| Endpoint | Method | Caller | Description |
|----------|--------|--------|-------------|
| `/send-alert` | POST | Integration Service | Send immediate alert email (high-confidence signal) |
| `/reports/daily` | POST | Scheduler | Generate + send daily summary report |
| `/reports/weekly` | POST | Scheduler | Generate + send weekly summary report |
| `/reports/monthly` | POST | Scheduler | Generate + send monthly summary report |
| `/health` | GET | All | Health check |

---

## Immediate Alerts

Called by the Integration Service when `confidence >= CONFIDENCE_THRESHOLD`:

```bash
curl -X POST http://localhost:8002/send-alert \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "analysis": {
      "context": {"confidence": 0.85, "recommendation": "consider_long", "reasoning": "..."},
      "patterns": [{"type": "bullish_engulfing", "confidence": 0.85}],
      "ma20": {"trend": "bullish", "distance_pct": 3.17}
    },
    "priority": "high"
  }'
```

Response:
```json
{"status": "sent", "symbol": "BTCUSD"}
```

---

## Scheduled Reports

```bash
# Trigger manually (also called by scheduler on cron)
curl -X POST http://localhost:8002/reports/daily
curl -X POST http://localhost:8002/reports/weekly
curl -X POST http://localhost:8002/reports/monthly

# Trigger a specific date
curl -X POST http://localhost:8002/reports/daily \
  -H "Content-Type: application/json" \
  -d '{"report_date": "2026-04-08"}'
```

---

## Email Format

- **HTML** with dark-themed styling (Jinja2 templates)
- Pattern badges with confidence scores (colour-coded green/yellow/red)
- MA20 status with visual indicator
- Multi-timeframe alignment grid (1W/1D/4H/1H)
- Context reasoning section
- 5-level recommendation scale
- Plain-text fallback

---

## Email Providers

Configure via `EMAIL_PROVIDER` in `.env`:

| Provider | `EMAIL_PROVIDER` | Required Variables |
|----------|-----------------|-------------------|
| Gmail / SMTP | `smtp` (default) | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| SendGrid | `sendgrid` | `SENDGRID_API_KEY` |
| AWS SES | `aws_ses` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password / app password |
| `EMAIL_FROM` | — | Sender address |
| `EMAIL_TO` | — | Recipient address |
| `EMAIL_NOTIFIER_DB_PATH` | `/app/data/alerts.db` | Alerts database |
| `EMAIL_NOTIFIER_OHLCV_DB_PATH` | `/app/data/ohlcv.db` | OHLCV database |
| `DAILY_REPORT_HOUR` | `17` | Daily report hour (EST) |
| `WEEKLY_REPORT_HOUR` | `17` | Weekly report hour (EST) |
| `MONTHLY_REPORT_HOUR` | `17` | Monthly report hour (EST) |
| `SCHEDULE_TIMEZONE` | `America/New_York` | Timezone for report scheduling |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Docker

```bash
docker build -t email-notifier .

docker run -d \
  -p 8002:8002 \
  -v tv_data:/app/data \
  -e SMTP_USER=your@gmail.com \
  -e SMTP_PASSWORD=your_app_password \
  -e EMAIL_FROM=your@gmail.com \
  -e EMAIL_TO=recipient@example.com \
  email-notifier
```

---

## Local Development

```bash
pip install -r requirements.txt
uvicorn email_notifier:app --reload --port 8002
```

---

## File Reference

| File | Purpose |
|------|---------|
| `email_notifier.py` | FastAPI app — all endpoints + `EmailNotifier` class |
| `report_generator.py` | Queries databases, runs symbol analysis, builds report data |
| `templates.py` | Jinja2 HTML email templates |
| `config.py` | Email + schedule configuration |
| `Dockerfile` | Container setup |
| `requirements.txt` | Dependencies |

---

*Part of TradingView Alert Agent v2.0*
