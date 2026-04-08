# TradingView Webhook Receiver

A standalone FastAPI-based webhook receiver for TradingView alerts. Receives POST requests from TradingView, parses alert data, and stores it in SQLite for downstream processing.

## Features

- ✅ Receives TradingView webhook alerts via HTTP POST
- ✅ Parses JSON payload (symbol, price, message, timestamp)
- ✅ Stores alerts in SQLite database with indexing
- ✅ Returns HTTP 200 OK to confirm receipt
- ✅ Logs all incoming requests
- ✅ REST API for querying stored alerts
- ✅ Docker containerization
- ✅ Environment-based configuration

## Quick Start

### Using Docker (Recommended)

```bash
# Build the image
docker build -t tradingview-webhook .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --name tradingview-webhook \
  tradingview-webhook
```

### Using Python Directly

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run the server
python webhook_receiver.py
```

## Configuration

Environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DATABASE_PATH` | `data/alerts.db` | SQLite database file path |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `WEBHOOK_SECRET` | (empty) | **Optional** secret for HMAC-SHA256 signature validation |

## API Endpoints

### Health Check
```
GET /
GET /health
```
Returns server health status and database stats.

### Receive Webhook
```
POST /webhook
POST /webhook/tradingview
```

### Behavior Tracking
```
POST /log
GET /logs?limit=100
GET /logs/{symbol}?limit=100
GET /attention?days=7
```
Log and query manual market observations. See [Behavior Tracking](#behavior-tracking) section below.

Receives TradingView alert payload:

```json
{
  "symbol": "BTCUSD",
  "price": 45000.00,
  "message": "RSI Oversold",
  "time": "2026-04-08T10:30:00Z"
}
```

Response:
```json
{
  "status": "received",
  "alert_id": 1,
  "symbol": "BTCUSD",
  "received_at": "2026-04-08T10:30:05Z"
}
```

### Query Alerts
```
GET /alerts?limit=100
GET /alerts/{symbol}?limit=100
GET /stats
```

## TradingView Configuration

1. Create an alert in TradingView
2. Set "Webhook URL" to: `http://your-server:8000/webhook`
3. Use message format:
```json
{"symbol": "{{ticker}}", "price": {{close}}, "message": "{{strategy.order.action}}", "time": "{{time}}"}
```

## Webhook Signature Validation

To secure your webhook endpoint, enable HMAC-SHA256 signature validation:

### 1. Set the Webhook Secret

```bash
# In your .env file
WEBHOOK_SECRET=your-secret-key-here
```

### 2. TradingView Signature Header

When `WEBHOOK_SECRET` is configured, the receiver expects the signature in the `X-TradingView-Signature` header. The signature is computed as:

```
HMAC-SHA256(webhook_secret, raw_request_body)
```

### 3. Testing with Valid Signatures

Generate a valid signature and test the webhook:

```bash
# Set your secret
WEBHOOK_SECRET="my-secret-key"

# JSON payload
PAYLOAD='{"symbol": "BTCUSD", "price": 45000, "message": "Test alert"}'

# Generate HMAC-SHA256 signature
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')

echo "Signature: $SIGNATURE"

# Send request with signature header
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

### 4. Python Example

```python
import hmac
import hashlib
import requests

webhook_secret = "my-secret-key"
payload = '{"symbol": "BTCUSD", "price": 45000, "message": "Test alert"}'

# Generate signature
signature = hmac.new(
    webhook_secret.encode("utf-8"),
    payload.encode("utf-8"),
    hashlib.sha256
).hexdigest()

# Send request
response = requests.post(
    "http://localhost:8000/webhook",
    headers={
        "Content-Type": "application/json",
        "X-TradingView-Signature": signature
    },
    data=payload
)
print(response.json())
```

### 5. Query Parameter Fallback

If the header is not available, the signature can also be passed as a query parameter:

```bash
curl -X POST "http://localhost:8000/webhook?signature=$SIGNATURE" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSD", "price": 45000}'
```

### Security Notes

- If `WEBHOOK_SECRET` is **not set**, signature validation is **skipped** (useful for local testing)
- If `WEBHOOK_SECRET` is set, requests without a valid signature receive **401 Unauthorized**
- The receiver uses constant-time comparison to prevent timing attacks
- Keep your `WEBHOOK_SECRET` secure and rotate it periodically

## Database Schema

### Alerts Table
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    price REAL,
    message TEXT,
    alert_time TEXT,
    raw_payload TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);
```

### Behavior Logs Table
```sql
CREATE TABLE behavior_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    note TEXT,
    source TEXT DEFAULT 'manual'
);
```

## Project Structure

```
webhook-receiver/
├── webhook_receiver.py   # Main FastAPI application
├── database.py          # SQLite operations
├── config.py            # Configuration management
├── Dockerfile           # Container setup
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment file
└── README.md            # This file
```

## Behavior Tracking

The `/log` endpoint allows you to manually log market observations from the terminal or other tools. This builds a personal database of what you're watching and thinking about.

### Log a Behavior Observation

```bash
curl -X POST http://localhost:8000/log \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSD", "timeframe": "4H", "note": "looks like accumulation"}'
```

Response:
```json
{
  "status": "logged",
  "log_id": 1,
  "symbol": "BTCUSD",
  "timeframe": "4H",
  "timestamp": "2026-04-08T10:30:05Z"
}
```

### Query Behavior Logs

```bash
# Get recent logs
curl http://localhost:8000/logs

# Get logs for specific symbol
curl http://localhost:8000/logs/BTCUSD

# Get attention heatmap (most watched symbols)
curl http://localhost:8000/attention

# Get heatmap for last 30 days
curl http://localhost:8000/attention?days=30
```

### Shell Alias Setup

Add this to your `~/.zshrc` or `~/.bashrc`:

```bash
# TradingView behavior log alias
alias tv='function _tv(){ curl -s -X POST "http://localhost:8000/log" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$1\",\"timeframe\":\"$2\",\"note\":\"$3\"}" | python3 -m json.tool; }; _tv'
```

Usage:
```bash
# Log an observation
tv BTCUSD 4H "looks like accumulation"

# Log with empty timeframe
tv ETHUSD "" "breaking resistance"
```

### Attention Heatmap Query

The attention endpoint returns symbols ranked by how often you've logged them:

```bash
curl http://localhost:8000/attention | python3 -m json.tool
```

Example response:
```json
{
  "days": 7,
  "symbol_count": 3,
  "heatmap": [
    {
      "symbol": "BTCUSD",
      "observation_count": 12,
      "last_observed": "2026-04-08T10:30:05Z",
      "timeframes": "4H,1D"
    },
    {
      "symbol": "ETHUSD",
      "observation_count": 8,
      "last_observed": "2026-04-08T09:15:00Z",
      "timeframes": "1H,4H"
    }
  ]
}
```

## Testing

### Basic Testing (No Signature Validation)

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test webhook (simulate TradingView)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSD", "price": 45000, "message": "Test alert"}'

# Get recent alerts
curl http://localhost:8000/alerts

# Get stats
curl http://localhost:8000/stats
```

### Testing Behavior Tracking

```bash
# Log a manual observation
curl -X POST http://localhost:8000/log \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSD", "timeframe": "4H", "note": "accumulation pattern forming"}'

# Log another observation
curl -X POST http://localhost:8000/log \
  -H "Content-Type: application/json" \
  -d '{"symbol": "ETHUSD", "timeframe": "1H", "note": "volume spike"}'

# Query recent logs
curl http://localhost:8000/logs

# Query logs for specific symbol
curl http://localhost:8000/logs/BTCUSD

# Get attention heatmap
curl http://localhost:8000/attention

# Get 30-day heatmap
curl http://localhost:8000/attention?days=30
```

### Testing with Signature Validation

```bash
# Set your webhook secret
export WEBHOOK_SECRET="my-secret-key"

# Create payload
PAYLOAD='{"symbol": "BTCUSD", "price": 45000, "message": "Test alert"}'

# Generate HMAC-SHA256 signature (macOS/Linux)
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')

# Test with valid signature (should succeed)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: $SIGNATURE" \
  -d "$PAYLOAD"

# Test without signature (should fail with 401)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

# Test with invalid signature (should fail with 401)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-TradingView-Signature: invalid-signature" \
  -d "$PAYLOAD"

# Test with signature in query parameter
curl -X POST "http://localhost:8000/webhook?signature=$SIGNATURE" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
```

## Production Deployment

### Using Docker Compose

```yaml
version: '3.8'
services:
  webhook:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_PATH=/app/data/alerts.db
      - LOG_LEVEL=INFO
    restart: unless-stopped
```

### Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location /webhook {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Logs

Logs are written to:
- Console (stdout)
- `data/webhook.log` (file)

View logs:
```bash
# Docker
docker logs tradingview-webhook

# Local
tail -f data/webhook.log
```

## License

MIT
