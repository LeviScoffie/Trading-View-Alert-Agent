# TradingView Alert Agent - Setup Guide

## Architecture Overview

The TradingView Alert Agent consists of 5 microservices:

| Service | Port | Purpose |
|---------|------|---------|
| webhook-receiver | 8000 | Receives TradingView webhook alerts |
| analysis-engine | 8001 | Processes and analyzes alert data |
| email-notifier | 8002 | Sends email notifications |
| scheduler | 8003 | Manages scheduled tasks and reports |
| **integration-service** | **8004** | **Orchestrates webhook→analysis→email flow** |

## Prerequisites

- Docker and Docker Compose
- TradingView account (free or paid)
- SMTP email credentials (Gmail recommended)

## Primary Deployment: Docker Compose

### 1. Clone and Configure

```bash
cd /home/node/.openclaw/workspace/projects/tradingview-alert-agent

# Copy environment template
cp .env.example .env

# Edit with your credentials
nano .env
```

### 2. Configure Environment Variables

**Global Settings:**
```
# Database
DB_PATH=/data/tradingview_agent.db

# Redis (for inter-service communication)
REDIS_URL=redis://redis:6379

# Service ports (internal)
WEBHOOK_PORT=8000
ANALYSIS_PORT=8001
EMAIL_PORT=8002
SCHEDULER_PORT=8003
INTEGRATION_PORT=8004
```

**Email Configuration:**
```
# Email settings (required for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_16_char_app_password
EMAIL_TO=your_email@gmail.com
EMAIL_FROM=your_email@gmail.com
```

**Webhook Receiver Settings:**
```
# Webhook receiver
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8000
```

**Analysis Engine Settings:**
```
# Analysis engine
ANALYSIS_HOST=0.0.0.0
ANALYSIS_PORT=8001
```

**Email Notifier Settings:**
```
# Email notifier
EMAIL_HOST=0.0.0.0
EMAIL_PORT=8002
```

**Scheduler Settings:**
```
# Scheduler
SCHEDULER_HOST=0.0.0.0
SCHEDULER_PORT=8003
```

**Integration Service Settings:**
```
# Integration service
INTEGRATION_HOST=0.0.0.0
INTEGRATION_PORT=8004
CONFIDENCE_THRESHOLD=0.75
```

### 3. Start the Services

```bash
# Build and start all services
docker-compose up -d

# Check status of all services
docker-compose ps

# Check logs for specific service
docker-compose logs -f webhook-receiver
docker-compose logs -f analysis-engine
docker-compose logs -f email-notifier
docker-compose logs -f scheduler
docker-compose logs -f integration-service
```

### 4. Verify Health Checks

Each service has a health endpoint:

```bash
# Webhook Receiver
curl http://localhost:8000/health

# Analysis Engine
curl http://localhost:8001/health

# Email Notifier
curl http://localhost:8002/health

# Scheduler
curl http://localhost:8003/health

# Integration Service (checks all services)
curl http://localhost:8004/health
```

Expected responses:
```json
{"status": "healthy", "service": "webhook-receiver", "timestamp": "..."}
{"status": "healthy", "service": "analysis-engine", "timestamp": "..."}
{"status": "healthy", "service": "email-notifier", "timestamp": "..."}
{"status": "healthy", "service": "scheduler", "timestamp": "..."}
```

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

**Option A: Test via Integration Service (Recommended)**

The integration service orchestrates the full flow:
```bash
curl -X POST http://localhost:8004/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSD",
    "price": 65000,
    "timeframe": "1D",
    "message": "Test webhook via integration service"
  }'
```

This will:
1. Store the alert in webhook-receiver
2. Trigger analysis in analysis-engine
3. Send email if confidence >= 0.75
4. Return combined results

**Test manual analysis trigger:**
```bash
curl -X POST http://localhost:8004/trigger-analysis \
  -H "Content-Type: application/json" \
  -d '{"symbol": "ETHUSD", "timeframe": "4H"}'
```

**Run end-to-end test:**
```bash
python test_integration.py --host http://localhost:8004
```

**Option B: Test Individual Services**

**Test webhook endpoint directly:**
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
curl -X POST http://localhost:8003/api/reports/daily
```

**Check database:**
```bash
docker-compose exec webhook-receiver sqlite3 /data/tradingview_agent.db "SELECT * FROM alerts LIMIT 5;"
```

## Alternative Deployment: Service-by-Service

If you prefer to deploy services individually instead of using Docker Compose:

### 1. Individual Service Setup

**Start webhook-receiver:**
```bash
cd services/webhook-receiver
docker build -t webhook-receiver .
docker run -d --name webhook-receiver \
  -p 8000:8000 \
  --env-file ../.env \
  -v $(pwd)/data:/data \
  webhook-receiver
```

**Start analysis-engine:**
```bash
cd services/analysis-engine
docker build -t analysis-engine .
docker run -d --name analysis-engine \
  -p 8001:8001 \
  --env-file ../.env \
  analysis-engine
```

**Start email-notifier:**
```bash
cd services/email-notifier
docker build -t email-notifier .
docker run -d --name email-notifier \
  -p 8002:8002 \
  --env-file ../.env \
  email-notifier
```

**Start scheduler:**
```bash
cd services/scheduler
docker build -t scheduler .
docker run -d --name scheduler \
  -p 8003:8003 \
  --env-file ../.env \
  scheduler
```

### 2. Individual Health Checks

Check each service separately:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
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
ANALYSIS_HOST=0.0.0.0
EMAIL_HOST=0.0.0.0
SCHEDULER_HOST=0.0.0.0
```

**Open firewall ports:**
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
sudo ufw allow 8002/tcp
sudo ufw allow 8003/tcp
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

## Troubleshooting

### Webhook Receiver Issues
```bash
# Check logs
docker-compose logs -f webhook-receiver

# Common issues:
# - Port 8000 already in use: change WEBHOOK_PORT in .env
# - Database permission: chmod 755 ./data
```

### Analysis Engine Issues
```bash
# Check logs
docker-compose logs -f analysis-engine

# Common issues:
# - Can't connect to database
# - Can't communicate with Redis
# - Processing errors in alert data
```

### Email Notifier Issues
```bash
# Check logs
docker-compose logs -f email-notifier

# Test SMTP connection
docker-compose exec email-notifier python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your_email@gmail.com', 'your_app_password')
print('SMTP OK')
"
```

### Scheduler Issues
```bash
# Check logs
docker-compose logs -f scheduler

# Common issues:
# - Can't schedule recurring tasks
# - Connection issues with other services
# - Cron expression errors
```

### General Troubleshooting
```bash
# Check all services status
docker-compose ps

# Check all logs at once
docker-compose logs

# Check individual service logs
docker-compose logs -f webhook-receiver
docker-compose logs -f analysis-engine
docker-compose logs -f email-notifier
docker-compose logs -f scheduler

# Restart a specific service
docker-compose restart webhook-receiver

# Restart all services
docker-compose restart
```

## Maintenance

### View logs for specific service
```bash
docker-compose logs -f webhook-receiver
docker-compose logs -f analysis-engine
docker-compose logs -f email-notifier
docker-compose logs -f scheduler
```

### Restart service
```bash
docker-compose restart
# or restart specific service
docker-compose restart webhook-receiver
```

### Backup database
```bash
cp ./data/tradingview_agent.db ./data/tradingview_agent.db.backup.$(date +%Y%m%d)
```

### Update services
```bash
docker-compose pull
docker-compose up -d --force-recreate
```

### Stop services
```bash
docker-compose down
```

## Next Steps

1. **Create TradingView alerts** for your 20+ tracked assets
2. **Customize analysis thresholds** in `.env` if needed
3. **Monitor first daily report** to verify email delivery
4. **Review system performance** across all services
5. **Expand pattern detection** as needed (see DESIGN.md)

---

**Support:** Check DESIGN.md for architecture details and caveats.