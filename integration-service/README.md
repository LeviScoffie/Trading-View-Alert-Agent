# Integration Service

Central orchestrator for the TradingView Alert Agent.

**Port:** 8004  
**Role:** Primary TradingView webhook entry point. Coordinates the full pipeline across all downstream services and returns a unified response.

---

## Why This Service Exists

Without the integration service:
- Webhook Receiver stored alerts but didn't trigger analysis
- Analysis Engine had no data source
- Email Notifier only sent scheduled reports, not immediate alerts
- Services were isolated and didn't communicate

The Integration Service wires them all together with retry logic, timeout handling, and a unified response shape.

---

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | **Primary TradingView webhook endpoint** |
| `/health` | GET | Aggregate health of all downstream services |
| `/status/{alert_id}` | GET | Processing status for a stored alert |
| `/trigger-analysis` | POST | Manually trigger analysis without a webhook |

---

## Pipeline

Every `POST /webhook` runs this sequence synchronously:

```
1. POST webhook-receiver:8000/webhook     → store alert, get alert_id
2. POST analysis-engine:8001/analyze      → run analysis pipeline
3. POST webhook-receiver:8000/analysis/{alert_id} → persist analysis result
4. (if confidence >= threshold)
   POST email-notifier:8002/send-alert   → send immediate email
5. Return unified JSON (always HTTP 200)
```

Each step uses async httpx with 3-attempt exponential backoff (0.5s → 1s → 2s) and a 10s timeout. A failure in any step is logged and reported in `services.*` but never causes a non-200 response to TradingView.

---

## TradingView Configuration

**Webhook URL:**
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

---

## Example Responses

**Full success (confidence >= threshold):**
```json
{
  "status": "processed",
  "alert_id": 42,
  "symbol": "BTCUSD",
  "confidence": 0.85,
  "email_sent": true,
  "processing_time_ms": 312,
  "timestamp": "2026-04-09T12:00:01Z",
  "services": {
    "webhook": "success",
    "analysis": "success",
    "email": "success"
  }
}
```

**Confidence below threshold:**
```json
{
  "status": "processed",
  "alert_id": 43,
  "symbol": "ETHUSD",
  "confidence": 0.45,
  "email_sent": false,
  "processing_time_ms": 210,
  "services": {
    "webhook": "success",
    "analysis": "success",
    "email": "skipped"
  }
}
```

**Partial failure (analysis engine down):**
```json
{
  "status": "partial",
  "alert_id": 44,
  "symbol": "XAUUSD",
  "confidence": 0.0,
  "email_sent": false,
  "error": "Analysis Engine unavailable: timeout",
  "services": {
    "webhook": "success",
    "analysis": "failed",
    "email": "skipped"
  }
}
```

---

## Health Check

```bash
curl http://localhost:8004/health | python3 -m json.tool
```

```json
{
  "status": "healthy",
  "timestamp": "2026-04-09T12:00:00Z",
  "services": [
    {"name": "webhook-receiver", "status": "healthy", "response_time_ms": 12.5},
    {"name": "analysis-engine",  "status": "healthy", "response_time_ms": 45.2},
    {"name": "email-notifier",   "status": "healthy", "response_time_ms": 8.1},
    {"name": "scheduler",        "status": "healthy", "response_time_ms": 6.3}
  ]
}
```

---

## Manual Analysis Trigger

```bash
curl -X POST http://localhost:8004/trigger-analysis \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSD", "timeframe": "4H", "force_email": false}'
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_RECEIVER_URL` | `http://webhook-receiver:8000` | Webhook receiver URL |
| `ANALYSIS_ENGINE_URL` | `http://analysis-engine:8001` | Analysis engine URL |
| `EMAIL_NOTIFIER_URL` | `http://email-notifier:8002` | Email notifier URL |
| `SCHEDULER_URL` | `http://scheduler:8003` | Scheduler URL (health check only) |
| `CONFIDENCE_THRESHOLD` | `0.75` | Email trigger threshold (0–1) |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Per-call timeout |
| `MAX_RETRIES` | `3` | Retry attempts per call |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8004` | Listen port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Docker

```bash
docker build -t integration-service .

docker run -d \
  -p 8004:8004 \
  -e WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000 \
  -e ANALYSIS_ENGINE_URL=http://analysis-engine:8001 \
  -e EMAIL_NOTIFIER_URL=http://email-notifier:8002 \
  integration-service
```

---

## Local Development

```bash
pip install -r requirements.txt
uvicorn integration_service:app --reload --port 8004
```

---

## File Reference

| File | Purpose |
|------|---------|
| `integration_service.py` | FastAPI app — 4 endpoints |
| `orchestrator.py` | Core pipeline logic (store → analyze → persist → email) |
| `clients.py` | Async httpx wrappers with retry + timeout |
| `models.py` | Pydantic request/response models |
| `config.py` | pydantic-settings configuration |
| `Dockerfile` | Container setup |
| `requirements.txt` | fastapi, uvicorn, httpx, pydantic-settings |

---

*Part of TradingView Alert Agent v2.0*
