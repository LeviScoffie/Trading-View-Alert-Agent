# Caveats & Limitations

## Known Issues

### 1. TradingView Webhook Requirements
- **Paid Plan Required:** Webhook alerts require TradingView Essential+ plan ($14.95/mo)
- **Rate Limits:** TradingView limits webhook calls (varies by plan)
- **No Backtesting:** Webhooks only fire on new alerts, not historical data

### 2. Browser Extension Limitations
- **Chrome/Edge Only:** Manifest V3 extension works on Chromium browsers only
- **No Firefox Support:** Would require separate Manifest V2/V3 hybrid build
- **DOM Dependency:** Relies on TradingView's DOM structure; breaks if TradingView updates UI
- **Single Tab Tracking:** Only tracks active TradingView tab; multi-tab users may have gaps

### 3. Email Delivery
- **Gmail App Password Required:** Regular Gmail passwords don't work with 2FA
- **Daily Limits:** Gmail limits ~500 emails/day; Yahoo ~200/day
- **Spam Filters:** Automated emails may land in spam; whitelist sender
- **No SMS/Push:** Email-only notifications; no Telegram/Discord integration yet

### 4. Analysis Engine
- **Simplified Patterns:** Only engulfing patterns implemented; no complex patterns (head & shoulders, triangles, etc.)
- **No Volume Analysis:** Volume confirmation not yet integrated
- **MA Calculation:** Simple MA; no EMA, WMA, or other variants
- **Single Timeframe:** Analyzes one timeframe at a time; no multi-timeframe confluence
- **No Machine Learning:** Rule-based only; no ML pattern recognition

### 5. Data Storage
- **SQLite Only:** Single-user design; not suitable for multi-user deployments
- **No Cloud Sync:** All data local; no backup/restore automation
- **Unlimited Growth:** No automatic pruning; database grows indefinitely
- **No Encryption:** Data stored in plaintext

### 6. Scheduling
- **Server Timezone Dependent:** Reports use server timezone; DST changes may cause issues
- **No Catch-up:** If service is down during scheduled time, report is skipped
- **Single Thread:** Reports run synchronously; long reports block other operations

### 7. Security
- **No Authentication:** Webhook endpoint is open; anyone can POST alerts
- **No Rate Limiting:** No protection against abuse
- **Secret Optional:** `WEBHOOK_SECRET` exists but not enforced
- **Plain HTTP:** No HTTPS by default; requires manual nginx/certbot setup

### 8. Asset Coverage
- **Symbol Matching:** Requires exact symbol match (e.g., "BTCUSD" not "BTC/USD")
- **No Auto-Discovery:** Must manually configure all 20+ assets
- **No Price Feeds:** Relies on TradingView for price data; no independent verification

## Technical Debt

### Code Quality
- **Limited Error Handling:** Many functions assume happy path
- **No Unit Tests:** Zero test coverage
- **Logging Incomplete:** Some critical paths not logged
- **Type Hints Partial:** Not all functions have complete type annotations

### Architecture
- **Tight Coupling:** Analysis engine directly tied to FastAPI app
- **No Caching:** Repeated queries hit database every time
- **No Queue:** Background tasks use FastAPI's simple queue; no Redis/Celery
- **Monolithic:** All code in single service; no microservices separation

## Performance Considerations

### Expected Load
- **Alerts:** ~10-50/day (depends on TradingView alert configuration)
- **Behavior Events:** ~100-500/day (depends on user activity)
- **Database Size:** ~10-50 MB/year (SQLite handles this fine)
- **Memory:** ~200-500 MB (Python + FastAPI + SQLite)
- **CPU:** Minimal; mostly I/O bound

### Bottlenecks
1. **Email Sending:** SMTP is slow (~2-5 seconds per email)
2. **Pattern Detection:** O(n) for each symbol; could be slow with many assets
3. **Database Locks:** SQLite locks on write; concurrent writes queue

## Scalability Limits

| Metric | Current Limit | Breaking Point |
|--------|---------------|----------------|
| Assets tracked | 20+ | ~100 (analysis time) |
| Alerts/day | ~100 | ~500 (email limits) |
| Concurrent users | 1 | 1 (SQLite locks) |
| Browser tabs | 1-2 | 5+ (memory) |
| Email recipients | 1 | 10+ (SMTP limits) |

## Workarounds

### For Paid Plan Requirement
- Use TradingView's free "Alert on Screen" + manual webhook trigger
- Build custom Pine Script alert + third-party webhook service
- Use alternative: manual analysis + scheduled reports only

### For Multi-User Support
- Deploy separate instance per user
- Migrate to PostgreSQL + user authentication
- Add API key authentication to webhooks

### For Better Pattern Detection
- Integrate TA-Lib library for 150+ patterns
- Add machine learning model for custom pattern recognition
- Use external API (e.g., Alpha Vantage, Polygon) for confirmed signals

### For HTTPS
```bash
# Quick nginx + certbot setup
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
# Update TradingView webhook to https://
```

## Future Breaking Changes

### TradingView API Changes
- TradingView may change DOM structure, breaking extension
- Webhook payload format may change
- Rate limits may tighten

### Python Dependencies
- FastAPI v0.110+ may have breaking changes
- SQLAlchemy 2.0+ has significant API changes
- APScheduler 4.0 (in beta) will have breaking changes

### Browser Extension
- Manifest V2 fully deprecated (already done in Chrome)
- Chrome may change extension APIs
- Firefox may drop Manifest V3 support

## Recommendations

### Immediate (Before Production Use)
1. ✅ Add webhook authentication (implement `WEBHOOK_SECRET` validation)
2. ✅ Set up HTTPS reverse proxy
3. ✅ Configure email spam whitelist
4. ✅ Test all 20+ assets with sample alerts

### Short-term (1-2 weeks)
1. Add unit tests for analysis engine
2. Implement database pruning (keep last 90 days)
3. Add error notifications (email on service failure)
4. Create dashboard for viewing alerts/patterns

### Long-term (1-3 months)
1. Migrate to PostgreSQL for multi-user support
2. Add Redis queue for background tasks
3. Implement ML-based pattern recognition
4. Build web UI for configuration and monitoring
5. Add Telegram/Discord notification channels

---

**Last Updated:** April 2025  
**Version:** 1.0.0
