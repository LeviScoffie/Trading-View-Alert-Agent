# Webhook Receiver

Alert storage and behaviour logging service for the TradingView Alert Agent.

**Port:** 8000  
**Role:** Pure data layer — stores alerts, analysis results, and manual behaviour logs. No orchestration logic.

> In v2.0, TradingView webhooks point to the **Integration Service** (port 8004), not this service directly. The integration service calls this service internally.

---

## Endpoints

### Storage (called by Integration Service)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Store an incoming alert — returns `alert_id` |
| `/analysis/{alert_id}` | POST | Persist analysis result from analysis-engine |

### Query

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/alerts` | GET | Recent alerts |
| `/alerts/{symbol}` | GET | Alerts for a specific symbol |
| `/analysis` | GET | Recent analysis results |
| `/analysis/{symbol}` | GET | Analysis results for a specific symbol |
| `/logs` | GET | Recent manual behaviour logs |
| `/logs/{symbol}` | GET | Behaviour logs for a specific symbol |
| `/attention` | GET | Attention heatmap (symbols by log frequency) |
| `/stats` | GET | Database statistics |
| `/health` | GET | Health check |

### Behaviour Logging

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/log` | POST | Add a manual behaviour log entry |
| `/webhook/tradingview` | POST | Alternative webhook storage endpoint |

---

## Store Alert

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSD","close":65000,"interval":"1D"}'
```

Response:
```json
{"status": "received", "alert_id": 42, "symbol": "BTCUSD", "received_at": "..."}
```

---

## Manual Behaviour Logging

```bash
# Add terminal alias
alias tv='function _tv(){ curl -s -X POST "http://localhost:8000/log" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$1\",\"timeframe\":\"$2\",\"note\":\"$3\"}" | python3 -m json.tool; }; _tv'

# Usage
tv BTCUSD 4H "accumulation at support"
tv MORPHOUSDT 1D "watching weekly close"
```

---

## Database Schema

Three tables in `alerts.db`:

```sql
-- Incoming TradingView alerts
alerts (id, symbol, price, message, alert_time, received_at, raw_payload, processed)

-- Manual behaviour entries
behavior_logs (id, timestamp, symbol, timeframe, note, source)

-- Analysis results from analysis-engine (written by integration-service)
analysis_results (id, alert_id, symbol, timeframe, confidence, recommendation,
                  patterns_json, ma20_json, context_json, full_result_json, created_at)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `/app/data/alerts.db` | SQLite database path |
| `WEBHOOK_SECRET` | `""` | HMAC-SHA256 secret (optional; leave blank for local testing) |
| `CONFIDENCE_THRESHOLD` | `0.75` | Legacy config — no longer used for triggering email |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Docker

```bash
docker build -t webhook-receiver .

docker run -d \
  -p 8000:8000 \
  -v tv_data:/app/data \
  webhook-receiver
```

---

## Local Development

```bash
pip install -r requirements.txt
uvicorn webhook_receiver:app --reload --port 8000
```

---

## File Reference

| File | Purpose |
|------|---------|
| `webhook_receiver.py` | FastAPI app — all endpoints |
| `database.py` | SQLite schema and operations |
| `config.py` | Environment configuration |
| `Dockerfile` | Container setup |
| `requirements.txt` | Dependencies |

---

*Part of TradingView Alert Agent v2.0*
