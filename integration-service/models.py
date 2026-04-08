"""Pydantic models for inter-service communication."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class TradingViewAlert(BaseModel):
    """TradingView webhook payload schema."""
    
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSD)")
    price: Optional[float] = Field(None, description="Price at alert time")
    message: Optional[str] = Field(None, description="Alert message")
    time: Optional[str] = Field(None, description="Alert timestamp from TradingView")
    timeframe: Optional[str] = Field("1D", description="Chart timeframe")
    
    class Config:
        extra = "allow"
    
    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        """Normalize symbol to uppercase."""
        return v.upper()


class AnalysisRequest(BaseModel):
    """Request to trigger analysis for a symbol."""
    
    symbol: str = Field(..., description="Trading symbol to analyze")
    timeframe: str = Field("1D", description="Timeframe for analysis")
    
    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class PatternInfo(BaseModel):
    """Pattern information from analysis."""
    
    type: str
    confidence: float
    timeframe: str
    timestamp: str
    index: int


class MA20Info(BaseModel):
    """MA20 analysis information."""
    
    price: float
    ma20: float
    distance_pct: float
    trend: str
    slope: str
    slope_value: float


class ContextInfo(BaseModel):
    """Context analysis information."""
    
    sentiment: str
    confidence: float
    reasoning: str
    key_levels: List[float] = Field(default_factory=list)
    recommendation: str
    triggered_rules: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Analysis result from Analysis Engine."""
    
    symbol: str
    timestamp: datetime
    patterns: List[PatternInfo] = Field(default_factory=list)
    ma20: Optional[MA20Info] = None
    context: Optional[ContextInfo] = None
    raw_data: Optional[Dict[str, Any]] = None


class WebhookStoreResponse(BaseModel):
    """Response from webhook receiver when storing alert."""
    
    status: str
    alert_id: int
    symbol: str
    received_at: str


class EmailAlertRequest(BaseModel):
    """Request to send immediate email alert."""
    
    symbol: str
    analysis: AnalysisResult
    recipient: Optional[str] = None


class ProcessAlertResponse(BaseModel):
    """Response from processing an alert through the full flow."""
    
    alert_id: int
    symbol: str
    status: str
    analysis: Optional[AnalysisResult] = None
    email_sent: bool = False
    confidence: Optional[float] = None
    message: Optional[str] = None
    processed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AlertStatusResponse(BaseModel):
    """Response for alert status check."""
    
    alert_id: int
    symbol: str
    received_at: str
    processed: bool
    analysis: Optional[AnalysisResult] = None
    email_sent: bool = False


class ServiceHealth(BaseModel):
    """Health status of a single service."""
    
    name: str
    url: str
    status: str  # "healthy", "unhealthy", "unknown"
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response for all services."""
    
    status: str
    timestamp: str
    services: List[ServiceHealth]
    integration_service: str = "healthy"
