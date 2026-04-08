
# TradingView Alert Agent - Setup Guide

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- TradingView account (free or paid)
- SMTP email credentials (Gmail recommended)

## Quick Start

### 1. Clone and Configure

```bash
cd /home/node/.openclaw/workspace/projects/tradingview-alert-agent

# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

### 2. Configure Email (Required for notifications)

**For Gmail:**
1. Go to https://myaccount.google.com/apppasswords
2. Generate an app password for "Mail"
3. Add to `.env`:
   ```
   SMTP_USER=your_email@gmail.com
   SMTP_PASS=your_16_char_app_password
   EMAIL_TO=your_email@gmail.com
   ```

**For other providers:**
- Update `SMTP_HOST` and `SMTP_PORT` accordingly
- Ensure SMTP authentication is enabled

### 3. Start the Service

```bash
# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify health
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "timestamp": "...", "version": "1.0.0"}
```

### 4. Install Browser Extension

**Chrome/Edge:**
1. Open `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `extension/` folder
5. Extension icon should appear in toolbar

**Configure Extension:**
1. Click extension icon
2. Set Backend URL to `http://localhost:8000` (or your VPS URL)
3. Verify "Active - Tracking enabled" status

### 5. Configure TradingView Webhooks

**Create Alert in TradingView:**
1. Open any chart on TradingView
2. Click "Alert" button (clock icon) or press `Alt+A`
3. Configure alert conditions (price, indicators, etc.)
4. In "Webhook URL" field, enter:
   ```
   http://your-vps-ip:8000/webhook/tradingview
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

### 6. Test the System

**Test webhook endpoint:**
```bash
curl -X POST http://localhost:8000/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "price": 65000,
    "timeframe": "1D",
    "alert_name": "Test Alert",
    "message": "Test webhook"
  }'
```

**Test daily report manually:**
```bash
curl -X POST http://localhost:8000/api/reports/daily
```

**Check database:**
```bash
docker-compose exec tradingview-agent sqlite3 /data/tradingview_agent.db "SELECT * FROM alerts LIMIT 5;"
```

## VPS Deployment (Hetzner)

### 1. Transfer Files

```bash
# From your local machine
scp -r projects/tradingview-alert-agent rodgers@your-vps-ip:/home/rodgers/.openclaw/workspace/projects/
```

### 2. Configure for Public Access

**Update `.env`:**
```
WEBHOOK_HOST=0.0.0.0
```

**Open firewall port:**
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

### 3. Start on VPS

```bash
cd /home/rodgers/.openclaw/workspace/projects/tradingview-alert-agent
docker-compose up -d
```

### 4. Configure TradingView with VPS URL

```
Webhook URL: http://your-vps-ip:8000/webhook/tradingview
```

**Optional - Use domain with HTTPS:**
1. Point domain to VPS IP
2. Install nginx + certbot
3. Reverse proxy to port 8000
4. Update TradingView webhook to `https://your-domain.com/webhook/tradingview`

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run with hot reload
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs tradingview-agent

# Common issues:
# - Port 8000 already in use: change WEBHOOK_PORT
# - Database permission: chmod 755 ./data
```

### Emails not sending
```bash
# Test SMTP connection
docker-compose exec tradingview-agent python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your_email@gmail.com', 'your_app_password')
print('SMTP OK')
"
```

### Extension not tracking
1. Open TradingView chart
2. Open browser DevTools (F12)
3. Check Console for `[TV Agent]` messages
4. Verify extension is enabled in `chrome://extensions/`

### Webhook not receiving alerts
1. Verify TradingView alert has webhook enabled
2. Check webhook URL is correct (no trailing slash)
3. Verify JSON message format is valid
4. Check firewall allows inbound on port 8000

## Maintenance

### View logs
```bash
docker-compose logs -f tradingview-agent
```

### Restart service
```bash
docker-compose restart
```

### Backup database
```bash
cp ./data/tradingview_agent.db ./data/tradingview_agent.db.backup.$(date +%Y%m%d)
```

### Update service
```bash
docker-compose pull
docker-compose up -d --force-recreate
```

### Stop service
```bash
docker-compose down
```

## Next Steps

1. **Create TradingView alerts** for your 20+ tracked assets
2. **Customize analysis thresholds** in `.env` if needed
3. **Monitor first daily report** to verify email delivery
4. **Review browser extension data** in popup stats
5. **Expand pattern detection** as needed (see DESIGN.md)

---

**Support:** Check DESIGN.md for architecture details and caveats.
