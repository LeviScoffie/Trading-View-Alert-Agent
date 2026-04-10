# Caveats & Limitations

**Version:** 2.0.0

---

## Known Issues

### 1. TradingView Webhook Requirements
- **Paid Plan Required:** Webhook alerts require TradingView Essential+ plan ($14.95/mo)
- **Rate Limits:** TradingView limits webhook calls (varies by plan)
- **No Backtesting:** Webhooks only fire on new alerts, not historical data

### 2. Analysis Engine — Fresh Install
- **No Seed Data:** `ohlcv.db` is empty on first run. The analysis engine returns `confidence: 0.0` until OHLCV candle history accumulates from real TradingView alerts.
- **Use the Full Template:** The TradingView alert message template must include `{{open}}`, `{{high}}`, `{{low}}`, `{{close}}`, `{{volume}}` fields so candle data flows into ohlcv.db.
- **No Independent Price Feed:** All price data comes from TradingView alert payloads — no external data source.

### 3. Email Delivery
- **Gmail App Password Required:** Regular passwords don't work with 2FA. Use an app-specific password.
- **Daily Limits:** Gmail ~500/day; Yahoo ~200/day
- **Spam Filters:** Automated emails may land in spam — whitelist the sender address.
- **Email Only:** No Telegram/Discord integration yet.

### 4. Analysis Engine Limitations
- **No Volume Confirmation:** Volume data stored but not used in context rules.
- **Simple 20MA Only:** No EMA, WMA, Bollinger Bands, or other variants.
- **Rule-Based Only:** No machine learning — all confidence scoring is deterministic.

### 5. Data Storage
- **SQLite Only:** Single-writer design; not suitable for high-volume or multi-user deployments.
- **No Cloud Sync:** All data local; no automated cloud backup.
- **No Encryption:** Data stored in plaintext SQLite files.

### 6. Scheduling
- **No Catch-up:** If services are down at a scheduled report time, that report is skipped (not queued).
- **DST Edge Cases:** pytz handles most transitions, but verify the first report after a daylight saving changeover.
- **Scheduler DB Path:** Scheduler mounts volume at `/data` (not `/app/data`); the other services use `/app/data`. Both map to `tv_data` volume — don't change the mount paths without updating all services.

### 7. Security
- **No Rate Limiting:** The `/webhook` endpoint on port 8004 has no protection against abuse — set `WEBHOOK_SECRET` in `.env`.
- **WEBHOOK_SECRET Optional:** HMAC validation exists but is not enforced by default.
- **Plain HTTP by Default:** Set up nginx + certbot for HTTPS in production (see SETUP.md).
- **Internal Ports Unauthenticated:** Ports 8000–8003 should not be exposed publicly — they have no auth.

---

## Technical Debt

### Code
- **Limited Integration Tests:** Unit tests exist for pattern detection and email generation, but no automated end-to-end test covering the full 5-service pipeline.

### Architecture
- **No Background Queue:** Integration service makes synchronous HTTP calls — no Redis/Celery for retry durability on crash.
- **No Caching:** Repeated analysis calls for the same symbol hit SQLite every time; no in-memory cache.

---

## Performance Considerations

### Expected Load
- **Alerts:** ~10–50/day depending on TradingView alert configuration
- **Analysis calls:** One per alert (synchronous, ~50–200ms per call)
- **Database size:** ~10–50MB/year (auto-pruned at 90 days)
- **Memory:** ~100–200MB per container

### Bottlenecks
1. **SMTP Send:** ~2–5 seconds — runs after analysis, so doesn't block webhook response
2. **Pattern Detection:** O(n) per symbol; can slow for very large OHLCV histories
3. **SQLite Writes:** Concurrent writes from multiple services queue briefly — not a concern at current scale

---

## Scalability Limits

| Metric | Current Limit |
|--------|---------------|
| Assets tracked | 20+ (analysis time grows linearly) |
| Alerts/day | ~100 (email limits apply above ~500/day) |
| Concurrent users | 1 (SQLite single-writer) |
| Webhooks/minute | 100 (PRD target; integration-service async pipeline) |

---

## Future Breaking Changes

### TradingView
- Webhook payload format may change — validate `{{ticker}}`, `{{close}}`, `{{interval}}` variables periodically.

### Python Dependencies
- **APScheduler:** Pinned to `3.10.4` (3.x). APScheduler 4.x is a complete rewrite — do not upgrade without testing.
- **FastAPI:** `0.109.0` pinned across all services — upgrade separately and test each service.
- **Pydantic:** All services use v2 (`pydantic==2.x`) — do not mix v1 and v2.

---

## Recommendations

### Before Production Use
1. Set `WEBHOOK_SECRET` in `.env` and verify HMAC validation fires correctly
2. Set up HTTPS reverse proxy (nginx + certbot) — expose only port 8004 publicly
3. Whitelist your sending email address in your inbox spam filter
4. Run a full end-to-end test: send webhook → check `/status/{id}` → verify analysis in `/analysis` → manually trigger `/reports/daily` → verify email arrives

### Short-Term (1–2 Weeks)
1. Add automated integration tests for the 5-service pipeline
2. Add error notification: email yourself when a service goes down or a scheduled job fails

### Long-Term (1–3 Months)
1. Migrate to PostgreSQL for higher-volume or multi-user support
2. Add Redis queue for background task durability
3. Add Telegram/Discord notification channels
4. Implement ML-based pattern success prediction (Phase 3)
5. Simple web dashboard for viewing alerts and analysis without terminal access

---

*Last Updated: 2026-04-09 | Version: 2.0.0*
