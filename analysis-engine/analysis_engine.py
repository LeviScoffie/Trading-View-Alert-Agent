"""
Analysis Engine - Main Orchestrator.
Coordinates pattern detection, MA analysis, context intelligence, and multi-timeframe analysis.
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List

from models import (
    AnalysisResult, AlertInput, Config, Timeframe,
    Pattern, MA20Analysis, ContextAnalysis, MultiTimeframeContext
)
from database import OHLCVDatabase
from pattern_detector import PatternDetector
from ma_analyzer import MAAnalyzer
from context_engine import ContextEngine
from multi_timeframe import MultiTimeframeAnalyzer


class AnalysisEngine:
    """
    Main analysis engine that orchestrates all analysis components.
    
    Usage:
        engine = AnalysisEngine()
        result = engine.analyze_symbol("BTCUSD", Timeframe.DAILY)
    """
    
    def __init__(self, config: Optional[Config] = None, db_path: Optional[str] = None):
        """
        Initialize the analysis engine.
        
        Args:
            config: Configuration object
            db_path: Path to SQLite database
        """
        self.config = config or Config()
        self.db = OHLCVDatabase(db_path or self.config.db_path)
        
        # Initialize analyzers
        self.pattern_detector = PatternDetector(self.config)
        self.ma_analyzer = MAAnalyzer(self.config)
        self.context_engine = ContextEngine()
        self.mtf_analyzer = MultiTimeframeAnalyzer(self.config)
    
    def analyze_symbol(
        self,
        symbol: str,
        primary_timeframe: Timeframe = Timeframe.DAILY,
        end_time: Optional[datetime] = None
    ) -> AnalysisResult:
        """
        Perform complete analysis on a symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSD")
            primary_timeframe: Main timeframe for analysis
            end_time: Optional end time for historical analysis
        
        Returns:
            Complete AnalysisResult with all components
        """
        timestamp = datetime.utcnow()
        
        # Get data for primary timeframe
        df = self.db.get_ohlcv(symbol, primary_timeframe, limit=100, end_time=end_time)
        
        if df.empty:
            return AnalysisResult(
                symbol=symbol,
                timestamp=timestamp,
                patterns=[],
                ma20=None,
                context=None,
                multi_timeframe=None
            )
        
        # 1. Detect patterns
        patterns = self.pattern_detector.detect_all_patterns(df, primary_timeframe)
        
        # 2. Analyze MA20
        ma20 = self.ma_analyzer.analyze(df)
        
        # 3. Multi-timeframe analysis
        mtf_data = self.db.get_multi_timeframe_data(symbol, end_time=end_time, config=self.config)
        mtf_context = self.mtf_analyzer.analyze(mtf_data, primary_timeframe)
        
        # 4. Context analysis
        context = self.context_engine.analyze(
            symbol=symbol,
            patterns=patterns,
            ma20=ma20,
            df=df,
            multi_timeframe_context=mtf_context.model_dump() if mtf_context else None
        )
        
        return AnalysisResult(
            symbol=symbol,
            timestamp=timestamp,
            patterns=patterns,
            ma20=ma20,
            context=context,
            multi_timeframe=mtf_context,
            raw_data={
                'data_points': len(df),
                'timeframe': primary_timeframe.value,
                'latest_price': float(df['close'].iloc[-1]),
                'latest_timestamp': df['timestamp'].iloc[-1].isoformat()
            }
        )
    
    def process_alert(self, alert: AlertInput) -> AnalysisResult:
        """
        Process a TradingView alert and return analysis.
        
        Args:
            alert: AlertInput with alert details
        
        Returns:
            AnalysisResult with context-aware analysis
        """
        return self.analyze_symbol(alert.symbol, alert.timeframe, alert.alert_time)
    
    def analyze_with_alert_context(
        self,
        symbol: str,
        alert_pattern: str,
        alert_price: float,
        primary_timeframe: Timeframe = Timeframe.DAILY
    ) -> AnalysisResult:
        """
        Analyze with specific alert pattern context.
        
        Args:
            symbol: Trading symbol
            alert_pattern: Pattern mentioned in alert (e.g., "Bullish Engulfing")
            alert_price: Price at alert time
            primary_timeframe: Primary timeframe
        
        Returns:
            AnalysisResult with alert context
        """
        result = self.analyze_symbol(symbol, primary_timeframe)
        
        # Enhance context with alert information
        if result.context:
            result.context.reasoning = (
                f"Alert: {alert_pattern} at ${alert_price:.2f}. "
                f"{result.context.reasoning}"
            )
        
        return result
    
    def get_recent_patterns(
        self,
        symbol: str,
        timeframe: Timeframe,
        n_candles: int = 5
    ) -> List[Pattern]:
        """
        Get patterns from recent candles only.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to analyze
            n_candles: Number of recent candles to check
        
        Returns:
            List of recent patterns
        """
        df = self.db.get_ohlcv(symbol, timeframe, limit=n_candles + 10)
        
        if df.empty:
            return []
        
        all_patterns = self.pattern_detector.detect_all_patterns(df, timeframe)
        
        # Filter to recent patterns only
        latest_idx = len(df) - 1
        recent = [p for p in all_patterns if p.index >= latest_idx - n_candles + 1]
        
        return recent
    
    def store_ohlcv_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        data: List[Dict]
    ):
        """
        Store OHLCV data in the database.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            data: List of OHLCV dictionaries
        """
        from models import OHLCV
        
        ohlcv_data = [
            OHLCV(
                timestamp=datetime.fromisoformat(d['timestamp']) if isinstance(d['timestamp'], str) else d['timestamp'],
                open=float(d['open']),
                high=float(d['high']),
                low=float(d['low']),
                close=float(d['close']),
                volume=float(d['volume'])
            )
            for d in data
        ]
        
        self.db.store_ohlcv(symbol, timeframe, ohlcv_data)
    
    def get_multi_timeframe_summary(
        self,
        symbol: str
    ) -> str:
        """
        Get a quick multi-timeframe summary for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Human-readable summary string
        """
        mtf_data = self.db.get_multi_timeframe_data(symbol, config=self.config)
        mtf_context = self.mtf_analyzer.analyze(mtf_data)
        
        return self.mtf_analyzer.get_alignment_summary(mtf_context)
    
    def get_support_resistance(
        self,
        symbol: str,
        timeframe: Timeframe = Timeframe.DAILY
    ) -> Dict[str, List[float]]:
        """
        Get support and resistance levels for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to analyze
        
        Returns:
            Dictionary with 'support' and 'resistance' lists
        """
        df = self.db.get_ohlcv(symbol, timeframe, limit=50)
        
        if df.empty:
            return {'support': [], 'resistance': []}
        
        supports, resistances = self.ma_analyzer.get_support_resistance_levels(df)
        
        return {
            'support': supports,
            'resistance': resistances
        }
    
    def close(self):
        """Close database connection."""
        self.db.close()


# Convenience function for quick analysis
def analyze(
    symbol: str,
    timeframe: Timeframe = Timeframe.DAILY,
    db_path: Optional[str] = None
) -> AnalysisResult:
    """
    Quick analysis function.
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe to analyze
        db_path: Optional database path
    
    Returns:
        AnalysisResult
    """
    engine = AnalysisEngine(db_path=db_path)
    try:
        return engine.analyze_symbol(symbol, timeframe)
    finally:
        engine.close()