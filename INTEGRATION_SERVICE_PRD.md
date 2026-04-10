# Integration Service — Product Requirements Document (PRD)

**Version:** 1.0  
**Date:** 2026-04-08  
**Status:** Ready for Development  
**Author:** Rodgers (AI Coordinator)  
**Target:** AI Agent Developer

---

## 1. Overview

### 1.1 Purpose
The Integration Service is the **central orchestrator** of the TradingView Alert Agent. It receives TradingView webhook alerts, coordinates analysis across multiple services, and triggers email notifications based on confidence thresholds.

### 1.2 Problem Statement
Without the Integration Service:
- Webhook Receiver stores alerts but doesn't trigger analysis
- Analysis Engine has no data source
- Email Notifier only sends scheduled reports, not immediate alerts
- Services are isolated and don't communicate

### 1.3 Solution
A single orchestration service that:
1. Receives TradingView webhooks
2. Stores alerts via Webhook Receiver
3. Triggers analysis via Analysis Engine
4. Stores analysis results
5. Sends immediate emails if confidence >= threshold
6. Returns unified response

---

## 2. Architecture

### 2.1 System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRADINGVIEW ALERT AGENT                      │
└─────────────────────────────────────────────────────────────────┘

External Systems:
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ TradingView  │      │     SMTP     │      │   SQLite     │
│  (Source)    │─────▶│  (Email)     │      │  (Storage)   │
└──────────────┘      └──────────────┘      └──────────────┘
       │                                           ▲
       │                                           │
       ▼                                           │
┌─────────────────────────┐              ┌────────┴────────┐
│  INTEGRATION SERVICE    │─────────────▶│ Webhook Receiver│
│      (Port 8004)        │              │    (Port 8000)  │
│                         │              └─────────────────┘
│  ┌─────────────────┐    │                       ▲
│  │   Orchestrator  │    │                       │
│  │                 │    │              ┌────────┴────────┐
│  │ 1. Receive      │────┼─────────────▶│ Analysis Engine │
│  │ 2. Store        │    │              │    (Port 8001)  │
│  │ 3. Analyze      │    │              └─────────────────┘
│  │ 4. Store result │    │                       │
│  │ 5. Email?       │────┼───────────────────────┘
│  │ 6. Respond      │    │              ┌─────────────────┐
│  └─────────────────┘    │─────────────▶│ Email Notifier  │
│                         │              │    (Port 8002)  │
└─────────────────────────┘              └─────────────────┘
```

### 2.2 Service Dependencies

| Service | URL | Purpose | Required |
|---------|-----|---------|----------|
| Webhook Receiver | `http://webhook-receiver:8000` | Alert storage | Yes |
| Analysis Engine | `http://analysis-engine:8001` | Pattern analysis | Yes |
| Email Notifier | `http://email-notifier:8002` | Email delivery | Yes |
| Scheduler | `http://scheduler:8003` | Job status (optional) | No |

---

## 3. Functional Requirements

### 3.1 Core Flow (FR-001 to FR-006)

#### FR-001: Receive Webhook
**Description:** Accept POST requests from TradingView

**Endpoint:** `POST /webhook`

**Request Body:**
```json
{
  "symbol": "BTCUSD",
  "price": 45000.00,
  "open": 44000.00,
  "high": 46000.00,
  "low": 43500.00,
  "volume": 1234567,
  "timeframe": "1D",
  "time": "2026-04-08T10:30:00Z",
  "exchange": "BINANCE",
  "message": "Bullish engulfing detected"
}
```

**Validation:**
- `symbol` (required, string, uppercase)
- `price` (required, number)
- `timeframe` (optional, string, default: "1D")
- All other fields optional

**Response:**
```json
{
  "status": "processed",
  "alert_id": 123,
  "symbol": "BTCUSD",
  "confidence": 0.85,
  "email_sent": true,
  "processing_time_ms": 450,
  "timestamp": "2026-04-08T10:30:01Z"
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": "Analysis engine unavailable",
  "alert_id": 123,
  "stored": true,
  "analyzed": false
}
```

#### FR-002: Store Alert via Webhook Receiver
**Description:** Call Webhook Receiver to store incoming alert

**Method:** `POST http://webhook-receiver:8000/webhook`

**Request:** Raw TradingView payload

**Expected Response:**
```json
{
  "status": "received",
  "alert_id": 123,
  "symbol": "BTCUSD",
  "received_at": "2026-04-08T10:30:01Z"
}
```

**Error Handling:**
- If Webhook Receiver fails: Log error, continue with analysis
- Return partial success to TradingView (don't fail the webhook)

#### FR-003: Trigger Analysis
**Description:** Call Analysis Engine to analyze symbol/timeframe

**Method:** `POST http://analysis-engine:8001/analyze`

**Request:**
```json
{
  "symbol": "BTCUSD",
  "timeframe": "1D",
  "lookback_days": 30
}
```

**Expected Response:**
```json
{
  "symbol": "BTCUSD",
  "timestamp": "2026-04-08T10:30:01Z",
  "patterns": [
    {
      "type": "bullish_engulfing",
      "confidence": 0.85,
      "timeframe": "1D"
    }
  ],
  "ma20": {
    "price": 45000,
    "ma20": 44000,
    "distance_pct": 2.27,
    "trend": "bullish",
    "slope": "rising"
  },
  "context": {
    "sentiment": "bullish",
    "confidence": 0.85,
    "reasoning": "Weekly bullish engulfing + past 3 days bearish pullback",
    "recommendation": "consider_long"
  },
  "multi_timeframe": {
    "weekly": {"trend": "bullish", "alignment": true},
    "daily": {"trend": "bullish", "alignment": true},
    "4h": {"trend": "bearish", "alignment": false}
  }
}
```

**Error Handling:**
- If Analysis Engine fails: Return empty analysis with confidence 0
- Log error for monitoring
- Continue processing (don't fail the webhook)

#### FR-004: Store Analysis Result
**Description:** Store analysis result in Webhook Receiver database

**Method:** `POST http://webhook-receiver:8000/analysis/{alert_id}`

**Request:** Analysis result from FR-003

**Expected Response:**
```json
{
  "status": "stored",
  "alert_id": 123,
  "analysis_id": 456
}
```

#### FR-005: Conditional Email Trigger
**Description:** Send email if confidence >= threshold

**Condition:** `analysis.context.confidence >= CONFIDENCE_THRESHOLD` (default: 0.75)

**Method:** `POST http://email-notifier:8002/send-alert`

**Request:**
```json
{
  "symbol": "BTCUSD",
  "analysis": {
    "patterns": [...],
    "ma20": {...},
    "context": {...}
  },
  "priority": "high"
}
```

**Expected Response:**
```json
{
  "status": "sent",
  "message_id": "abc123",
  "recipient": "scoffie@example.com"
}
```

**If confidence < threshold:**
- Skip email
- Set `email_sent: false` in response
- Log for monitoring

#### FR-006: Return Unified Response
**Description:** Return combined result to TradingView

**Success Response (HTTP 200):**
```json
{
  "status": "processed",
  "alert_id": 123,
  "symbol": "BTCUSD",
  "confidence": 0.85,
  "email_sent": true,
  "processing_time_ms": 450,
  "timestamp": "2026-04-08T10:30:01Z",
  "services": {
    "webhook": "success",
    "analysis": "success",
    "email": "success"
  }
}
```

**Partial Success (HTTP 200):**
```json
{
  "status": "partial",
  "alert_id": 123,
  "symbol": "BTCUSD",
  "confidence": 0,
  "email_sent": false,
  "error": "Analysis engine timeout",
  "services": {
    "webhook": "success",
    "analysis": "timeout",
    "email": "skipped"
  }
}
```

**Note:** Always return HTTP 200 to TradingView to prevent retry spam, even on partial failures.

---

## 4. Additional Endpoints

### FR-007: Health Check
**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-08T10:30:00Z",
  "services": [
    {"name": "webhook-receiver", "status": "healthy", "response_time_ms": 12.5},
    {"name": "analysis-engine", "status": "healthy", "response_time_ms": 45.2},
    {"name": "email-notifier", "status": "healthy", "response_time_ms": 8.1}
  ]
}
```

### FR-008: Alert Status Query
**Endpoint:** `GET /status/{alert_id}`

**Response:**
```json
{
  "alert_id": 123,
  "symbol": "BTCUSD",
  "status": "complete",
  "stored": true,
  "analyzed": true,
  "email_sent": true,
  "confidence": 0.85
}
```

### FR-009: Manual Analysis Trigger
**Endpoint:** `POST /trigger-analysis`

**Request:**
```json
{
  "symbol": "BTCUSD",
  "timeframe": "4H",
  "force_email": false
}
```

---

## 5. Non-Functional Requirements

### 5.1 Performance
- **Response Time:** Complete flow in < 2 seconds
- **Throughput:** Handle 100 webhooks/minute
- **Availability:** 99.9% uptime

### 5.2 Reliability
- Never fail TradingView webhook (always HTTP 200)
- Retry failed service calls (3 attempts, exponential backoff)
- Continue processing on partial failures

### 5.3 Security
- Validate all inputs (Pydantic models)
- Timeout all service calls (10 seconds)
- Internal Docker network only

---

## 6. Technical Specifications

### 6.1 Technology Stack
- **Framework:** FastAPI
- **HTTP Client:** httpx (async)
- **Validation:** Pydantic v2
- **Configuration:** pydantic-settings

### 6.2 File Structure
```
integration-service/
├── integration_service.py    # FastAPI app
├── orchestrator.py           # Core flow logic
├── clients.py                # HTTP clients
├── models.py                 # Pydantic models
├── config.py                 # Configuration
├── Dockerfile
├── requirements.txt
└── README.md
```

### 6.3 Environment Variables
```bash
WEBHOOK_RECEIVER_URL=http://webhook-receiver:8000
ANALYSIS_ENGINE_URL=http://analysis-engine:8001
EMAIL_NOTIFIER_URL=http://email-notifier:8002
CONFIDENCE_THRESHOLD=0.75
REQUEST_TIMEOUT_SECONDS=10
MAX_RETRIES=3
HOST=0.0.0.0
PORT=8004
```

---

## 7. Error Handling

| Scenario | Behavior | TradingView Response |
|----------|----------|---------------------|
| Webhook Receiver fails | Log error, continue | HTTP 200, `stored: false` |
| Analysis Engine fails | Log error, skip | HTTP 200, `analyzed: false` |
| Email Notifier fails | Log error, skip | HTTP 200, `email_sent: false` |

---

## 8. Acceptance Criteria

- [ ] POST /webhook receives and processes alerts
- [ ] Calls all 3 downstream services in sequence
- [ ] Sends email only when confidence >= 0.75
- [ ] Returns HTTP 200 even on partial failures
- [ ] Health check shows all service statuses
- [ ] Complete flow finishes in < 2 seconds
- [ ] Logs all errors with context

---

*PRD Complete — Ready for Development*

