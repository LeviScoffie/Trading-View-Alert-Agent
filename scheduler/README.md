# TradingView Alert Agent Scheduler

APScheduler-based job scheduler with timezone support, persistence, and monitoring for the TradingView Alert Agent system.

## Features

- **Timezone-aware scheduling**: EST/EDT with automatic DST handling
- **Job persistence**: SQLite-based storage for job state and execution history
- **Retry logic**: Exponential backoff for failed jobs
- **Health monitoring**: Real-time job status and alerting
- **REST API**: Full management via HTTP endpoints
- **Docker support**: Containerized deployment

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily Report | Daily at 5:00 PM EST | Generate and send daily analysis report |
| Weekly Report | Every Sunday at 5:00 PM EST | Generate and send weekly analysis report |
| Monthly Report | Last day of month at 5:00 PM EST | Generate and send monthly analysis report |
| Data Cleanup | Every Sunday at 3:00 AM EST | Prune alerts/logs older than 90 days |
| Health Check | Every hour | Verify webhook receiver and email notifier health |

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scheduler (foreground)
python scheduler.py

# Run the API server
python api.py
```

### Docker

```bash
# Build image
docker build -t tradingview-scheduler .

# Run container
docker run -d \
  --name tradingview-scheduler \
  -p 8003:8003 \
  -v $(pwd)/data:/data \
  tradingview-scheduler
```

### Docker Compose

```yaml
version: '3.8'

services:
  scheduler:
    build: .
    container_name: tradingview-scheduler
    ports:
      - "8003:8003"
    volumes:
      - ./data:/data
    environment:
      - SCHEDULER_LOG_LEVEL=INFO
      - WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
      - EMAIL_NOTIFIER_URL=http://email-notifier:8001
    restart: unless-stopped
```

## API Endpoints

### Health & Status

```bash
# Get system health
GET /health

# Get dashboard data
GET /dashboard

# Get active alerts
GET /alerts
```

### Job Management

```bash
# List all jobs
GET /jobs

# Get job details
GET /jobs/{id}

# Trigger job manually
POST /jobs/{id}/trigger

# Pause a job
POST /jobs/{id}/pause

# Resume a job
POST /jobs/{id}/resume
```

### Example API Calls

```bash
# Check health
curl http://localhost:8003/health

# List jobs
curl http://localhost:8003/jobs

# Trigger daily report manually
curl -X POST http://localhost:8003/jobs/daily_report/trigger

# Pause weekly report
curl -X POST http://localhost:8003/jobs/weekly_report/pause

# Resume weekly report
curl -X POST http://localhost:8003/jobs/weekly_report/resume
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULER_DB_PATH` | `/data/scheduler.db` | SQLite database path |
| `SCHEDULER_LOG_LEVEL` | `INFO` | Logging level |
| `SCHEDULER_API_HOST` | `0.0.0.0` | API server host |
| `SCHEDULER_API_PORT` | `8003` | API server port |
| `WEBHOOK_RECEIVER_URL` | `http://webhook-receiver:8000` | Webhook receiver service URL |
| `EMAIL_NOTIFIER_URL` | `http://email-notifier:8001` | Email notifier service URL |
| `ANALYSIS_ENGINE_URL` | `http://analysis-engine:8002` | Analysis engine service URL |
| `TZ` | `America/New_York` | Timezone (EST/EDT) |

### Schedule Configuration

Edit `config.py` to modify job schedules:

```python
SCHEDULE_CONFIG = {
    "timezone": "America/New_York",
    "jobs": {
        "daily_report": {"hour": 17, "minute": 0},  # 5:00 PM
        "weekly_report": {"day_of_week": "sun", "hour": 17, "minute": 0},
        "monthly_report": {"day": "last", "hour": 17, "minute": 0},
        "cleanup": {"day_of_week": "sun", "hour": 3, "minute": 0},
        "health_check": {"minute": 0}  # Every hour
    },
    "retention_days": 90,
    "retry_attempts": 3,
    "retry_delay_minutes": 5
}
```

## Project Structure

```
scheduler/
├── scheduler.py        # Main APScheduler app
├── jobs.py             # Individual job functions
├── timezone_utils.py   # EST/EDT handling with DST
├── job_store.py        # SQLite persistence
├── api.py              # FastAPI endpoints
├── monitor.py          # Health checks and status
├── config.py           # Schedule configuration
├── Dockerfile          # Container setup
├── requirements.txt    # Dependencies
└── README.md           # This file
```

## Job Functions

### Daily Report
- **Trigger**: Daily at 5:00 PM EST
- **Action**: Calls email notifier to generate daily analysis
- **Retry**: 3 attempts with exponential backoff

### Weekly Report
- **Trigger**: Every Sunday at 5:00 PM EST
- **Action**: Calls email notifier to generate weekly analysis
- **Retry**: 3 attempts with exponential backoff

### Monthly Report
- **Trigger**: Last day of month at 5:00 PM EST
- **Action**: Calls email notifier to generate monthly analysis
- **Note**: Runs on the 1st of each month, generates report for previous month

### Data Cleanup
- **Trigger**: Every Sunday at 3:00 AM EST
- **Action**: Deletes alerts and behavior logs older than 90 days
- **Safety**: Uses transactions, rolls back on error

### Health Check
- **Trigger**: Every hour
- **Action**: Verifies webhook receiver and email notifier are responding
- **Timeout**: 10 seconds per service

## Retry Logic

Failed jobs are automatically retried with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1st | 5 minutes |
| 2nd | 10 minutes |
| 3rd | 20 minutes |

Maximum delay is capped at 60 minutes.

## Monitoring

### Health Status Levels

- **healthy**: Job running normally
- **warning**: Job has failed 1+ times but below threshold
- **critical**: Job has failed 3+ times consecutively
- **unknown**: No execution history

### Alert Thresholds

- Consecutive failures before alert: 3
- Health check timeout: 10 seconds
- Max execution history: 100 runs per job

### Dashboard Metrics

- Overall system health
- Per-job success rates
- Last run times
- Consecutive failure counts
- 24-hour uptime percentage

## Integration Points

### Email Notifier
```python
POST /reports/daily
POST /reports/weekly
POST /reports/monthly
```

### Webhook Receiver
```python
GET /health
```

### Analysis Engine
```python
GET /health
```

## Troubleshooting

### Job Not Running

1. Check job status: `GET /jobs/{id}`
2. Check execution history in database
3. Verify timezone configuration
4. Check logs for errors

### Database Issues

```bash
# Reset database (WARNING: loses history)
rm /data/scheduler.db

# Or use SQLite CLI to inspect
sqlite3 /data/scheduler.db "SELECT * FROM job_executions ORDER BY executed_at DESC LIMIT 10;"
```

### Timezone Issues

```python
# Check current timezone
from timezone_utils import now, is_dst
print(now())  # Current time in EST/EDT
print(is_dst())  # True if DST is active
```

### Service Connectivity

```bash
# Test webhook receiver
curl http://webhook-receiver:8000/health

# Test email notifier
curl http://email-notifier:8001/health
```

## Development

### Running Tests

```bash
# Test individual job manually
python jobs.py daily_report

# Test with retry logic
python jobs.py health_check
```

### Adding New Jobs

1. Add job function to `jobs.py`:
```python
@with_retry()
def my_new_job():
    """Description of what this job does."""
    # Job implementation
    pass
```

2. Register in `JOB_REGISTRY`:
```python
JOB_REGISTRY = {
    # ... existing jobs
    "my_new_job": my_new_job
}
```

3. Add schedule in `config.py`:
```python
"jobs": {
    # ... existing jobs
    "my_new_job": {"hour": 9, "minute": 0}  # 9:00 AM
}
```

## License

MIT License - See LICENSE file for details.
