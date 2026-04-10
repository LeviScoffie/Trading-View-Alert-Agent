# Production Deployment Guide

"The real thing" means two things: a permanent server (not your laptop) and real TradingView alerts on actual charts.

---

## Step 1 — Get a VPS

Cheapest options that work fine for this:
- **Hetzner CX22** — €4/month (best value, EU servers) → [hetzner.com](https://hetzner.com)
- **DigitalOcean Basic Droplet** — $6/month → [digitalocean.com](https://digitalocean.com)

Pick **Ubuntu 24.04**, 2GB RAM minimum. Save the IP address they give you.

---

## Step 2 — Set up the server

SSH in and install Docker:
```bash
ssh root@YOUR_SERVER_IP

# Install Docker
curl -fsSL https://get.docker.com | sh

# Verify
docker --version
```

---

## Step 3 — Deploy the app

```bash
# Clone the repo
git clone https://github.com/LeviScoffie/Trading-View-Alert-Agent.git
cd Trading-View-Alert-Agent
git checkout claudecode-version

# Create your .env
nano .env
```

Paste your `.env` contents:
```env
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM=your@gmail.com
EMAIL_TO=your@gmail.com
CONFIDENCE_THRESHOLD=0.75
LOG_LEVEL=INFO
SCHEDULE_TIMEZONE=America/New_York
```

```bash
# Start all 5 services
docker compose up -d

# Verify all healthy (wait ~45s)
docker ps
```

---

## Step 4 — Open the firewall

```bash
# On the server
ufw allow 8004
ufw allow 22
ufw enable
```

On DigitalOcean/Hetzner also open port `8004` in their web dashboard under **Networking → Firewall**.

---

## Step 5 — Configure TradingView

1. Open any chart on a symbol you actually trade
2. Add your strategy/indicator alert condition
3. Click **Alert** → **Notifications** → enable **Webhook URL**
4. Enter: `http://YOUR_SERVER_IP:8004/webhook`
5. In the **Message** box paste:

```json
{
  "symbol": "{{ticker}}",
  "open": {{open}},
  "high": {{high}},
  "low": {{low}},
  "close": {{close}},
  "volume": {{volume}},
  "time": "{{time}}",
  "interval": "{{interval}}",
  "message": "{{strategy.order.action}}"
}
```

6. Set alert frequency to **Once Per Bar Close** (recommended)
7. Save

> **Note:** TradingView requires **Essential+ plan** ($15/month) for webhook delivery. Free/Pro plans cannot send webhooks.

---

## Step 6 — Seed historical data and verify

The analysis engine needs 20+ candles per symbol before confidence scores above 0. Run this once after deployment to seed data and confirm the full pipeline works:

```bash
# Seed 25 candles
for i in $(seq 1 25); do
  CLOSE=$((64000 + RANDOM % 4000))
  OPEN=$((64000 + RANDOM % 4000))
  HIGH=$(( (CLOSE > OPEN ? CLOSE : OPEN) + RANDOM % 300 ))
  LOW=$(( (CLOSE < OPEN ? CLOSE : OPEN) - RANDOM % 300 ))
  DAY=$(printf "%02d" $i)
  curl -s -X POST http://localhost:8004/webhook \
    -H "Content-Type: application/json" \
    -d "{\"symbol\":\"BTCUSD\",\"open\":$OPEN,\"high\":$HIGH,\"low\":$LOW,\"close\":$CLOSE,\"volume\":1200,\"time\":\"2026-03-${DAY}T12:00:00\",\"interval\":\"1D\",\"message\":\"candle $i\"}" > /dev/null
  echo "Candle $i sent"
done

# Fire a test alert and check the response
curl -s -X POST http://localhost:8004/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSD","open":65000,"high":67800,"low":64800,"close":67500,"volume":3200,"time":"2026-04-10T15:00:00","interval":"1D","message":"breakout"}' \
  | python3 -m json.tool
```

You're looking for:
```json
{
    "alert_id": 27,
    "confidence": 0.84,
    "email_sent": true,
    "services": {
        "webhook": "success",
        "analysis": "success",
        "email": "success"
    }
}
```

Watch live logs as TradingView alerts come in:
```bash
docker compose logs -f integration-service
```

---

## What happens per alert

1. TradingView fires → hits `YOUR_SERVER_IP:8004/webhook`
2. Alert stored in SQLite → analysis engine runs pattern detection + MA20
3. If confidence ≥ 0.75 → email sent immediately
4. Daily summary report arrives at 5 PM EST
