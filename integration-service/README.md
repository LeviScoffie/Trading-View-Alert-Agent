# Integration Service

The Integration Service is the orchestration layer for the TradingView Alert Agent. It connects all services via HTTP APIs and manages the flow from webhook receipt to email notification.

## Architecture

```
TradingView Alert
       │
       ▼
┌─────────────────────┐
│ Integration Service │  Port 8004
│ POST /webhook       │
└──────────┬──────────┘
           │ 1. Store alert in Webhook Receiver
           │ 2. Call Analysis Engine
           ▼
┌─────────────────────┐
│ Analysis Engine     │  Port 8001
│ POST /analyze       │
└──────────┬──────────┘
           │ Return analysis
           ▼
┌─────────────────────┐
│ Integration Service │
│ (check confidence)  │
└──────────┬──────────┘
           │ High confidence (>= 0.75)?
           ├─ YES → Call Email Notifier
           └─ NO  → Done
           ▼
┌─────────────────────┐
│ Email Notifier      │  Port 8002
│ POST /send-alert    │
│ (immediate email)   │
└─────────────────────┘
```

## API Endpoints

### POST /webhook
Receive TradingView webhook and orchestrate full processing flow.

**Request Body:**
```json
{
  "symbol": "BTCUSD",
  "price": 45000.00,
  "message": "Bullish Engulfing detected",
  "time": "2024-01-15T10:30:00Z",
  "timeframe": "1D"
}
```

**Response:**
```json
{
  "alert_id": 123,
  "symbol": "BTCUSD",
  "status": "processed_with_email",
  "analysis": { ... },
  "email_sent": true,
  "confidence": 0.85,
  "message": "Alert processed. Confidence: 0.85, Email sent: true",
  "processed_at": "2024-01-15T10:30:05Z"
}
```

### GET /status/{alert_id}
Get the full alert + analysis status.

**Response:**
```json
{
  "alert_id": 123,
  "symbol": "BTCUSD",
  "received_at": "2024-01-15T10:30:00Z",
  "processed": true,
  "analysis": { ... }
}
```

### POST /trigger-analysis
Manually trigger analysis for a symbol.

**Request Body:**
```json
{
  "symbol": "ETHUSD",
  "timeframe": "4H"
}
```

**Response:** Same as `/webhook`

### GET /health
Health check endpoint that checks all connected services.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "integration_service": "healthy",
  "services": [
    {
      "name": "webhook-receiver",
      "url": "http://webhook-receiver:8000",
      "status": "healthy",
      "response_time_ms": 12.5
    },
    {
      "name": "analysis-engine",
      "url": "http://analysis-engine:8001",
      "status": "healthy",
      "response_time_ms": 45.2
    },
    {
      "name": "email-notifier",
      "url": "http://email-notifier:8002",
      "status": "healthy",
      "response_time_ms": 8.1
    },
    {
      "name": "scheduler",
      "url": "http://scheduler:8003",
      "status": "healthy",
      "response_time_ms": 5.3
    }
  ]
}
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_RECEIVER_URL` | http://webhook-receiver:8000 | Webhook Receiver service URL |
| `ANALYSIS_ENGINE_URL` | http://analysis-engine:8001 | Analysis Engine service URL |
| `EMAIL_NOTIFIER_URL` | http://email-notifier:8002 | Email Notifier service URL |
| `SCHEDULER_URL` | http://scheduler:8003 | Scheduler service URL |
| `HOST` | 0.0.0.0 | Bind host |
| `PORT` | 8004 | Bind port |
| `LOG_LEVEL` | INFO | Logging level |
| `CONFIDENCE_THRESHOLD` | 0.75 | Minimum confidence for email alerts |
| `REQUEST_TIMEOUT` | 30 | HTTP request timeout in seconds |
| `WEBHOOK_SECRET` | None | Secret for webhook signature validation |

## Flow Logic

1. **Receive Alert**: TradingView sends webhook to `/webhook`
2. **Store Alert**: Integration service stores alert in Webhook Receiver
3. **Analyze**: Integration service calls Analysis Engine for symbol analysis
4. **Check Confidence**: If analysis confidence >= threshold, proceed to email
5. **Send Email**: Integration service calls Email Notifier to send immediate alert
6. **Return Result**: Combined response with alert ID, analysis, and email status

## Testing

```bash
# Test webhook endpoint
curl -X POST http://localhost:8004/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "price": 45000.00,
    "message": "Test alert",
    "timeframe": "1D"
  }'

# Test manual analysis trigger
curl -X POST http://localhost:8004/trigger-analysis \
  -H "Content-Type: application/json" \
  -d '{"symbol": "ETHUSD", "timeframe": "4H"}'

# Check health
curl http://localhost:8004/health

# Get alert status
curl http://localhost:8004/status/1
```

## Files

- `integration_service.py` - FastAPI application with endpoints
- `orchestrator.py` - Core flow orchestration logic
- `clients.py` - HTTP clients for each service
- `models.py` - Pydantic models for inter-service communication
- `config.py` - Configuration settings
- `Dockerfile` - Container setup
- `requirements.txt` - Python dependencies
