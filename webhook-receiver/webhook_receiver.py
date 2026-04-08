"""TradingView Webhook Receiver - FastAPI application."""

import hmac
import hashlib
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from config import settings, ensure_data_directory
from database import AlertDatabase, db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/webhook.log")
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TradingView Webhook Receiver",
    description="Receives and stores TradingView alert webhooks",
    version="1.0.0"
)


class TradingViewAlert(BaseModel):
    """TradingView webhook payload schema."""
    
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSD)")
    price: Optional[float] = Field(None, description="Price at alert time")
    message: Optional[str] = Field(None, description="Alert message")
    time: Optional[str] = Field(None, description="Alert timestamp from TradingView")
    
    # Allow additional fields
    class Config:
        extra = "allow"
    
    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Normalize symbol to uppercase."""
        return v.upper()


class AlertResponse(BaseModel):
    """Response schema for successful alert storage."""
    
    status: str
    alert_id: int
    symbol: str
    received_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    timestamp: str
    database: str


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    ensure_data_directory()
    logger.info("Webhook receiver started")
    logger.info(f"Database path: {settings.database_path}")
    logger.info(f"Server: {settings.host}:{settings.port}")


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    stats = db.get_stats()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        database=f"{stats['total_alerts']} alerts stored"
    )


@app.get("/health", response_model=HealthResponse)
async def health_check_alt():
    """Alternative health check endpoint."""
    return await health_check()


async def validate_webhook_signature(request: Request) -> None:
    """Dependency to validate webhook signature.
    
    Raises HTTPException with 401 status if signature is invalid.
    """
    # Skip validation if no secret is configured
    if not settings.webhook_secret:
        return
    
    # Get signature from header (TradingView uses X-TradingView-Signature)
    signature = request.headers.get("X-TradingView-Signature")
    
    # Fallback: check query parameter
    if not signature:
        signature = request.query_params.get("signature")
    
    if not signature:
        logger.warning("Webhook request missing signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature"
        )
    
    # Read raw body
    body = await request.body()
    
    # Compute expected signature
    expected_signature = hmac.new(
        settings.webhook_secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature.lower(), expected_signature.lower()):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )


@app.post("/webhook", response_model=AlertResponse, status_code=status.HTTP_200_OK)
async def receive_webhook(
    alert: TradingViewAlert,
    request: Request,
    _: None = Depends(validate_webhook_signature)
):
    """Receive TradingView webhook alert.
    
    TradingView sends POST requests with JSON payload containing:
    - symbol: Trading pair (required)
    - price: Current price (optional)
    - message: Alert message (optional)
    - time: Alert timestamp (optional)
    
    Signature validation is performed if WEBHOOK_SECRET is configured.
    TradingView sends the signature in the X-TradingView-Signature header.
    
    Returns HTTP 200 OK to confirm receipt.
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Received webhook from {client_ip} for symbol: {alert.symbol}")
    
    try:
        # Get raw payload including any extra fields
        raw_payload = alert.model_dump()
        
        # Store in database
        alert_id = db.store_alert(
            symbol=alert.symbol,
            price=alert.price,
            message=alert.message,
            alert_time=alert.time,
            raw_payload=raw_payload
        )
        
        logger.info(f"Alert {alert_id} stored successfully")
        
        return AlertResponse(
            status="received",
            alert_id=alert_id,
            symbol=alert.symbol,
            received_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to store alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store alert: {str(e)}"
        )


@app.post("/webhook/tradingview", response_model=AlertResponse, status_code=status.HTTP_200_OK)
async def receive_webhook_alt(
    alert: TradingViewAlert,
    request: Request,
    _: None = Depends(validate_webhook_signature)
):
    """Alternative webhook endpoint at /webhook/tradingview.
    
    Signature validation is performed via the validate_webhook_signature dependency.
    """
    return await receive_webhook(alert, request)


@app.get("/alerts")
async def get_recent_alerts(limit: int = 100):
    """Get recent alerts from the database."""
    alerts = db.get_recent_alerts(limit=limit)
    return {
        "count": len(alerts),
        "alerts": alerts
    }


@app.get("/alerts/{symbol}")
async def get_alerts_by_symbol(symbol: str, limit: int = 100):
    """Get alerts for a specific symbol."""
    alerts = db.get_alerts_by_symbol(symbol, limit=limit)
    return {
        "symbol": symbol.upper(),
        "count": len(alerts),
        "alerts": alerts
    }


@app.get("/stats")
async def get_stats():
    """Get database statistics."""
    return db.get_stats()


class BehaviorLogRequest(BaseModel):
    """Request schema for behavior log entry."""
    
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSD)")
    timeframe: Optional[str] = Field("", description="Chart timeframe (e.g., 4H, 1D)")
    note: str = Field("", description="Observation note/description")
    
    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Normalize symbol to uppercase."""
        return v.upper()


class BehaviorLogResponse(BaseModel):
    """Response schema for behavior log entry."""
    
    status: str
    log_id: int
    symbol: str
    timeframe: Optional[str]
    timestamp: str


@app.post("/log", response_model=BehaviorLogResponse, status_code=status.HTTP_200_OK)
async def log_behavior(request: BehaviorLogRequest):
    """Log manual behavior observation.
    
    Usage: curl -X POST "http://localhost:8000/log" \\
               -H "Content-Type: application/json" \\
               -d '{"symbol": "BTCUSD", "timeframe": "4H", "note": "accumulation"}'
    
    This endpoint allows manual logging of market observations from the terminal
    or other tools. Useful for tracking attention and building a personal
    market observation database.
    """
    try:
        log_id = db.store_behavior_log(
            symbol=request.symbol,
            timeframe=request.timeframe or None,
            note=request.note or None,
            source='manual'
        )
        
        logger.info(f"Behavior log {log_id} stored for {request.symbol}")
        
        return BehaviorLogResponse(
            status="logged",
            log_id=log_id,
            symbol=request.symbol,
            timeframe=request.timeframe or None,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to store behavior log: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store behavior log: {str(e)}"
        )


@app.get("/logs")
async def get_recent_behavior_logs(limit: int = 100):
    """Get recent behavior logs from the database."""
    logs = db.get_recent_behavior_logs(limit=limit)
    return {
        "count": len(logs),
        "logs": logs
    }


@app.get("/logs/{symbol}")
async def get_behavior_by_symbol(symbol: str, limit: int = 100):
    """Get behavior logs for a specific symbol."""
    logs = db.get_behavior_by_symbol(symbol, limit=limit)
    return {
        "symbol": symbol.upper(),
        "count": len(logs),
        "logs": logs
    }


@app.get("/attention")
async def get_attention_heatmap(days: int = 7):
    """Get attention heatmap showing most observed symbols.
    
    Returns symbols ranked by observation frequency over the specified
    number of days (default: 7).
    """
    heatmap = db.get_behavior_attention_heatmap(days=days)
    return {
        "days": days,
        "symbol_count": len(heatmap),
        "heatmap": heatmap
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "webhook_receiver:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower()
    )
