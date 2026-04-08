# TradingView Alert Agent - Setup Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development only)
- TradingView account (Essential+ for webhooks)
- SMTP email credentials (Gmail recommended)

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/LeviScoffie/Trading-View-Alert-Agent.git
cd tradingview-alert-agent

# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

### 2. Configure Email (Required)

**For Gmail:**
1. Go to https://myaccount.google.com/apppasswords
2. Generate an app password for "Mail"
3. Add to `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_16_char_app_password
   EMAIL_FROM=your_email@gmail.com
   EMAIL_TO=your_email@gmail.com
   ```

**For other providers:**
- Update `SMTP_HOST` and `SMTP_PORT` accordingly
- Ensure SMTP authentication is enabled

### 3. Start All Services

```bash
# Build and start all 3 services
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify each service is healthy
curl http://localhost:8000/health   # webhook-receiver
curl http://localhost:8001/health   # email-notifier
curl http://localhost:8003/health   # scheduler
```

Expected response:
```json
{"status": "healthy", "timestamp": "...", "version": "1.0.0"}
```

### 4. Configure TradingView Webhooks

**Create Alert in TradingView:**
1. Open any chart on TradingView
2. Click "Alert" button (clock icon) or press `Alt+A`
3. Configure alert conditions (price, indicators, etc.)
4. In "Webhook URL" field, enter:
   ```
   http://your-server-ip:8000/webhook
   ```
5. In "Message" field, use this JSON template:
   ```json
   {
     "symbol": "{{ticker}}",
     "price": {{close}},
     "timeframe": "{{interval}}",
     "alert_name": "{{alertname}}",
     "message": "Alert triggered for {{ticker}}"
   }
   ```
6. Enable "Webhook" checkbox
7. Click "Create"

**Note:** Webhook alerts require TradingView paid plan (Essential+).

**Alert Naming Convention (for behavior context):**
```
{SYMBOL} - {conviction} - {context}

BTCUSD - high conviction - weekly engulfing
MORPHOUSDT - watching - support test
ETHUSD - set and forget - 200MA
```

### 5. Test the System

**Test webhook endpoint:**
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "price": 65000,
    "timeframe": "1D",
    "alert_name": "Test Alert",
    "message": "Test webhook"
  }'
```

**Manually trigger a daily report:**
```bash
curl -X POST http://localhost:8001/reports/daily
```

**Manually trigger a scheduled job via scheduler API:**
```bash
# List jobs and their IDs
curl http://localhost:8003/jobs

# Trigger a specific job by ID
curl -X POST http://localhost:8003/jobs/daily_report/trigger
```

**Check recent alerts:**
```bash
curl http://localhost:8000/alerts
```

**Check analysis results:**
```bash
curl http://localhost:8000/analysis
curl http://localhost:8000/analysis/BTCUSD
```

**Query the database directly:**
```bash
docker-compose exec webhook-receiver sqlite3 /app/data/alerts.db \
  "SELECT symbol, price, received_at FROM alerts ORDER BY received_at DESC LIMIT 5;"
```

## VPS Deployment (Hetzner / DigitalOcean)

### 1. Transfer Files

```bash
# From your local machine
scp -r tradingview-alert-agent user@your-vps-ip:/home/user/
```

### 2. Configure for Public Access

**Update `.env`:**
```
WEBHOOK_SECRET=your-strong-random-secret
```

**Open firewall ports:**
```bash
sudo ufw allow 8000/tcp   # webhook-receiver
sudo ufw allow 8001/tcp   # email-notifier
sudo ufw allow 8003/tcp   # scheduler
sudo ufw reload
```

> For production, expose only port 8000 publicly (TradingView needs it). Keep 8001 and 8003 internal or behind a reverse proxy.

### 3. Start on VPS

```bash
cd /home/user/tradingview-alert-agent
docker-compose up -d
```

### 4. Configure TradingView with VPS URL

```
Webhook URL: http://your-vps-ip:8000/webhook
```

**Optional - Use domain with HTTPS:**
1. Point domain to VPS IP
2. Install nginx + certbot
3. Reverse proxy to port 8000
4. Update TradingView webhook to `https://your-domain.com/webhook`

```bash
# Quick nginx + certbot setup
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Local Development

```bash
# Develop the webhook-receiver service
python -m venv venv
source venv/bin/activate
pip install -r webhook-receiver/requirements.txt
cd webhook-receiver && uvicorn webhook_receiver:app --reload --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Service won't start

```bash
# Check logs for a specific service
docker-compose logs webhook-receiver
docker-compose logs email-notifier
docker-compose logs scheduler

# Common issues:
# - Port already in use: check with lsof -i :8000
# - Volume permission: docker volume rm tradingview-alert-agent_tv_data
```

### Emails not sending

```bash
# Test SMTP connection
docker-compose exec email-notifier python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your_email@gmail.com', 'your_app_password')
print('SMTP OK')
"

# Trigger a test report manually
curl -X POST http://localhost:8001/reports/daily
```

### Webhook not receiving alerts

1. Verify TradingView alert has webhook enabled
2. Check webhook URL is correct (no trailing slash)
3. Verify JSON message format is valid
4. Check firewall allows inbound on port 8000
5. Test locally: `curl -X POST http://localhost:8000/webhook -H "Content-Type: application/json" -d '{"symbol":"TEST","price":100}'`

### Scheduler not triggering reports

```bash
# Check scheduler logs
docker-compose logs scheduler

# View all scheduled jobs
curl http://localhost:8003/jobs

# Check scheduler dashboard
curl http://localhost:8003/dashboard

# Manually trigger a report to confirm email-notifier works
curl -X POST http://localhost:8003/jobs/daily_report/trigger
```

### Checking analysis results

```bash
# View recent analysis via API
curl http://localhost:8000/analysis | python3 -m json.tool

# Or query directly
docker-compose exec webhook-receiver sqlite3 /app/data/alerts.db \
  "SELECT symbol, confidence, recommendation, created_at FROM analysis_results ORDER BY created_at DESC LIMIT 10;"
```

## Maintenance

### View logs

```bash
# All services
docker-compose logs -f

# Individual services
docker-compose logs -f webhook-receiver
docker-compose logs -f email-notifier
docker-compose logs -f scheduler
```

### Restart services

```bash
docker-compose restart
# or individually:
docker-compose restart webhook-receiver
```

### Backup databases

```bash
# Create a backup of all databases
docker run --rm -v tradingview-alert-agent_tv_data:/data \
  -v $(pwd)/backups:/backup alpine \
  sh -c "cp /data/*.db /backup/ && echo 'Backup complete'"
```

### Update services

```bash
docker-compose pull
docker-compose up -d --force-recreate
```

### Stop all services

```bash
docker-compose down
```

## Manual Behavior Logging

Add this alias to your shell profile (`~/.zshrc` or `~/.bashrc`) for quick manual logging:

```bash
alias tv='function _tv(){ curl -s -X POST "http://localhost:8000/log" \
  -H "Content-Type: application/json" \
  -d "{\"symbol\":\"$1\",\"timeframe\":\"$2\",\"note\":\"$3\"}" | python3 -m json.tool; }; _tv'
```

Usage:
```bash
tv BTCUSD 4H "looks like accumulation at support"
tv MORPHOUSDT 1D "watching weekly close"
```

## Next Steps

1. **Create TradingView alerts** for your 20+ tracked assets using the naming convention
2. **Set WEBHOOK_SECRET** in `.env` for security
3. **Monitor the first daily report** at 5 PM EST to verify email delivery
4. **Review analysis results** via `curl http://localhost:8000/analysis`
5. **Tune CONFIDENCE_THRESHOLD** in `.env` to control immediate email sensitivity (default: 0.75)

---

**Support:** Check [DESIGN.md](DESIGN.md) for architecture details and [CAVEATS.md](CAVEATS.md) for known limitations.
