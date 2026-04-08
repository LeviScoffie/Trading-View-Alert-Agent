# Caveats & Limitations

## Known Issues

### 1. TradingView Webhook Requirements
- **Paid Plan Required:** Webhook alerts require TradingView Essential+ plan ($14.95/mo)
- **Rate Limits:** TradingView limits webhook calls (varies by plan)
- **No Backtesting:** Webhooks only fire on new alerts, not historical data

### 2. Email Delivery
- **Gmail App Password Required:** Regular Gmail passwords don't work with 2FA enabled
- **Daily Limits:** Gmail limits ~500 emails/day; Yahoo ~200/day
- **Spam Filters:** Automated emails may land in spam; whitelist sender
- **No SMS/Push:** Email-only notifications; no Telegram/Discord integration yet

### 3. Analysis Engine
- **No Volume Analysis:** Volume confirmation not yet integrated
- **MA Calculation:** Simple 20-period MA; no EMA, WMA, or other variants
- **No Machine Learning:** Rule-based only; no ML pattern recognition
- **OHLCV Source:** Analysis runs on data from TradingView alert payloads; no independent price feed for gap-fills or corrections

### 4. Data Storage
- **SQLite Only:** Single-user design; not suitable for multi-user deployments
- **No Cloud Sync:** All data local; no automated backup
- **No Encryption:** Data stored in plaintext

### 5. Scheduling
- **No Catch-up:** If a service is down during a scheduled time, that report is skipped (not queued)
- **EST/EDT Edge Cases:** pytz handles most DST transitions, but verify the first report after a daylight saving changeover
- **Scheduler DB separate from alerts DB:** If scheduler volume mount (`/data`) and app volume mount (`/app/data`) diverge, check docker-compose volume paths

### 6. Security
- **No Rate Limiting:** No protection against webhook endpoint abuse
- **WEBHOOK_SECRET Optional:** HMAC validation exists but is not enforced by default; set it in `.env` for production
- **Plain HTTP:** No HTTPS by default; requires manual nginx/certbot setup (see SETUP.md)
- **Ports 8001/8003 Exposed:** Email-notifier and scheduler endpoints are unauthenticated; in production, keep them internal or behind a reverse proxy

### 7. Asset Coverage
- **Symbol Matching:** Requires exact symbol match (e.g., `BTCUSD` not `BTC/USD`)
- **No Auto-Discovery:** Must manually configure alerts in TradingView for each asset
- **No Independent Price Feeds:** All price data comes from TradingView webhook payloads

## Technical Debt

### Code Quality
- **Limited Error Handling:** Some analysis paths assume happy path; edge cases (empty OHLCV, missing fields) may silently skip
- **Partial Test Coverage:** `test_patterns.py` and `test_email_notifier.py` exist but integration tests are missing
- **Logging Incomplete:** Some background task paths not fully logged

### Architecture
- **analysis_bridge Coupling:** analysis-engine code is tightly coupled to webhook-receiver via `analysis_bridge.py`; cannot scale independently
- **No Caching:** Repeated analysis queries hit SQLite every time; no in-memory cache
- **No Background Queue:** `alert_processor.py` uses FastAPI's background task queue; no Redis/Celery for durability

## Performance Considerations

### Expected Load
- **Alerts:** ~10–50/day (depends on TradingView alert configuration)
- **Behavior Events:** ~50–100/day (manual `/log` usage)
- **Database Size:** ~10–50 MB/year (auto-pruned at 90 days by scheduler)
- **Memory:** ~100–200 MB per container (Python + FastAPI)
- **CPU:** Minimal; mostly I/O bound

### Bottlenecks
1. **Email Sending:** SMTP is slow (~2–5 seconds per send)
2. **Pattern Detection:** O(n) per symbol; could slow for large OHLCV histories
3. **SQLite Locks:** Concurrent writes from webhook-receiver + scheduler may queue briefly

## Scalability Limits

| Metric | Current Limit | Breaking Point |
|--------|---------------|----------------|
| Assets tracked | 20+ | ~100 (analysis time) |
| Alerts/day | ~100 | ~500 (email limits) |
| Concurrent users | 1 | 1 (SQLite locks) |
| Email recipients | 1 | 10+ (SMTP limits) |

## Workarounds

### For Paid Plan Requirement
- Use TradingView's "Alert on Screen" + manual `/log` endpoint for testing
- Build custom Pine Script alert + third-party webhook relay

### For Multi-User Support
- Deploy separate instance per user
- Migrate to PostgreSQL + user authentication
- Add API key authentication to webhook endpoint

### For Better Pattern Detection
- Integrate TA-Lib library for 150+ patterns
- Add machine learning model for custom pattern recognition
- Use external API (Alpha Vantage, Polygon) for confirmed signals

### For HTTPS
```bash
# Quick nginx + certbot setup
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
# Update TradingView webhook to https://
```

## Future Breaking Changes

### TradingView API Changes
- Webhook payload format may change (validate your `{{ticker}}` / `{{close}}` variables)
- Rate limits may tighten with plan changes

### Python Dependencies
- APScheduler 4.0 (in beta at time of writing) will have breaking API changes — pin to `3.x`
- FastAPI v0.110+ may have minor breaking changes in dependency injection
- SQLAlchemy 2.0+ has significant ORM API changes (job_store.py uses 2.0 style)

## Recommendations

### Before Production Use
1. Set `WEBHOOK_SECRET` in `.env` and verify HMAC validation is active
2. Set up HTTPS reverse proxy (nginx + certbot) — TradingView will reject non-HTTPS webhooks in some configurations
3. Whitelist your sending email address in your own inbox spam filter
4. Test end-to-end: send a test webhook → verify analysis appears at `/analysis` → manually trigger `/reports/daily` → verify email arrives

### Short-term (1–2 weeks)
1. Add integration tests for the full alert → analysis → email pipeline
2. Add error notification: email yourself if a service goes down or a scheduled job fails
3. Create a simple web dashboard for viewing alerts and analysis results without terminal access

### Long-term (1–3 months)
1. Migrate to PostgreSQL for multi-user or higher-volume support
2. Add Redis queue for background task durability
3. Add Telegram/Discord notification channels alongside email
4. Implement ML-based pattern success prediction (Phase 3)

---

**Last Updated:** April 2026  
**Version:** 1.1.0
