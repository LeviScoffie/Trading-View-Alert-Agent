"""Pydantic models for Integration Service."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


# ── Inbound ───────────────────────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    """TradingView webhook payload — mirrors TradingViewAlert in webhook-receiver."""

    symbol: str = Field(..., description="Trading symbol, e.g. BTCUSD")
    price: Optional[float] = Field(None, description="Alias for close price (legacy)")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    timeframe: Optional[str] = Field(None, description="Chart timeframe, e.g. 1D, 4H")
    # TradingView uses 'interval' in its template variables
    interval: Optional[str] = Field(None, description="TradingView interval field")
    time: Optional[str] = None
    exchange: Optional[str] = None
    message: Optional[str] = None

    class Config:
        extra = "allow"

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()

    def effective_timeframe(self) -> str:
        return self.timeframe or self.interval or "1D"


class TriggerAnalysisRequest(BaseModel):
    """Request body for POST /trigger-analysis."""

    symbol: str = Field(..., description="Trading symbol, e.g. BTCUSD")
    timeframe: str = Field("1D", description="Chart timeframe")
    force_email: bool = Field(False, description="Send email regardless of confidence")

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


# ── Internal ──────────────────────────────────────────────────────────────────

class OrchestrationResult:
    """Mutable container tracking state through the orchestration flow."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.alert_id: Optional[int] = None
        self.analysis: Dict[str, Any] = {}
        self.confidence: float = 0.0
        self.email_sent: bool = False
        self.webhook_status: str = "pending"
        self.analysis_status: str = "pending"
        self.email_status: str = "pending"
        self.processing_time_ms: int = 0
        self.error: Optional[str] = None


# ── Outbound ──────────────────────────────────────────────────────────────────

class ServiceStatus(BaseModel):
    name: str
    status: str
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


class WebhookResponse(BaseModel):
    """Unified response returned to TradingView (always HTTP 200)."""

    status: str
    alert_id: Optional[int] = None
    symbol: str
    confidence: float = 0.0
    email_sent: bool = False
    processing_time_ms: int = 0
    timestamp: str
    services: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: list = Field(default_factory=list)


class AlertStatusResponse(BaseModel):
    alert_id: int
    symbol: str
    status: str
    stored: bool
    analyzed: bool
    email_sent: bool
    confidence: float
