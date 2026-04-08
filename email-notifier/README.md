# Email Notifier

Scheduled email reports for the TradingView Alert Agent.

## Overview

The Email Notifier delivers automated trading analysis reports via email on three schedules:

| Report | Time (EST/EDT) | Content |
|--------|----------------|---------|
| Daily Close | 5:00 PM daily | Daily patterns, MA20 status, context signals |
| Weekly Close | Sunday 5:00 PM | Weekly engulfing analysis, multi-TF alignment |
| Monthly Close | Last day 5:00 PM | Monthly trend, key levels, major signals |

## Features

- **HTML Email Templates**: Beautiful, dark-themed reports with pattern badges, confidence scores, and multi-timeframe alignment
- **Multiple Email Providers**: Support for SMTP (Gmail), SendGrid, and AWS SES
- **Timezone-Aware Scheduling**: All schedules use America/New_York (EST/EDT) timezone
- **Retry Logic**: Automatic retry on failed sends (configurable)
- **Plain Text Fallback**: Every email includes a plain text version

## Quick Start

### 1. Configure Environment

```bash
cd /home/node/.openclaw/workspace/projects/tradingview-alert-agent/email-notifier

cp .env.example .env
nano .env  # Edit with your settings
```

### 2. Set Email Provider

#### Option A: SMTP (Gmail)

```env
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_TO=scoffie@example.com
EMAIL_FROM=your-email@gmail.com
```

#### Option B: SendGrid

```env
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxxxxx
EMAIL_TO=scoffie@example.com
EMAIL_FROM=alerts@yourdomain.com
```

#### Option C: AWS SES

```env
EMAIL_PROVIDER=aws_ses
AWS_ACCESS_KEY_ID=AKIAxxxxx
AWS_SECRET_ACCESS_KEY=xxxxx
AWS_REGION=us-east-1
EMAIL_TO=scoffie@example.com
EMAIL_FROM=alerts@yourdomain.com
```

### 3. Run

#### Test Mode (Send One Report)

```bash
python email_notifier.py --test
```

#### Production Mode (Start Scheduler)

```bash
python email_notifier.py
```

### 4. Docker Deployment

```bash
# Build
docker build -t tv-alert-email-notifier .

# Run
docker run -d \
  --name email-notifier \
  --env-file .env \
  -v $(pwd)/../webhook-receiver/data:/app/data \
  tv-alert-email-notifier
```

## Configuration

### Email Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_PROVIDER` | `smtp` | Provider: `smtp`, `sendgrid`, or `aws_ses` |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password |
| `SMTP_TLS` | `true` | Enable TLS |
| `SENDGRID_API_KEY` | — | SendGrid API key |
| `AWS_ACCESS_KEY_ID` | — | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | — | AWS secret key |
| `AWS_REGION` | `us-east-1` | AWS region |
| `EMAIL_TO` | — | Recipient email |
| `EMAIL_FROM` | — | Sender email |

### Schedule Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULE_TIMEZONE` | `America/New_York` | Timezone for all schedules |
| `DAILY_REPORT_HOUR` | `17` | Daily report hour (24h) |
| `DAILY_REPORT_MINUTE` | `0` | Daily report minute |
| `WEEKLY_REPORT_DAY` | `6` | Day of week (0=Mon, 6=Sun) |
| `WEEKLY_REPORT_HOUR` | `17` | Weekly report hour |
| `MONTHLY_REPORT_HOUR` | `17` | Monthly report hour |

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `EMAIL_MAX_RETRIES` | `3` | Max send retries |
| `EMAIL_RETRY_DELAY_SECONDS` | `60` | Delay between retries |
| `REPORT_LOOKBACK_DAYS` | `30` | Max lookback for reports |
| `TOP_SYMBOLS_LIMIT` | `10` | Max symbols in report |

## Email Template Preview

Reports include:

1. **Header**: Report type and date
2. **Summary Metrics**: Total alerts, symbols, bullish/bearish signals
3. **Symbol Analysis Cards**:
   - Detected patterns with confidence scores
   - MA20 status with visual indicator
   - Context reasoning
   - Actionable recommendation
   - Multi-timeframe alignment grid
4. **Recent Alerts List**: Last 10-20 alerts in period

## Integration

### Database Connection

The notifier reads from the webhook-receiver SQLite database:

```env
EMAIL_NOTIFIER_DB_PATH=../webhook-receiver/data/alerts.db
EMAIL_NOTIFIER_OHLCV_DB_PATH=../analysis-engine/ohlcv.db
```

### Analysis Engine Integration

To add real-time analysis to reports, integrate with the analysis engine:

```python
from analysis_engine import AnalysisEngine

engine = AnalysisEngine()
result = engine.analyze_symbol("BTCUSD", Timeframe.DAILY)

# Use result.patterns, result.ma20, result.context in report
```

## Testing

```bash
# Unit tests
pytest tests/

# Send test email
python email_notifier.py --test

# Check scheduler (dry run)
python -c "from email_notifier import EmailNotifier; n = EmailNotifier(); print('Scheduler configured OK')"
```

## Troubleshooting

### Gmail "Less Secure Apps"

Gmail requires an App Password:

1. Go to Google Account → Security
2. Enable 2-Factor Authentication
3. Generate App Password
4. Use app password in `SMTP_PASSWORD`

### SendGrid Verification

SendGrid requires verified sender addresses on free tier:

1. Go to SendGrid Dashboard → Settings → Sender Authentication
2. Verify your "From" email address

### AWS SES Sandbox

AWS SES starts in sandbox mode (1000 emails/day, verified recipients only):

1. Go to AWS SES Console
2. Request production access
3. Verify all recipient emails

### Database Not Found

Ensure the webhook-receiver database exists:

```bash
ls -la ../webhook-receiver/data/alerts.db
```

If missing, run the webhook-receiver first to generate data.

## Logs

View logs:

```bash
# Docker
docker logs -f email-notifier

# Direct
tail -f /var/log/email-notifier.log
```

## File Structure

```
email-notifier/
├── config.py           # Configuration management
├── templates.py        # HTML email templates
├── report_generator.py # Database queries and report data
├── email_notifier.py   # Main scheduler and sender
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build
├── README.md           # This file
└── .env.example        # Environment template
```

## Dependencies

- **APScheduler**: Cron-like scheduling
- **Jinja2**: HTML templating
- **pydantic**: Configuration validation
- **pytz**: Timezone handling
- **boto3**: AWS SES (optional)
- **sendgrid**: SendGrid API (optional)

## License

MIT License - See project root for details.
