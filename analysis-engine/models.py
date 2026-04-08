"""
Pydantic data models for the Analysis Engine.
Defines all data structures used across the analysis pipeline.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PatternType(str, Enum):
    """Candlestick pattern types."""
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    DOJI = "doji"
    DRAGONFLY_DOJI = "dragonfly_doji"
    GRAVESTONE_DOJI = "gravestone_doji"
    HAMMER = "hammer"
    INVERTED_HAMMER = "inverted_hammer"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    THREE_BLACK_CROWS = "three_black_crows"


class TrendDirection(str, Enum):
    """Trend direction enumeration."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SlopeDirection(str, Enum):
    """Slope direction for moving averages."""
    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"


class Timeframe(str, Enum):
    """Supported timeframes for analysis."""
    WEEKLY = "1W"
    DAILY = "1D"
    FOUR_HOUR = "4H"
    ONE_HOUR = "1H"


class OHLCV(BaseModel):
    """OHLCV candlestick data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Pattern(BaseModel):
    """Detected candlestick pattern."""
    type: PatternType
    confidence: float = Field(..., ge=0.0, le=1.0)
    timeframe: Timeframe
    timestamp: datetime
    index: int  # Position in the data series


class MA20Analysis(BaseModel):
    """20-period moving average analysis."""
    price: float
    ma20: float
    distance_pct: float
    trend: TrendDirection
    slope: SlopeDirection
    slope_value: float  # Actual slope value for reference


class TimeframeContext(BaseModel):
    """Context for a single timeframe."""
    trend: TrendDirection
    alignment: bool  # Whether this timeframe aligns with the primary signal
    ma20: Optional[MA20Analysis] = None
    patterns: List[Pattern] = Field(default_factory=list)


class MultiTimeframeContext(BaseModel):
    """Multi-timeframe analysis results."""
    weekly: Optional[TimeframeContext] = None
    daily: Optional[TimeframeContext] = None
    four_hour: Optional[TimeframeContext] = Field(None, alias="4h")
    one_hour: Optional[TimeframeContext] = Field(None, alias="1h")
    overall_alignment: float = Field(..., ge=0.0, le=1.0)
    divergence_detected: bool = False


class ContextRecommendation(str, Enum):
    """Trading recommendations based on context analysis."""
    STRONG_LONG = "strong_long"
    CONSIDER_LONG = "consider_long"
    NEUTRAL = "neutral"
    CONSIDER_SHORT = "consider_short"
    STRONG_SHORT = "strong_short"
    WAIT = "wait"


class ContextAnalysis(BaseModel):
    """Context intelligence analysis results."""
    sentiment: TrendDirection
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    key_levels: List[float] = Field(default_factory=list)
    recommendation: ContextRecommendation
    triggered_rules: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Complete analysis result for a symbol."""
    symbol: str
    timestamp: datetime
    patterns: List[Pattern] = Field(default_factory=list)
    ma20: Optional[MA20Analysis] = None
    context: Optional[ContextAnalysis] = None
    multi_timeframe: Optional[MultiTimeframeContext] = None
    raw_data: Optional[Dict[str, Any]] = None  # For debugging


class AlertInput(BaseModel):
    """Input from TradingView alert."""
    symbol: str
    alert_message: str
    alert_price: float
    alert_time: datetime
    timeframe: Timeframe


class Config(BaseModel):
    """Analysis engine configuration."""
    db_path: str = "ohlcv.db"
    ma_period: int = 20
    slope_threshold: float = 0.001  # Threshold for flat slope detection
    doji_threshold: float = 0.05  # Body/range ratio for doji detection
    hammer_threshold: float = 0.3  # Lower shadow ratio for hammer detection
    pattern_lookback: int = 5  # Days to look back for context
    confidence_weights: Dict[str, float] = Field(default_factory=lambda: {
        "weekly": 0.4,
        "daily": 0.3,
        "4h": 0.2,
        "1h": 0.1
    })
