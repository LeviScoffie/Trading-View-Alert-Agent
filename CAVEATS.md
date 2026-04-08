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
- **Alert Enrichment via /log:** Now uses alert enrichment functionality with /log endpoint instead of direct DOM manipulation

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
- **Multiple SQLite Databases:** Each service maintains its own SQLite database, leading to potential data consistency challenges

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

## Architecture-Specific Limitations

### Multi-Service Complexity
- **Orchestration Challenges:** Managing 4 separate services (webhook-receiver, analysis-engine, email-notifier, scheduler) requires careful coordination
- **Service Discovery:** Services must know each other's endpoints and handle service restarts gracefully
- **Configuration Management:** Each service needs individual configuration and environment variable management
- **Monitoring Overhead:** More complex to monitor and debug compared to monolithic approach

### Inter-Service Communication Latency
- **Network Overhead:** Communication between services adds latency compared to in-process calls
- **Potential Bottlenecks:** Service dependencies can create delays if one service is slow or unavailable
- **Retry Logic:** Network failures between services require robust retry mechanisms
- **Message Queuing:** Without proper queuing, service unavailability can lead to lost messages

### Data Consistency Across SQLite Databases
- **Distributed Transactions:** No ACID guarantees across multiple SQLite databases
- **Eventual Consistency:** Data synchronization between services may have delays
- **Conflict Resolution:** No built-in mechanism to handle conflicting updates across databases
- **Backup Coordination:** Coordinating backups across multiple databases to maintain consistency

### Known Limitations of Distributed Approach
- **Increased Resource Usage:** Running 4 separate services consumes more memory and CPU than monolithic approach
- **Complex Deployment:** Requires managing 4 ports (8000-8003) and inter-service networking
- **Failure Propagation:** Failure in one service can cascade to dependent services
- **Debugging Difficulty:** Tracing issues across service boundaries is more challenging
- **Service Synchronization:** Maintaining consistent state across services requires additional logic

## Technical Debt

### Code Quality
- **Limited Error Handling:** Many functions assume happy path
- **No Unit Tests:** Zero test coverage
- **Logging Incomplete:** Some critical paths not logged
- **Type Hints Partial:** Not all functions have complete type annotations

### Architecture
- **Tight Coupling:** Despite service separation, some components remain tightly coupled
- **No Caching:** Repeated queries hit database every time
- **No Queue:** Background tasks use basic inter-service communication; no Redis/Celery
- **Distributed Services:** Code is now separated across 4 services:
  - webhook-receiver (Port 8000)
  - analysis-engine (Port 8001) 
  - email-notifier (Port 8002)
  - scheduler (Port 8003)

## Performance Considerations

### Expected Load
- **Alerts:** ~10-50/day (depends on TradingView alert configuration)
- **Behavior Events:** ~100-500/day (depends on user activity)
- **Database Size:** ~10-50 MB/year per service (SQLite handles this fine)
- **Memory:** ~800-2000 MB total (4 services x Python + FastAPI + SQLite)
- **CPU:** Higher due to inter-service communication overhead

### Bottlenecks
1. **Inter-Service Communication:** Network calls between services slower than internal function calls
2. **Email Sending:** SMTP is slow (~2-5 seconds per email) and blocks the email-notifier service
3. **Database Locks:** SQLite locks on write; concurrent writes queue (worse across multiple services)
4. **Service Dependencies:** Downstream services wait for upstream services to complete

## Scalability Limits

| Metric | Current Limit | Breaking Point |
|--------|---------------|----------------|
| Assets tracked | 20+ | ~50 (analysis time across services) |
| Alerts/day | ~100 | ~300 (email limits and service coordination) |
| Concurrent users | 1 | 1 (SQLite locks still apply per service) |
| Browser tabs | 1-2 | 5+ (memory) |
| Email recipients | 1 | 10+ (SMTP limits) |
| Services | 4 | ~8 (resource constraints) |

The multi-service architecture introduces additional constraints compared to the monolithic approach:
- Each service has its own resource consumption
- Inter-service communication overhead increases with scale
- Coordination complexity grows with more services

## Workarounds

### For Multi-Service Complexity
- Use Docker Compose for easier orchestration
- Implement service mesh for better inter-service communication
- Centralized logging across all services
- Health checks for each service

### For Data Consistency Issues
- Implement eventual consistency patterns
- Use distributed transactions when absolutely necessary
- Add data validation between services
- Implement reconciliation processes

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
5. ✅ Implement service health checks and monitoring

### Short-term (1-2 weeks)
1. Add unit tests for analysis engine
2. Implement database pruning (keep last 90 days)
3. Add error notifications (email on service failure)
4. Create dashboard for viewing alerts/patterns
5. Implement circuit breakers for service-to-service calls

### Long-term (1-3 months)
1. Migrate to PostgreSQL for multi-user support
2. Add Redis queue for background tasks
3. Implement ML-based pattern recognition
4. Build web UI for configuration and monitoring
5. Add Telegram/Discord notification channels
6. Consider container orchestration with Kubernetes

---

**Last Updated:** April 2026  
**Version:** 2.0.0