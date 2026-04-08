# TradingView Alert Agent - Docker Deployment Guide

This document covers Docker deployment for the TradingView Alert Agent, a multi-service system for processing TradingView alerts, analyzing market data, and sending notifications.

## Architecture Overview

The system consists of 5 microservices:

```
                         ┌─────────────────────┐
                         │  Integration        │
 TradingView Alert ─────▶│  Service            │
                         │  Port: 8004         │
                         └──────────┬──────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Webhook        │◄────│  Analysis        │────▶│  Email          │
│  Receiver       │     │  Engine          │     │  Notifier       │
│  Port: 8000     │     │  Port: 8001      │     │  Port: 8002     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                         ┌───────▼────────┐
                         │   Scheduler    │
                         │   Port: 8003   │
                         └────────────────┘
```

### Service Responsibilities

1. **Integration Service** (Port 8004)
   - Orchestrates the complete alert processing flow
   - Receives TradingView webhooks as primary entry point
   - Coordinates webhook → analysis → email pipeline
   - Checks confidence threshold before sending emails
   - Provides unified health check for all services

2. **Webhook Receiver** (Port 8000)
   - Receives TradingView webhook alerts
   - Validates webhook signatures
   - Stores alerts in SQLite database

3. **Analysis Engine** (Port 8001)
   - Processes OHLCV data
   - Calculates moving averages
   - Generates trading signals with confidence scores

4. **Email Notifier** (Port 8002)
   - Sends email notifications for high-confidence signals
   - Configurable SMTP settings
   - HTML and plain text email support

5. **Scheduler** (Port 8003)
   - Manages periodic analysis jobs
   - Cron-based scheduling
   - Timezone-aware execution

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- curl (for health checks)

### 1. Clone and Configure

```bash
cd projects/tradingview-alert-agent

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Required Environment Variables

Edit `.env` and set these required values:

```bash
# Webhook security
WEBHOOK_SECRET=your_secure_random_string

# Email configuration
SMTP_HOST=smtp.gmail.com
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
EMAIL_TO=alerts@yourdomain.com

# Optional: Adjust analysis parameters
MA_PERIOD=20
CONFIDENCE_THRESHOLD=0.75
TIMEZONE=UTC
```

### 3. Build and Start

```bash
# Build all images and start services
docker-compose up --build -d

# Or without rebuilding if images exist
docker-compose up -d
```

### 4. Verify Deployment

```bash
# Check all services are running
docker-compose ps

# View logs
docker-compose logs -f

# Test health endpoints
curl http://localhost:8000/health  # Webhook Receiver
curl http://localhost:8001/health  # Analysis Engine
curl http://localhost:8002/health  # Email Notifier
curl http://localhost:8003/health  # Scheduler
curl http://localhost:8004/health  # Integration Service
```

## Service Management

### Start Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d analysis-engine

# Start with build (after code changes)
docker-compose up --build -d
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Stop specific service
docker-compose stop email-notifier
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f analysis-engine

# Last 100 lines
docker-compose logs --tail=100
```

### Scale Services

```bash
# Scale webhook receivers (if supported)
docker-compose up -d --scale webhook-receiver=3
```

## Development Mode

The `docker-compose.override.yml` file provides development-friendly defaults:

- Debug logging enabled
- Source code mounted for hot-reload
- Shorter MA period for faster testing
- Mailtrap SMTP for safe email testing

```bash
# Automatically uses override file
docker-compose up -d

# Production mode (ignore override)
docker-compose -f docker-compose.yml up -d
```

## Data Persistence

### SQLite Databases

- **Alerts DB**: `/app/data/alerts.db` - Stores incoming webhook alerts
- **OHLCV DB**: `/app/data/ohlcv.db` - Stores price data and analysis results

### Backup Data

```bash
# Backup databases
cp -r ./data ./data-backup-$(date +%Y%m%d)

# Or using Docker
docker cp tradingview-webhook-receiver:/app/data/alerts.db ./backup-alerts.db
```

### Reset Data

```bash
# Stop services and remove data
docker-compose down -v
rm -rf ./data/*
docker-compose up -d
```

## Network Configuration

Services communicate via the `tradingview-network` bridge network:

| Service | Internal URL | External URL |
|---------|-------------|--------------|
| Webhook Receiver | http://webhook-receiver:8000 | http://localhost:8000 |
| Analysis Engine | http://analysis-engine:8001 | http://localhost:8001 |
| Email Notifier | http://email-notifier:8002 | http://localhost:8002 |
| Scheduler | http://scheduler:8003 | http://localhost:8003 |
| Integration Service | http://integration-service:8004 | http://localhost:8004 |

## Health Checks

Each service includes a health check endpoint:

```bash
# Check individual service health
curl -f http://localhost:8000/health || echo "Webhook Receiver unhealthy"
curl -f http://localhost:8001/health || echo "Analysis Engine unhealthy"
curl -f http://localhost:8002/health || echo "Email Notifier unhealthy"
curl -f http://localhost:8003/health || echo "Scheduler unhealthy"
curl -f http://localhost:8004/health || echo "Integration Service unhealthy"
```

Health checks verify:
- Service is responding to HTTP requests
- Database connections are functional
- Required environment variables are set

## Troubleshooting

### Services Won't Start

```bash
# Check for port conflicts
sudo netstat -tlnp | grep -E '800[0-4]'

# View detailed logs
docker-compose logs --no-color > logs.txt
```

### Database Permission Errors

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 ./data
sudo chmod -R 755 ./data
```

### Email Not Sending

1. Verify SMTP credentials in `.env`
2. Check Email Notifier logs: `docker-compose logs email-notifier`
3. For Gmail: Use App Password, not account password
4. Test with Mailtrap for development

### Webhook Not Receiving

1. Verify `WEBHOOK_SECRET` is set
2. Check Webhook Receiver logs: `docker-compose logs webhook-receiver`
3. Ensure TradingView webhook URL points to your server
4. Test locally: `curl -X POST http://localhost:8000/webhook -H "Authorization: Bearer $WEBHOOK_SECRET"`

## Production Deployment

### Security Considerations

1. **Change default passwords** in `.env`
2. **Use strong WEBHOOK_SECRET** (32+ random characters)
3. **Enable HTTPS** using reverse proxy (nginx/traefik)
4. **Restrict port access** with firewall rules
5. **Regular backups** of `./data` directory

### Resource Limits

Add to `docker-compose.yml` for production:

```yaml
services:
  webhook-receiver:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

### Reverse Proxy Setup (nginx)

```nginx
server {
    listen 443 ssl;
    server_name tradingview.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBHOOK_SECRET` | Yes | - | Secret for webhook validation |
| `DATABASE_PATH` | No | /app/data/alerts.db | Alerts database path |
| `OHLCV_DB_PATH` | No | /app/data/ohlcv.db | OHLCV database path |
| `MA_PERIOD` | No | 20 | Moving average period |
| `CONFIDENCE_THRESHOLD` | No | 0.75 | Signal confidence threshold |
| `SMTP_HOST` | Yes | - | SMTP server hostname |
| `SMTP_PORT` | No | 587 | SMTP server port |
| `SMTP_USER` | Yes | - | SMTP username |
| `SCHEDULER_URL` | No | http://scheduler:8003 | Scheduler service URL |
| `REQUEST_TIMEOUT` | No | 30 | HTTP request timeout (seconds) |